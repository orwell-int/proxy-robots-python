from orwell.proxy_robots.status import Status


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
