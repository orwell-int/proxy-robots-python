from enum import Enum

import orwell.messages.controller_pb2 as controller_messages
import orwell.messages.robot_pb2 as robot_messages
import orwell.messages.server_game_pb2 as server_game_messages


class Messages(Enum):
    Register = 'Register'
    Registered = 'Registered'
    Input = 'Input'


REGISTRY = {
    Messages.Register.name: lambda: robot_messages.Register(),
    Messages.Registered.name: lambda: server_game_messages.Registered(),
    Messages.Input.name: lambda: controller_messages.Input(),
}
