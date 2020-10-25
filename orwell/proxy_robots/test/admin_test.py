from orwell.proxy_robots.admin import Admin
from unittest import mock
import json


def test_list_robot():
    zmq_context =  mock.MagicMock()
    program = mock.MagicMock()
    robot1 = mock.MagicMock()
    robot1.robot_id = "1"
    robot2 = mock.MagicMock()
    robot2.robot_id = "2"
    program.robots = {robot1.robot_id: robot1, robot2.robot_id: robot2}
    admin_socket = mock.MagicMock()
    admin_socket.return_value = admin_socket
    admin = Admin(zmq_context, program, 9082, admin_socket)
    admin._handle_admin_message("list robot")
    merged_robots = ["1", "2"]
    admin_socket.write.assert_called_once_with(str(merged_robots))


def test_json_list_robot():
    zmq_context =  mock.MagicMock()
    program = mock.MagicMock()
    robot1 = mock.MagicMock()
    robot_id1 = "1"
    robot_id2 = "2"
    robot_dict1 = {robot_id1: {"address": "1.1.1.1"}}
    robot1.to_dict.return_value = robot_dict1
    robot2 = mock.MagicMock()
    robot_dict2 = {robot_id2: {"address": "2.2.2.2"}}
    robot2.to_dict.return_value = robot_dict2
    program.robots = {robot_id1: robot1, robot_id2: robot2}
    admin_socket = mock.MagicMock()
    admin_socket.return_value = admin_socket
    admin = Admin(zmq_context, program, 9082, admin_socket)
    admin._handle_admin_message("json list robot")
    merged_robots = {**robot_dict1, **robot_dict2}
    admin_socket.write.assert_called_once_with(json.dumps(merged_robots))
