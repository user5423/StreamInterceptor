
import selectors
import socket
import signal
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Dict, NamedTuple, Optional
from weakref import KeyedRef

from torch import Stream


## TODO: Replace default exceptions with custom exceptions
## TODO: Implement Context management for TCPProxyServer
## TODO: Evaluate and implement additional exception handling

## TODO: Write functional code tests
## TODO: Benchmark server and evaluate performance bottlenecks



proxyHandlerDescriptor = NamedTuple("ProxyHandlerData", [("PROXY_HOST", str), ("PROXY_PORT", int), ("StreamInterceptor", object)])


## TODO: Use ABCs to create abstract class
## NOTE: We will subclass this for the Stream Interceptor
## NOTE: This should be performed on a per protocol basis!!!
class ProxyInterceptor:
    ## NOTE: This needs to rewrite any requests to the real server
    def clientToServerHook(self, requestChunk: bytes, buffer: "Buffer") -> None:
         ...

    ## NOTE: This needs to rewrite any responses back to the client
    def serverToClientHook(self, responseChunk: bytes, buffer: "Buffer") -> None:
         ...


## NOTE: This is not intended to work robustly - this is just a code that is meant to show an example
class HTTPProxyInterceptor(ProxyInterceptor):
    def clientToServerHook(self, requestChunk: bytes, buffer: "Buffer") -> None:
        buffer._data = buffer._data.replace(b"0.0.0.0:8080", b"127.0.0.1:80")

    def serverToClientHook(self, requestChunk: bytes, buffer: "Buffer") -> bytes:
        buffer._data = buffer._data.replace(b"127.0.0.1:80", b"0.0.0.0:8080")




@dataclass
class Buffer:
    _data: bytearray = field(init=False, default_factory=bytearray)


    def read(self, bytes: int = 0) -> bytes:
        if bytes <= 0:
            return self._data
        return self._data[max(len(self._data) - bytes, 0):]


    def pop(self, bytes: int = 0) -> bytes:
        if bytes <= 0:
            self._data = bytearray()
        self._data = self._data[:min(len(self._data) - bytes, 0)]


    def write(self, chunk: bytearray) -> None:
        self._data += chunk
        self.execWriteHook(chunk)


    def execWriteHook(self, chunk: bytearray) -> None:
        return self._writeHook(chunk, self)


    def setHook(self, hook: Callable[[bytearray, "Buffer"], None]) -> None:
        self._writeHook = hook
        

    def _writeHook(chunk: bytearray, buffer: "Buffer") -> None:
        ## NOTE: This method should be overriden by the Buffer.setHook method
        raise NotImplementedError

@dataclass
class ProxyTunnel:
    clientToProxySocket: socket.socket
    proxyToServerSocket: socket.socket
    streamInterceptor: ProxyInterceptor
    CHUNK_SIZE: int = field(default=1024)

    clientToServerBuffer: Buffer = field(init=False, default_factory=Buffer)
    serverToClientBuffer: Buffer = field(init=False, default_factory=Buffer)

    def __post_init__(self):
        self.streamInterceptor = self.streamInterceptor()
        self.clientToServerBuffer.setHook(self.streamInterceptor.clientToServerHook)
        self.serverToClientBuffer.setHook(self.streamInterceptor.serverToClientHook)

    def getDestination(self, source: socket.socket) -> socket.socket:
        if self.clientToProxySocket == source:
            return self.proxyToServerSocket
        elif self.proxyToServerSocket == source:
            return self.clientToProxySocket
        else:
            raise Exception("The socket provided is not associated with this tunnel")


    def read(self, source: socket.socket) -> Optional[int]:
        ## Check if the source socket is associated with the tunnel
        if not (self.clientToProxySocket == source or self.proxyToServerSocket == source):
            raise Exception("The socket provided is not associated with this tunnel")

        ## Read the source 
        data = source.recv(1024)
        if not data:
            return None
        
        ## Read it into the buffer
        buffer = self._selectBufferToWrite(source)
        buffer.write(data)
        return len(data)


    def write(self, destination: socket.socket) -> Optional[int]:
        ## Check if the source socket is associated with the tunnel
        if not (self.clientToProxySocket == destination or self.proxyToServerSocket == destination):
            raise Exception("The socket provided is not associated with this tunnel")

        ## Read from the buffer and send it to destination socket
        buffer = self._selectBufferToRead(destination)
        data = buffer.read(self.CHUNK_SIZE)
        
        try:
            bytesSent = destination.send(data, self.CHUNK_SIZE)
            buffer.pop(bytesSent)
            return bytesSent
        except OSError:
            return None
            

    def _selectBufferToWrite(self, source: socket.socket) -> bytes:
        if self.clientToProxySocket == source:
            return self.clientToServerBuffer
        elif self.proxyToServerSocket == source:
            return self.serverToClientBuffer
        else:
            raise Exception("The socket provided is not associated with this tunnel")


    def _selectBufferToRead(self, source: socket.socket) -> bytes:
        if self.clientToProxySocket == source:
            return self.serverToClientBuffer
        elif self.proxyToServerSocket == source:
            return self.clientToServerBuffer
        else:
            raise Exception("The socket provided is not associated with this tunnel")


