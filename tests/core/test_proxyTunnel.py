import collections
import os
import sys
from typing import List, Tuple
import pytest
import socket


sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyTunnel
from _proxyDS import Buffer, StreamInterceptorRegister, StreamInterceptor
from _exceptions import *
from tests.testhelper.TestResources import PTTestResources

## Fixtures
@pytest.fixture(scope="function")
def createProxyTunnel():
    ## Create PT
    pt, socketList, interceptorDeques = PTTestResources._setupPT()
    yield pt, socketList, interceptorDeques

    ## Close PT
    PTTestResources._closePT(socketList)

@pytest.fixture(scope="function")
def createPT_mockedSockets_sendHalfBytes(createProxyTunnel):
    pt, socketList, _ = createProxyTunnel

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
    pt, socketList, _ = createProxyTunnel

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
        streamInterceptor, _ = PTTestResources.createMockStreamInterceptor()

        streamInterceptorRegistration = ((
                    [StreamInterceptorRegister(streamInterceptor.ClientToServerHook, False, False),],
                    [StreamInterceptorRegister(streamInterceptor.ServerToClientHook, False, False),]
                ),
            )
        with pytest.raises(ValueError) as excInfo:
            ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptorRegistration)

        assert "duplicate sockets" in str(excInfo.value)


    def test_init_closedSocket_ClientToProxy(self):
        clientToProxySocket = PTTestResources.createClientSocket()
        proxyToServerSocket = PTTestResources.createClientSocket()
        streamInterceptor, _ = PTTestResources.createMockStreamInterceptor()

        PTTestResources.closeSocket(clientToProxySocket)
        streamInterceptorRegistration = ((
                    (StreamInterceptorRegister(streamInterceptor.ClientToServerHook, False, False),),
                    (StreamInterceptorRegister(streamInterceptor.ServerToClientHook, False, False),)
                ),
        )
        with pytest.raises(ValueError) as excInfo:
            ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptorRegistration)


        assert "closed socket" in str(excInfo.value)
        assert "ClientToServer" in str(excInfo.value)


    def test_init_closedSocket_ProxyToServer(self):
        clientToProxySocket = PTTestResources.createClientSocket()
        proxyToServerSocket = PTTestResources.createClientSocket()
        streamInterceptor, _ = PTTestResources.createMockStreamInterceptor()

        PTTestResources.closeSocket(proxyToServerSocket)
        streamInterceptorRegistration = ((
                    (StreamInterceptorRegister(streamInterceptor.ClientToServerHook, False, False),),
                    (StreamInterceptorRegister(streamInterceptor.ServerToClientHook, False, False),)
                ),
        )
        with pytest.raises(ValueError) as excInfo:
            ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptorRegistration)


        assert "closed socket" in str(excInfo.value)
        assert "ProxyToServer" in str(excInfo.value)


    def test_init_correct(self):
        clientToProxySocket = PTTestResources.createClientSocket()
        proxyToServerSocket = PTTestResources.createClientSocket()
        streamInterceptor, (clientToServerDeque, serverToClientDeque) = PTTestResources.createMockStreamInterceptor()

        streamInterceptorRegistration = ((
                    (StreamInterceptorRegister(streamInterceptor.ClientToServerHook, False, False),),
                    (StreamInterceptorRegister(streamInterceptor.ServerToClientHook, False, False),)
                ),
        )
        
        pt = ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptorRegistration)

        assert isinstance(pt.clientToProxySocket, socket.socket)
        assert isinstance(pt.proxyToServerSocket, socket.socket)

        ## TODO: Assertions on Buffers and RequestHook
        assert isinstance(pt.serverToClientBuffer, Buffer)
        assert isinstance(pt.clientToServerBuffer, Buffer)

        assert len(pt.clientToServerBuffer._hooks) == 1
        assert isinstance(pt.clientToServerBuffer._hooks[0].streamInterceptor, StreamInterceptor.Hook)
        assert len(pt.serverToClientBuffer._hooks) == 1
        assert isinstance(pt.serverToClientBuffer._hooks[0].streamInterceptor, StreamInterceptor.Hook)
        
        request = b"completeRequest\r\n"
        pt.clientToServerBuffer._hooks[0].streamInterceptor(request)
        assert len(clientToServerDeque) == 1
        assert clientToServerDeque[-1] == request

        response = b"completeResponse\r\n"
        pt.serverToClientBuffer._hooks[0].streamInterceptor(response)
        assert len(serverToClientDeque) == 1
        assert serverToClientDeque[-1] == response

    

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
        pt, _, _ = createProxyTunnel
        nonparticipatingSocket = PTTestResources.createClientSocket()

        with pytest.raises(UnassociatedTunnelSocket) as excInfo:
            pt.readFrom(nonparticipatingSocket)
        
        assert "not associated with the ProxyTunnel" in str(excInfo.value)


    def test_readFrom_bufferOverflow_clientToProxy(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        buffer = pt._selectBufferForRead(socketList[1])
        testdata = b"A" * (buffer._MAX_BUFFER_SIZE + 1)
        socketList[0].sendall(testdata)

        with pytest.raises(BufferOverflowError) as excInfo:
            pt.readFrom(pt.clientToProxySocket)

        assert "Max Buffer Size has been exceeded" in str(excInfo.value)


    def test_readFrom_emptyRead_clientToProxy(self, createProxyTunnel):
        ## NOTE: An empty recv() should mean the connection was closed on the otherside
        pt, socketList, _ = createProxyTunnel
        socketList[0].close()
        buffer = pt._selectBufferForRead(socketList[1])

        ret = pt.readFrom(socketList[1])

        assert ret == None
        assert buffer._incomingData == b""
        assert buffer._outgoingData == b""
        assert len(buffer._messages) == 0


    def test_readFrom_emptyRead_proxyToServer(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        socketList[3].close()
        buffer = pt._selectBufferForRead(socketList[2])

        ret = pt.readFrom(socketList[2])

        assert ret == None
        assert buffer._incomingData == b""
        assert buffer._outgoingData == b""
        assert len(buffer._messages) == 0

    
    def test_readFrom_nonEmptyRecv_clientToProxy(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        testData = b"testdata\r\n"
        socketList[0].sendall(testData)
        ret = pt.readFrom(socketList[1])
        buffer = pt._selectBufferForRead(socketList[1])

        assert ret == len(testData)
        assert buffer._incomingData == b""
        assert buffer._outgoingData == testData
        assert len(buffer._messages) == 0
    

    def test_readFrom_OneRead_OneEmptyRead_clientToProxy(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        buffer = pt._selectBufferForRead(socketList[1])
        testData = b"testdata\r\n"
        
        socketList[0].sendall(testData)
        socketList[0].close()
        
        ret = pt.readFrom(socketList[1])
        assert ret == len(testData)
        assert buffer._incomingData == b""
        assert buffer._outgoingData == testData
        assert len(buffer._messages) == 0

        ret = pt.readFrom(socketList[1])
        assert ret == None
        assert buffer._incomingData == b""
        assert buffer._outgoingData == testData
        assert len(buffer._messages) == 0

    def test_readFrom_OneRead_OneEmptyRead_proxyToServer(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        buffer = pt._selectBufferForRead(socketList[2])
        testData = b"testdata\r\n"
        
        socketList[3].sendall(testData)
        socketList[3].close()
        
        ret = pt.readFrom(socketList[2])
        assert ret == len(testData)
        assert buffer._incomingData == b""
        assert buffer._outgoingData == testData
        assert len(buffer._messages) == 0

        ret = pt.readFrom(socketList[2])
        assert ret is  None
        assert buffer._incomingData == b""
        assert buffer._outgoingData == testData
        assert len(buffer._messages) == 0

    ## TODO: Add additional socket error tests (after some interactions)
    def test_readFrom_SocketError_clientToProxy(self, createProxyTunnel_mockedErrorSockets):
        pt, socketList = createProxyTunnel_mockedErrorSockets
        testdata = b"testdata\r\n"
        buffer = pt._selectBufferForRead(socketList[1])
        socketList[0].sendall(testdata)

        ret1 = pt.readFrom(socketList[1])
        assert ret1 == None
        assert buffer._outgoingData == b""
        assert buffer._incomingData == b""
        assert len(buffer._messages) == 0

    def test_readFrom_SocketError_proxyToServer(self, createProxyTunnel_mockedErrorSockets):
        pt, socketList = createProxyTunnel_mockedErrorSockets
        testdata = b"testdata\r\n"
        buffer = pt._selectBufferForRead(socketList[2])
        socketList[3].sendall(testdata)

        ret1 = pt.readFrom(socketList[2])
        assert ret1 == None
        assert buffer._incomingData == b""
        assert buffer._outgoingData == b""
        assert len(buffer._messages) == 0


    ## writeTo() tests
    ## - nonparticipating socket
    ## - no data in the buffer to read from
    ## - send() returns 0
    ## - send() doesn't return all data
    ## - send() returns all data
    ## - socket.error raised??
    
    def test_writeTo_nonparticipatingSocket(self, createProxyTunnel):
        pt, _, _ = createProxyTunnel
        nonparticipatingSocket = PTTestResources.createClientSocket()

        with pytest.raises(UnassociatedTunnelSocket) as excInfo:
            pt.writeTo(nonparticipatingSocket)
        
        assert "not associated with the ProxyTunnel" in str(excInfo.value)


    def test_writeTo_noDataInBuffer_clientToProxy(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        socketList[0].setblocking(False)
        buffer = pt._selectBufferForWrite(pt.clientToProxySocket)
        
        ## Buffer should be empty
        ret = pt.writeTo(socketList[1])

        ## Test whether recv() fails
        with pytest.raises(socket.error) as excInfo:
            socketList[0].recv(1024)
        assert "unavailable" in str(excInfo.value)
        assert ret == 0
        assert buffer._incomingData == b""
        assert buffer._outgoingData == b""
        assert len(buffer._messages) == 0


    def test_writeTo_noDataInBuffer_proxyToClient(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        socketList[3].setblocking(False)
        buffer = pt._selectBufferForWrite(pt.clientToProxySocket)
        
        ## Buffer should be empty
        ret = pt.writeTo(socketList[2])

        ## Test whether recv() fails
        with pytest.raises(socket.error) as excInfo:
            socketList[3].recv(1024)
        assert "unavailable" in str(excInfo.value)
        assert ret == 0
        assert buffer._incomingData == b""
        assert buffer._outgoingData == b""
        assert len(buffer._messages) == 0


    def test_writeTo_zeroLengthReturned_clientToProxy(self):
        ## This test case does not exist
        ## --> If Zero is returned, that means the socket is
        ## -- not available for WRITE_EVENT.
        ## --> Since the socket.setblocking() has been set to false
        ## -- this should return an ERROR instead of a 0 length return
        ## NOTE: We can still mock this if we want to
        return None

    def test_writeTo_zeroLengthReturned_proxyToClient(self):
        ## NOTE: See above
        return None


    def test_writeTo_exceedsRemoteMaxChunkSize_clientToProxy(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        socketList[0].setblocking(False)
        socketList[1].setblocking(False)
        buffer = pt._selectBufferForWrite(socketList[1])
        
        testdata = b"testdata\r\n"
        buffer.write(testdata)
        ret = pt.writeTo(socketList[1])
        assert ret == len(testdata)

        ## First recv()
        ret = socketList[0].recv(len(testdata)//2)
        assert ret == testdata[:len(testdata)//2]
        assert buffer._incomingData == b""
        assert buffer._outgoingData == ret[len(testdata)//2:]
        assert len(buffer._messages) == 0

        ## Second recv()
        ret = socketList[0].recv(len(testdata)//2)
        assert ret == testdata[len(testdata)//2:]
        assert buffer._incomingData == b""
        assert buffer._outgoingData == b""
        assert len(buffer._messages) == 0


    def test_writeTo_exceedsRemoteMaxChunkSize_proxyToClient(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        socketList[3].setblocking(False)
        socketList[2].setblocking(False)
        buffer = pt._selectBufferForWrite(socketList[2])
        
        testdata = b"testdata\r\n"
        buffer.write(testdata)
        ret = pt.writeTo(socketList[2])
        assert ret == len(testdata)

        ## First recv()
        ret = socketList[3].recv(len(testdata)//2)
        assert ret == testdata[:len(testdata)//2]
        assert buffer._incomingData == b""
        assert buffer._outgoingData == ret[len(testdata)//2:]
        assert len(buffer._messages) == 0

        ## Second recv()
        ret = socketList[3].recv(len(testdata)//2)
        assert ret == testdata[len(testdata)//2:]
        assert buffer._incomingData == b""
        assert buffer._outgoingData == b""
        assert len(buffer._messages) == 0


    def test_writeTo_PartialLengthReturned_clientToProxy(self, createPT_mockedSockets_sendHalfBytes):
        pt, socketList = createPT_mockedSockets_sendHalfBytes

        socketList[0].setblocking(False)
        socketList[1].setblocking(False)
        buffer = pt._selectBufferForWrite(socketList[1])

        testdata = b"testdata\r\n"
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[1])
        assert ret1 == len(testdata)//2
        assert buffer._incomingData == b""
        assert buffer._outgoingData == testdata[len(testdata)//2:]
        assert len(buffer._messages) == 0

        ret2 = socketList[0].recv(1024)
        assert len(ret2) == len(testdata) - ret1
        assert ret2 == testdata[:len(testdata)//2]


    def test_writeTo_PartialLengthReturned_proxyToClient(self, createPT_mockedSockets_sendHalfBytes):
        pt, socketList = createPT_mockedSockets_sendHalfBytes

        socketList[0].setblocking(False)
        socketList[1].setblocking(False)
        buffer = pt._selectBufferForWrite(socketList[2])

        testdata = b"testdata\r\n"
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[2])
        assert ret1 == len(testdata)//2
        assert buffer._incomingData == b""
        assert buffer._outgoingData == testdata[len(testdata)//2:]
        assert len(buffer._messages) == 0

        ret2 = socketList[3].recv(1024)
        assert len(ret2) == len(testdata) - ret1
        assert ret2 == testdata[:len(testdata)//2]


    def test_writeTo_BufferLengthReturned_clientToProxy(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        testdata = b"testdata\r\n"
        buffer = pt._selectBufferForWrite(socketList[1])
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[1])
        assert ret1 == len(testdata)
        assert buffer._incomingData == b""
        assert buffer._outgoingData == b""
        assert len(buffer._messages) == 0

        ret2 = socketList[0].recv(1024)
        assert ret2 == testdata

    def test_writeTo_BufferLengthReturned_proxyToServer(self, createProxyTunnel):
        pt, socketList, _ = createProxyTunnel
        testdata = b"testdata\r\n"
        buffer = pt._selectBufferForWrite(socketList[2])
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[2])
        assert ret1 == len(testdata)        
        assert buffer._incomingData == b""
        assert buffer._outgoingData == b""

        assert len(buffer._messages) == 0

        ret2 = socketList[3].recv(1024)
        assert ret2 == testdata

    def test_writeTo_SocketError_clientToProxy(self, createProxyTunnel_mockedErrorSockets):
        pt, socketList = createProxyTunnel_mockedErrorSockets
        testdata = b"testdata\r\n"
        buffer = pt._selectBufferForWrite(socketList[1])
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[1])
        assert ret1 == None
        assert buffer._incomingData == b""
        assert buffer._outgoingData == testdata
        assert len(buffer._messages) == 0

    def test_writeTo_SocketError_proxyToClient(self, createProxyTunnel_mockedErrorSockets):
        pt, socketList = createProxyTunnel_mockedErrorSockets
        testdata = b"testdata\r\n"
        buffer = pt._selectBufferForWrite(socketList[2])
        buffer.write(testdata)

        ret1 = pt.writeTo(socketList[2])
        assert ret1 == None
        assert buffer._incomingData == b""
        assert buffer._outgoingData == testdata
        assert len(buffer._messages) == 0


class Test_ProxyTunnel_HelperMethods:


    ## Writing to a socket requires
    ## 1. reading from OPPOSITE buffer
    ## 2. writing to destination socket
    def test_selectBufferForWrite_clientToProxy(self, createProxyTunnel):
        pt, _, _ = createProxyTunnel
        b = pt._selectBufferForWrite(pt.clientToProxySocket)
        assert b == pt.serverToClientBuffer


    def test_selectBufferForWrite_proxyToClient(self, createProxyTunnel):
        pt, _, _ = createProxyTunnel
        buffer = pt._selectBufferForWrite(pt.proxyToServerSocket)
        assert buffer == pt.clientToServerBuffer


    def test_selectBufferForWrite_IncorrectSocket(self, createProxyTunnel):
        pt, _, _ = createProxyTunnel
        nonparticipatingSocket = PTTestResources.createClientSocket()
        with pytest.raises(UnassociatedTunnelSocket) as excInfo:
            pt._selectBufferForRead(nonparticipatingSocket)
        assert "not associated with the ProxyTunnel" in str(excInfo.value)


    ## Reading from a socket requires
    ## 1. reading from destination socket
    ## 2. writing to destination buffer
    def test_selectBufferForWrite_clientToProxy(self, createProxyTunnel):
        pt, _, _ = createProxyTunnel
        b = pt._selectBufferForRead(pt.clientToProxySocket)
        assert b == pt.clientToServerBuffer

    def test_selectBufferForWrite_proxyToClient(self, createProxyTunnel):
        pt, _, _ = createProxyTunnel
        b = pt._selectBufferForRead(pt.proxyToServerSocket)
        assert b == pt.serverToClientBuffer

    def test_selectBufferForWrite_IncorrectSocket(self, createProxyTunnel):
        pt, _, _ = createProxyTunnel
        nonparticipatingSocket = PTTestResources.createClientSocket()
        with pytest.raises(UnassociatedTunnelSocket) as excInfo:
            pt._selectBufferForRead(nonparticipatingSocket)
        assert "not associated with the ProxyTunnel" in str(excInfo.value)
