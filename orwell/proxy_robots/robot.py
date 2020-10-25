import logging

from orwell.proxy_robots.action import Action
from orwell.proxy_robots.proxy import Proxy
from orwell.proxy_robots.registry import Messages
from orwell.proxy_robots.registry import REGISTRY

LOGGER = logging.getLogger(__name__)


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
        # LOGGER.debug('queue_register')
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
        assert (self._robot_id == routing_id)
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

    # def move(self, left, right):
    # """
    # Nothing yet.
    # """
    # pass


