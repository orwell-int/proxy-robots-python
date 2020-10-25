import argparse
import logging
import time

from orwell_common.broadcast_listener import BroadcastListener
from orwell_common.sockets_lister import SocketsLister
import orwell_common.logging

from orwell.proxy_robots.devices import HarpiDevice

LOGGER = logging.getLogger(__name__)


class Program(object):
    def __init__(
            self,
            arguments):
        """
        """
        self._devices = {}
        if not arguments.no_proxy_broadcast:
            self._broadcast = BroadcastListener(arguments.proxy_broadcast_port)
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
        if self._broadcast:
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
        help="Do not listen for broadcast messages.",
        default=False,
        action="store_true")
    parser.add_argument(
        '--verbose', '-v',
        help='Verbose mode',
        default=False,
        action="store_true")
    arguments = parser.parse_args()
    orwell_common.logging.configure_logging(arguments.verbose)
    sockets_lister = SocketsLister()
    robots = ['951']
    program = Program(arguments)
    for robot in robots:
        socket = sockets_lister.pop_available_socket()
        if socket:
            device = HarpiDevice(socket)
            program.add_robot(robot, device)
            LOGGER.info('Device found for robot ' + str(robot))
        else:
            LOGGER.info('Oups, no device to associate to robot ' + str(robot))
            return
    program.start()
    while True:
        program.step()
        time.sleep(5)


if "__main__" == __name__:
    main()
