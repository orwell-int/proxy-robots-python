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
            return self._socket.recv(flags=zmq.NOBLOCK)
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
        return self._socket.recv(flags=zmq.NOBLOCK)


class AdminSocket(object):
    def __init__(self, admin_port, zmq_context):
        self._zmq_context = zmq_context
        self._socket = self._zmq_context.socket(zmq.REP)
        self._socket.bind("tcp://*:{port}".format(port=admin_port))

    def read(self):
        try:
            return self._socket.recv_string(zmq.NOBLOCK)
        except zmq.error.Again:
            pass
        except zmq.ZMQError as e:
            LOGGER.warning("AdminSocket could not read: %s %s", e.errno, e)
            return None

    def write(self, message):
        try:
            return self._socket.send_string(message)
        except zmq.ZMQError as e:
            LOGGER.warning("AdminSocket could not send reply! %s %s", e.errno, e)
            return None

