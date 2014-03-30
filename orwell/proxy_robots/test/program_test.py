import orwell.proxy_robots.program as opp
import orwell.messages.server_game_pb2 as server_game_messages
#import orwell.messages.controller_pb2 as controller_messages
from nose.tools import assert_equals
from nose.tools import assert_true
from nose.tools import assert_false


INPUTS = [
    ('951', 1.0, 0, False, False),
    ('951', 0.5, -0.5, True, False)
]


class FakeDevice(object):
    def __init__(self, robot_id):
        self.expected_moves = []
        for other_robot_id, left, right, fire1, fire2 in INPUTS:
            if (robot_id == other_robot_id):
                self.expected_moves.append((left, right))

    def move(
            self,
            left,
            right):
        expected_left, expected_right = self.expected_moves.pop(0)
        assert_equals(expected_left, left)
        assert_equals(expected_right, right)


ROBOT_DESCRIPTORS = [('951', 'Grenade', FakeDevice('951'))]


class FakeArguments(object):
    publisher_port = '1'
    puller_port = '2'
    address = '1.2.3.4'


class MockPusher(object):
    def __init__(self, address, port, context):
        self.messages = []
        for robot_id, _, _ in ROBOT_DESCRIPTORS:
            message = opp.REGISTRY[opp.Messages.Register.name]()
            message.robot_id = robot_id
            payload = "{0} {1} {2}".format(
                opp.Messages.Register.name,
                robot_id,
                message.SerializeToString())
            self.messages.append(payload)

    def write(self, message):
        #print 'Fake writing message =', message
        expected_message = self.messages.pop(0)
        assert_equals(expected_message, message)


class MockSubscriber(object):
    def __init__(self, address, port, context):
        self.messages = [None]
        for robot_id, robot_name, _ in ROBOT_DESCRIPTORS:
            message = opp.REGISTRY[opp.Messages.Registered.name]()
            message.name = robot_name
            message.team = server_game_messages.BLU
            payload = "{0} {1} {2}".format(
                opp.Messages.Registered.name,
                robot_id,
                message.SerializeToString())
            self.messages.append(payload)
        for robot_id, left, right, fire1, fire2 in INPUTS:
            message = opp.REGISTRY[opp.Messages.Input.name]()
            message.move.left = left
            message.move.right = right
            message.fire.weapon1 = fire1
            message.fire.weapon2 = fire2
            payload = "{0} {1} {2}".format(
                opp.Messages.Input.name,
                robot_id,
                message.SerializeToString())
            self.messages.append(payload)

    def read(self):
        if (self.messages):
            message = self.messages.pop(0)
        else:
            message = None
        #print 'Fake reading message =', message
        return message


def test_robot_registration():
    arguments = FakeArguments()
    program = opp.Program(arguments, MockSubscriber, MockPusher)
    for robot_id, _, device in ROBOT_DESCRIPTORS:
        program.add_robot(robot_id, device)
    program.step()
    program.step()
    for item, expected in zip(program.robots.items(), ROBOT_DESCRIPTORS):
        robot_id, robot = item
        expected_robot_id, expected_robot_name, _ = expected
        assert_equals(robot_id, robot.robot_id)
        assert_equals(expected_robot_id, robot_id)
        assert_equals(expected_robot_name, robot.name)
        assert_true(robot.registered)
    print "OK"
    check_simple_input(program)


def check_simple_input(program):
    for robot_id, _, _ in ROBOT_DESCRIPTORS:
        robot = program.robots[robot_id]
        assert_equals(0.0, robot.left)
        assert_equals(0.0, robot.right)
        assert_false(robot.fire1)
        assert_false(robot.fire2)
    for robot_id, left, right, fire1, fire2 in INPUTS:
        program.step()
        robot = program.robots[robot_id]
        assert_equals(left, robot.left)
        assert_equals(right, robot.right)
        assert_equals(fire1, robot.fire1)
        assert_equals(fire2, robot.fire2)
    for robot_id, _, device in ROBOT_DESCRIPTORS:
        print 'robot_id =', robot_id
        assert_equals(len(device.expected_moves), 0)


def main():
    test_robot_registration()

if ("__main__" == __name__):
    main()
