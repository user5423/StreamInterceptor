import functools
import time
import os
import selectors
import signal
import socket
import sys
import threading
from typing import Tuple, List, Dict, Callable
import pytest
import psutil
import errno
import random
import string


sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyConnections, TCPProxyServer
from _exceptions import *
from _proxyDS import StreamInterceptor, Buffer
from _testResources import PTTestResources

class TPSTestResources:
    @classmethod
    def freePort(cls, PORT: int) -> None:
        for proc in psutil.process_iter():
            for conns in proc.connections(kind='inet'):
                if conns.laddr.port == PORT:
                    proc.send_signal(signal.SIGTERM) # or SIGKILL

    @classmethod
    def setupEchoServer(cls, HOST: str, PORT: int) -> "EchoServer":
        ## Free the port
        # cls.freePort(PORT)

        ## echo server defined (non performant but simple to set up)
        class EchoServer:
            def __init__(self, HOST: str, PORT: int) -> None:
                self._threads = []
                self._threadExit = []
                self._threadLock = threading.Lock()

                self._exitFlag = False
                self._mainThread = threading.Thread(target=self._run, args=(HOST, PORT,))
                self._selector = selectors.DefaultSelector()
                self._counterEvent = threading.Event()
                self._counterLock = threading.Lock()
                self._counterTarget = 0
                self._counterCurrent = 0

            def _run(self, HOST: str, PORT: int) -> None:
                # print(f"Starting Echo Server @ {HOST}:{PORT}")
                with socket.socket() as serverSock:
                    try:
                        serverSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        serverSock.setblocking(False)
                        serverSock.bind((HOST, PORT))
                        serverSock.listen()
                    except Exception as e:
                        print(f"EchoServer server Exception: {e}")
                        raise e
                    print(f"Running Echo Server @ {HOST}:{PORT}")

                    try:
                        while self._exitFlag is False:
                            try:
                                conn, addr = serverSock.accept()
                            except BlockingIOError:
                                continue

                            self._instantiateNewThread(conn)
                            self._updateCounterEvent(1)
                    except Exception as e:
                        print(f"EchoServer exception: {e}")
                        raise e

            def _serviceConnection(self, conn: socket.socket, index: int) -> None:
                with conn:
                    try:
                        conn.setblocking(False)
                        while self._exitFlag is False and self._threadExit[index] is False:
                            try:
                                data = conn.recv(1024)
                            except OSError:
                                continue
                            if not data:
                                break
                            conn.sendall(data)
                    except Exception as e:
                        print(f"EchoServer - Exception raised when servicing echo connection: {conn} - {e}")
                        raise e
                    finally:
                        self._updateCounterEvent(-1)

            def run(self) -> None:
                return self._mainThread.start()

            def close(self) -> None:
                ## set exitFlag to exit eventLoop in self._run
                self._exitFlag = True
                ## close mainThread
                self._mainThread.join()
                ## close connection threads
                with self._threadLock:
                    for thread in self._threads:
                        # print("EchoServer - Closing child thread")
                        ## socket closing are handled by context managers
                        thread.join()

            def _updateCounterEvent(self, val: int) -> None:
                with self._counterLock:
                    self._counterCurrent += val
                    # print(f"current counter: {self._counterCurrent}")
                    if self._counterCurrent == self._counterTarget:
                        self._counterEvent.set()

            def _instantiateNewThread(self, conn: socket.socket) -> None:
                with self._threadLock:
                    with self._counterLock:
                        connThread = threading.Thread(target=self._serviceConnection, args=(conn, self._counterCurrent))
                    self._threads.append(connThread)
                    self._threadExit.append(False)
                
                connThread.start()

            def awaitConnectionCount(self, count: int) -> None:
                with self._counterLock:
                    self._counterTarget = count
                    if self._counterCurrent == self._counterTarget:
                        self._counterEvent.set()
                
                self._counterEvent.wait()
                self._counterEvent.clear()

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
        assert server.streamInterceptor == interceptor
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
            

    @classmethod
    def assertUserConnectionData(cls, connections: List[socket.socket], connectionData: List[bytes], bufferSize: int = 1024) -> None:
        ## We want to check that the expected data has been received
        for conn, expectedData in zip(connections, connectionData):
            assert conn.recv(bufferSize, socket.MSG_PEEK) == expectedData
    
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
            cls._assertProxyBufferState(sendData, sendBuffer)

            recvData = sendData
            recvBuffer = tunnel.serverToClientBuffer
            cls._assertProxyBufferState(recvData, recvBuffer)

    @classmethod
    def _assertProxyBufferState(cls, testData: bytes, testBuffer: Buffer) -> None:
        ## The data object is "full", so we will use the delimiters to split
        ## -- It's possible to define multiple delimiters
        ## Our check will compare with a single run of the buffer on flat data
        ## --> i.e. instead of multiple chunks, a single chunk is sent
        flatBuffer = Buffer(testBuffer.REQUEST_DELIMITERS)
        flatBuffer._execRequestParsing(testData)

        ## And then we will manually compare state between both buffers
        ## NOTE: This assumes a single run of the flat buffer is correct
        ## -- There already exist tests for the buffer
        assert flatBuffer._requests == testBuffer._requests
        assert flatBuffer._data == testBuffer._data
        assert flatBuffer._MAX_BUFFER_SIZE == testBuffer._MAX_BUFFER_SIZE
        assert flatBuffer.MAX_DELIMETER_LENGTH == testBuffer.MAX_DELIMETER_LENGTH
        assert flatBuffer.REQUEST_DELIMETER_REGEX == testBuffer.REQUEST_DELIMETER_REGEX


