from __future__ import print_function
import argparse
import zmq
import logging
import collections
from enum import Enum
import threading
import time
import datetime

from orwell_common.broadcast_listener import BroadcastListener
from orwell_common.broadcast import Broadcast
from orwell_common.broadcast import ServerGameDecoder
from orwell_common.sockets_lister import SocketsLister
import orwell_common.broadcast_listener
import orwell_common.broadcast

from orwell.proxy_robots.devices import FakeDevice, HarpiDevice
import orwell.messages.robot_pb2 as robot_messages
import orwell.messages.server_game_pb2 as server_game_messages
import orwell.messages.controller_pb2 as controller_messages

LOCK = threading.Lock()
LOCK_SOCKET = threading.Lock()

ZMQ_CONTEXT = zmq.Context.instance()


class Messages(Enum):
    Register = 'Register'
    Registered = 'Registered'
    Input = 'Input'


REGISTRY = {
    Messages.Register.name: lambda: robot_messages.Register(),
    Messages.Registered.name: lambda: server_game_messages.Registered(),
    Messages.Input.name: lambda: controller_messages.Input(),
}

LOGGER = None


class Subscriber(object):
    def __init__(self, address, context):
        self._socket = context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.setsockopt_string(zmq.SUBSCRIBE, "")
        LOGGER.info("Connect to {address} sub".format(address=address))
        self._socket.connect(address)

    def read(self):
        try:
            return self._socket.recv(flags=zmq.DONTWAIT)
        except zmq.error.Again:
            return None


class Pusher(object):
    def __init__(self, address, context):
        self._socket = context.socket(zmq.PUSH)
        self._socket.setsockopt(zmq.LINGER, 0)
        # print("Pusher ; address =", address)
        LOGGER.info("Connect to {address} push".format(address=address))
        self._socket.connect(address)

    def write(self, message):
        LOGGER.debug("Pusher.write: " + repr(message))
        self._socket.send(message)


class Replier(object):
    def __init__(self, address, context):
        self._socket = context.socket(zmq.REQ)
        self._socket.setsockopt(zmq.LINGER, 0)
        LOGGER.info("Connect to {address} req".format(address=address))
        self._socket.connect(address)

    def exchange(self, query):
        self.write(query)
        return self.read()

    def write(self, message):
        LOGGER.debug("Replier.write: " + repr(message))
        self._socket.send(message)

    def read(self):
        return self._socket.recv(flags=zmq.DONTWAIT)


class AdminSocket(object):
    def __init__(self, admin_port, zmq_context=ZMQ_CONTEXT):
        self._context = zmq_context
        self._admin = self._context.socket(zmq.REP)
        self._admin.bind("tcp://*:{port}".format(port=admin_port))

    def recv_string(self, flags=0, encoding='utf-8'):
        return self._admin.recv_string(flags, encoding)

    def send_string(self, u, flags=0, copy=True, encoding='utf-8', **kwargs):
        return self._admin.send_string(u, flags, copy, encoding, **kwargs)


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
        self._context = zmq_context
        self._admin_socket = admin_socket_type(admin_port)

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


