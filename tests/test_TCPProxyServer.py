import functools
import time
import os
import selectors
import signal
import socket
import sys
import threading
from typing import Tuple
from weakref import proxy
from phonenumbers import expected_cost
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
                    ## print("EchoServer - Closing child thread")
                    ## socket closing are handled by context managers
                    thread.join()

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
    def _assertConstantAttributes(cls, server: TCPProxyServer,
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

    proxyServerWrapper = threadWrapper(proxyServer)
    yield HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor, proxyServerWrapper

    # print("TCPProxyServer closing")
    proxyServer.close()
    # print("TCPProxyServer exitFlag set")
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
        TPSTestResources._assertConstantAttributes(server, HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor)


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
        TPSTestResources._assertConstantAttributes(server1, HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor)






    ## two connections

    ## multiple connections
    pass


class Test_ProxyServer_connectionTeardown:
    pass



class Test_ProxyServer_connectionHandling:
    ...


class Test_ProxyServer_shutdown:
    pass
