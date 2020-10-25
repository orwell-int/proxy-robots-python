from orwell.proxy_robots.robot import Robot
from unittest import mock

from nose.tools import assert_equals


def test_robot_to_dict():
    message_hub_wrapper = mock.MagicMock()
    engine = mock.MagicMock()
    device = mock.MagicMock()
    device.address = None
    robot_id = "robot_id"
    robot = Robot(robot_id, message_hub_wrapper, engine, device)
    expected_dict = {robot_id: {"address": ""}}
    assert_equals(expected_dict, robot.to_dict())
    device.ready.return_value = True
    address = "12.34.56.78"
    device.address = address
    robot.step()
    expected_dict = {robot_id: {"address": address}}
    assert_equals(expected_dict, robot.to_dict())
