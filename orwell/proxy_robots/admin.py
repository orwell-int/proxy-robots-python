import logging
import json

from orwell.proxy_robots.connectors import AdminSocket

LOGGER = logging.getLogger(__name__)


class Admin(object):
    LIST_ROBOT = "list robot"
    JSON_LIST_ROBOT = "json list robot"

    def __init__(
            self,
            zmq_context,
            program,
            admin_port=9082,
            admin_socket_type=AdminSocket):
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
            self._admin_socket.write(robots)
        elif Admin.JSON_LIST_ROBOT == admin_message:
            response = {}
            for robot in self._program.robots.values():
                robot_dict = robot.to_dict()
                response.update(robot_dict)
            json_response = json.dumps(response)
            LOGGER.info("admin send json robots = %s", json_response)
            self._admin_socket.write(json_response)

    def step(self):
        self._handle_admin_message(self._admin_socket.read())
