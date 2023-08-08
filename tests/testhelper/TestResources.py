import os
import sys
import psutil
import socket
import signal
import selectors
import threading
import collections
from typing import Tuple, List, Dict, Generator, Callable

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
sys.path.insert(0, "testhelper")

from tcp_proxyserver import ProxyTunnel, ProxyConnections, TCPProxyServer
from _proxyDS import Buffer, CommsDirection, StreamInterceptor, PrivateStreamInterceptorRegister, SharedStreamInterceptorRegister
from _exceptions import *
from tests.testhelper.ThreadedEchoServer import EchoServer



## TODO: At some point in the future we want to 
## perform UDP and TCP tests

## TODO: Add resources for UDP and TCP connections
## Consider testing for UDP and TCP on proxyTunnel
class PTTestResources:

    @staticmethod
    def createMockStreamInterceptor():
        clientToServerDeque = collections.deque([])
        serverToClientDeque = collections.deque([])
        
        class mockStreamInterceptor(StreamInterceptor):

            class ClientToServerHook(StreamInterceptor.Hook):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)

                def __call__(self, message: bytes) -> None:
                    nonlocal clientToServerDeque
                    clientToServerDeque.append(message)
                    return message, True

            class ServerToClientHook(StreamInterceptor.Hook):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)

                def __call__(self, message: bytes) -> None:
                    nonlocal serverToClientDeque
                    serverToClientDeque.append(message)
                    return message, True

        return mockStreamInterceptor, (clientToServerDeque, serverToClientDeque)

    @staticmethod
    def createClientSocket() -> socket.socket:
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.setblocking(True)
        return clientSocket

    @staticmethod
    def createServerSocket() -> socket.socket:
        ## TODO: We need a method of setting up ephemeral server sockets
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ## NOTE: socket.bind(("",0)) passes response of PORT selection on localhost
        ## for binding to the host operating system
        serverSocket.setblocking(True)
        serverSocket.bind(("", 0))
        serverSocket.listen()
        return serverSocket

    @staticmethod
    def acceptConnection(serverSocket: socket.socket) -> socket.socket:
        clientToProxySocket, (hostname, port) = serverSocket.accept()
        return clientToProxySocket

    @staticmethod
    def closeSocket(s: socket) -> None:
        s.close()


    @staticmethod
    def connect(client: socket.socket, server: socket.socket) -> socket.socket:
        serverHost, serverPort = server.getsockname()
        client.connect((serverHost, serverPort))
        ephemeralSocket, _ = server.accept()
        return ephemeralSocket

    @staticmethod
    def _setupPT() -> Tuple[ProxyTunnel, List[socket.socket]]:
        ## Setup Client <--> Proxy connection
        proxyServerSocket = PTTestResources.createServerSocket()
        clientSocket = PTTestResources.createClientSocket()
        ephemeralProxyServerSocket = PTTestResources.connect(clientSocket, proxyServerSocket)

        ## Setup Proxy <--> Server connection
        serverSocket = PTTestResources.createServerSocket()
        proxyClientSocket = PTTestResources.createClientSocket()
        ephemeralServerSocket = PTTestResources.connect(proxyClientSocket, serverSocket)

        ## Rename the sockets
        clientToProxySocket = ephemeralProxyServerSocket
        proxyToServerSocket = proxyClientSocket

        ## Create ProxyTunnel
        streamInterceptor, interceptorDeques = PTTestResources.createMockStreamInterceptor()
        streamInterceptorRegistration = (
                                            (
                                                (PrivateStreamInterceptorRegister(streamInterceptor.ClientToServerHook, False, False),),
                                                (PrivateStreamInterceptorRegister(streamInterceptor.ServerToClientHook, False, False),),
                                            ),
                                    )

        pt = ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptorRegistration)
        hopList = [clientSocket, clientToProxySocket, proxyToServerSocket, ephemeralServerSocket]
        return pt, hopList, interceptorDeques

    @staticmethod
    def _closePT(socketList: List[socket.socket]) -> None:
        for sock in socketList:
            sock.close()



