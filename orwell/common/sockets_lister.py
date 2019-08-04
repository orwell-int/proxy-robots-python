import socket


class SocketsLister(object):
    """
    Class that for now lists available sockets.
    """
    def __init__(self, socket_count=1):
        self._sockets = []
        self._used_sockets = set()
        for i in range(socket_count):
            sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            sock.setblocking(False)
            sock.bind(("", 0))
            self._sockets.append(sock)

    def __del__(self):
        """
        Make sure we close all the sockets.
        """
        for sock in self._sockets:
            sock.close()
        for sock in self._used_sockets:
            sock.close()

    def pop_available_socket(self):
        """
        Return the first available socket (or None if none is found).
        #You will be responsible of closing it.
        """
        available_socket = None
        if (self._sockets):
            available_socket = self._sockets.pop(0)
            self._used_sockets.add(available_socket)
        return available_socket