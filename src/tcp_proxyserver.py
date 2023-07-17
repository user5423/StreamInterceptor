
from abc import ABCMeta
import os
import time
import threading
import ipaddress
import selectors
import socket
import signal
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Type

from _proxyDS import Buffer, proxyHandlerDescriptor, StreamInterceptor
from _exceptions import *
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
    streamInterceptorType: Type[StreamInterceptor]
    CHUNK_SIZE: int = field(default=1024, hash=None)

    def __post_init__(self):
        ## Initialize streamInterceptor
        self.streamInterceptor = self.streamInterceptorType()
        ## Setup Bidirectional Buffers
        self.serverToClientBuffer = Buffer(self.streamInterceptor.MESSAGE_DELIMITERS)
        self.clientToServerBuffer = Buffer(self.streamInterceptor.MESSAGE_DELIMITERS)
        ## Set hooks on Bidirectional Buffers
        self.clientToServerBuffer.setTransparentHook(self.streamInterceptor.ClientToServerHook)
        self.serverToClientBuffer.setTransparentHook(self.streamInterceptor.ServerToClientHook)


    ## TODO: Rename to 'transferFromSocketToBuffer(...)'
    def readFrom(self, source: socket.socket) -> Optional[int]:
        ## Check if the source socket is associated with the tunnel
        if not (self.clientToProxySocket == source or self.proxyToServerSocket == source):
            raise UnassociatedTunnelSocket(self, socket)

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

    ## TODO: Rename to 'transferFromBufferToSocket(...);
    def writeTo(self, destination: socket.socket) -> Optional[int]:
        ## Check if the source socket is associated with the tunnel
        if not (self.clientToProxySocket == destination or self.proxyToServerSocket == destination):
            raise UnassociatedTunnelSocket(self, socket)

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
            raise UnassociatedTunnelSocket(self, socket)


    def _selectBufferForRead(self, source: socket.socket) -> Buffer:
        ## For READ, we write to the source Buffer
        if self.clientToProxySocket == source:
            return self.clientToServerBuffer
        elif self.proxyToServerSocket == source:
            return self.serverToClientBuffer
        else:
            raise UnassociatedTunnelSocket(self, socket)



@dataclass
class ProxyConnections:
    PROXY_HOST: str
    PROXY_PORT: int
    streamInterceptorType: Type[StreamInterceptor]
    selector: selectors.BaseSelector

    _sock: Dict[socket.socket, ProxyTunnel] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._validateArgs()

    def _validateArgs(self) -> None:
        ## Validate host
        ## -- Raises an exception if not a valid ip_address
        addr = ipaddress.ip_address(self.PROXY_HOST)

        ## Validate port
        if not (isinstance(self.PROXY_PORT, int) and 0 < self.PROXY_PORT):
            raise InvalidProxyPortError(self.PROXY_PORT)

        ## Validate interceptor
        if (StreamInterceptor not in self.streamInterceptorType.__mro__):
            raise AbsentStreamInterceptorParentError(self.streamInterceptorType)
        elif (StreamInterceptor == self.streamInterceptorType.__mro__[0]):
            raise AbstractStreamInterceptorError(self.streamInterceptorType)

        ## TODO: We'll be moving to ABC Meta class for StreamInterceptor abstract classes
        ## --> Therefore the validation process and the corresponding pytest tests will likely change

    def __len__(self) -> int:
        return len(self._sock)

    def get(self, sock: socket.socket) -> ProxyTunnel:
        return self._sock.get(sock)

    ## TODO: We need to add methods for rewriting
    def createTunnel(self, clientToProxySocket: socket.socket, proxyToServerSocket: socket.socket, selectorData: str = "connection", blocking: bool = True) -> ProxyTunnel:
        ## Check if the sockets are registered with a pre-existing tunnel
        if self._sock.get(clientToProxySocket):
            raise AlreadyRegisteredSocketError("clientToProxySocket", clientToProxySocket, self)
        elif self._sock.get(proxyToServerSocket):
            raise AlreadyRegisteredSocketError("proxyToServerSocket", proxyToServerSocket, self)

        ## We set the proxy sockets to non-blocking
        clientToProxySocket.setblocking(blocking)
        proxyToServerSocket.setblocking(blocking)
        ## We then create a new proxyTunnel
        proxyTunnel = ProxyTunnel(clientToProxySocket, proxyToServerSocket, self.streamInterceptorType)
        self._sock[clientToProxySocket] = proxyTunnel
        self._sock[proxyToServerSocket] = proxyTunnel

        self.selector.register(clientToProxySocket, selectors.EVENT_READ | selectors.EVENT_WRITE, data=selectorData)
        self.selector.register(proxyToServerSocket, selectors.EVENT_READ | selectors.EVENT_WRITE, data=selectorData)
        
        return proxyTunnel


    def closeTunnel(self, proxyTunnel: ProxyTunnel) -> None:
        ## NOTE: This method can be called by either the client or the server
        proxyTunnel = self._sock.get(proxyTunnel.clientToProxySocket)
        if proxyTunnel is None:
            raise UnregisteredProxyTunnelError(self, proxyTunnel)
        
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
        try:
            s.connect((self.PROXY_HOST, self.PROXY_PORT))
        except socket.error as e:
            print(f"Failed to setup proxy to server connection @ {self.PROXY_HOST}:{self.PROXY_PORT}: {e}")
            raise e

        return s



