from enum import Enum
from nose.tools import assert_equals
from nose.tools import assert_false
from nose.tools import assert_true
import datetime
import socket
import threading
import unittest.mock
import zmq
import queue

import orwell_common.broadcast_listener
import orwell_common.logging

from orwell.proxy_robots.message_hub import BroadcasterMessageHubWrapper
from orwell.proxy_robots.program import Program
from orwell.proxy_robots.registry import Messages
from orwell.proxy_robots.registry import REGISTRY

orwell_common.logging.configure_logging(False)

MOVES = [
    ('951', 1.0, 0),
    ('951', 0.5, -0.5)
]

FIRES = [
    # the first states for fires are not acted upon because
    # the states do not change
    (None, False, False),
    ('951', True, False)
]


class FakeDevice(object):
    def __init__(self, robot_id):
        self.expected_moves = []
        for other_robot_id, left, right in MOVES:
            if robot_id == other_robot_id:
                self.expected_moves.append((left, right))
        self.expected_fires = []
        for other_robot_id, fire1, fire2 in FIRES:
            if robot_id == other_robot_id:
                self.expected_fires.append((fire1, fire2))

    def move(
            self,
            left,
            right):
        expected_left, expected_right = self.expected_moves.pop(0)
        print("FakeDevice::move(%s, %s) - %s %s" % (left, right, expected_left, expected_right))
        assert_equals(expected_left, left)
        assert_equals(expected_right, right)

    def fire(self, fire1, fire2):
        expected_fire1, expected_fire2 = self.expected_fires.pop(0)
        print("FakeDevice::fire(%s, %s) - %s %s" % (fire1, fire2, expected_fire1, expected_fire2))
        assert_equals(expected_fire1, fire1)
        assert_equals(expected_fire2, fire2)

    def ready(self):
        return True

    def get_socket(self):
        return FakeSocket([], ["FakeDevice/FakeSocket"])


ROBOT_DESCRIPTORS = [('951', 'Grenade', FakeDevice('951'))]


class FakeArguments(object):
    publisher_port = 1
    puller_port = 2
    replier_port = 3
    admin_port = 4
    address = '1.2.3.4'
    no_server_broadcast = True
    no_proxy_broadcast = False
    proxy_broadcast_port = 0


class MockPusher(object):
    def __init__(self, address, context):
        self.messages = []
        for robot_id, _, _ in ROBOT_DESCRIPTORS:
            message = REGISTRY[Messages.Register.name]()
            message.temporary_robot_id = robot_id
            message.image = "no image"
            payload = "{0} {1} ".format(
                robot_id,
                Messages.Register.name).encode()
            payload += message.SerializeToString()
            self.messages.append(payload)

    def write(self, message):
        #print('Fake writing message =', message)
        expected_message = self.messages.pop(0)
        assert_equals(expected_message, message)


class MockSubscriber(object):
    def __init__(self, address, context):
        self.messages = [None]
        for robot_id, robot_name, _ in ROBOT_DESCRIPTORS:
            message = REGISTRY[Messages.Registered.name]()
            message.team = "BLU"
            message.robot_id = "real_" + robot_id
            payload = "{0} {1} ".format(
                robot_id,
                Messages.Registered.name).encode()
            payload += message.SerializeToString()
            self.messages.append(payload)
        for (robot_id, left, right), (robot_id_2, fire1, fire2) in zip(MOVES, FIRES):
            message = REGISTRY[Messages.Input.name]()
            message.move.left = left
            message.move.right = right
            message.fire.weapon1 = fire1
            message.fire.weapon2 = fire2
            payload = "{0} {1} ".format(
                "real_" + robot_id,
                Messages.Input.name).encode()
            payload += message.SerializeToString()
            self.messages.append(payload)

    def read(self):
        if self.messages:
            message = self.messages.pop(0)
            print("message sent:", message)
        else:
            message = None
        #print('Fake reading message =', message)
        return message


class MockReplier(object):
    def __init__(self, address, context):
        pass

    def exchange(self, query):
        return None


class FakeRobot(threading.Thread):
    def __init__(self, port=9081):
        """
        """
        threading.Thread.__init__(self)
        self._port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def run(self):
        print("FakeRobot::run -> send to {port}".format(port=self._port))
        self._socket.sendto(b"robot", ('127.0.0.1', self._port))


def test_robot_registration():
    print("\ntest_robot_registration")
    arguments = FakeArguments()
    # we do not care about the admin
    admin_mock = unittest.mock.MagicMock()
    admin_mock.return_value = admin_mock
    program = Program(
        zmq.Context(1),
        arguments,
        MockSubscriber,
        MockPusher,
        MockReplier,
        admin_mock)
    for robot_id, _, device in ROBOT_DESCRIPTORS:
        program.add_robot(robot_id, device)
    # fake_robot = FakeRobot()
    # fake_robot.start()
    program.step()
    program.step()
    for item, expected in zip(program.robots.items(), ROBOT_DESCRIPTORS):
        robot_id, robot = item
        expected_robot_id, expected_robot_name, _ = expected
        assert_equals("real_" + expected_robot_id, robot.robot_id)
        assert_equals(expected_robot_id, robot_id)
        # assert_equals(expected_robot_name, robot.name)
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
    for (robot_id, left, right), (robot_id_2, fire1, fire2) in zip(MOVES, FIRES):
        program.step()
        robot = program.robots[robot_id]
        assert_equals(left, robot.left)
        assert_equals(right, robot.right)
        assert_equals(fire1, robot.fire1)
        assert_equals(fire2, robot.fire2)
    # make sure all inputs have been consumed
    for robot_id, _, device in ROBOT_DESCRIPTORS:
        print('robot_id =', robot_id)
        assert_equals(0, len(device.expected_moves))
        assert_equals(0, len(device.expected_fires))


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

    def ready(self):
        return True

    def get_socket(self):
        return FakeSocket([], ["DummyDevice/FakeSocket"])