class MessageHub(object):
    """
    Class that is in charge of orchestrating reads and writes.
    Items that are to be written are provided with #post and
    objects that want to be notified of reads listen through #register_listener.
    """

    def __init__(
            self,
            publisher_address,
            pusher_address,
            replier_address,
            subscriber_type=Subscriber,
            pusher_type=Pusher,
            replier_type=Replier,
            zmq_context=ZMQ_CONTEXT):
        """
        `publisher_address`: address to read from.
        `pusher_address`: address to write to.
        `replier_address`: address to read replies from.
        `subscriber_type`: for testing purpose ; class to use as a subscriber
          which reads from the publisher address.
        `pusher_type`: for testing purpose ; class to use as pusher which
          writes to the puller address.
        `replier_type`: for testing purpose ; class to use as replier which
          writes to and reads from the replier address.
        """
        # print("MessageHub ; pusher_address =", pusher_address)
        self._context = zmq_context
        self._pusher = pusher_type(
                pusher_address,
                self._context)
        self._subscriber = subscriber_type(
                publisher_address,
                self._context)
        self._replier = replier_type(
                replier_address,
                self._context)
        self._listeners = collections.defaultdict(list)
        self._outgoing = []

    def register_listener(self, listener, message_type, routing_id):
        """
        `listener`: object which has a #notify method (which takes a message
            type, a routing id and a decoded protobuf message as arguments).
        `message_type`: the types of messages the listener is interested in.
            If empty means all types are interesting.
        `routing_id`: the routing ids the listener is interested in. If empty
            means all ids are interesting.
        Tell that #listener wants to be notified of messages read for type
        #message_type and routing id #routing_id.
        """
        LOGGER.debug('MessageHub.register_listener({0}, {1}, {2}'.format(
            listener, message_type, routing_id))
        if (listener, routing_id) not in self._listeners[message_type]:
            self._listeners[message_type].append((routing_id, listener))

    def unregister_listener(self, listener, message_type, routing_id):
        """
        Reverts the effects of #register_listener (the parameters must be the same).
        """
        if (listener, routing_id) in self._listeners[message_type]:
            self._listeners[message_type].remove((listener, routing_id))

    def post(self, payload):
        """
        Put a message (type + routing id + encode protobuf message) in the list
        of messages to write to the pusher.
        """
        self._outgoing.append(payload)


    def step(self):
        """
        Process one incoming message (if any) and process all outgoing
        messages (if any).
        """
        # LOGGER.debug('MessageHub.step()')
        # LOGGER.debug('_listeners = ' + str(self._listeners))
        string = self._subscriber.read()
        # LOGGER.debug('string = ' + repr(string))
        if string is not None:
            routing_id, message_type, raw_message = string.split(b' ', 2)
            message_type = message_type.decode('ascii')
            routing_id = routing_id.decode('ascii')
            if message_type in REGISTRY:
                LOGGER.debug('message known = ' + repr(message_type))
                message = REGISTRY[message_type]()
                message.ParseFromString(raw_message)
                for expected_routing_id, listener in \
                        self._listeners[message_type]:
                    LOGGER.debug('listener = ' + str(listener))
                    LOGGER.debug(
                            'expected_routing_id = ' +
                            str(expected_routing_id))
                    if expected_routing_id:
                        is_expected = True
                    else:
                        is_expected = (expected_routing_id == routing_id)
                    if is_expected:
                        listener.notify(message_type, routing_id, message)
            else:
                LOGGER.debug('message NOT known = ' + repr(message_type))
        for payload in self._outgoing:
            self._pusher.write(payload)
        del self._outgoing[:]


class DumbMessageHubWrapper(object):
    def __init__(
            self,
            message_hub=None):
        self._message_hub = message_hub
        self._waiters = []

    @property
    def message_hub(self):
        return self._message_hub

    @property
    def is_valid(self):
        return self._message_hub is not None

    def step(self):
        if self._message_hub is not None:
            self._message_hub.step()

    def register_waiter(self, waiter):
        self._waiters.append(waiter)

    def notify_waiters(self):
        for waiter in self._waiters:
            waiter.notify_message_hub(self._message_hub)


class BroadcasterMessageHubWrapper(DumbMessageHubWrapper):
    """
    MessageHub wrapper that periodically checks if the game server responds to
    broadcast to make sure it is up.
    Creates a MessageHub when the game server becomes available.
    Destroys the wrapped MessageHub when the game server becomes unavailable.
    """

    def __init__(
            self,
            delta_check,
            broadcast_type=Broadcast,
            subscriber_type=Subscriber,
            pusher_type=Pusher,
            replier_type=Replier):
        """
        `delta_check`: interval between two checks (test presence of game server).
        """
        super().__init__()
        self._subscriber_type = subscriber_type
        self._pusher_type = pusher_type
        self._replier_type = replier_type
        self._broadcaster = broadcast_type(ServerGameDecoder(), retries=1)
        self._delta_check = delta_check
        self._next_check = datetime.datetime.now()

    def _check_message_hub(self):
        LOGGER.debug("BroadcasterMessageHubWrapper._check_message_hub")
        if self._message_hub:
            if not self._broadcaster.send_one_broadcast_message(silent=True):
                LOGGER.info("Lost contact with ServerGame.")
                self._message_hub = None
        else:
            self._broadcaster.send_all_broadcast_messages()
            if not self._broadcaster.decoder.success:
                LOGGER.info("Could not find ServerGame.")
            else:
                # We assume this is still the same instance of server game
                # or at least with the same properties.
                # If the game server disconnects and a new one takes its place
                # it might be unnoticed and things will not work properly.
                LOGGER.info(
                    "push: " + self._broadcaster.decoder.push_address +
                    " / subscribe: " + self._broadcaster.decoder.subscribe_address +
                    " / reply: " + self._broadcaster.decoder.reply_address)
                push_address = self._broadcaster.decoder.push_address
                subscribe_address = self._broadcaster.decoder.subscribe_address
                replier_address = self._broadcaster.decoder.reply_address
                self._message_hub = MessageHub(
                    subscribe_address,
                    push_address,
                    replier_address,
                    self._subscriber_type,
                    self._pusher_type,
                    self._replier_type)
                self.notify_waiters()

    def step(self):
        now = datetime.datetime.now()
        if self._next_check <= now:
            self._check_message_hub()
            self._next_check = now + self._delta_check
        super().step()