@pytest.fixture()
def createTCPProxyServer():
    PROXY_HOST, PROXY_PORT = "127.0.0.1", 1337
    HOST, PORT = "127.0.0.1", 8080
    streamInterceptor = PTTestResources.createMockStreamInterceptor()

    ## first we need to kill any processes running on the (HOST, PORT)
    # TPSTestResources.freePort(PORT)

    ## we can then try to create the server (not execute it yet)
    server = TCPProxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor, addressReuse=True)
    yield HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor, server

    ## we then want to shut down the server (at least the server socket)
    server._close()


@pytest.fixture()
def createSingleThreadTCPProxyServer(createTCPProxyServer):
    HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor, proxyServer = createTCPProxyServer

    class threadWrapper:
        def __init__(self, proxyServer) -> None:
            self.proxyServer = proxyServer
            self.thread = threading.Thread(target=proxyServer.run, daemon=True)

        def run(self):
            return self.thread.start()

        def awaitConnectionCount(self, count: int) -> None:
            ## we'll use a spinlock to avoid modifying the class for the sake of testing
            while len(self.proxyServer.proxyConnections._sock) != count * 2: ## for each user connection, the server manages 2 connections
                pass
            return None

        def close(self, blocking: bool) -> None:
            return self.proxyServer.close(blocking=blocking)


    proxyServerWrapper = threadWrapper(proxyServer)
    yield HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor, proxyServerWrapper

    # print("TCPProxyServer closing")
    proxyServer.close(blocking=True)
    proxyServerWrapper.thread.join()
    # print("TCPProxyServer closed")


@pytest.fixture()
def createBackendEchoServer(createTCPProxyServer):
    HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor, proxyServer = createTCPProxyServer
    echoServer = TPSTestResources.setupEchoServer(PROXY_HOST, PROXY_PORT)
    yield echoServer

    # print("EchoServer closing")
    echoServer.close()
    # print("EchoServer closed")



## TODO: Add tests for input vaildation on TCPProxyServer
## initialization

## TODO: We want to move the validation from encompossed
## objects (to top level in TCPProxyServer)
class Test_ProxyServer_Init:
    def test_default_init(self):
        with pytest.raises(TypeError) as excInfo:
            TCPProxyServer()

        errorMsg = str(excInfo.value)
        assert "HOST" in errorMsg
        assert "PROXY_HOST" in errorMsg
        assert "PORT" in errorMsg
        assert "PROXY_PORT" in errorMsg
        assert "streamInterceptor" in errorMsg


    def test_init_singleRealServerSocket(self, createTCPProxyServer) -> None:
        HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor, server = createTCPProxyServer

        ## we need to create the socket
            ## should be listening at (server.HOST, server.PORT)
        assert isinstance(server.serverSocket, socket.socket)
        assert server.serverSocket.getsockname() == (HOST, PORT)
        assert server.serverSocket.getblocking() is False

        ## we need to check if it has been registered
            ## selectors.EVENT_READ | selectors.EVENT_WRITE
            ## data = "serverSocket"
        assert isinstance(server.selector, selectors.DefaultSelector)
        assert len(server.selector.get_map()) == 1
        selectorKey = server.selector.get_key(server.serverSocket)
        assert selectorKey.data == "ServerSocket"
        assert selectorKey.events == selectors.EVENT_READ

        ## check that the selector has been created correctly
        assert server.selector == server.proxyConnections.selector
        TPSTestResources.assertConstantAttributes(server, HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor)


    def test_init_alreadyRegistered(self, createTCPProxyServer) -> None:
        HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor, server1 = createTCPProxyServer

        with pytest.raises(OSError) as excInfo:
            TCPProxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor, addressReuse=True)

        assert "Address already in use" in str(excInfo.value)

        ## server 1 serverSocket should be bound and registered
        assert server1.serverSocket.getblocking() is False
        assert server1.serverSocket.getsockname() == (HOST, PORT)
        assert len(server1.selector.get_map()) == 1
        selectorKey = server1.selector.get_key(server1.serverSocket)
        assert selectorKey.data == "ServerSocket"
        assert selectorKey.events == selectors.EVENT_READ

        ## server2 should never be created
        TPSTestResources.assertConstantAttributes(server1, HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor)




