import logging
import socket
import codecs
from enum import Enum


LOGGER = logging.getLogger("orwell.proxy_robot")


decode_hex = codecs.getdecoder("hex_codec")


class MoveOrder(Enum):
    POWER = 1
    SPEED = 2


class Motors(Enum):
    A = 1
    B = 2
    C = 4
    D = 8


class EV3Device(object):
    def __init__(self, socket):
        assert(socket is not None)
        self._socket = socket

    def __del__(self):
        """
        Just in case the last order was a move command, stop the robot.
        """
        self.stop()
        #self._socket.close()

    def get_move_command(self, motor, power, move=MoveOrder.POWER, safe=True):
        """
        `motor`: Motors enum (can be a sum)
        `power`: -31..31
        """
        str_motor = "{0:02d}".format(motor)
        if (safe):
            converted_power = max(-31, min(31, power))
            if (converted_power < 0):
                converted_power = 64 + converted_power
        else:
            converted_power = power
        str_power = hex(converted_power)[2:].zfill(2)
        if (MoveOrder.POWER == move):
            order = "A4"
        elif (MoveOrder.SPEED == move):
            order = "A5"
        else:
            order = "A4"
        command = "0C000000800000" + order + "00"\
            + str_motor + str_power + "A600" + str_motor
        return decode_hex(command)

    def get_stop_command(self, motor):
        """
        `motor`: Motors enum (can be a sum)
        """
        str_motor = "{0:02d}".format(motor)
        command = "09000000800000A300" + str_motor + "00"
        return decode_hex(command)

    def move(self, left, right):
        """
        `left`: -1..1
        `right`: -1..1
        """
        # 31 is a magic number comming from trial and error
        scaled_left = int(float(left) * float(31))
        scaled_right = int(float(right) * float(31))
        command = self.get_move_command(Motors.A.value, scaled_left)
        self._socket.send(command)
        command = self.get_move_command(Motors.D.value, scaled_right)
        self._socket.send(command)

    def stop(self):
        command = self.get_stop_command(Motors.A.value + Motors.D.value)
        self._socket.send(command)

    def get_socket(self):
        return self._socket

    def ready(self):
        return True


class FakeDevice(object):
    def __init__(self):
        pass

    def __del__(self):
        """
        Just in case the last order was a move command, stop the robot.
        """
        self.stop()

    def move(self, left, right):
        """
        `left`: -1..1
        `right`: -1..1
        """
        LOGGER.debug("move({left}, {right})".format(left=left, right=right))

    def stop(self):
        LOGGER.debug("stop()")

    def ready(self):
        return True


class HarpiDevice(object):
    def __init__(self, socket):
        self._socket = socket
        self._address = None

    def __del__(self):
        """
        Just in case the last order was a move command, stop the robot.
        """
        self.stop()

    def move(self, left, right):
        """
        `left`: -1..1
        `right`: -1..1
        """
        if (self._address):
            left = int(left * 255)
            right = int(right * 255)
            command = "move {left} {right}".format(left=left, right=right)
            LOGGER.debug("harpi::" + command)
            self._socket.sendto(bytearray(command, "ascii"), self._address)
        else:
            LOGGER.debug("harpi::move device not ready to send command")

    def stop(self):
        LOGGER.debug("stop()")
        self.move(0, 0)

    def get_socket(self):
        return self._socket

    def ready(self):
        if (not self._address):
            try:
                message, address = self._socket.recvfrom(4096)
                if (message):
                    LOGGER.info(
                            "First message from robot: {message}".format(
                                message=message))
                    self._address = address
            except socket.timeout:
                LOGGER.debug("Failed to receive first mesage from robot - socket.timeout")
                pass
            except BlockingIOError:
                # no message yet?
                pass
        else:
            try:
                message, address = self._socket.recvfrom(4096)
                if (message):
                    LOGGER.info(
                            "Message from robot: {message}".format(
                                message=message))
            except socket.timeout:
                pass
            except BlockingIOError:
                pass
        return self._address is not None