@dataclass
class ProxyConnections:
    PROXY_HOST: str = field(init=True)
    PROXY_PORT: int = field(init=True)
    StreamInterceptor: ProxyInterceptor = field(init=True)

    _sock: Dict[socket.socket, ProxyTunnel] = field(init=False, default_factory=dict)
    selector: selectors.BaseSelector = field(init=False)


    def get(self, sock: socket.socket) -> ProxyTunnel:
        return self._sock.get(sock)


    def put(self, sock: int, proxyTunnel: ProxyTunnel) -> None:
        self._sock[sock] = proxyTunnel


    def len(self) -> int:
        return len(self._sock)


    def getDestination(self, sock: int) -> None:
        return self._sock.get(sock).getDestination(fd)


    ## TODO: We need to add methods for rewriting
    def createTunnel(self, clientToProxySocket: socket.socket, proxyToServerSocket: socket.socket) -> ProxyTunnel:
        ## Check if the sockets are registered with a pre-existing tunnel
        if self._sock.get(clientToProxySocket):
            raise Exception("The `clientToProxySocket` is already registered with a tunnel")
        elif self._sock.get(proxyToServerSocket):
            raise Exception("The `proxyToServerSocket` is already registered with a tunnel")

        ## We then create a new proxyTunnel
        proxyTunnel = ProxyTunnel(clientToProxySocket, proxyToServerSocket, self.StreamInterceptor)
        self.put(clientToProxySocket, proxyTunnel)
        self.put(proxyToServerSocket, proxyTunnel)

        ## We then register the associated sockets (so that they can be polled)
        self.selector.register(clientToProxySocket, selectors.EVENT_READ | selectors.EVENT_WRITE, data="connection")
        self.selector.register(proxyToServerSocket, selectors.EVENT_READ | selectors.EVENT_WRITE, data="connection")
        
        return proxyTunnel


    def closeTunnel(self, proxyTunnel: ProxyTunnel) -> None:
        ## NOTE: This method can be called by either the client or the server
        proxyTunnel = self._sock[proxyTunnel.clientToProxySocket]
        
        ## Close and unregister the clientToProxySocket
        if not proxyTunnel.clientToProxySocket._closed:
            proxyTunnel.clientToProxySocket.close()
        self.selector.unregister(proxyTunnel.clientToProxySocket)
        del self._sock[proxyTunnel.clientToProxySocket]

        ## Close and unregister the proxyToServerSocket
        if not proxyTunnel.proxyToServerSocket._closed:
            proxyTunnel.proxyToServerSocket.close()
        self.selector.unregister(proxyTunnel.proxyToServerSocket)
        del self._sock[proxyTunnel.proxyToServerSocket]
                



    def closeAllTunnels(self) -> None:
        proxyTunnels = {tunnel for tunnel in self._sock.values}
        for tunnel in proxyTunnels:
            self.closeTunnel(tunnel)


    def setupProxyToServerSocket(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.PROXY_HOST, self.PROXY_PORT))
        return s




