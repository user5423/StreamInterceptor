import functools
import os
import selectors
import signal
import socket
import sys
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


@pytest.fixture()
def createTCPProxyServer():
    PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
    HOST, PORT = "127.0.0.1", 8080
    streamInterceptor = PTTestResources.createMockStreamInterceptor()

    ## first we need to kill any processes running on the (HOST, PORT)
    TPSTestResources.freePort(PORT)

    ## we can then try to create the server (not execute it yet)
    server = TCPProxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor)

    yield HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor, server

    ## we then want to shut down the server (at least the server socket)
    server.serverSocket.close()
    server.proxyConnections.closeAllTunnels()
    return None


class Test_ProxyServer_Init:
    ### Helper method
    def _assertConstantAttributes(self, server: TCPProxyServer,
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


    def test_default_init(self):
        with pytest.raises(TypeError) as excInfo:
            TCPProxyServer()

        errorMsg = str(excInfo.value)
        assert "HOST" in errorMsg
        assert "PROXY_HOST" in errorMsg
        assert "PORT" in errorMsg
        assert "PROXY_PORT" in errorMsg
        assert "streamInterceptor" in errorMsg

    def test_attribute_init(self):
        HOST, PORT = "127.0.0.1", 8080
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
        interceptor = PTTestResources.createMockStreamInterceptor()
        server = TCPProxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor)

        self._assertConstantAttributes(server, HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor)

        ## Rename eventLoopFlag to _exitFlag
        assert server._exitFlag == False
        ## We need to check signal handlers have been set
        ## NOTE: SIGNAL types are dependent on the host system
        ## --> We'll focus on linux
        assert signal.getsignal(signal.SIGINT) == server.sig_handler


    ## TODO: Add tests for input vaildation on TCPProxyServer
    ## initialization 

    ## TODO: We want to move the validation from encompossed
    ## objects (to top level in TCPProxyServer)

class Test_ProxyServer_Setup:
    def test_setup_mockedServerSocket(self, createTCPProxyServer):
        HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor, server = createTCPProxyServer

        def mocked_setupServerSocket(self) -> bool:
            class serverSocket:
                def close(self, *args, **kwargs): ...
            self.serverSocket = serverSocket()
            return True

        server._setupServerSocket = functools.partial(mocked_setupServerSocket, server)
        
        ret = server._setup()
        assert ret is True
        assert TPSTestResources
        assert isinstance(server.selector, selectors.DefaultSelector)
        assert server.proxyConnections.selector == server.selector


    def test_setup_singleRealServerSocket(self, createTCPProxyServer) -> None:
        HOST, PORT, PROXY_HOST, PROXY_PORT, interceptor, server = createTCPProxyServer
        
        ret = server._setup()

        assert ret is True
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

    def test_setup_alreadyRegistered(self) -> None:
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
        HOST, PORT = "127.0.0.1", 8080
        streamInterceptor = PTTestResources.createMockStreamInterceptor()

        server1 = TCPProxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor)
        server2 = TCPProxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor)
        
        ret1 = server1._setupServerSocket()
        with pytest.raises(OSError) as excInfo:
            server2._setupServerSocket()

        assert "Address already in use" in str(excInfo.value)

        ## server 1 serverSocket should be bound and registered
        assert ret1 is True ## sucecssful setup
        assert server1.serverSocket.getblocking() is False
        assert server1.serverSocket.getsockname() == (HOST, PORT)
        assert len(server1.selector.get_map()) == 1
        selectorKey = server1.selector.get_key(server1.serverSocket)
        assert selectorKey.data == "ServerSocket"
        assert selectorKey.events == selectors.EVENT_READ

        ## server 2 serverSocket should NOT be bound or registered
        assert len(server2.selector.get_map()) == 0
        assert server2.serverSocket is None



class Test_ProxyServer_connectionHandling:
    pass


class Test_ProxyServer_connectionTeardown:
    pass


class Test_ProxyServer_shutdown:
    pass
