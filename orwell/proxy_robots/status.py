from enum import Enum


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
