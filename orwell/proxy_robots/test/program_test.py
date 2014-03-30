import orwell.proxy_robots.program as opp
import orwell.messages.server_game_pb2 as server_game_messages


ROBOT_DESCRIPTORS = [('951', 'Grenade')]


class FakeArguments(object):
    publisher_port = '1'
    puller_port = '2'
    address = '1.2.3.4'


class MockPusher(object):
    def __init__(self, address, port, context):
        self.messages = []
        for robot_id, _ in ROBOT_DESCRIPTORS:
            message = opp.REGISTRY[opp.Messages.Register.name]()
            message.robot_id = robot_id
            payload = "{0} {1} {2}".format(
                opp.Messages.Register.name,
                robot_id,
                message.SerializeToString())
            self.messages.append(payload)

    def write(self, message):
        #print 'Fake writing message =', message
        expected_message = self.messages.pop(0)
        assert(expected_message == message)


class MockSubscriber(object):
    def __init__(self, address, port, context):
        self.messages = [None]
        for robot_id, robot_name in ROBOT_DESCRIPTORS:
            message = opp.REGISTRY[opp.Messages.Registered.name]()
            message.name = robot_name
            message.team = server_game_messages.BLU
            payload = "{0} {1} {2}".format(
                opp.Messages.Registered.name,
                robot_id,
                message.SerializeToString())
            self.messages.append(payload)

    def read(self):
        if (self.messages):
            message = self.messages.pop(0)
        else:
            message = None
        #print 'Fake reading message =', message
        return message


def test_robot_registration():
    arguments = FakeArguments()
    program = opp.Program(arguments, MockSubscriber, MockPusher)
    for robot_id, _ in ROBOT_DESCRIPTORS:
        program.add_robot(robot_id)
    program.step()
    program.step()
    program.step()
    for item, expected in zip(program.robots.items(), ROBOT_DESCRIPTORS):
        robot_id, robot = item
        expected_robot_id, expected_robot_name = expected
        assert(robot_id == robot.robot_id)
        assert(expected_robot_id == robot_id)
        assert(expected_robot_name == robot.name)
        assert(robot.registered)
    print "OK"


def main():
    test_robot_registration()

if ("__main__" == __name__):
    main()
