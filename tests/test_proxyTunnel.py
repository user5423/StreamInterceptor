import collections
import copy
import os
import sys
import functools
import types
from typing import List, Tuple
from aiohttp import ClientTimeout
import pytest
import socket
import importlib

from tests.temp import test


sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyTunnel
from _proxyDS import Buffer
from _exceptions import *

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
        streamInterceptor = PTTestResources.createMockStreamInterceptor()
        pt = ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)
        hopList = [clientSocket, clientToProxySocket, proxyToServerSocket, ephemeralServerSocket]
        return pt, hopList

    @staticmethod
    def _closePT(socketList: List[socket.socket]) -> None:
        for sock in socketList:
            sock.close()


## Fixtures
@pytest.fixture(scope="function")
def createProxyTunnel():
    ## Create PT
    pt, socketList = PTTestResources._setupPT()
    yield pt, socketList

    ## Close PT
    PTTestResources._closePT(socketList)

@pytest.fixture(scope="function")
def createProxyTunnel_mockedSockets(createProxyTunnel):
    pt, socketList = createProxyTunnel

    class wrappedSocket:
        def __init__(self, sock: socket.socket) -> None:
            self.sock = sock

        def send(self, bytes, *flags) -> None:
            return self.sock.send(bytes[:len(bytes)//2])

        def __getattr__(self, name):
            return getattr(self.sock, name)

        def __eq__(self, other):
            return other == self.sock


    socketList[1] = wrappedSocket(socketList[1])
    socketList[2] = wrappedSocket(socketList[2])
    return pt, socketList

@pytest.fixture(scope="function")
def createProxyTunnel_mockedErrorSockets(createProxyTunnel):
    pt, socketList = createProxyTunnel

    class wrappedSocket:
        def __init__(self, sock: socket.socket) -> None:
            self.sock = sock
            self.exception = OSError

        def send(self, bytes, *flags) -> None:
            raise self.exception()

        def recv(self, chunk_size, *flags) -> None:
            raise self.exception()

        def __getattr__(self, name):
            return getattr(self.sock, name)

        def __eq__(self, other):
            return other == self.sock


    socketList[1] = wrappedSocket(socketList[1])
    socketList[2] = wrappedSocket(socketList[2])
    return pt, socketList

    



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

    

class Test_ProxyTunnel_ByteOperations:
    ## ProxyTunnel().readFrom()
    ## ProxyTunnel().writeTo()

    ## readFrom() tests
    ## - nonparticipating socket
    ## - write to buffer (exceeds MAX_LENGTH) 
    ## - data.recv() == b"" (socket closed)
    ## - len(data.recv()) > 0 (continuation)

    ## ProxyTunnel().readFrom() tests
    def test_readFrom_nonparticipatingSocket(self, createProxyTunnel):
        # pt, _ = PTTestResources._setupPT()
        pt, _ = createProxyTunnel
        nonparticipatingSocket = PTTestResources.createClientSocket()

        with pytest.raises(UnassociatedTunnelSocket) as excInfo:
            pt.readFrom(nonparticipatingSocket)
        
        assert "not associated with the ProxyTunnel" in str(excInfo.value)


    def test_readFrom_bufferOverflow_clientToProxy(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        buffer = pt._selectBufferForRead(socketList[1])
        testdata = b"A" * (buffer._MAX_BUFFER_SIZE + 1)
        socketList[0].sendall(testdata)

        with pytest.raises(BufferOverflowError) as excInfo:
            pt.readFrom(pt.clientToProxySocket)

        assert "Max Buffer Size has been exceeded" in str(excInfo.value)


    def test_readFrom_emptyRead_clientToProxy(self, createProxyTunnel):
        ## NOTE: An empty recv() should mean the connection was closed on the otherside
        pt, socketList = createProxyTunnel
        socketList[0].close()
        buffer = pt._selectBufferForRead(socketList[1])

        ret = pt.readFrom(socketList[1])

        assert ret == None
        assert buffer._data == bytearray(b"")
        assert len(buffer._requests) == 0


    def test_readFrom_emptyRead_proxyToServer(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        socketList[3].close()
        buffer = pt._selectBufferForRead(socketList[2])

        ret = pt.readFrom(socketList[2])

        assert ret == None
        assert buffer._data == bytearray(b"")
        assert len(buffer._requests) == 0

    
    def test_readFrom_nonEmptyRecv_clientToProxy(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        testData = b"testdata"
        socketList[0].sendall(testData)
        ret = pt.readFrom(socketList[1])
        buffer = pt._selectBufferForRead(socketList[1])

        assert ret == len(testData)
        assert buffer._data == bytearray(testData)
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [bytearray(testData), False]
    

    def test_readFrom_nonEmptyRecv_clientToProxy(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        testData = b"testdata"
        socketList[3].sendall(testData)
        ret = pt.readFrom(socketList[2])
        buffer = pt._selectBufferForRead(socketList[2])

        assert ret == len(testData)
        assert buffer._data == bytearray(testData)
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [bytearray(testData), False]

    
    def test_readFrom_OneRead_OneEmptyRead_clientToProxy(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        buffer = pt._selectBufferForRead(socketList[1])
        testData = b"testdata"
        
        socketList[0].sendall(testData)
        socketList[0].close()
        
        ret = pt.readFrom(socketList[1])
        assert ret == len(testData)
        assert buffer._data == bytearray(testData)
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [bytearray(testData), False]

        ret = pt.readFrom(socketList[1])
        assert ret ==  None
        assert buffer._data == bytearray(testData)
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [bytearray(testData), False]


    def test_readFrom_OneRead_OneEmptyRead_proxyToServer(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        buffer = pt._selectBufferForRead(socketList[2])
        testData = b"testdata"
        
        socketList[3].sendall(testData)
        socketList[3].close()
        
        ret = pt.readFrom(socketList[2])
        assert ret == len(testData)
        assert buffer._data == bytearray(testData)
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [bytearray(testData), False]

        ret = pt.readFrom(socketList[2])
        assert ret ==  None
        assert buffer._data == bytearray(testData)
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [bytearray(testData), False]

    ## TODO: Add additional socket error tests (after some interactions)
    def test_readFrom_SocketError_clientToProxy(self, createProxyTunnel_mockedErrorSockets):
        pt, socketList = createProxyTunnel_mockedErrorSockets
        testdata = bytearray(b"testdata")
        buffer = pt._selectBufferForRead(socketList[1])
        socketList[0].sendall(testdata)

        ret1 = pt.readFrom(socketList[1])
        assert ret1 == None
        assert buffer._data == bytearray(b"")
        assert len(buffer._requests) == 0

    def test_readFrom_SocketError_proxyToServer(self, createProxyTunnel_mockedErrorSockets):
        pt, socketList = createProxyTunnel_mockedErrorSockets
        testdata = bytearray(b"testdata")
        buffer = pt._selectBufferForRead(socketList[2])
        socketList[3].sendall(testdata)

        ret1 = pt.readFrom(socketList[2])
        assert ret1 == None
        assert buffer._data == bytearray(b"")
        assert len(buffer._requests) == 0


    ## writeTo() tests
    ## - nonparticipating socket
    ## - no data in the buffer to read from
    ## - send() returns 0
    ## - send() doesn't return all data
    ## - send() returns all data
    ## - socket.error raised??
    
    def test_writeTo_nonparticipatingSocket(self, createProxyTunnel):
        pt, _ = createProxyTunnel
        nonparticipatingSocket = PTTestResources.createClientSocket()

        with pytest.raises(Exception) as excInfo:
            pt.writeTo(nonparticipatingSocket)
        
        assert "not associated with the ProxyTunnel" in str(excInfo.value)


    def test_writeTo_noDataInBuffer_clientToProxy(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        socketList[0].setblocking(False)
        buffer = pt._selectBufferForWrite(pt.clientToProxySocket)
        
        ## Buffer should be empty
        ret = pt.writeTo(socketList[1])

        ## Test whether recv() fails
        with pytest.raises(socket.error) as excInfo:
            socketList[0].recv(1024)
        assert "unavailable" in str(excInfo.value)
        assert ret == 0
        assert buffer._data == bytearray(b"")
        assert len(buffer._requests) == 0


    def test_writeTo_noDataInBuffer_proxyToClient(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        socketList[3].setblocking(False)
        buffer = pt._selectBufferForWrite(pt.clientToProxySocket)
        
        ## Buffer should be empty
        ret = pt.writeTo(socketList[2])

        ## Test whether recv() fails
        with pytest.raises(socket.error) as excInfo:
            socketList[3].recv(1024)
        assert "unavailable" in str(excInfo.value)
        assert ret == 0
        assert buffer._data == bytearray(b"")
        assert len(buffer._requests) == 0


    def test_writeTo_zeroLengthReturned_clientToProxy(self):
        ## This test case does not exist
        ## --> If Zero is returned, that means the socket is
        ## -- not available for WRITE_EVENT.
        ## --> Since the socket.setblocking() has been set to false
        ## -- this should return an ERROR instead of a 0 length return
        ## NOTE: We can still mock this if we want to
        ...

    def test_writeTo_zeroLengthReturned_proxyToClient(self):
        ## NOTE: See above
        ...


    def test_writeTo_exceedsRemoteMaxChunkSize_clientToProxy(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        socketList[0].setblocking(False)
        socketList[1].setblocking(False)
        buffer = pt._selectBufferForWrite(socketList[1])
        
        testdata = bytearray(b"testdata")
        buffer.write(testdata)
        ret = pt.writeTo(socketList[1])
        assert ret == len(testdata)

        ## First recv()
        ret = socketList[0].recv(len(testdata)//2)
        assert ret == testdata[:len(testdata)//2]
        assert buffer._data == ret[len(testdata)//2:]
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [testdata, False]

        ## Second recv()
        ret = socketList[0].recv(len(testdata)//2)
        assert ret == testdata[len(testdata)//2:]
        assert buffer._data == bytearray(b"")
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [testdata, False]


    def test_writeTo_exceedsRemoteMaxChunkSize_proxyToClient(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        socketList[3].setblocking(False)
        socketList[2].setblocking(False)
        buffer = pt._selectBufferForWrite(socketList[2])
        
        testdata = bytearray(b"testdata")
        buffer.write(testdata)
        ret = pt.writeTo(socketList[2])
        assert ret == len(testdata)

        ## First recv()
        ret = socketList[3].recv(len(testdata)//2)
        assert ret == testdata[:len(testdata)//2]
        assert buffer._data == ret[len(testdata)//2:]
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [testdata, False]

        ## Second recv()
        ret = socketList[3].recv(len(testdata)//2)
        assert ret == testdata[len(testdata)//2:]
        assert buffer._data == bytearray(b"")
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [testdata, False]


    def test_writeTo_PartialLengthReturned_clientToProxy(self, createProxyTunnel_mockedSockets):
        pt, socketList = createProxyTunnel_mockedSockets

        socketList[0].setblocking(False)
        socketList[1].setblocking(False)
        buffer = pt._selectBufferForWrite(socketList[1])

        testdata = bytearray(b"testdata")
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[1])
        assert ret1 == len(testdata)//2
        assert buffer._data == testdata[len(testdata)//2:]
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [testdata, False]

        ret2 = socketList[0].recv(1024)
        assert len(ret2) == len(testdata) - ret1
        assert bytearray(ret2) == testdata[:len(testdata)//2]


    def test_writeTo_PartialLengthReturned_proxyToClient(self, createProxyTunnel_mockedSockets):
        pt, socketList = createProxyTunnel_mockedSockets

        socketList[0].setblocking(False)
        socketList[1].setblocking(False)
        buffer = pt._selectBufferForWrite(socketList[2])

        testdata = bytearray(b"testdata")
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[2])
        assert ret1 == len(testdata)//2
        assert buffer._data == testdata[len(testdata)//2:]
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [testdata, False]

        ret2 = socketList[3].recv(1024)
        assert len(ret2) == len(testdata) - ret1
        assert bytearray(ret2) == testdata[:len(testdata)//2]


    def test_writeTo_BufferLengthReturned_clientToProxy(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        testdata = bytearray(b"testdata")
        buffer = pt._selectBufferForWrite(socketList[1])
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[1])
        assert ret1 == len(testdata)        
        assert buffer._data == bytearray(b"")
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [testdata, False]

        ret2 = socketList[0].recv(1024)
        assert bytearray(ret2) == testdata

    def test_writeTo_BufferLengthReturned_proxyToServer(self, createProxyTunnel):
        pt, socketList = createProxyTunnel
        testdata = bytearray(b"testdata")
        buffer = pt._selectBufferForWrite(socketList[2])
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[2])
        assert ret1 == len(testdata)        
        assert buffer._data == bytearray(b"")
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [testdata, False]

        ret2 = socketList[3].recv(1024)
        assert bytearray(ret2) == testdata

    def test_writeTo_SocketError_clientToProxy(self, createProxyTunnel_mockedErrorSockets):
        pt, socketList = createProxyTunnel_mockedErrorSockets
        testdata = bytearray(b"testdata")
        buffer = pt._selectBufferForWrite(socketList[1])
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[1])
        assert ret1 == None
        assert buffer._data == testdata
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [testdata, False]

    def test_writeTo_SocketError_proxyToClient(self, createProxyTunnel_mockedErrorSockets):
        pt, socketList = createProxyTunnel_mockedErrorSockets
        testdata = bytearray(b"testdata")
        buffer = pt._selectBufferForWrite(socketList[2])
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[2])
        assert ret1 == None
        assert buffer._data == testdata
        assert len(buffer._requests) == 1
        assert buffer._requests[-1] == [testdata, False]


class Test_ProxyTunnel_HelperMethods:


    ## Writing to a socket requires
    ## 1. reading from OPPOSITE buffer
    ## 2. writing to destination socket
    def test_selectBufferForWrite_clientToProxy(self, createProxyTunnel):
        pt, _ = createProxyTunnel
        b = pt._selectBufferForRead(pt.clientToProxySocket)
        assert b == pt.clientToServerBuffer


    def test_selectBufferForWrite_proxyToClient(self, createProxyTunnel):
        pt, _ = createProxyTunnel
        buffer = pt._selectBufferForRead(pt.proxyToServerSocket)
        assert buffer == pt.serverToClientBuffer


    def test_selectBufferForWrite_IncorrectSocket(self, createProxyTunnel):
        pt, _ = createProxyTunnel
        nonparticipatingSocket = PTTestResources.createClientSocket()
        with pytest.raises(Exception) as excInfo:
            pt._selectBufferForRead(nonparticipatingSocket)
        assert "not associated with the ProxyTunnel" in str(excInfo.value)


    ## Reading from a socket requires
    ## 1. reading from destination socket
    ## 2. writing to destination buffer
    def test_selectBufferForWrite_clientToProxy(self, createProxyTunnel):
        pt, _ = createProxyTunnel
        b = pt._selectBufferForRead(pt.clientToProxySocket)
        assert b == pt.serverToClientBuffer

    def test_selectBufferForWrite_proxyToClient(self, createProxyTunnel):
        pt, _ = createProxyTunnel
        b = pt._selectBufferForRead(pt.proxyToServerSocket)
        assert b == pt.clientToServerBuffer

    def test_selectBufferForWrite_IncorrectSocket(self, createProxyTunnel):
        pt, _ = createProxyTunnel
        nonparticipatingSocket = PTTestResources.createClientSocket()
        with pytest.raises(Exception) as excInfo:
            pt._selectBufferForRead(nonparticipatingSocket)
        assert "not associated with the ProxyTunnel" in str(excInfo.value)
