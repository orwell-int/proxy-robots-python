from __future__ import print_function
import argparse
import logging
import time

from orwell.common.broadcast_listener import BroadcastListener
import collections
from enum import Enum
import socket
import threading

from orwell.common.sockets_lister import SocketsLister
from orwell.proxy_robots.devices import FakeDevice, HarpiDevice

LOCK = threading.Lock()
LOCK_SOCKET = threading.Lock()


LOGGER = None


class Program(object):
    def __init__(
            self,
            arguments):
        """
        """
        self._devices = {}
        if (not arguments.no_proxy_broadcast):
            self._broadcast = BroadcastListener(arguments.proxy_broadcast_port)
            # self._actionner.add_action(action)
        else:
            self._broadcast = None
        self._fire_pattern = False

    def add_robot(self, robot_id, device):
        """
        """
        self._devices[robot_id] = device
        robot_socket = device.get_socket()
        port = robot_socket.getsockname()[1]
        LOGGER.info(
                "Robot {id} is using port {port}".format(
                    id=robot_id, port=port))
        self._broadcast.add_socket_port(port)

    @property
    def robots(self):
        return self._robots

    def step(self):
        """
        """
        for device in self._devices.values():
            if device.ready():
                device.move(-0.8, 0.9)
                if self._fire_pattern:
                    device.fire(True, False)
                else:
                    device.fire(False, True)
                self._fire_pattern = not self._fire_pattern

    def start(self):
        """
        This should be called once the robots have been added.
        """
        if (self._broadcast):
            self._broadcast.start()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--proxy-broadcast-port",
        "-b",
        help="The port for the broadcast on the proxy",
        default=9081, type=int)
    parser.add_argument(
        "--no-proxy-broadcast",
        help="The port for the broadcast on the proxy",
        default=False,
        action="store_true")
    parser.add_argument(
        '--verbose', '-v',
        help='Verbose mode',
        default=False,
        action="store_true")
    arguments = parser.parse_args()
    configure_logging(arguments.verbose)
    sockets_lister = SocketsLister()
    robots = ['951']
    program = Program(arguments)
    for robot in robots:
        socket = sockets_lister.pop_available_socket()
        if (socket):
            device = HarpiDevice(socket)
            program.add_robot(robot, device)
            LOGGER.info('Device found for robot ' + str(robot))
        else:
            LOGGER.info('Oups, no device to associate to robot ' + str(robot))
            return
    program.start()
    while (True):
        program.step()
        time.sleep(5)


def configure_logging(verbose):
    print("program.configure_logging")
    logger = logging.getLogger("orwell")
    logger.propagate = False
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
            '%(asctime)s %(name)-12s %(levelname)-8s '
            '%(filename)s %(lineno)d %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    if (verbose):
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    global LOGGER
    LOGGER = logging.getLogger("orwell.proxy_robot")

if ("__main__" == __name__):
    main()