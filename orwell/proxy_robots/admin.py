import logging
import zmq

from orwell.proxy_robots.connectors import AdminSocket
from orwell.proxy_robots.zmq_context import ZMQ_CONTEXT

LOGGER = logging.getLogger(__name__)


class Admin(object):
    LIST_ROBOT = "list robot"

    def __init__(
            self,
            program,
            admin_port=9082,
            admin_socket_type=AdminSocket,
            zmq_context=ZMQ_CONTEXT):
        """
        `admin_port`: port to bind to and receive connections from the admin GUI
        """
        self._program = program
        self._admin_socket = admin_socket_type(admin_port, zmq_context)

    def _handle_admin_message(self, admin_message):
        if not admin_message:
            return
        LOGGER.info("received admin command: %s", admin_message)
        if Admin.LIST_ROBOT == admin_message:
            robot_ids = [robot.robot_id
                         for robot in self._program.robots.values()]
            robots = str(robot_ids)
            LOGGER.info("admin send robots = %s", robots)
            self._admin_socket.send_string(robots)

    def step(self):
        try:
            self._handle_admin_message(
                self._admin_socket.recv_string(flags=zmq.DONTWAIT))
        except zmq.error.Again:
            pass