class TPSTestResources:
    @classmethod
    def freePort(cls, PORT: int) -> None:
        for proc in psutil.process_iter():
            for conns in proc.connections(kind='inet'):
                if conns.laddr.port == PORT:
                    proc.send_signal(signal.SIGTERM) # or SIGKILL

    @classmethod
    def setupEchoServer(cls, HOST: str, PORT: int) -> "EchoServer":
        return EchoServer(HOST, PORT)


    @classmethod
    def setupConnection(cls, proxyServer: TCPProxyServer) -> socket.socket:
        ## print("setting up connection")
        ## setup client <--> proxy connection
        clientSocket = socket.socket()
        clientSocket.setblocking(True)
        clientSocket.connect(proxyServer.serverSocket.getsockname())
        ## The proxy <--> server connection is handled by `proxyServer`
        return clientSocket

    @classmethod
    def runProxyServerInThread(cls, proxyServer: TCPProxyServer) -> threading.Thread:
        thread = threading.Thread(target=proxyServer.run)
        thread.start()
        return thread

    @classmethod
    def assertConstantAttributes(cls, server: TCPProxyServer,
        HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor) -> None:
        ## NOTE: There some ambiguity about which host refers to the
        ## proxy interceptor and which one refers to the target service
        ## At the moment
        ## -> HOST == proxyInterceptor server
        ## -> PROXY_HOST == target service server
        assert server.HOST == HOST
        assert server.PORT == PORT
        assert server.PROXY_HOST == PROXY_HOST
        assert server.PROXY_PORT == PROXY_PORT
        assert isinstance(server.selector, selectors.DefaultSelector)

        ## Depends if we want to be strict
        # assert isinstance(server.streamInterceptor, StreamInterceptor)
        # assert interceptor in server.streamInterceptor.__mro__[1:]

        ## What should happen is that the TCPProxyServer creates its own selector
        ## This should be pased on to encompassed data structures
        assert isinstance(server.proxyConnections, ProxyConnections)
        assert server.proxyConnections.PROXY_HOST == server.PROXY_HOST
        assert server.proxyConnections.PROXY_PORT == server.PROXY_PORT
        assert server.proxyConnections.selector == server.selector

        ## We need to check signal handlers have been set
        ## NOTE: SIGNAL types are dependent on the host system
        ## --> We'll focus on linux
        ## BUG: This is a weak test that fails sometimes!!!
        assert signal.getsignal(signal.SIGINT) == server._sigHandler

    @classmethod
    def _retrieveTunnelSocksFromSelector(cls, proxyServer: TCPProxyServer) -> Dict[Tuple, socket.socket]:
        registeredConnections = {}
        for _, key in proxyServer.selector.get_map().items():
            sock = key.fileobj
            if proxyServer.serverSocket != sock:
                registeredConnections[(sock.getsockname(), sock.getpeername())] = sock
        return registeredConnections


    @classmethod
    def assertSelectorState(cls, proxyServer: TCPProxyServer, connections: List[socket.socket]) -> None:
        ## it should be added to the selector (correct  key, no duplicates)
        ## There should be two fd's socket server, and new connection and proxy
        ## We check that the selector has the correct number of fd being polled
        assert len(proxyServer.selector.get_map()) == 1 + len(connections)*2 ## serverSock + 2 endpoints for each connection

        ## checking server socket is logged
        serverSocketKey = proxyServer.selector.get_key(proxyServer.serverSocket)
        assert serverSocketKey.data == "ServerSocket"
        assert serverSocketKey.events == selectors.EVENT_READ

        ## We create a set based on the peernames of the descriptors (then we can look them up)
        ## NOTE: Be careful - There may be some weirdness (e.g. "" is equal to "0.0.0.0")
        registeredSockNames = cls._retrieveTunnelSocksFromSelector(proxyServer)

        ## for each user connection, there should be two sockets managed by server 
        ## (this ensure equal number of types of sockets (clientTOProxy, and ProxyToServer))
        assert len(proxyServer.selector.get_map()) == 1 + len(connections)*2 ## serverSock + 2 endpoints for each connection
        assert len(registeredSockNames) == len(connections) * 2

        ## Here we perform assertions on the client <--> proxy connections
        for conn in connections:
            connKey = (conn.getpeername(), conn.getsockname())
            assert connKey in registeredSockNames
            registeredSockNames.pop(connKey) ## remove from dict

        ## Here we perform assertions on the proxy <--> server connections
        for sock in registeredSockNames.values():
            ## The peer should be the destination server for all proxy <--> server connections
            peername = sock.getpeername()
            assert peername[0] == proxyServer.PROXY_HOST
            assert peername[1] == proxyServer.PROXY_PORT


    @classmethod
    def assertProxyConnectionsState(cls, proxyServer: TCPProxyServer, connections: List[socket.socket]) -> None:
        ## proxyServer.proxyConnections contains two socket keys for each tunnel (hence multiply by 2)
        assert len(proxyServer.proxyConnections._sock) == len(connections) * 2

        ## NOTE: We will NOT take a look at the internal state of the proxyTunnels
        tunnels = {}
        for sock, tunnel in proxyServer.proxyConnections._sock.items():
            if tunnels.get(tunnel) is None:
                tunnels[tunnel] = set()
            tunnels[tunnel].add(sock)

        ## validate that each tunnel has two elements and that they are linked to the tunnel, 
        ## they are not closed, and have correct peernames / socknames
        for tunnel, socks in tunnels.items():
            assert len(socks) == 2
            assert tunnel.clientToProxySocket in socks
            assert tunnel.clientToProxySocket.fileno() != -1
            ## NOTE: Eventhough serverSock.accept() creates an ephemeral socket (it seems the new socket retains the same sockname as serverSock)
            assert tunnel.clientToProxySocket.getsockname() == proxyServer.serverSocket.getsockname()

            assert tunnel.proxyToServerSocket in socks
            assert tunnel.proxyToServerSocket.fileno() != -1 # if socket is closed, socket.fileno() == -1
            peerAddress =  tunnel.proxyToServerSocket.getpeername()
            assert peerAddress[0] == proxyServer.PROXY_HOST
            assert peerAddress[1] == proxyServer.PROXY_PORT
            

    ##
    @classmethod
    def assertUserConnectionData(cls, MESSAGE_DELIMITERS: List[bytes], connections: List[socket.socket], connectionData: List[bytes]) -> None:
        delimiter = MESSAGE_DELIMITERS[0]
        ## We want to check that the expected data has been received
        for conn, sentData in zip(connections, connectionData):

            index = sentData.rfind(delimiter)
            if index == -1:
                expectedData = b""
            else:
                expectedData = sentData[:index + len(delimiter)]

            socketData = bytearray()
            while True:
                ## NOTE: Avoids race conditions and ensures socket has the entire 
                ## socket data before performing the assertion
                socketData = conn.recv(len(expectedData), socket.MSG_PEEK)
                if len(socketData) == len(expectedData):
                    break
            assert socketData == expectedData
    
    @classmethod
    def assertProxyTunnelsState(cls, proxyServer: TCPProxyServer, connections: List[socket.socket], connectionData: List[bytes]) -> None:
        ## creates a map {peername: tunnelObject}
        peernameToTunnel = {}
        tunnels = list(proxyServer.proxyConnections._sock.values())
        for tunnel in tunnels:
            peernameToTunnel[tunnel.clientToProxySocket.getpeername()] = tunnel

        ## now we can assert the buffer state
        for index, connectionSock in enumerate(connections):
            tunnel = peernameToTunnel[connectionSock.getsockname()]
            
            sendData = connectionData[index] ## sendData = recvData since it is an echo server
            sendBuffer = tunnel.clientToServerBuffer
            cls._assertProxyBufferState(sendData, sendBuffer, index)

            recvData = sendData
            recvBuffer = tunnel.serverToClientBuffer
            cls._assertProxyBufferState(recvData, recvBuffer, index)

    @classmethod
    def _assertProxyBufferState(cls, testData: bytes, testBuffer: Buffer, index: int) -> None:
        ## BUG: There's a bug that's happening on the message boundary (i.e. delimiter)
        ## It seems that the delimited + undelimited message are stuck into a single item in the queue (odd)


        ## The data object is "full", so we will use the delimiters to split
        ## -- It's possible to define multiple delimiters
        ## Our check will compare with a single run of the buffer on flat data
        ## --> i.e. instead of multiple chunks, a single chunk is sent
        flatBuffer = Buffer(testBuffer.MESSAGE_DELIMITERS, CommsDirection.CLIENT_TO_SERVER)
        flatBuffer.write(testData)

        ## And then we will manually compare state between both buffers
        ## NOTE: This assumes a single run of the flat buffer is correct
        ## -- There already exist tests for the buffer
        # print(f"Index {index}:")
        # print(flatBuffer)
        # print(testBuffer, end="\n\n")

        assert flatBuffer._messages == testBuffer._messages ## The remaining requests should be the same
        # assert flatBuffer._data == testBuffer._data ## The data is likely not the same (since the flatBuffer is never popped from)
        assert flatBuffer._MAX_BUFFER_SIZE == testBuffer._MAX_BUFFER_SIZE
        assert flatBuffer.MAX_DELIMETER_LENGTH == testBuffer.MAX_DELIMETER_LENGTH
        assert flatBuffer.MESSAGE_DELIMITER_REGEX == testBuffer.MESSAGE_DELIMITER_REGEX