## TODO: Add context manager
@dataclass
class TCPProxyServer:
    HOST: str
    PORT: int
    PROXY_HOST: str
    PROXY_PORT: int
    StreamInterceptor: ProxyInterceptor

    serverSocket: socket.socket = field(init=False, default=None)
    selector: selectors.BaseSelector = field(init=False)


    def __post_init__(self):
        logging.basicConfig(filename="server.log", level=logging.DEBUG)
        self._setupDataStructures()
        self._setupSignalHandlers()
        self.eventLoopFlag: bool = True


    def _setupDataStructures(self):
        ## TODO: Add argument for StreamInterception for ProxyConnections construction
        self.proxyHandlerDescriptor = proxyHandlerDescriptor(self.PROXY_HOST, self.PROXY_PORT, self.StreamInterceptor)
        self.proxyConnections = ProxyConnections(self.PROXY_HOST, self.PROXY_PORT, self.StreamInterceptor)


    def _setupSignalHandlers(self):
        try:
            signal.signal(signal.SIGBREAK, self.sig_handler)
        except AttributeError: pass ## Avoid errors caused by OS differences
        try:
            signal.signal(signal.SIGINT, self.sig_handler)
        except AttributeError: pass ## Avoid errors caused by OS differences


    def run(self) -> None:
        if self._setup() is True:
            self.logDebug("Server", "Server-Setup", "Success")
            return self._executeEventLoop()
        else:
            self.logDebug("Server", "Server-Setup", "Failure")

        return False


    def _setup(self) -> None:
        self.selector = selectors.DefaultSelector()
        self.proxyConnections.selector = self.selector
        return self._setupServerSocket()


    def _executeEventLoop(self) -> None:
        self.logDebug("Server", "Server-Running", "Success")
        while self.eventLoopFlag:
            ## TODO: Modify the timeout??
            events = self.selector.select(timeout=2.0)
            for selectorKey, bitmask in events:
                if selectorKey.data == "ServerSocket":
                    self.__acceptConnection()
                else:
                    self.__serviceConnection(selectorKey, bitmask)
        try:
            print("Server is Terminating")
            self.proxyConnections.closeAllTunnels()
            self.serverSocket.close()
            self.logDebug("Server", "Server-Termination", "Success")
        except (KeyboardInterrupt, Exception):
            self.logDebug("Server", "Server-Termination" "Warning")


    def _setupServerSocket(self) -> bool:
        if self.__createServerSocket() == False: return False
        self.__registerServerSocket()
        print(f"Server listening on {self.HOST}:{self.PORT}\n\n")
        return True


    ##TODO: Provide exception handling for setting up the server sock
    def __createServerSocket(self) -> bool:
        try:
            self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.serverSocket.bind((self.HOST, self.PORT))
            self.serverSocket.listen()
            self.serverSocket.setblocking(False)
            return True
        except OSError:
            print(f"Socket Setup Error: The address has already been bound")
            return False


    def __registerServerSocket(self) -> None:
        self.selector.register(self.serverSocket, selectors.EVENT_READ, data="ServerSocket")


    def __acceptConnection(self) -> None:
        clientToProxySocket, (hostname, port) = self.serverSocket.accept()
        proxyToServerSocket = self.proxyConnections.setupProxyToServerSocket()
        self.proxyConnections.createTunnel(clientToProxySocket, proxyToServerSocket)
        logging.info(f"{datetime.now()}\t{hostname}\t{port}\tUndefined\tConnection-Accepted\tSuccess")
        

    def __serviceConnection(self, selectorKey: selectors.SelectorKey, bitmask: int) -> None:
        sock = selectorKey.fileobj
        data = selectorKey.data

        ## NOTE: It's possible the the other socket of the tunnel closed the tunnel
        proxyTunnel = self.proxyConnections.get(sock)
        if proxyTunnel is None:
            return None

        ## In order to transfer from one socket, to another, we need to create buffers between them
        if bitmask & selectors.EVENT_READ:
            ## Read data from socket into buffer
            out = proxyTunnel.read(sock)
            ## If socket is closed, close tunnel
            if out is None:
                return self.proxyConnections.closeTunnel(proxyTunnel)

        if bitmask & selectors.EVENT_WRITE:
            ## Writes data from buffer into socket (if any)
            out = proxyTunnel.write(sock)
            ## If socket is closed, close tunnel
            if out is None:
                return self.proxyConnections.closeTunnel(proxyTunnel)
            

    def logDebug(self, user: str = "Server", eventType: str = "Default", description: str = "Default",) -> None:
        logging.debug(f"{datetime.now()}\t{self.HOST}\t{self.PORT}\t{user}\t{eventType}\t{description}")
        

    def exit(self) -> None:
        self.eventLoopFlag = False
    

   ## Required parameters by signal handler
    def sig_handler(self, signum, frame) -> None:
        self.exit()




def main():
    HOST = "0.0.0.0"
    PORT = 8080
    PROXY_HOST = "127.0.0.1"
    PROXY_PORT = 80
    StreamInterceptor = HTTPProxyInterceptor
    tcp = TCPProxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT, StreamInterceptor)
    tcp.run()


if __name__ == "__main__":
    main()
