from __future__ import print_function
import socket
import struct
import logging
import netifaces


LOGGER = logging.getLogger(__name__)


def get_network_ips():
    results = []
    for interface in netifaces.interfaces():
        addresses = netifaces.ifaddresses(interface)
        if netifaces.AF_INET not in addresses:
            continue
        ipv4_addresses = addresses[netifaces.AF_INET]
        if not ipv4_addresses:
            continue
        for ipv4_address in ipv4_addresses:
            if "broadcast" not in ipv4_address:
                continue
            results.append(ipv4_address["broadcast"])
    return results[::-1]


class Broadcast(object):
    def __init__(self, port=9080, retries=2, timeout=3):
        self._port = port
        self._size = 512
        self._retries = retries
        self._timeout = timeout
        self._build_socket()
        self._ips_pool = get_network_ips()
        self._group = self._get_next_group()
        self._received = False
        self._data = None
        self._sender = None
        self._decoding_successful = False
        self.send_all_broadcast_messages()

    def _build_socket(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.settimeout(self._timeout)
        ttl = struct.pack('b', 1)
        self._socket.setsockopt(
            socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

    def _get_next_group(self):
        broadcast = self._ips_pool.pop()
        group = broadcast, self._port
        LOGGER.debug('group = ' + str(group))
        return group

    def send_all_broadcast_messages(self):
        while (True):
            tries = 0
            while ((tries < self._retries) and (not self._received)):
                tries += 1
                LOGGER.debug("Try " + str(tries))
                self.send_one_broadcast_message()
            if (self._received):
                self.decode_data()
                break
            self._group = self._get_next_group()

    def send_one_broadcast_message(self):
        try:
            LOGGER.debug("before sendto")
            sent = self._socket.sendto(
                    "1".encode("ascii"), self._group)
            LOGGER.debug("after sendto ; " + repr(sent))
            while not self._received:
                try:
                    self._data, self._sender = self._socket.recvfrom(
                            self._size)
                    self._received = True
                except socket.timeout:
                    LOGGER.warning('timed out, no more responses')
                    break
                else:
                    LOGGER.info(
                        'received "%s" from %s'
                        % (repr(self._data), self._sender))
        finally:
            LOGGER.info('closing socket')
            self._socket.close()
            self._build_socket()

    def decode_data(self):
        # data (split on multiple lines for clarity):
        # 0xA0
        # size on 8 bytes
        # Address of puller
        # 0xA1
        # size on 8 bytes
        # Address of publisher
        # 0x00
        import struct
        # to_char = lambda x: struct.unpack('B', x)[0]
        to_char = lambda x: chr(x)
        to_str = lambda x: x.decode("ascii")
        assert(self._data[0] == 0xa0)
        puller_size = int(self._data[1])
        # print("puller_size =", puller_size)
        end_puller = 2 + puller_size
        puller_address = to_str(self._data[2:end_puller])
        # print("puller_address =", puller_address)
        assert(self._data[end_puller] == 0xa1)
        publisher_size = int(self._data[end_puller + 1])
        # print("publisher_size =", str(publisher_size))
        end_publisher = end_puller + 2 + publisher_size
        publisher_address = to_str(self._data[end_puller + 2:end_publisher])
        # print("publisher_address =", publisher_address)
        assert(self._data[end_publisher] == 0xa2)
        replier_size = int(self._data[end_publisher + 1])
        # print("replier_size =", str(replier_size))
        end_replier = end_publisher + 2 + replier_size
        replier_address = to_str(self._data[end_publisher + 2:end_replier])
        # print("replier_address =", replier_address)
        sender_ip, _ = self._sender
        self._push_address = puller_address.replace('*', sender_ip)
        self._subscribe_address = publisher_address.replace('*', sender_ip)
        self._reply_address = replier_address.replace('*', sender_ip)
        self._decoding_successful = True

    @property
    def push_address(self):
        return self._push_address

    @property
    def subscribe_address(self):
        return self._subscribe_address

    @property
    def reply_address(self):
        return self._reply_address
