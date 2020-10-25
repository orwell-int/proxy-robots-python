import collections
import datetime
import logging

from orwell_common.broadcast import Broadcast
from orwell_common.broadcast import ServerGameDecoder

from orwell.proxy_robots.connectors import Pusher
from orwell.proxy_robots.connectors import Replier
from orwell.proxy_robots.connectors import Subscriber
from orwell.proxy_robots.zmq_context import ZMQ_CONTEXT
from orwell.proxy_robots.registry import REGISTRY


LOGGER = logging.getLogger(__name__)


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
