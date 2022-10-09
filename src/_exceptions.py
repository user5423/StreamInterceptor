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


class UnregisteredSocketError(Exception):
    def __init__(self, proxyConnections: "proxyConnections", socket: "socket.socket", socketName: Optional[str] = None) -> None:
        self.msg = "Socket (name=%s) is not registered in ProxyConnections instance. \n", socketName
        super().__init__(self.msg)


class UnregisteredProxyTunnelError(Exception):
    def __init__(self, proxyConnections: "proxyConnections", socket: "socket.socket", proxyTunnelName: Optional[str] = None) -> None:
        self.msg = "ProxyTunnel (name=%s) is not registered in ProxyConnections instance. \n", proxyTunnelName
        super().__init__(self.msg)


class UnassociatedTunnelSocket(Exception):
    def __init__(self, proxyTunnel: "proxyTunnel", socket: "socket.socket", socketName: Optional[str] = None) -> None:
        self.msg = "Socket (name=%s) is not associated with the ProxyTunnel instance. \n", socketName
        super().__init__(self.msg)


class AbsentStreamInterceptorParentError(Exception):
    def __init__(self, streamInterceptor: object) -> None:
        self.msg = "A subclass of StreamInterceptor is required for streamInterceptor \
        arg for ProxyConnection.__init__() - No ancestor class was detected"
        super().__init__(self.msg)


class AbstractStreamInterceptorError(Exception):
    def __init__(self, streamInterceptor: "streamInterceptor") -> None:
        self.msg = "A subclass of StreamInterceptor is required for streamInterceptor \
        arg for ProxyConnection.__init__() - Cannot use an instance of the abstract class"
        super().__init__(self.msg)


class InvalidProxyPortError(Exception):
    def __init__(self, PROXY_PORT: object):
        self.msg = f"Invalid PROXY_PORT arg for ProxyConnections instance: %s", PROXY_PORT
        super().__init__(self.msg)


class IncorrectDelimitersTypeError(TypeError):
    def __init__(self, REQUEST_DELIMITERS):
        self.msg = f"Incorrect type for Buffer().REQUEST_DELIMITERS - {type(REQUEST_DELIMITERS)}"
        super().__init__(self.msg)

class EmptyDelimiterTypeError(ValueError):
    def __init__(self, REQUEST_DELIMITERS):
        self.msg = F"Cannot pass empty REQUEST_DELIMITERS argument - {REQUEST_DELIMITERS}"
        super().__init__(self.msg)

class IncorrectDelimiterTypeErrpr(TypeError):
    def __init__(self, delimiter):
        self.msg = f"Incorrect type for Buffer().REQUEST_DELIMITERS[i] - {type(delimiter)}"
        super().__init__(self.msg)

class DuplicateDelimitersError(ValueError):
    def __init__(self, REQUEST_DELIMITERS):
        self.msg = f"Duplicate request delimiters were detected in the argument REQUEST_DELIMITERS - {REQUEST_DELIMITERS}"
        super().__init__(self.msg)

class PopFromEmptyQueueError(IndexError):
    def __init__(self):
        self.msg = "Cannot pop a request from empty buffer._requests deque"
        super().__init__(self.msg)

class PopUndelimitedItemInQueueError(ValueError):
    def __init__(self):
        self.msg = "Cannot pop a request from undelimited buffer._requests deque"
        super().__init__(self.msg)


class PeakFromEmptyQueueError(IndexError):
    def __init__(self):
        self.msg = "Cannot peak a request from empty buffer._requests deque"
        super().__init__(self.msg)