class Test_ProxyServer_connectionSetup:
    def _assertConnectionSetup(self, echoServer , proxyServerThreadWrapper, proxyServerArgs: List[object], connectionCount: int) -> None:
        ## Setting up
        proxyServer = proxyServerThreadWrapper.proxyServer
        HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor = proxyServerArgs

        ## Run servers
        echoServer.run()
        proxyServerThreadWrapper.run()

        ## Setup a single client connection
        connectionSize = connectionCount
        connections = [TPSTestResources.setupConnection(proxyServer) for i in range(connectionSize)]
        
        ## wait until the connections have been setup
        echoServer.awaitConnectionCount(connectionSize)
        proxyServerThreadWrapper.awaitConnectionCount(connectionSize)

        ## Assertions
        try:
            ## we should check the following
            TPSTestResources.assertConstantAttributes(proxyServer, HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor)
            TPSTestResources.assertSelectorState(proxyServer, connections)
            TPSTestResources.assertProxyConnectionsState(proxyServer, connections)
        except Exception as e:
            print(f"Exception raised: {e}")
            raise e
        finally:
            for sock in connections:
                sock.close()
                

    def test_singleConnection(self, createSingleThreadTCPProxyServer, createBackendEchoServer) -> None:
        proxyServerThreadWrapper = createSingleThreadTCPProxyServer[-1]
        proxyServerArgs = createSingleThreadTCPProxyServer[:-1]
        echoServer = createBackendEchoServer

        ## Perform assertions
        connectionCount = 1
        self._assertConnectionSetup(echoServer, proxyServerThreadWrapper, proxyServerArgs, connectionCount)


    def test_multipleConnections(self, createSingleThreadTCPProxyServer, createBackendEchoServer) -> None:
        proxyServerThreadWrapper = createSingleThreadTCPProxyServer[-1]
        proxyServerArgs = createSingleThreadTCPProxyServer[:-1]
        echoServer = createBackendEchoServer

        ## Perform assertions
        connectionCount = 100
        self._assertConnectionSetup(echoServer, proxyServerThreadWrapper, proxyServerArgs, connectionCount)




@pytest.fixture()
def createEchoProxyEnvironment(createSingleThreadTCPProxyServer, createBackendEchoServer):
        ## Setting up
        proxyServerThreadWrapper = createSingleThreadTCPProxyServer[-1]
        proxyServerArgs = createSingleThreadTCPProxyServer[:-1]
        echoServer = createBackendEchoServer

        ## Run servers
        echoServer.run()
        proxyServerThreadWrapper.run()

        yield echoServer, proxyServerThreadWrapper, proxyServerArgs,


