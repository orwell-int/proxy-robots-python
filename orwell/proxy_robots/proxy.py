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
