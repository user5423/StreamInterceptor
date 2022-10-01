import collections
import os
import sys
import functools
import pytest
import socket

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyTunnel
from _proxyDS import Buffer


class PTTestResources:
    ...
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
    def createSocket() -> socket.socket:
        return socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    @staticmethod
    def closeSocket(s: socket) -> None:
        s.close()



class Test_ProxyTunnel_Init:
    def test_default_init(self):
        with pytest.raises(TypeError) as excInfo:
            ProxyTunnel()

        assert "clientToProxySocket" in str(excInfo.value)
        assert "proxyToServerSocket" in str(excInfo.value)
        assert "streamInterceptor" in str(excInfo.value)
    

    def test_init_duplicatedSockets(self):
        clientToProxySocket = PTTestResources.createSocket()
        proxyToServerSocket = clientToProxySocket
        streamInterceptor = PTTestResources.createMockStreamInterceptor()

        with pytest.raises(ValueError) as excInfo:
            ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)

        assert "duplicate sockets" in str(excInfo.value)


    def test_init_closedSocket_ClientToProxy(self):
        clientToProxySocket = PTTestResources.createSocket()
        proxyToServerSocket = PTTestResources.createSocket()
        streamInterceptor = PTTestResources.createMockStreamInterceptor()

        PTTestResources.closeSocket(clientToProxySocket)
        with pytest.raises(ValueError) as excInfo:
            ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)

        assert "closed socket" in str(excInfo.value)
        assert "ClientToServer" in str(excInfo.value)


    def test_init_closedSocket_ProxyToServer(self):
        clientToProxySocket = PTTestResources.createSocket()
        proxyToServerSocket = PTTestResources.createSocket()
        streamInterceptor = PTTestResources.createMockStreamInterceptor()

        PTTestResources.closeSocket(proxyToServerSocket)
        with pytest.raises(ValueError) as excInfo:
            ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)

        assert "closed socket" in str(excInfo.value)
        assert "ProxyToServer" in str(excInfo.value)


    def test_init_correct(self):
        clientToProxySocket = PTTestResources.createSocket()
        proxyToServerSocket = PTTestResources.createSocket()
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

    


class Test_ProxyTunnel_ByteOperations:
    ## ProxyTunnel().read()
    ## ProxyTunnel().write()
    ...


class Test_ProxyTunnel_HelperMethods:
    def _setupPT(self):
        clientToProxySocket = PTTestResources.createSocket()
        proxyToServerSocket = PTTestResources.createSocket()
        streamInterceptor = PTTestResources.createMockStreamInterceptor()
        pt = ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)
        return pt

    ## Writing to a socket requires
    ## 1. reading from OPPOSITE buffer
    ## 2. writing to destination socket
    def test_selectBufferForWrite_clientToProxy(self):
        pt = self._setupPT()
        b = pt._selectBufferForRead(pt.clientToProxySocket)
        assert b == pt.clientToServerBuffer


    def test_selectBufferForWrite_proxyToClient(self):
        pt = self._setupPT()
        buffer = pt._selectBufferForRead(pt.proxyToServerSocket)
        assert buffer == pt.serverToClientBuffer


    def test_selectBufferForWrite_IncorrectSocket(self):
        pt = self._setupPT()
        nonparticipatingSocket = PTTestResources.createSocket()
        with pytest.raises(Exception) as excInfo:
            pt._selectBufferForRead(nonparticipatingSocket)
        assert "not associated with this tunnel" in str(excInfo.value)


    ## Reading from a socket requires
    ## 1. reading from destination socket
    ## 2. writing to destination buffer
    def test_selectBufferForWrite_clientToProxy(self):
        pt = self._setupPT()
        b = pt._selectBufferForRead(pt.clientToProxySocket)
        assert b == pt.serverToClientBuffer

    def test_selectBufferForWrite_proxyToClient(self):
        pt = self._setupPT()
        b = pt._selectBufferForRead(pt.proxyToServerSocket)
        assert b == pt.clientToServerBuffer

    def test_selectBufferForWrite_IncorrectSocket(self):
        pt = self._setupPT()
        nonparticipatingSocket = PTTestResources.createSocket()
        with pytest.raises(Exception) as excInfo:
            pt._selectBufferForRead(nonparticipatingSocket)
        assert "not associated with this tunnel" in str(excInfo.value)