## BUG: It seems that the eventLoop may not be handling requests when the selector is polled
## --> The events are retrieved, and then immediately polled again
## --> I ran this for a single TCP connectino setup (no data sent)
## ==> This could be common (e.g. bytes are being transfered during TCP setup)
## --> Need to doule check though!!!

## TODO: Add context manager
## TODO: Make into abst
@dataclass
class TCPProxyServer:
    HOST: str
    PORT: int
    PROXY_HOST: str
    PROXY_PORT: int
    streamInterceptorType: Type[StreamInterceptor]
    addressReuse: bool = field(default=False)

    serverSocket: socket.socket = field(init=False, repr=False)
    selector: selectors.BaseSelector = field(init=False, repr=False, default_factory=selectors.DefaultSelector)
    proxyConnections: ProxyConnections = field(init=False, repr=True)
    _exitFlag: bool = field(init=False, default=False)
    _terminated: threading.Event = field(init=False, default_factory=threading.Event)

    def __post_init__(self):
        try:
            ## NOTE: This removes root Handlers - if root handlers are not empty, logging won't write to our desired file
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)

            logging.basicConfig(filename="server.log", level=logging.DEBUG)

            self._setupDataStructures()
            self._setupSignalHandlers()
            self._logDebugMessage("Server", "Server-Setup", "Success")
        except Exception as e:
            self._logDebugMessage("Server", "Server-Setup", "Failure")
            raise e


    def _setupDataStructures(self):
        self.selector = selectors.DefaultSelector()
        self.proxyConnections = ProxyConnections(self.PROXY_HOST, self.PROXY_PORT, self.streamInterceptorType, self.selector)
        self._setupServerSocket()


    def _setupSignalHandlers(self):
        try:
            signal.signal(signal.SIGBREAK, self._sigHandler)
        except AttributeError: pass ## Avoid errors caused by OS differences
        try:
            signal.signal(signal.SIGINT, self._sigHandler)
        except AttributeError: pass ## Avoid errors caused by OS differences


    def run(self) -> None:
        return self._executeEventLoop()


    def _executeEventLoop(self) -> None:
        self._logDebugMessage("Server", "Server-Running", "Success")
        while self._exitFlag is False:
            ## TODO: Modify the timeout??
            events = self.selector.select(timeout=0.1)
            for selectorKey, bitmask in events:
                if selectorKey.data == "ServerSocket":
                    # print("TCPProxyServer - Accepting new connection")
                    self._acceptConnection()
                else:
                    # print(f"TCPProxyServer - Servicing connection: {selectorKey}")
                    self._serviceConnection(selectorKey, bitmask, self.proxyConnections)

        self._close()

    def _close(self):
        try:
            self.proxyConnections.closeAllTunnels()
            self.serverSocket.close()
            self._logDebugMessage("Server", "Server-Termination", "Success")
        except (KeyboardInterrupt, Exception) as e:
            self._logDebugMessage("Server", "Server-Termination" "Warning")
            if not isinstance(e, KeyboardInterrupt):
                raise e
        finally:
            self._terminated.set()


    def _setupServerSocket(self) -> bool:
        self.serverSocket = self._createServerSocket()
        self._registerServerSocket(self.serverSocket)
        print(f"Server listening on {self.HOST}:{self.PORT}\n\n")


    ##TODO: Provide exception handling for setting up the server sock
    def _createServerSocket(self, address: Optional[Tuple[str, int]] = None) -> socket.socket:
        if address is None:
            address = (self.HOST, self.PORT)

        try:
            serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.addressReuse:
                serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            serverSocket.bind(address)
            serverSocket.listen()
            serverSocket.setblocking(False)
        except socket.error as e:
            print(f"TCPProxy Server Socker Error: {e}")
            serverSocket.close()
            raise e

        return serverSocket


    def _registerServerSocket(self, serverSocket: socket.socket, selectorKey: str = "ServerSocket") -> None:
        self.selector.register(serverSocket, selectors.EVENT_READ, data=selectorKey)


    def _acceptConnection(self) -> None:
        clientToProxySocket, (hostname, port) = self.serverSocket.accept()
        try:
            proxyToServerSocket = self.proxyConnections.setupProxyToServerSocket()
        except socket.error as e:
            clientToProxySocket.close()
            ## socket hasn't been registered yet, so no need to unregister
            logging.info(f"{datetime.now()}\t{hostname}\t{port}\tRejected\tConnection-Rejected\tFailure")
            return None

        self.proxyConnections.createTunnel(clientToProxySocket, proxyToServerSocket)
        logging.info(f"{datetime.now()}\t{hostname}\t{port}\tUndefined\tConnection-Accepted\tSuccess")
        

    def _serviceConnection(self, selectorKey: selectors.SelectorKey, bitmask: int, proxyConns: Optional[ProxyConnections] = None) -> None:
        sock = selectorKey.fileobj

        ## NOTE: It's possible the the other socket of the tunnel closed the tunnel
        proxyTunnel = proxyConns.get(sock)
        if proxyTunnel is None:
            return None

        ## In order to transfer from one socket, to another, we need to create buffers between them
        if bitmask & selectors.EVENT_READ:
            ## Read data from socket into buffer
            out = proxyTunnel.readFrom(sock)
            ## If socket is closed, close tunnel
            if out is None:
                return proxyConns.closeTunnel(proxyTunnel)

        if bitmask & selectors.EVENT_WRITE:
            ## Writes data from buffer into socket (if any)
            out = proxyTunnel.writeTo(sock)
            ## If socket is closed, close tunnel
            if out is None:
                return proxyConns.closeTunnel(proxyTunnel)
            

    def _logDebugMessage(self, user: str = "Server", eventType: str = "Default", description: str = "Default",) -> None:
        logging.debug(f"{datetime.now()}\t{self.HOST}\t{self.PORT}\t{user}\t{eventType}\t{description}")
        

    def close(self, blocking: bool = True) -> None:
        self._exitFlag = True
        self._terminated.wait()

   ## Required parameters by signal handler
    def _sigHandler(self, signum, frame) -> None:
        self.close()




def main():
    HOST, PORT = "0.0.0.0", 8080
    PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
    streamInterceptorType = StreamInterceptor
    TPS = TCPProxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptorType)
    TPS.run()


if __name__ == "__main__":
    main()
