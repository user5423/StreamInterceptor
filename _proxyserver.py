
import argparse
import selectors
import socket
import signal
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Dict, NamedTuple



proxyHandlerDescriptor = NamedTuple("ProxyHandlerData", [("PROXY_HOST", str), ("PROXY_PORT", int), ("StreamInterceptor", object)])


## NOTE: We will subclass this for the Stream Interceptor
@dataclass
class ProxyInterceptor:
    clientToServerBuffer: bytearray = field(init=False, default_factory=bytearray)
    ServerToClientBuffer: bytearray = field(init=False, default_factory=bytearray)
    clientToServerCallback: Callable = field(init=False)
    serverToClientCallback: Callable = field(init=False)

    def __post_init__(self) -> None:
        self.clientToServerCallback = self._weakHTTPRequestReroute
        self.serverToClientCallback = self._weakHTTPResponseReroute


    # ## NOTE: This needs to rewrite any requests to the real server
    # def clientToServerCallback(self, requestChunk: bytes) -> None:
    #      ...

    # ## NOTE: This needs to rewrite any responses back to the client
    # def serverToClientCallback(self, responseChunk: bytes) -> None:
    #      ...

    ## NOTE: This should be performed on a per protocol basis!!!

    ## BUG: This is intended to be a weak request rewrite (and will break depending on chunks)
    def _weakHTTPRequestReroute(self, requestChunk: bytes) -> None:
        self.clientToServerBuffer += requestChunk
        self.clientToServerBuffer.replace(b"0.0.0.0:8080", b"127.0.0.1:80")

    ## BUG: This is intended to be a weak response reroute (and will break depending on chunks)
    def _weakHTTPResponseReroute(self, requestChunk: bytes) -> bytes:
        self.ServerToClientBuffer += requestChunk
        self.ServerToClientBuffer.replace(b"0.0.0.0:8080", b"127.0.0.1:80")



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
