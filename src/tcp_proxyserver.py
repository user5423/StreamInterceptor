
import selectors
import socket
import signal
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from _proxyDS import Buffer, proxyHandlerDescriptor, StreamInterceptor
## TODO: Replace default exceptions with custom exceptions
## TODO: Implement Context management for TCPProxyServer
## TODO: Evaluate and implement additional exception handling

## TODO: Write functional code tests
## TODO: Benchmark server and evaluate performance bottlenecks



## BUG: Call to write() calls read() and calls to read() call write()
## --> Results in infinite recursive loop
@dataclass(unsafe_hash=True)
class ProxyTunnel:
    clientToProxySocket: socket.socket
    proxyToServerSocket: socket.socket
    streamInterceptor: StreamInterceptor
    CHUNK_SIZE: int = field(default=1024, hash=None)

    def __post_init__(self):
        ## Initialize streamInterceptor
        self.streamInterceptor = self.streamInterceptor()
        ## Setup Bidirectional Buffers
        self.serverToClientBuffer = Buffer(self.streamInterceptor.REQUEST_DELIMITERS)
        self.clientToServerBuffer = Buffer(self.streamInterceptor.REQUEST_DELIMITERS)
        ## Set hooks on Bidirectional Buffers
        self.clientToServerBuffer.setHook(self.streamInterceptor.clientToServerHook)
        self.serverToClientBuffer.setHook(self.streamInterceptor.serverToClientHook)


    def readFrom(self, source: socket.socket) -> Optional[int]:
        ## Check if the source socket is associated with the tunnel
        if not (self.clientToProxySocket == source or self.proxyToServerSocket == source):
            raise Exception("The socket provided is not associated with this tunnel")

        ## Read the source
        try:
            data = source.recv(1024)
            if not data:
                return None
        except socket.error:
            return None
        
        ## Read it into the buffer
        buffer = self._selectBufferForRead(source)
        buffer.write(data)
        return len(data)


    def writeTo(self, destination: socket.socket) -> Optional[int]:
        ## Check if the source socket is associated with the tunnel
        if not (self.clientToProxySocket == destination or self.proxyToServerSocket == destination):
            raise Exception("The socket provided is not associated with this tunnel")

        ## Read from the buffer and send it to destination socket
        buffer = self._selectBufferForWrite(destination)
        data = buffer.read(self.CHUNK_SIZE)
        
        ## We try to send data via the destination socket
        try:
            bytesSent = destination.send(data, self.CHUNK_SIZE)
            buffer.pop(bytesSent)
            return bytesSent
        except socket.error:
            return None
            

    def _selectBufferForWrite(self, source: socket.socket) -> Buffer:
        ## For WRITE, we read from the opposite Buffer and perform source.sendall()
        if self.clientToProxySocket == source:
            return self.serverToClientBuffer
        elif self.proxyToServerSocket == source:
            return self.clientToServerBuffer
        else:
            raise Exception("The socket provided is not associated with this tunnel")


    def _selectBufferForRead(self, source: socket.socket) -> Buffer:
        ## For READ, we write to the source Buffer
        if self.clientToProxySocket == source:
            return self.clientToServerBuffer
        elif self.proxyToServerSocket == source:
            return self.serverToClientBuffer
        else:
            raise Exception("The socket provided is not associated with this tunnel")


@dataclass
class ProxyConnections:
    PROXY_HOST: str = field(init=True)
    PROXY_PORT: int = field(init=True)
    streamInterceptor: StreamInterceptor = field(init=True)

    _sock: Dict[socket.socket, ProxyTunnel] = field(init=False, default_factory=dict)
    selector: selectors.BaseSelector = field(init=False, default_factory=selectors.DefaultSelector)

    def get(self, sock: socket.socket) -> ProxyTunnel:
        return self._sock.get(sock)

    def __len__(self) -> int:
        return len(self._sock)

    ## TODO: We need to add methods for rewriting
    def createTunnel(self, clientToProxySocket: socket.socket, proxyToServerSocket: socket.socket) -> ProxyTunnel:
        ## Check if the sockets are registered with a pre-existing tunnel
        if self._sock.get(clientToProxySocket):
            raise Exception("The `clientToProxySocket` is already registered with a tunnel")
        elif self._sock.get(proxyToServerSocket):
            raise Exception("The `proxyToServerSocket` is already registered with a tunnel")

        ## We then create a new proxyTunnel
        proxyTunnel = ProxyTunnel(clientToProxySocket, proxyToServerSocket, self.streamInterceptor)
        self._sock[clientToProxySocket] = proxyTunnel
        self._sock[proxyToServerSocket] = proxyTunnel

        ## We then register the associated sockets (so that they can be polled)
        self.selector.register(clientToProxySocket, selectors.EVENT_READ | selectors.EVENT_WRITE, data="connection")
        self.selector.register(proxyToServerSocket, selectors.EVENT_READ | selectors.EVENT_WRITE, data="connection")
        
        return proxyTunnel


    def closeTunnel(self, proxyTunnel: ProxyTunnel) -> None:
        ## NOTE: This method can be called by either the client or the server
        proxyTunnel = self._sock.get(proxyTunnel.clientToProxySocket)
        if proxyTunnel is None:
            raise KeyError(f"Cannot close ProxyTunnel that is not registered: {proxyTunnel}")
        
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
        proxyTunnels = {tunnel for tunnel in self._sock.values()}
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
    streamInterceptor: StreamInterceptor

    serverSocket: socket.socket = field(init=False, default=None)
    selector: selectors.BaseSelector = field(init=False)


    def __post_init__(self):
        logging.basicConfig(filename="server.log", level=logging.DEBUG)
        self._setupDataStructures()
        self._setupSignalHandlers()
        self.eventLoopFlag: bool = True


    def _setupDataStructures(self):
        ## TODO: Add argument for StreamInterception for ProxyConnections construction
        self.proxyHandlerDescriptor = proxyHandlerDescriptor(self.PROXY_HOST, self.PROXY_PORT, self.streamInterceptor)
        self.proxyConnections = ProxyConnections(self.PROXY_HOST, self.PROXY_PORT, self.streamInterceptor)


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
    HOST, PORT = "0.0.0.0", 8080
    PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
    streamInterceptor = StreamInterceptor
    TPS = TCPProxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor)
    TPS.run()


if __name__ == "__main__":
    main()
