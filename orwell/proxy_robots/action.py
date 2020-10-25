import logging

from orwell.proxy_robots.status import Status


LOGGER = logging.getLogger(__name__)


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
