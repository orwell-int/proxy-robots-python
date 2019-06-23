from __future__ import print_function
import orwell.proxy_robots.program as opp
import orwell.messages.server_game_pb2 as server_game_messages
#import orwell.messages.controller_pb2 as controller_messages
from nose.tools import assert_equals
from nose.tools import assert_true
from nose.tools import assert_false
from enum import Enum


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
    publisher_port = 1
    puller_port = 2
    address = '1.2.3.4'


class MockPusher(object):
    def __init__(self, address, port, context):
        self.messages = []
        for robot_id, _, _ in ROBOT_DESCRIPTORS:
            message = opp.REGISTRY[opp.Messages.Register.name]()
            message.temporary_robot_id = robot_id
            message.image = "no image"
            payload = "{0} {1} {2}".format(
                opp.Messages.Register.name,
                robot_id,
                message.SerializeToString())
            self.messages.append(payload)

    def write(self, message):
        #print('Fake writing message =', message)
        expected_message = self.messages.pop(0)
        assertEqual(expected_message, message)


class MockSubscriber(object):
    def __init__(self, address, port, context):
        self.messages = [None]
        for robot_id, robot_name, _ in ROBOT_DESCRIPTORS:
            message = opp.REGISTRY[opp.Messages.Registered.name]()
            message.name = robot_name
            message.team = "BLU"
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
        #print('Fake reading message =', message)
        return message


def test_robot_registration():
    print("\ntest_robot_registration")
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
    print("OK")
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
        print('robot_id =', robot_id)
        assert_equals(len(device.expected_moves), 0)


INPUT_MOVE = (0.89, -0.5)


class DummyDevice(object):
    def __init__(self, robot_id):
        self._moved = False

    def __dell(self):
        assert_true(self._moved)

    def move(
            self,
            left,
            right):
        print('move', left, right)
        assert_equals(INPUT_MOVE[0], left)
        assert_equals(INPUT_MOVE[1], right)
        self._moved = True


INPUT_ROBOT_DESCRIPTOR = ('55', 'Jambon', DummyDevice('55'))


class MockerStorage(object):
    def __init__(self, address, port, context):
        self.address = address
        self.port = port
        self.context = context


class Mocker(object):
    def __init__(self):
        self._pusher = None
        self._publisher = None

    def pusher_init_faker(self):
        def fake_init(address, port, context):
            self._pusher = MockerStorage(address, port, context)
            return self
        return fake_init

    def publisher_init_faker(self):
        def fake_init(address, port, context):
            self._publisher = MockerStorage(address, port, context)
            return self
        return fake_init


class InputMockerState(Enum):
    Created = 0
    Register = 1
    Registered = 2
    Input = 3


class InputMocker(Mocker):
    def __init__(self):
        super(Mocker, self).__init__()
        self._state = InputMockerState.Created
        self._robot_id = None
        self._robot_name = INPUT_ROBOT_DESCRIPTOR[1]
        self._team = "BLU"

    def read(self):
        print('Fake read')
        payload = None
        if (InputMockerState.Register == self._state):
            message = opp.REGISTRY[opp.Messages.Registered.name]()
            message.name = self._robot_name
            message.team = self._team
            payload = "{0} {1} {2}".format(
                opp.Messages.Registered.name,
                self._robot_id,
                message.SerializeToString())
            print('Fake message =', message)
            self._state = InputMockerState.Input
        elif (InputMockerState.Input == self._state):
            message = opp.REGISTRY[opp.Messages.Input.name]()
            message.move.left = INPUT_MOVE[0]
            message.move.right = INPUT_MOVE[1]
            message.fire.weapon1 = False
            message.fire.weapon2 = False
            payload = "{0} {1} {2}".format(
                opp.Messages.Input.name,
                self._robot_id,
                message.SerializeToString())
            print('Fake message =', message)
        return payload

    def write(self, payload):
        print('Fake write')
        if (InputMockerState.Created == self._state):
            message_type, routing_id, raw_message = payload.split(' ', 2)
            if (opp.Messages.Register.name == message_type):
                message = opp.REGISTRY[message_type]()
                message.ParseFromString(raw_message)
                self._robot_id = message.robot_id
                self._state = InputMockerState.Register
            else:
                print("We should not be here")
                assert(False)


def test_robot_input():
    print("\ntest_robot_input")
    arguments = FakeArguments()
    input_mocker = InputMocker()
    program = opp.Program(
        arguments,
        input_mocker.publisher_init_faker(),
        input_mocker.pusher_init_faker())
    robot_id, robot_name, device = INPUT_ROBOT_DESCRIPTOR
    program.add_robot(robot_id, device)
    program.step()
    program.step()
    program.step()
    #import time
    #time.sleep(1)


class FakeSocket(object):
    def __init__(self, expected_content_list):
        self._expected_content_list = expected_content_list

    def __del__(self):
        #assert_equals(0, len(self._expected_content_list))
        pass

    #def close(self):
        #pass

    def send(self, content):
        expected_content = self._expected_content_list.pop(0)
        #assert_equals(expected_content, content)


def test_fake_socket():
    robots = ['951']
    arguments = FakeArguments()
    program = opp.Program(arguments)
    for robot in robots:
        socket = FakeSocket(
            ['\x0c\x00\x00\x00\x80\x00\x00\xa4\x00\x01\x1f\xa6\x00\x01',
             '\x0c\x00\x00\x00\x80\x00\x00\xa4\x00\x08\x1f\xa6\x00\x08',
             '\t\x00\x00\x00\x80\x00\x00\xa3\x00\t\x00'])
        device = opp.EV3Device(socket)
        program.add_robot(robot, device)
        device.move(1, 1)


def main():
    test_robot_registration()
    test_robot_input()
    test_fake_socket()

if ("__main__" == __name__):
    main()
