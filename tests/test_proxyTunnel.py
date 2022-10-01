import collections
import os
import sys
import functools
from typing import List, Tuple
from aiohttp import ClientTimeout
import pytest
import socket

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyTunnel
from _proxyDS import Buffer

## TODO: At some point in the future we want to 
## perform UDP and TCP tests

## TODO: Add resources for UDP and TCP connections
## Consider testing for UDP and TCP on proxyTunnel
class PTTestResources:

    @staticmethod
    def createMockStreamInterceptor():
        class mockStreamInterceptor:
            REQUEST_DELIMITERS = [b"\r\n"]
            def __init__(self):
                self.clientToServerDeque = collections.deque([])
                self.serverToClientDeque = collections.deque([])

            def clientToServerHook(self, request: bytearray) -> None:
                self.clientToServerDeque.append(request)

            def serverToClientHook(self, response: bytearray) -> None:
                self.serverToClientDeque.append(response)

        return mockStreamInterceptor

    @staticmethod
    def createClientSocket() -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(True)
        return s

    @staticmethod
    def createServerSocket() -> socket.socket:
        ## TODO: We need a method of setting up ephemeral server sockets
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ## NOTE: socket.bind(("",0)) passes response of PORT selection on localhost
        ## for binding to the host operating system
        serverSocket.bind(("", 0))
        serverSocket.listen()
        serverSocket.setblocking(False)
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
        print("hello")
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
        proxyToServerSocket = ephemeralServerSocket

        ## Create ProxyTunnel
        streamInterceptor = PTTestResources.createMockStreamInterceptor()
        pt = ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)
        hopList = [clientSocket, clientToProxySocket, proxyToServerSocket, serverSocket]
        return pt, hopList



class Test_ProxyTunnel_Init:
    def test_default_init(self):
        with pytest.raises(TypeError) as excInfo:
            ProxyTunnel()

        assert "clientToProxySocket" in str(excInfo.value)
        assert "proxyToServerSocket" in str(excInfo.value)
        assert "streamInterceptor" in str(excInfo.value)
    

    def test_init_duplicatedSockets(self):
        clientToProxySocket = PTTestResources.createClientSocket()
        proxyToServerSocket = clientToProxySocket
        streamInterceptor = PTTestResources.createMockStreamInterceptor()

        with pytest.raises(ValueError) as excInfo:
            ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)

        assert "duplicate sockets" in str(excInfo.value)


    def test_init_closedSocket_ClientToProxy(self):
        clientToProxySocket = PTTestResources.createClientSocket()
        proxyToServerSocket = PTTestResources.createClientSocket()
        streamInterceptor = PTTestResources.createMockStreamInterceptor()

        PTTestResources.closeSocket(clientToProxySocket)
        with pytest.raises(ValueError) as excInfo:
            ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)

        assert "closed socket" in str(excInfo.value)
        assert "ClientToServer" in str(excInfo.value)


    def test_init_closedSocket_ProxyToServer(self):
        clientToProxySocket = PTTestResources.createClientSocket()
        proxyToServerSocket = PTTestResources.createClientSocket()
        streamInterceptor = PTTestResources.createMockStreamInterceptor()

        PTTestResources.closeSocket(proxyToServerSocket)
        with pytest.raises(ValueError) as excInfo:
            ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)

        assert "closed socket" in str(excInfo.value)
        assert "ProxyToServer" in str(excInfo.value)


    def test_init_correct(self):
        clientToProxySocket = PTTestResources.createClientSocket()
        proxyToServerSocket = PTTestResources.createClientSocket()
        streamInterceptor = PTTestResources.createMockStreamInterceptor()

        pt = ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)

        assert isinstance(pt.streamInterceptor, streamInterceptor)
        assert isinstance(pt.clientToProxySocket, socket.socket)
        assert isinstance(pt.proxyToServerSocket, socket.socket)

        ## TODO: Assertions on Buffers and RequestHook
        assert isinstance(pt.serverToClientBuffer, Buffer)
        assert isinstance(pt.clientToServerBuffer, Buffer)
        
        request = bytearray(b"completeRequest\r\n")
        pt.streamInterceptor.clientToServerHook(request)
        assert len(pt.streamInterceptor.clientToServerDeque) == 1
        assert pt.streamInterceptor.clientToServerDeque[-1] == request

        response = bytearray(b"completeResponse\r\n")
        pt.streamInterceptor.serverToClientHook(response)
        assert len(pt.streamInterceptor.serverToClientDeque) == 1
        assert pt.streamInterceptor.serverToClientDeque[-1] == response

    



class Test_ProxyTunnel_HelperMethods:


    ## Writing to a socket requires
    ## 1. reading from OPPOSITE buffer
    ## 2. writing to destination socket
    def test_selectBufferForWrite_clientToProxy(self):
        pt, _ = PTTestResources._setupPT()
        b = pt._selectBufferForRead(pt.clientToProxySocket)
        assert b == pt.clientToServerBuffer


    def test_selectBufferForWrite_proxyToClient(self):
        pt, _ = PTTestResources._setupPT()
        buffer = pt._selectBufferForRead(pt.proxyToServerSocket)
        assert buffer == pt.serverToClientBuffer


    def test_selectBufferForWrite_IncorrectSocket(self):
        pt, _ = PTTestResources._setupPT()
        nonparticipatingSocket = PTTestResources.createClientSocket()
        with pytest.raises(Exception) as excInfo:
            pt._selectBufferForRead(nonparticipatingSocket)
        assert "not associated with this tunnel" in str(excInfo.value)


    ## Reading from a socket requires
    ## 1. reading from destination socket
    ## 2. writing to destination buffer
    def test_selectBufferForWrite_clientToProxy(self):
        pt, _ = PTTestResources._setupPT()
        b = pt._selectBufferForRead(pt.clientToProxySocket)
        assert b == pt.serverToClientBuffer

    def test_selectBufferForWrite_proxyToClient(self):
        pt, _ = PTTestResources._setupPT()
        b = pt._selectBufferForRead(pt.proxyToServerSocket)
        assert b == pt.clientToServerBuffer

    def test_selectBufferForWrite_IncorrectSocket(self):
        pt, _ = PTTestResources._setupPT()
        nonparticipatingSocket = PTTestResources.createClientSocket()
        with pytest.raises(Exception) as excInfo:
            pt._selectBufferForRead(nonparticipatingSocket)
        assert "not associated with this tunnel" in str(excInfo.value)
