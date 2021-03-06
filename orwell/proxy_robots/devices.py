import logging
import socket

LOGGER = logging.getLogger(__name__)


class FakeDevice(object):
    def __init__(self):
        self._address = "1.2.3.4"

    def __del__(self):
        """
        Just in case the last order was a move command, stop the robot.
        """
        self.stop()

    @property
    def address(self):
        return self._address

    def move(self, left, right):
        """
        `left`: -1..1
        `right`: -1..1
        """
        LOGGER.debug("move({left}, {right})".format(left=left, right=right))

    def fire(self, fire1, fire2):
        """
        `fire1`: 0/1
        `fire2`: 0/1
        """
        LOGGER.debug("fire({fire1}, {fire2})".format(fire1=fire1, fire2=fire2))

    def stop(self):
        LOGGER.debug("stop()")

    def ready(self):
        return True

    def get_socket(self):
        return None


class HarpiDevice(object):
    def __init__(self, sock):
        self._socket = sock
        self._address = None

    def __del__(self):
        """
        Just in case the last order was a move command, stop the robot.
        """
        self.stop()

    @property
    def address(self):
        return self._address

    def move(self, left, right):
        """
        `left`: -1..1
        `right`: -1..1
        """
        if self._address:
            left = int(left * 255)
            right = int(right * 255)
            command = "move {left} {right}".format(left=left, right=right)
            LOGGER.debug("harpi::" + command)
            self._socket.sendto(bytearray(command, "ascii"), self._address)
        else:
            LOGGER.debug("harpi::move device not ready to send command")

    def fire(self, fire1, fire2):
        """
        `fire1`: 0/1
        `fire2`: 0/1
        """
        if self._address:
            fire1 = 1 if fire1 else 0
            fire2 = 1 if fire2 else 0
            command = "fire {fire1} {fire2})".format(fire1=fire1, fire2=fire2)
            LOGGER.debug("harpi::" + command)
            self._socket.sendto(bytearray(command, "ascii"), self._address)
        else:
            LOGGER.debug("harpi::fire device not ready to send command")

    def stop(self):
        LOGGER.debug("stop()")
        self.move(0, 0)

    def get_socket(self):
        return self._socket

    def ready(self):
        if not self._address:
            try:
                message, address = self._socket.recvfrom(4096)
                if message:
                    LOGGER.info(
                        "First message from robot: {message}".format(
                            message=message))
                    self._address = address
            except socket.timeout:
                LOGGER.debug(
                    "Failed to receive message from robot - socket.timeout")
                pass
            except BlockingIOError:
                # no message yet?
                pass
        else:
            try:
                message, address = self._socket.recvfrom(4096)
                # if (message):
                # LOGGER.info(
                #         "Message from robot: {message}".format(
                #             message=message))
            except socket.timeout:
                pass
            except BlockingIOError:
                pass
        return self._address is not None