class Proxy(object):
    """
    Helper class.
    """
    def __init__(
            self,
            message_hub_wrapper,
            callback,
            message_type,
            routing_id):
        self.message_hub_wrapper = message_hub_wrapper
        message_hub_wrapper.register_waiter(self)
        self.callback = callback
        self.message_type = message_type
        self.routing_id = routing_id
        self._actions = []

    def register_listener(self, action):
        if self.message_hub_wrapper.is_valid:
            self.message_hub_wrapper.message_hub.register_listener(
                action, self.message_type, self.routing_id)
        else:
            self._actions.append(action)

    def notify_message_hub(self, message_hub):
        for action in self._actions:
            message_hub.register_listener(
                action, self.message_type, self.routing_id)

    def unregister(self, action):
        if self.message_hub_wrapper.is_valid:
            self.message_hub_wrapper.message_hub.unregister_listener(
                action, self.message_type, self.routing_id)


class Status(Enum):
    # just created
    created = 0
    # action called, but no reply yet
    pending = 1
    # action called, reply received
    waiting = 2
    # action failed
    failed = 3
    # action successful
    successful = 4


class Action(object):
    """
    Object functor to wrap a function and possibly the notification associated
    to the function (the function sends the message and the notification is
    triggered when the reply is received).
    """
    def __init__(
            self,
            doer,
            success,
            proxy=None,
            repeat=False):
        """
        `doer`: the function that does something.
        `success`: the function to call to check if the action is successful
            or not.
        `proxy`: the object containing information about the notification to
            register to (if needed). If None, there is no registration.
        `repeat`: True if and only if the action is to be attempted again on
            failure. The function #doer is called again when this happens.
        """
        self._doer = doer
        self._success = success
        self._repeat = repeat
        self._proxy = proxy
        self._status = Status.created
        if self._proxy:
            self._proxy.register_listener(self)

    def call(self):
        """
        Call the wrapped function.
        """
        self._doer()
        self._update_status()

    def reset(self):
        """
        To be called on failure to make it possible to repeat the action.
        """
        self._update_status()

    @property
    def status(self):
        """
        Status tracking where the action stands.
        """
        return self._status

    def _update_status(self):
        """
        Update the status of the action.
        """
        updated = False
        if Status.created == self._status:
            if self._proxy:
                self._status = Status.pending
            else:
                self._status = Status.waiting
            updated = True
        if not updated:
            if Status.pending == self._status:
                self._status = Status.waiting
            elif self._status in (Status.successful, Status.failed):
                self._status = Status.created
        if Status.waiting == self._status:
            if not self._proxy:
                if self._success():
                    self._status = Status.successful
                else:
                    self._status = Status.failed

    def notify(
            self,
            message_type,
            routing_id,
            message):
        """
        May only be called if a proxy was provided to the constructor. Called
        when the message registered to is read.
        """
        LOGGER.debug('Action.notify({0}, {1}, {2})'.format(
            message_type,
            routing_id,
            repr(message)))
        if self._proxy.message_type:
            if self._proxy.message_type != message_type:
                raise Exception("Expected message type {0} but got {1}".format(
                    self._proxy.message_type, message_type))
        if self._proxy.routing_id:
            if self._proxy.routing_id != routing_id:
                raise Exception("Expected routing id {0} but got {1}".format(
                    self._proxy.routing_id, routing_id))
        self._update_status()
        self._proxy.callback(message_type, routing_id, message)
        self._update_status()
        self._proxy.unregister(self)


class Engine(object):
    """
    Engine that makes the actions run.
    """
    def __init__(self):
        self._created_actions = []
        self._pending_actions = []

    def add_action(self, action):
        """
        Simply add an action to be run in the next call to #step.
        """
        self._created_actions.append(action)

    def step(self):
        """
        Check all pending actions to see if a notification has been received.
        Run all the actions that are in the created state.
        """
        #LOGGER.debug('Engine.step()')
        #LOGGER.debug('_created_actions = ' + str(self._created_actions))
        #LOGGER.debug('_pending_actions = ' + str(self._pending_actions))
        to_remove = []
        new_actions = []
        for action in self._pending_actions:
            if Status.waiting == action.status:
                action.reset()
                to_remove.append(action)
                if Status.successful == action.status:
                    pass
                elif Status.failed == action.status:
                    if action.repeat:
                        action.reset()
                        new_actions.append(action)
        for action in to_remove:
            self._pending_actions.remove(action)
        for action in self._created_actions:
            action.call()
            if Status.pending == action.status:
                self._pending_actions.append(action)
            elif Status.successful == action.status:
                pass
            elif Status.failed == action.status:
                if action.repeat:
                    action.reset()
                    new_actions.append(action)
        self._created_actions = new_actions


