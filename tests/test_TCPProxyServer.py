import functools
import time
import os
import selectors
import signal
import socket
import sys
import threading
from typing import Tuple, List
import pytest
import psutil

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyConnections, TCPProxyServer
from _exceptions import *
from _proxyDS import StreamInterceptor
from _testResources import PTTestResources

class TPSTestResources:
    @classmethod
    def freePort(cls, PORT: int) -> None:
        for proc in psutil.process_iter():
            for conns in proc.connections(kind='inet'):
                if conns.laddr.port == PORT:
                    proc.send_signal(signal.SIGTERM) # or SIGKILL

    @classmethod
    def setupEchoServer(cls, HOST: str, PORT: int):
        ## Free the port
        # cls.freePort(PORT)

        ## echo server defined (non performant but simple to set up)
        class EchoServer:
            def __init__(self, HOST: str, PORT: int) -> None:
                self._threads = []
                self._exitFlag = False
                self._mainThread = threading.Thread(target=self._run, args=(HOST, PORT,))
                self._selector = selectors.DefaultSelector()
                self._counterEvent = threading.Event()
                self._counterLock = threading.Lock()
                self._counterTarget = 0
                self._counterCurrent = 0

            def _run(self, HOST, PORT) -> None:
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
                    # print(f"Running Echo Server @ {HOST}:{PORT}")

                    try:
                        while self._exitFlag is False:
                            try:
                                conn, addr = serverSock.accept()
                            except BlockingIOError:
                                continue

                            self._updateCounterEvent()
                            connThread = threading.Thread(target=self._serviceConnection, args=(conn,))
                            self._threads.append(connThread)
                            connThread.start()
                    except Exception as e:
                        print(f"EchoServer exception: {e}")

            def _serviceConnection(self, conn: socket.socket):
                with conn:
                    conn.setblocking(False)
                    while self._exitFlag is False:
                        try:
                            data = conn.recv(1024)
                        except socket.error:
                            continue

                        if not data:
                            break
                        conn.sendall(data)
                ## print("EchoServer connection closed")

            def run(self) -> None:
                return self._mainThread.start()

            def close(self) -> None:
                ## set exitFlag to exit eventLoop in self._run
                self._exitFlag = True
                ## close mainThread
                self._mainThread.join()
                ## close connection threads
                for thread in self._threads:
                    # print("EchoServer - Closing child thread")
                    ## socket closing are handled by context managers
                    thread.join()

            def _updateCounterEvent(self):
                with self._counterLock:
                    self._counterCurrent += 1
                    if self._counterCurrent >= self._counterTarget:
                        self._counterEvent.set()

            def awaitConnectionCount(self, count: int):
                with self._counterLock:
                    self._counterTarget = count
                    if self._counterCurrent >= self._counterTarget:
                        self._counterEvent.set()
                    else:
                        self._counterEvent.clear()
            
                self._counterEvent.wait()
                # print("returned from await")
                return None

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
    def runProxyServerInThread(cls, proxyServer: TCPProxyServer):
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
    def _retrieveTunnelSocksFromSelector(cls, proxyServer):
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
    def assertProxyTunnelsState(cls, proxyServer: TCPProxyServer, connections: List[socket.socket], connectionData: List[str]):
        ## NOTE: Here we can evaluate the state of the bytes stored in the proxyTunnels
        ...



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
            while len(self.proxyServer.proxyConnections) != count * 2: ## for each user connection, the server manages 2 connections
                pass
            return None


    proxyServerWrapper = threadWrapper(proxyServer)
    yield HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor, proxyServerWrapper

    print("TCPProxyServer closing")
    proxyServer.close(blocking=True)
    proxyServerWrapper.thread.join()
    print("TCPProxyServer closed")


@pytest.fixture()
def createBackendEchoServer(createTCPProxyServer):
    HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor, proxyServer = createTCPProxyServer
    echoServer = TPSTestResources.setupEchoServer(PROXY_HOST, PROXY_PORT)
    yield echoServer

    print("EchoServer closing")
    echoServer.close()
    print("EchoServer closed")



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

class Test_ProxyServer_connectionTeardown:
    pass



class Test_ProxyServer_connectionHandling:
    ...


class Test_ProxyServer_shutdown:
    pass
