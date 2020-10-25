import argparse
import datetime
import logging
import time

from orwell_common.broadcast import Broadcast
from orwell_common.broadcast_listener import BroadcastListener
from orwell_common.sockets_lister import SocketsLister
import orwell_common.broadcast
import orwell_common.broadcast_listener
import orwell_common.logging

from orwell.proxy_robots.admin import Admin
from orwell.proxy_robots.connectors import Pusher
from orwell.proxy_robots.connectors import Replier
from orwell.proxy_robots.connectors import Subscriber
from orwell.proxy_robots.devices import FakeDevice
from orwell.proxy_robots.devices import HarpiDevice
from orwell.proxy_robots.engine import Engine
from orwell.proxy_robots.message_hub import BroadcasterMessageHubWrapper
from orwell.proxy_robots.message_hub import DumbMessageHubWrapper
from orwell.proxy_robots.message_hub import MessageHub
from orwell.proxy_robots.robot import Robot

LOGGER = logging.getLogger(__name__)


class Program(object):
    def __init__(
            self,
            arguments,
            subscriber_type=Subscriber,
            pusher_type=Pusher,
            replier_type=Replier,
            admin_type=Admin):
        """
        `arguments`: object that must at least contain publisher_port,
            puller_port, address. (not any longer with the broadcast)
        `subscriber_type`: see #MessageHub
        `pusher_type`: see #MessageHub
        `replier_type`: see #MessageHub
        """
        if arguments.no_server_broadcast:
            ip = arguments.address
            push_address = "tcp://{ip}:{port}".format(
                ip=ip, port=arguments.puller_port)
            subscribe_address = "tcp://{ip}:{port}".format(
                ip=ip, port=arguments.publisher_port)
            replier_address = "tcp://{ip}:{port}".format(
                ip=ip, port=arguments.replier_port)
            self._message_hub_wrapper = DumbMessageHubWrapper(
                MessageHub(
                    subscribe_address,
                    push_address,
                    replier_address,
                    subscriber_type,
                    pusher_type,
                    replier_type))
        else:
            self._message_hub_wrapper = BroadcasterMessageHubWrapper(
                datetime.timedelta(seconds=5),
                Broadcast,
                subscriber_type,
                pusher_type,
                replier_type)
        self._admin = admin_type(self, arguments.admin_port)
        self._engine = Engine()
        self._robots = {}  # id -> Robot
        if not arguments.no_proxy_broadcast:
            self._broadcastListener = BroadcastListener(
                arguments.proxy_broadcast_port,
                arguments.admin_port)
        else:
            self._broadcastListener = None

    def add_robot(self, robot_id, device=None):
        """
        Create a robot and ask it to register into the server.
        """
        robot = Robot(robot_id, self._message_hub_wrapper, self._engine, device)
        self._robots[robot_id] = robot
        robot_socket = device.get_socket()
        port = robot_socket.getsockname()[1]
        LOGGER.info(
            "Robot {id} is using port {port}".format(
                id=robot_id, port=port))
        self._broadcastListener.add_socket_port(port)
        robot.queue_register()

    @property
    def robots(self):
        return self._robots

    def step(self):
        """
        Run the engine and the message hub (only one call).
        """
        self._message_hub_wrapper.step()
        self._engine.step()
        self._admin.step()
        for robot in self._robots.values():
            robot.step()

    def start(self):
        """
        This should be called once the robots have been added.
        """
        if self._broadcastListener:
            self._broadcastListener.start()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-P", "--publisher-port",
        help="Publisher port (the server publish and we subscribe).",
        default=9000, type=int)
    parser.add_argument(
        "-p", "--puller-port",
        help="Puller port (the server pulls and we push).",
        default=9001, type=int)
    parser.add_argument(
        "--address",
        help="The server address",
        default="127.0.0.1", type=str)
    parser.add_argument(
        "--server-broadcast-port",
        "-B",
        help="The port for the broadcast on server game",
        default=9080, type=int)
    parser.add_argument(
        "--no-server-broadcast",
        help="Do not send a broadcast message to the game server.",
        default=False,
        action="store_true")
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
        "--admin-port",
        "-a",
        help="The port the admin GUI can connect to",
        default=9082, type=int)
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
            device = FakeDevice()
            program.add_robot(robot, device)
    program.start()
    while True:
        program.step()
        time.sleep(0.01)


if "__main__" == __name__:
    main()
