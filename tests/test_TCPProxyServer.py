import functools
import time
import os
import selectors
import signal
import socket
import sys
import threading
from typing import Tuple, List, Dict, Callable, Generator
import pytest
import psutil
import errno
import random
import string
import queue
import datetime
import math

from testhelper.TCPProxyServer import TPSTestResources
from testhelper.DataTransferSimulator import DataTransferSimulator
from _testResources import PTTestResources


sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyConnections, TCPProxyServer
from _exceptions import *
from _proxyDS import StreamInterceptor, Buffer




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
            self.thread = threading.Thread(target=proxyServer.run, daemon=False)

        def run(self):
            host, port = self.proxyServer.serverSocket.getsockname()
            print(f"Running Proxy Server @ {host}:{port}")
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



class Test_ProxyServer_connectionDataHandling:
    ## TODO: Remove code
    def _assertConnectionHandling(self, echoServer, proxyServerThreadWrapper, proxyServerArgs, connectionsToCreate, dataTransferArgs):
        ## Setting up
        proxyServer = proxyServerThreadWrapper.proxyServer

        ## Setup a single client connection and wait until the connections have been accepted and handled
        print("setting up user connections, and awaiting on proxy and server setup")
        connections = [TPSTestResources.setupConnection(proxyServer) for _ in range(connectionsToCreate)]
        echoServer.awaitConnectionCount(connectionsToCreate)
        proxyServerThreadWrapper.awaitConnectionCount(connectionsToCreate)

        ## We then send unique data over
        # connectionData = self._sendRandomDataToProxy(connections)
        connectionData = DataTransferSimulator.sendMultiConnMultiMessage(connections, **dataTransferArgs)

        ## we then wait until each user socket has data (which means that data has propagated through proxy server)
        DataTransferSimulator._awaitRoundaboutConnection(connections)

        ## Assertions
        try:
            ## we should check the following
            TPSTestResources.assertConstantAttributes(proxyServer, *proxyServerArgs)
            TPSTestResources.assertSelectorState(proxyServer, connections)
            TPSTestResources.assertProxyConnectionsState(proxyServer, connections)
            TPSTestResources.assertUserConnectionData(connections, connectionData)
            TPSTestResources.assertProxyTunnelsState(proxyServer, connections, connectionData)
        except Exception as e:
            print(f"Exception raised: {e}")
            raise e
        finally:
            for sock in connections: sock.close()

    ## NOTE: Basic connection handling
    def test_singleConnection_dataHandling(self, createEchoProxyEnvironment) -> None:
        echoServer, proxyServerThreadWrapper, proxyServerArgs = createEchoProxyEnvironment
        connectionsToCreate = 1
        self._assertConnectionHandling(echoServer, proxyServerThreadWrapper, proxyServerArgs, connectionsToCreate)
 
    def test_multipleConnection_dataHandling(self, createEchoProxyEnvironment) -> None:
        ## BUG: This code works for all parameters, except for messageCount
        ## --> For some reason the server hangs when a message count > 1 is sent
        echoServer, proxyServerThreadWrapper, proxyServerArgs = createEchoProxyEnvironment
        connectionsToCreate = 1
        testTimeRange = 10 ## this is the range in seconds, that the chunks can be scheduled for
        dataSizeRange = (150, 200)  ## dataSizeRange must be >= 1
        messageCountRange = (1,4) ## messageCount must be >= 0 (isEndDelimited=False), or >= 1 (isEndDelimited=True)
        isEndDelimited = False
        chunkCountRange = (1, 5) ## chunk count must be >= 1

        def completeConnSender():
            nonlocal proxyServerThreadWrapper, testTimeRange, dataSizeRange, isEndDelimited
            dataSize = random.randint(*dataSizeRange)
            messageCount = random.randint(*messageCountRange)
            chunkCount = random.randint(*chunkCountRange)
            delimiters = DataTransferSimulator._delimitersSelector(proxyServerThreadWrapper.proxyServer.streamInterceptor.REQUEST_DELIMITERS, messageCount)
            datetimes = DataTransferSimulator._datetimesSelector(testTimeRange, chunkCount)
            return (dataSize, messageCount, chunkCount, delimiters, datetimes, isEndDelimited)

        dataTransferArgs = {"completeConnSender": completeConnSender}

        self._assertConnectionHandling(echoServer, proxyServerThreadWrapper, proxyServerArgs, connectionsToCreate, dataTransferArgs)
 


    ## NOTE: We want to test dropping chunks of data
    def test_singleConnection_chunked_dataHandling(self, createEchoProxyEnvironment) -> None:
        ...
    
    def test_multipleConnection_chunked_dataHandling(self, createEchoProxyEnvironment) -> None:
        ...

    ## NOTE: We want to test dropping several messages
    def test_singleConnection_multipleMessages(self, createEchoProxyEnvironment) -> None:
        ...

    def test_multipleConnection_multipleMessages(self, createEchoProxyEnvironment) -> None:
        ...

    ## NOTE: We also want to test chunked multiple messages
    def test_singleConnection_multipleMessages_chunked(self, createEchoProxyEnvironment) -> None:
        ...

    def test_multipleConnection_multipleMessages_chunked(self, createEchoProxyEnvironment) -> None: 
        ...



class Test_ProxyServer_connectionTermination:
    ...