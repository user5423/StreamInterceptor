import socket
from dataclasses import dataclass, field
from typing import Callable, Dict

from grpc import server



## NOTE: We will subclass this for the Stream Interceptor
@dataclass
class ProxyInterceptor:
    clientToProxyBuffer: bytearray = field(init=False, default_factory=bytearray)
    proxyToServerBuffer: bytearray = field(init=False, default_factory=bytearray)
    clientToProxyCallback: Callable = field(init=False)
    proxyToServerCallback: Callable = field(init=False)

    def __post_init__(self) -> None:
        self.clientToProxyCallback = self._weakHTTPRequestReroute
        self.proxyToServerCallback = self._weakHTTPResponseReroute


    # ## NOTE: This needs to rewrite any requests to the real server
    # def clientToProxyCallback(self, requestChunk: bytes) -> None:
    #      ...

    # ## NOTE: This needs to rewrite any responses back to the client
    # def proxyToServerCallback(self, responseChunk: bytes) -> None:
    #      ...

    ## BUG: This is intended to be a weak request (and will break depending on chunks)
    def _weakHTTPRequestReroute(self, requestChunk: bytes) -> bytes:
        return requestChunk.replace(b"0.0.0.0:8080", b"127.0.0.1:80")

    ## BUG: This is intended to be a weak request (and will break depending on chunks)
    def _weakHTTPResponseReroute(self, requestChunk: bytes) -> bytes:
        return requestChunk.replace(b"127.0.0.1:80", b"0.0.0.0:8080")



@dataclass
class ProxyTunnel:
    clientToProxySocket: socket.socket
    proxyToServerSocket: socket.socket
    proxyInterceptor: ProxyInterceptor = field(init=False, repr=False, default_factory=ProxyInterceptor)

    def getDestination(self, fd: int) -> socket.socket:
        if self.clientToProxySocket.fileno() == fd:
            return self.proxyToServerSocket
        elif self.proxyToServerSocket.fileno() == fd:
            return self.clientToProxySocket
        else:
            raise Exception("The socket provided is not associated with this tunnel")

    def close(self) -> None:
        self.clientToProxySocket.close()
        self.proxyToServerSocket.close()


@dataclass
class ProxyConnections:
    _fd: Dict[str, ProxyTunnel] = field(default_factory=dict)

    def get(self, fd: int) -> ProxyTunnel:
        return self._fd.get(fd)

    def put(self, fd: int, proxyTunnel: ProxyTunnel) -> None:
        self._fd[fd] = proxyTunnel

    def len(self) -> int:
        return len(self._fd)

    def getDestination(self, fd: int) -> None:
        return self._fd.get(fd).getDestination(fd)


    ## TODO: We need to add methods for rewriting
    def createTunnel(self, clientToProxySocket: socket.socket, proxyToServerSocket: socket.socket):
        ## Check if the sockets are registered with a pre-existing tunnel
        if self._fd.get(clientToProxySocket):
            raise Exception("The `clientToProxySocket` is already registered with a tunnel")
        elif self._fd.get(proxyToServerSocket):
            raise Exception("The `proxyToServerSocket` is already registered with a tunnel")

        ## We then create a new proxy and register it
        proxyTunnel = ProxyTunnel(clientToProxySocket, proxyToServerSocket)
        self.put(clientToProxySocket.fileno(), proxyTunnel)
        self.put(proxyToServerSocket.fileno(), proxyTunnel)


    def deleteTunnel(self, proxyTunnel: ProxyTunnel) -> None:
        del self._fd[proxyTunnel.clientToProxySocket]




def main():
    lhost = socket.socket()
    rhost = socket.socket()
    pt = ProxyTunnel(lhost, rhost)


if __name__ == "__main__":
    main()
