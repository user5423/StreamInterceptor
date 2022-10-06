from typing import Optional

## NOTE: There are unused variables for potential logging inside exceptions later

class BufferOverflowError(BufferError):
    def __init__(self, buffer: "Buffer"):
        self.msg = "Buffer Overflow at %s", buffer
        super().__init__(self.msg)


class AlreadyRegisteredSocketError(Exception):
    def __init__(self, proxyConnections: "ProxyConnections", socket: "socket.socket", socketName: Optional[str] = None):
        self.msg = "Socket (name=%s) already registered in ProxyConnections instance.\n", socketName
        super().__init__(self.msg)


class NotRegisteredSocketError(Exception):
    def __init__(self, proxyConnections: "proxyConnections", socket: "socket.socket", socketName: Optional[str] = None) -> None:
        self.msg = "Socket (name=%s) is not registered in ProxyConnections instance. \n", socketName
        super().__init__(self.msg)


class UnassociatedTunnelSocket(Exception):
    def __init__(self, proxyTunnel: "proxyTunnel", socket: "socket.socket", socketName: Optional[str] = None) -> None:
        self.msg = "Socket (name=%s) is not associated with the ProxyTunnel instance. \n", socketName
        super().__init__(self.msg)