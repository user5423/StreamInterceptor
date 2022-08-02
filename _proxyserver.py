
import selectors
import socket
import signal
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Dict, NamedTuple, Optional


proxyHandlerDescriptor = NamedTuple("ProxyHandlerData", [("PROXY_HOST", str), ("PROXY_PORT", int), ("StreamInterceptor", object)])


## NOTE: We will subclass this for the Stream Interceptor
@dataclass
class ProxyInterceptor:
    clientToServerBuffer: bytearray = field(init=False, default_factory=bytearray)
    serverToClientCallback: bytearray = field(init=False, default_factory=bytearray)
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
        self.serverToClientCallback += requestChunk
        self.serverToClientCallback.replace(b"0.0.0.0:8080", b"127.0.0.1:80")


@dataclass
class Buffer:
    _data: bytearray = field(init=False, default=bytearray)


    def read(self, bytes: int = 0) -> bytes:
        if bytes <= 0:
            return self._data
        return self._data[max(len(self._data) - bytes, 0):]


    def pop(self, bytes: int = 0) -> bytes:
        if bytes <= 0:
            self._data = bytearray()
        self._data = self._data[:min(len(self._data) - bytes, 0)]


    def write(self, chunk: bytearray) -> None:
        self.execWriteHook(chunk)
        self._data += chunk


    def execWriteHook(self, chunk: bytearray) -> None:
        return self._writeHook(chunk, self)


    def setHook(self, hook: Callable[[bytearray, "Buffer"], None]) -> None:
        self._writeHook = hook
        

    def _writeHook(chunk: bytearray, buffer: "Buffer") -> None:
        ...


@dataclass
class ProxyTunnel:
    clientToProxySocket: socket.socket
    proxyToServerSocket: socket.socket
    CHUNK_SIZE: int = field(default=1024)

    clientToServerBuffer: bytearray = field(init=False, default_factory=bytearray)
    serverToClientBuffer: bytearray = field(init=False, default_factory=bytearray)

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


    def read(self, source: socket.socket) -> Optional[int]:
        ## Check if the source socket is associated with the tunnel
        fd = source.fileno()
        if not (self.clientToProxySocket.fileno() == fd or self.proxyToServerSocket.fileno() == fd):
            raise Exception("The socket provided is not associated with this tunnel")

        ## Read the source 
        data = source.recv(1024)
        if not data:
            return None
        
        ## Read it into the buffer
        buffer = self._selectBuffer(source)
        buffer.write(data)
        return len(data)


    def write(self, destination: socket.socket) -> Optional[int]:
        ## Check if the source socket is associated with the tunnel
        fd = destination.fileno()
        if not (self.clientToProxySocket.fileno() == fd or self.proxyToServerSocket.fileno() == fd):
            raise Exception("The socket provided is not associated with this tunnel")

        ## Read from the buffer and send it to destination socket
        buffer = self._selectBuffer(destination)
        data = buffer.read(self.CHUNK_SIZE)
        
        bytesSent = destination.send(data, self.CHUNK_SIZE)
        buffer.pop(bytesSent)
        return bytesSent
        

    def _selectBuffer(self, source: socket.socket) -> bytes:
        fd = source.fileno()
        if self.clientToProxySocket.fileno() == fd:
            return self.proxyInterceptor.clientToServerBuffer
        elif self.proxyToServerSocket.fileno() == fd:
            return self.proxyInterceptor.serverToClientBuffer
        else:
            raise Exception("The socket provided is not associated with this tunnel")


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


    def closeTunnel(self, proxyTunnel: ProxyTunnel) -> None:
        proxyTunnel = self._fd[proxyTunnel.clientToProxySocket]
        proxyTunnel.close()
        del self._fd[proxyTunnel.clientToProxySocket]


def main():
    lhost = socket.socket()
    rhost = socket.socket()
    pt = ProxyTunnel(lhost, rhost)


if __name__ == "__main__":
    main()