class Test_ProxyServer_Termination:
    def _isSockClosed(self, sock: socket.socket) -> bool:
        ## if the fd has been released (then sock closed)
        if sock.fileno() == -1: return True

        ## otherwise, we can recv to check if FIN was sent
        sock.setblocking(False)
        try:
            data = sock.recv(1024)
            ## if the data is empty b"", then we the sock is closed (return True)
            return len(data) == 0
        except socket.error as e:
            error = e.args[0]
            ## if error is one of these we return False (the socket is not closed)
            return not error in (errno.EAGAIN, errno.EWOULDBLOCK)

    def _removeDisconnectedSockets(self, connections: List[socket.socket]) -> List[socket.socket]:
        refreshedConnections = []
        for conn in connections:
            if self._isSockClosed(conn) is False:
                refreshedConnections.append(conn)
        return refreshedConnections

    def _assertConnectionTeardown(self, echoServer, proxyServerThreadWrapper, proxyServerArgs: List[object],
                                 connectionsToCreate: int, connectionsToClose: int, connectionCloseMethod: Callable[..., None]):
        ## Setting up
        proxyServer = proxyServerThreadWrapper.proxyServer
        HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor = proxyServerArgs

        ## Setup a single client connection and wait until the connections have been accepted and handled
        print("setting up user connections, and awaiting on proxy and server setup")
        connections = [TPSTestResources.setupConnection(proxyServer) for i in range(connectionsToCreate)]
        echoServer.awaitConnectionCount(connectionsToCreate)
        proxyServerThreadWrapper.awaitConnectionCount(connectionsToCreate)

        ## we now kill connections - this depends on how the test case would like
        print("closing connections using custom handler")
        connectionCloseMethod(proxyServerThreadWrapper, echoServer, connections, connectionsToClose)

        ## and wait until these have been closed
        print("awaiting dropped connection cleanup")
        remainingConnections = connectionsToCreate - connectionsToClose
        echoServer.awaitConnectionCount(remainingConnections)
        proxyServerThreadWrapper.awaitConnectionCount(remainingConnections)

        ## refresh connections (we just killed a few connections so let's get an array with only active ones)
        print("refreshing dropped user connections")
        connections = self._removeDisconnectedSockets(connections)
        
        ## Assertions
        try:
            ## we should check the following
            TPSTestResources.assertConstantAttributes(proxyServer, HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor)
            TPSTestResources.assertSelectorState(proxyServer, connections)
            TPSTestResources.assertProxyConnectionsState(proxyServer, connections)
        except Exception as e:
            print(f"Exception raised: {e}")
            raise e
        finally:
            for sock in connections: sock.close()

    ## Methods to close connectinos
    @staticmethod
    def _userTerminatesConnections(proxyServerThreadWrapper, echoServer, connections: List[socket.socket], connectionsToKill: int):
        for i in range(connectionsToKill):
            connections[i].close()

    @staticmethod
    def _serverTerminatesConnections(proxyThreadWrapper, echoServer, connections: List[socket.socket], connectionsToKill: int):
        with echoServer._threadLock:
            for i in range(connectionsToKill):
                echoServer._threadExit[i] = True

    @staticmethod
    def _serverShutdown(proxyThreadWrapper, echoServer, connections: List[socket.socket], connectionsToKill: int):
        echoServer.close()

    @staticmethod
    def _proxyShutdown(proxyThreadWrapper, echoServer, connections: List[socket.socket], connectionsToKill: int):
        proxyThreadWrapper.proxyServer.close()


    def test_singleConnection_userDisconnect(self, createEchoProxyEnvironment) -> None:
        echoServer, proxyServerThreadWrapper, proxyServerArgs = createEchoProxyEnvironment
        connectionsToCreate = 1
        connectionsToClose = connectionsToCreate
        self._assertConnectionTeardown(echoServer, proxyServerThreadWrapper, proxyServerArgs,
                 connectionsToCreate, connectionsToClose, self._userTerminatesConnections)

    def test_multipleConnections_userDisconnect(self, createEchoProxyEnvironment) -> None:
        echoServer, proxyServerThreadWrapper, proxyServerArgs = createEchoProxyEnvironment
        connectionsToCreate = 50
        connectionsToClose = 30
        self._assertConnectionTeardown(echoServer, proxyServerThreadWrapper, proxyServerArgs,
                 connectionsToCreate, connectionsToClose, self._userTerminatesConnections)

    def test_singleConnection_serverDisconnect(self, createEchoProxyEnvironment) -> None:
        echoServer, proxyServerThreadWrapper, proxyServerArgs = createEchoProxyEnvironment

        connectionsToCreate = 1
        connectionsToClose = connectionsToCreate
        self._assertConnectionTeardown(echoServer, proxyServerThreadWrapper, proxyServerArgs,
                 connectionsToCreate, connectionsToClose, self._serverTerminatesConnections)

    def test_multipleConnections_serverDisconnect(self, createEchoProxyEnvironment) -> None:
        echoServer, proxyServerThreadWrapper, proxyServerArgs = createEchoProxyEnvironment
        connectionsToCreate = 50
        connectionsToClose = 30
        self._assertConnectionTeardown(echoServer, proxyServerThreadWrapper, proxyServerArgs,
                 connectionsToCreate, connectionsToClose, self._serverTerminatesConnections)

    def test_multipleConnections_serverTerminate(self, createEchoProxyEnvironment) -> None:
        echoServer, proxyServerThreadWrapper, proxyServerArgs = createEchoProxyEnvironment
        connectionsToCreate = 50
        connectionsToClose = connectionsToCreate
        self._assertConnectionTeardown(echoServer, proxyServerThreadWrapper, proxyServerArgs,
                 connectionsToCreate, connectionsToClose, self._serverShutdown)

    def test_multipleConnections_proxyTerminate(self, createEchoProxyEnvironment) -> None:
        echoServer, proxyServerThreadWrapper, proxyServerArgs = createEchoProxyEnvironment
        connectionsToCreate = 50
        connectionsToClose = connectionsToCreate
        self._assertConnectionTeardown(echoServer, proxyServerThreadWrapper, proxyServerArgs,
                 connectionsToCreate, connectionsToClose, self._proxyShutdown)
