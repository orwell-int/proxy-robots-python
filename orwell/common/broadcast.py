from __future__ import print_function
import socket
import struct
import sys
# @TODO ? implement proper broadcast address finding
# import netifaces


def get_network_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.connect(('<broadcast>', 0))
    return s.getsockname()[0]


class Broadcast(object):
    def __init__(self, port=9080, retries=5, timeout=10):
        ip_mask_all = '255'
        self._size = 512
        self._retries = retries
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.settimeout(timeout)
        ttl = struct.pack('b', 1)
        self._socket.setsockopt(
            socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        broadcast = get_network_ip().split('.')
        broadcast = '.'.join(broadcast[:-1] + [ip_mask_all])
        self._group = (broadcast, port)
        print('group = ' + str(self._group))
        self._received = False
        self._data = None
        self._sender = None
        self._decding_successful = False
        self.send_all_broadcast_messages()

    def send_all_broadcast_messages(self):
        tries = 0
        while ((tries < self._retries) and (not self._received)):
            self.send_one_broadcast_message()
            tries += 1
        if (self._received):
            self.decode_data()

    def send_one_broadcast_message(self):
        try:
            print("before sendto")
            sent = self._socket.sendto(
                    "<broadcast>".encode("ascii"), self._group)
            print("after sendto ; " + repr(sent))
            while not self._received:
                try:
                    self._data, self._sender = self._socket.recvfrom(
                            self._size)
                    self._received = True
                except socket.timeout:
                    print('timed out, no more responses', file=sys.stderr)
                    break
                else:
                    print(
                        'received "%s" from %s'
                        % (repr(self._data), self._sender),
                        file=sys.stderr)
        finally:
            print('closing socket', file=sys.stderr)
            self._socket.close()

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
        to_char = lambda x: struct.unpack('B', x)[0]
        to_str = lambda x: x.decode("ascii")
        assert(self._data[0] == '\xa0')
        puller_size = to_char(self._data[1])
        # print("puller_size = " + str(puller_size))
        end_puller = 2 + puller_size
        puller_address = to_str(self._data[2:end_puller])
        # print("puller_address = " + puller_address)
        assert(self._data[end_puller] == '\xa1')
        publisher_size = to_char(self._data[end_puller + 1])
        # print("publisher_size = " + str(publisher_size))
        end_publisher = end_puller + 2 + publisher_size
        publisher_address = to_str(self._data[end_puller + 2:end_publisher])
        # print("publisher_address = " + publisher_address)
        assert(self._data[end_publisher] == '\x00')
        sender_ip, _ = self._sender
        self._push_address = puller_address.replace('*', sender_ip)
        self._subscribe_address = publisher_address.replace('*', sender_ip)
        self._decding_successful = True

    @property
    def push_address(self):
        return self._push_address

    @property
    def subscribe_address(self):
        return self._subscribe_address