INPUT_ROBOT_DESCRIPTOR = ('55', 'Jambon', DummyDevice('55'))


class MockerStorage(object):
    def __init__(self, address, context):
        self.address = address
        self.context = context


class Mocker(object):
    def __init__(self):
        self._pusher = None
        self._publisher = None
        self._replier = None

    def pusher_init_faker(self):
        def fake_init(address, context):
            self._pusher = MockerStorage(address, context)
            return self
        return fake_init

    def publisher_init_faker(self):
        def fake_init(address, context):
            self._publisher = MockerStorage(address, context)
            return self
        return fake_init

    def replier_init_faker(self):
        def fake_init(address, context):
            self._replier = MockerStorage(address, context)
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
        if InputMockerState.Register == self._state:
            message = REGISTRY[Messages.Registered.name]()
            # message.name = self._robot_name
            message.team = self._team
            message.robot_id = "real " + self._robot_id
            payload = "{0} {1} ".format(
                self._robot_id,
                Messages.Registered.name).encode()
            payload += message.SerializeToString()
            print('Fake message (Registered) =', message)
            self._state = InputMockerState.Input
        elif InputMockerState.Input == self._state:
            message = REGISTRY[Messages.Input.name]()
            message.move.left = INPUT_MOVE[0]
            message.move.right = INPUT_MOVE[1]
            message.fire.weapon1 = False
            message.fire.weapon2 = False
            payload = "{0} {1} ".format(
                self._robot_id,
                Messages.Input.name).encode()
            payload += message.SerializeToString()
            print('Fake message (Input) =', message)
        return payload

    def write(self, payload):
        print('Fake write')
        if InputMockerState.Created == self._state:
            routing_id, message_type, raw_message = payload.split(b' ', 2)
            message_type = message_type.decode('ascii')
            routing_id = routing_id.decode('ascii')
            if Messages.Register.name == message_type:
                message = REGISTRY[message_type]()
                message.ParseFromString(raw_message)
                self._robot_id = message.temporary_robot_id
                self._state = InputMockerState.Register
            else:
                print("We should not be here")
                assert False


def test_robot_input():
    print("\ntest_robot_input")
    arguments = FakeArguments()
    input_mocker = InputMocker()
    # we do not care about the admin
    admin_mock = unittest.mock.MagicMock()
    admin_mock.return_value = admin_mock
    program = Program(
        zmq.Context(1),
        arguments,
        input_mocker.publisher_init_faker(),
        input_mocker.pusher_init_faker(),
        input_mocker.replier_init_faker(),
        admin_mock)
    robot_id, robot_name, device = INPUT_ROBOT_DESCRIPTOR
    program.add_robot(robot_id, device)
    program.step()
    program.step()
    program.step()


class FakeSocket(object):
    def __init__(self, expected_content_list, recvfrom_list, address="127.0.0.1", port="42"):
        print("FakeSocket({0}, {1}, {2})".format(expected_content_list, address, port))
        self._expected_content_list = expected_content_list
        self._address = address
        self._port = port
        self._recvfrom_list = recvfrom_list

    def __del__(self):
        assert_equals(0, len(self._expected_content_list))
        pass

    def send(self, content):
        expected_content = self._expected_content_list.pop(0)
        assert_equals(expected_content, content)

    def getsockname(self):
        print("FakeSocket::getsockname")
        return [self._address, self._port]

    def recvfrom(self, size):
        # print("FakeSocket::recvfrom")
        if self._recvfrom_list:
            item = self._recvfrom_list.pop(0)
        else:
            item = None
        return item, self._address


def test_missing_server_game():
    fake_server_game = orwell_common.broadcast_listener.BroadcastListener()
    # No message should be received
    subscriber_mock = unittest.mock.MagicMock()
    subscriber_mock.return_value = subscriber_mock
    subscriber_mock.read.return_value = None
    # first call find no game server
    # There are no message in the queue as the server has not been found yet
    message_queue = queue.Queue()
    wrapper = BroadcasterMessageHubWrapper(
        zmq.Context(1),
        message_queue,
        subscriber_mock,
        unittest.mock.MagicMock(),
        unittest.mock.MagicMock())
    assert_false(wrapper.is_valid)
    wrapper.step()
    # nothing running so far, no MessageHub should be created
    assert_false(wrapper.is_valid)
    # pretend game server had made a proper reply
    push_address = "127.0.0.1:9001"
    subscribe_address = "127.0.0.1:9000"
    reply_address = "127.0.0.1:9004"
    # server has been found and gave following addresses
    message_queue.put((push_address, subscribe_address, reply_address))
    waiter = unittest.mock.MagicMock()
    wrapper.register_waiter(waiter)
    wrapper.step()
    # notify_message_hub should be called once on waiter
    waiter.notify_message_hub.assert_called_once()
    waiter.reset_mock()
    assert_true(wrapper.is_valid)
    # game server remains available (no new message in the queue)
    wrapper.step()
    waiter.notify_message_hub.assert_not_called()
    # game server becomes unavailable
    message_queue.put(None)
    wrapper.step()
    assert_false(wrapper.is_valid)
    waiter.notify_message_hub.assert_not_called()
    # game server becomes available again
    message_queue.put((push_address, subscribe_address, reply_address))
    wrapper.step()
    waiter.notify_message_hub.assert_called_once()
    assert_true(wrapper.is_valid)


def main():
    test_robot_registration()
    test_robot_input()


if "__main__" == __name__:
    main()