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
    def createSocket():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        return s


class Test_ProxyTunnel_Init:
    def test_default_init(self):
        with pytest.raises(TypeError) as excInfo:
            ProxyTunnel()

        assert "clientToProxySocket" in str(excInfo.value)
        assert "proxyToServerSocket" in str(excInfo.value)
        assert "streamInterceptor" in str(excInfo.value)
    

    def test_init_duplicatedSockets(self):
        ...


    def test_init_deadSocket_ClientToProxy(self):
        ...


    def test_init_deadSocket_ProxyToServer(self):
        ...


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


class Test_ProxyTunnel_HelperMethods:
    ## ProxyTunnel()._selectBufferToWrite()
    ## ProxyTunnel()._selectBufferToRead()

