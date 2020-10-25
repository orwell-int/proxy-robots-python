import logging
import zmq


LOGGER = logging.getLogger(__name__)


class Subscriber(object):
    def __init__(self, address, zmq_context):
        self._socket = zmq_context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.LINGER, -1)
        self._socket.setsockopt_string(zmq.SUBSCRIBE, "")
        LOGGER.info("Connect to {address} sub".format(address=address))
        self._socket.connect(address)

    def read(self):
        try:
            return self._socket.recv(flags=zmq.DONTWAIT)
        except zmq.error.Again:
            return None


class Pusher(object):
    def __init__(self, address, zmq_context):
        self._socket = zmq_context.socket(zmq.PUSH)
        self._socket.setsockopt(zmq.LINGER, -1)
        # print("Pusher ; address =", address)
        LOGGER.info("Connect to {address} push".format(address=address))
        self._socket.connect(address)

    def write(self, message):
        LOGGER.debug("Pusher.write: " + repr(message))
        self._socket.send(message)


class Replier(object):
    def __init__(self, address, zmq_context):
        self._socket = zmq_context.socket(zmq.REQ)
        self._socket.setsockopt(zmq.LINGER, -1)
        LOGGER.info("Connect to {address} req".format(address=address))
        self._socket.connect(address)

    def exchange(self, query):
        self.write(query)
        return self.read()

    def write(self, message):
        LOGGER.debug("Replier.write: " + repr(message))
        self._socket.send(message)

    def read(self):
        return self._socket.recv(flags=zmq.DONTWAIT)


class AdminSocket(object):
    def __init__(self, admin_port, zmq_context):
        self._context = zmq_context
        self._admin = self._context.socket(zmq.REP)
        self._admin.bind("tcp://*:{port}".format(port=admin_port))

    def recv_string(self, flags=-1, encoding='utf-8'):
        return self._admin.recv_string(flags, encoding)

    def send_string(self, u, flags=-1, copy=True, encoding='utf-8', **kwargs):
        return self._admin.send_string(u, flags, copy, encoding, **kwargs)