class Robot(object):
    def __init__(
            self,
            robot_id,
            message_hub_wrapper,
            engine,
            device):
        """
        `robot_id`: identifies the robot somehow.
        `message_hub_wrapper`: used to post message and get notifications.
        `engine`: object that will run the actions for the robot.
        `device`: device used to communicate with the robot.
        """
        self._robot_id = robot_id
        # self._name = ''
        self._message_hub_wrapper = message_hub_wrapper
        self._engine = engine
        self._device = device
        self._registered = False
        self._left = 0.0
        self._right = 0.0
        self._fire1 = False
        self._fire2 = False
        self._previous_left = 0.0
        self._previous_right = 0.0
        self._previous_fire1 = False
        self._previous_fire2 = False

    @property
    def robot_id(self):
        return self._robot_id

    # @property
    # def name(self):
        # return self._name

    @property
    def left(self):
        return self._left

    @property
    def right(self):
        return self._right

    @property
    def fire1(self):
        return self._fire1

    @property
    def fire2(self):
        return self._fire2

    def step(self):
        if self._device.ready():
            if ((self._previous_left != self._left) or
                    (self._previous_right != self._right)):
                self._device.move(self._left, self._right)
                self._previous_left = self._left
                self._previous_right = self._right
            if ((self._previous_fire1 != self._fire1) or
                    (self._previous_fire2 != self._fire2)):
                self._device.fire(self._fire1, self._fire2)
                self._previous_fire1 = self._fire1
                self._previous_fire2 = self._fire2

    @property
    def registered(self):
        """
        True if and only if the robot has been registered in the game server.
        """
        return self._registered

    def queue_register(self):
        """
        Create an action that will take care of registering the robot and
        dispatch the notification.
        """
        #LOGGER.debug('queue_register')
        proxy = Proxy(
            self._message_hub_wrapper,
            self.notify,
            Messages.Registered.name,
            self._robot_id)
        action = Action(
            self.send_register,
            lambda: self.registered,
            proxy,
            repeat=True)
        self._engine.add_action(action)

    def send_register(self):
        """
        Post a message to ask for the registration of the robot.
        """
        if self._message_hub_wrapper.is_valid:
            message = REGISTRY[Messages.Register.name]()
            message.temporary_robot_id = self._robot_id
            message.image = "no image"
            payload = '{0} {1} '.format(
                self._robot_id,
                Messages.Register.name).encode()
            payload += message.SerializeToString()
            self._message_hub_wrapper.message_hub.post(payload)

    def notify(
            self,
            message_type,
            routing_id,
            message):
        """
        Notifications dispatcher.
        """
        LOGGER.info("notify message_type: " + str(message_type))
        assert(self._robot_id == routing_id)
        if Messages.Registered.name == message_type:
            self._notify_registered(message)
        elif Messages.Input.name == message_type:
            self._notify_input(message)
        else:
            raise Exception("Invalid message type: " + message_type)

    def _notify_registered(self, message):
        """
        Flag the robot as registered if the server replied with a name.
        """
        LOGGER.info("Registered")
        self._registered = True
        self._robot_id = message.robot_id
        if self._message_hub_wrapper.is_valid:
            # this is a hack as we should only register when the game starts
            self._message_hub_wrapper.message_hub.register_listener(
                self, Messages.Input.name, self._robot_id)
        else:
            # maybe we should even halt when this happens
            LOGGER.warn("Could not get message hub from Robot!")
        # there is no longer a name attribute in Registered
        # if (message.name):
            # self._registered = True
            # self._name = message.name
            # #LOGGER.debug('Robot registered (robot_id = {0} ; name = {1})'.format(
                # #self._robot_id,
                # #self._name))
            # # this is a hack as we should only register when the game starts
            # self._message_hub.register_listener(
                # self, Messages.Input.name, self._robot_id)

    def _notify_input(self, message):
        """
        Make the robot move.
        """
        LOGGER.debug('_notify_input({0})'.format(message))
        self._left = message.move.left
        self._right = message.move.right
        self._fire1 = message.fire.weapon1
        self._fire2 = message.fire.weapon2

    #def move(self, left, right):
        #"""
        #Nothing yet.
        #"""
        #pass


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
            # self._engine.add_action(action)
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
    configure_logging(arguments.verbose)
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
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    global LOGGER
    LOGGER = logging.getLogger("orwell.proxy_robot")
    orwell_common.broadcast_listener.configure_logging(verbose)
    orwell_common.broadcast.configure_logging(verbose)


if "__main__" == __name__:
    main()