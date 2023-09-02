import collections
import typing
import time
import pytest
# from ftp_proxyinterceptor import FTPProxyInterceptor
import threading
import inspect
import os
import sys
import socket
import pprint
from typing import Tuple, Generator, List, Optional
sys.path.insert(0, os.path.join("src"))
sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, os.path.join("..", "..", "src"))
sys.path.insert(0, os.path.join("tests", "testhelper"))
# sys.path.insert(0, os.path.join("..", "tests", "testhelper"))
from ftp_proxyinterceptor import FTPProxyInterceptor, FTPInterceptorHelperMixin, FTPLoginProxyInterceptor, FTPDataConnectionHandler
from tcp_proxyserver import TCPProxyServer, ProxyTunnel
from DataTransferSimulator import TelnetClientSimulator



class Test_FTPInterceptorHelperMixin:
    ## NOTE: We are only performing smoke tests on IPv4 here for the sake of saving time in the PoC

    def test_octectsToIPByteString_validLoopbackAddressByteTuple(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        address = b"127.0.0.1"
        assert address == helperMixinInstance._octectsToIPByteString((address.split(b".")))

    def test_octectsToIPByteString_validLoopbackAddressStringTuple(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        address = "127.0.0.1"

        ## NOTE: The tested method should only handle bytes
        with pytest.raises(TypeError):
            helperMixinInstance._octectsToIPByteString(address.split("."))



    def test_validateFTPIPAddress_validLoopbackAddressByteTuple(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        expectedIP = b"127.0.0.1"
        assert expectedIP == helperMixinInstance._validateFTPIPAddress(expectedIP.split(b"."), expectedIP)

    def test_validateFTPIPAddress_validLoopbackAddressStringTuple(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        expectedIP = "127.0.0.1"
        with pytest.raises(TypeError):
            helperMixinInstance._validateFTPIPAddress(expectedIP.split("."), expectedIP)
        
    def test_validateFTPIPAddress_InsufficientOctectCount(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        expectedIP = b"127.0.0"
        assert helperMixinInstance._validateFTPIPAddress(expectedIP.split(b"."), expectedIP) is None

    def test_validateFTPIPAddress_TooLargeOctectCount(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        expectedIP = b"127.0.0.1.1"
        assert helperMixinInstance._validateFTPIPAddress(expectedIP.split(b"."), expectedIP) is None
        
    def test_validateFTPIPAddress_TooSmallOctectValues(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        expectedIP = b"127.0.-1.1"
        assert helperMixinInstance._validateFTPIPAddress(expectedIP.split(b"."), expectedIP) is None

    def test_validateFTPIPAddress_TooLargeOctectValues(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        expectedIP = b"127.0.1000.1"
        assert helperMixinInstance._validateFTPIPAddress(expectedIP.split(b"."), expectedIP) is None
         


    def test_IPByteStringToFTPByteFormat_validLoopbackAddress(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        byteFormat = b"127.0.0.1"
        ftpByteFormat = b"127,0,0,1"
        assert ftpByteFormat == helperMixinInstance._IPByteStringToFTPByteFormat(byteFormat)

    def test_IPFTPByteFormatToByteString_validLoopbackAddress(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        ftpByteFormat = b"127,0,0,1"
        byteFormat = b"127.0.0.1"
        assert byteFormat == helperMixinInstance._IPFTPByteFormatToByteString(ftpByteFormat)




    def test_portIntToFTPByteFormat_zero(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intFormat = 0
        ftpFormat = b"0,0"
        assert helperMixinInstance._portIntToFTPByteFormat(intFormat) == ftpFormat

    def test_portFTPByteFormatToInt_zero(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intFormat = 0
        ftpFormat = (b"0", b"0")
        assert helperMixinInstance._portFTPByteFormatToInt(ftpFormat) == intFormat

    def test_portIntToFTPByteFormat_firstOctectZero_secondOctectFull(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intFormat = 255
        ftpFormat = b"0,255"
        assert helperMixinInstance._portIntToFTPByteFormat(intFormat) == ftpFormat

    def test_portFTPByteFormatToInt_firstOctectZero_secondOctectFull(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intFormat = 255
        ftpFormat = (b"0", b"255")
        assert helperMixinInstance._portFTPByteFormatToInt(ftpFormat) == intFormat

    def test_portIntToFTPByteFormat_firstOctectFull_secondOctectFull(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intFormat = (255 * 256) + 255
        ftpFormat = b"255,255"
        assert helperMixinInstance._portIntToFTPByteFormat(intFormat) == ftpFormat

    def test_portFTPByteFormatToInt_firstOctectFull_secondOctectFull(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intFormat = (255 * 256) + 255
        ftpFormat = (b"255", b"255")
        assert helperMixinInstance._portFTPByteFormatToInt(ftpFormat) == intFormat


    ## NOTE: There is a dependency on FTPInterceptorHelperMixin._portIntToFTPByteFormat
    ## ==> Therefore, if tests related to that method have failed, fix those tests first
    def test_validateFTPPort_validUnpriviledgedPort(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intPort = 20_000
        ftpPort = helperMixinInstance._portIntToFTPByteFormat(intPort).split(b",")
        assert intPort == helperMixinInstance._validateFTPPort(ftpPort)

    def test_validateFTPPort_maxSizeUnpriviledgedPort(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intPort = 2**16 -1 ## 2^16 = 65535
        ftpPort = helperMixinInstance._portIntToFTPByteFormat(intPort).split(b",")
        assert intPort == helperMixinInstance._validateFTPPort(ftpPort)

    def test_validateFTPPort_moreThanMaxSizeUnpriviledgedPort(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intPort = 2**16 + 1
        ftpPort = helperMixinInstance._portIntToFTPByteFormat(intPort).split(b",")
        assert helperMixinInstance._validateFTPPort(ftpPort) is None

    def test_validateFTPPort_MinSizeUnpriviledgedPort(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intPort = 1024
        ftpPort = helperMixinInstance._portIntToFTPByteFormat(intPort).split(b",")
        assert intPort == helperMixinInstance._validateFTPPort(ftpPort)

    def test_validateFTPPort_lessThanMinSizeUnpriviledgedPort(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intPort = 1024 - 1
        ftpPort = helperMixinInstance._portIntToFTPByteFormat(intPort).split(b",")
        assert helperMixinInstance._validateFTPPort(ftpPort) is None

    def test_validateFTPPort_priviledgedPortZero(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intPort = 0
        ftpPort = helperMixinInstance._portIntToFTPByteFormat(intPort).split(b",")
        assert helperMixinInstance._validateFTPPort(ftpPort) is None

    def test_validateFTPPort_negativePort(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        intPort = -1
        ftpPort = helperMixinInstance._portIntToFTPByteFormat(intPort).split(b",")
        assert helperMixinInstance._validateFTPPort(ftpPort) is None



    ## TODO: Due to limited time, we are restricted to testing only the socket configuration (i.e. blocking, and timeouts)

    def _assertBoundSocket(self, sock: socket) -> None:
        ## NOTE: If the port in the sockname is set to 0, then the socket is not bound to any port yet (so listen has not been called)
        assert sock.getsockname()[1] != 0

    def _assertUnboundSocket(self, sock: socket) -> None:
        assert sock.getsockname()[1] == 0

    def _assertUnconnectedSocket(self, sock: socket) -> None:
        ## We check whether we the socket is connected to anything
        with pytest.raises(OSError) as excInfo:
            sock.getpeername()
        assert "not connected" in str(excInfo.value)

    def _assertNonListeningSocket(self, sock: socket) -> None:
        ## TODO: This is not a good test/assertion. This modifies the state of the socket
        ## TODO: Replace this mechanism with another way for a check that doesn't modify state of socket

        ## We store previous sock settings
        prevTimeout = sock.gettimeout()
        prevBlocking = sock.getblocking()

        ## We attempt to accept() which only executes properly if the socket is listening
        with pytest.raises(socket.timeout):
            sock.setblocking(True)
            ## Since we are not going to connect to the sock, we wait for a timeout error 
            ## (this still means accept() function was entered correctly which is what we need)
            sock.settimeout(0.01)
            sock.accept()

        ## We load back in the previous sock settings
        sock.setblocking(prevBlocking)
        sock.settimeout(prevTimeout)

    def _assertEphemeralServerSocketSetup(self, sock: socket.socket) -> None:
        self._assertBoundSocket(sock)
        self._assertUnconnectedSocket(sock)
        self._assertNonListeningSocket(sock)

    def test_ephemeralServerSocketSetup_validLoopbackHost_blockingTrue(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        sock = helperMixinInstance._setupEphemeralServerSocket("127.0.0.1", True)
        assert sock.getblocking() is True
        assert sock.gettimeout() is None
        self._assertEphemeralServerSocketSetup(sock)

    def test_ephemeralServerSocketSetup_validLoopbackHost_blockingFalse(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        sock = helperMixinInstance._setupEphemeralServerSocket("127.0.0.1", False)
        assert sock.getblocking() is False
        assert sock.gettimeout() == 0.0
        self._assertEphemeralServerSocketSetup(sock)

    def test_ephemeralServerSocketSetup_validLoopbackHost_blockingDefault(self):
        ## NOTE: The default value should be non-blocking
        helperMixinInstance = FTPInterceptorHelperMixin()
        sock = helperMixinInstance._setupEphemeralServerSocket("127.0.0.1")
        assert sock.getblocking() is False
        assert sock.gettimeout() == 0.0
        self._assertEphemeralServerSocketSetup(sock)



    def _assertEphemeralClientSocketSetup(self, sock: socket.socket) -> None:
        self._assertUnboundSocket(sock)
        ## NOTE: We do not need to check whether the socket has connected / is listening, 
        ## This is because the socket would need to be bound for this to happen, (the assertion aboves makes those checks redundant)

    def test_ephemeralClientSocketSetup_validLoopbackHost_blockingTrue(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        sock = helperMixinInstance._createEphemeralClientSocket(True)
        assert sock.getblocking() is True
        assert sock.gettimeout() is None
        self._assertEphemeralClientSocketSetup(sock)

    def test_ephemeralClientSocketSetup_validLoopbackHost_blockingFalse(self):
        helperMixinInstance = FTPInterceptorHelperMixin()
        sock = helperMixinInstance._createEphemeralClientSocket(False)
        assert sock.getblocking() is False
        assert sock.gettimeout() == 0.0
        self._assertEphemeralClientSocketSetup(sock)

    def test_ephemeralClientSocketSetup_validLoopbackHost_blockingDefault(self):
        ## NOTE: The default value should be non-blocking
        helperMixinInstance = FTPInterceptorHelperMixin()
        sock = helperMixinInstance._createEphemeralClientSocket()
        assert sock.getblocking() is False
        assert sock.gettimeout() == 0.0
        self._assertEphemeralClientSocketSetup(sock)



@pytest.fixture
def setupMockDataConnHandler():
    ## NOTE: This function returns a FTPDataConnectionHandler that has an empty _connectionHandler that is used as an entrypoint via a proxy __call__() method
    ## NOTE: There is an expectation that _connectionHandler() will not be called using this Mock class
    class MockFTPDataConnectionHandler(FTPDataConnectionHandler):
        def _connectionHandler(self, *args, **kwargs):
            while True:
                yield

    HOST, PORT = "127.0.0.1", 8080 ## NOTE: This socket will not be queried!!!
    PROXY_HOST, PROXY_PORT = "127.0.0.1", 22 ## NOTE: This destination will not be connected to!!!

    proxyServer = TCPProxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT)
    proxyTunnel = ProxyTunnel(socket.socket(), socket.socket(), []) ## ProxyTunnel(clientToProxySock, ProxyToClientSock, StreamInterceptorRegistration)
    clientToServerBuffer = proxyTunnel.clientToServerBuffer
    serverToClientBuffer = proxyTunnel.serverToClientBuffer
    mockDataConnHandler = MockFTPDataConnectionHandler(proxyServer, proxyTunnel, clientToServerBuffer, serverToClientBuffer)
    yield proxyServer, proxyTunnel, mockDataConnHandler
    
    proxyServer.serverSocket.close()
    return None


@pytest.fixture
def setupLocalListener():
    ip = b"127.0.0.1"
    sock = socket.socket()
    sock.bind((ip, 0))
    sock.listen()
    port = sock.getsockname()[1]
    yield ip, port, sock

    sock.close()

@pytest.fixture
def setupPORTRequestForServer(setupLocalListener, setupMockDataConnHandler):
    proxyIP, proxyPort, proxySock = setupLocalListener
    proxyServer, proxyTunnel, mockDataConnHandler = setupMockDataConnHandler
    portCommand = b"PORT " + mockDataConnHandler._IPByteStringToFTPByteFormat(proxyIP) + b"," + mockDataConnHandler._portIntToFTPByteFormat(proxyPort) + b"\r\n"
    yield proxyIP, proxyPort, proxySock, portCommand


## NOTE: This is used as an empty class to dump arbitrary and store it in attribute names
class OutputStorage: ...


def stepThroughGenerator(generatorFunction, stepCallback, messages, timeout, generatorFunctionArgs=(), generatorFunctionKwargs={}):
    index = 0
    messages = [None] + messages
    startTime = time.time()
    generatorCompletedExecution = False
    subgen = generatorFunction(*generatorFunctionArgs, **generatorFunctionKwargs)
    while time.time() < startTime + timeout:
        try:
            output = subgen.send(messages[index])
            stepCallback(*output)
            index+=1
        except StopIteration as e:
            generatorCompletedExecution = True
            break

    return generatorCompletedExecution



class Test_FTPDataConnInterceptor_Helpers:
    ## Here we are testing the data conn interceptor which should handle correctly setting up 

    ## NOTE: ASSUMPTION - Only single delimited messages that have a single delimiter and end with it (CRLF)
    ## NOTE: ASSUMPTION - Only request messages are passed to this method
    ## NOTE: BEHAVIOR - There should not be any short-cutting
    def _assertValidatePortRequestSuccess(self, message: bytes, clientAddress: Optional[Tuple[bytes, int]], passedProcessing: bool, relayMessage: bool, req: bytes, validIPv4: bytes, validPort: int) -> None:
        assert relayMessage is True
        assert clientAddress == (validIPv4, validPort)
        assert passedProcessing is True
        assert message == req

    def _assertValidatePortRequestFailure(self, message: bytes, clientAddress: Optional[Tuple[bytes, int]], passedProcessing: bool, relayMessage: bool, req: bytes) -> None:
        assert relayMessage is True
        assert clientAddress is None
        assert passedProcessing is False
        assert message == req

    def _setupClientConnection(self, proxyTunnel: ProxyTunnel) -> socket.socket:
        proxyTunnel.clientToProxySocket.listen()
        clientSocket = socket.socket()
        clientSocket.connect(proxyTunnel.clientToProxySocket.getsockname())
        proxyTunnel.clientToProxySocket = proxyTunnel.clientToProxySocket.accept()[0]
        return clientSocket

    def test_validatePORTRequest_validNonPORTRequest(self, setupMockDataConnHandler):
        ## TODO: Expand this test to execute all request non-PORT request types
        proxyServer, proxyTunnel, mockDataConnHandler = setupMockDataConnHandler
        req = b"USER user5423\r\n"
        
        message, clientAddress, passedProcessing, relayMessage = mockDataConnHandler._validatePORTRequest(req, proxyTunnel)
        self._assertValidatePortRequestFailure(message, clientAddress, passedProcessing, relayMessage, req)

    def test_validatePORTRequest_PORTCommand_NoAddressArgs(self, setupMockDataConnHandler):
        proxyServer, proxyTunnel, mockDataConnHandler = setupMockDataConnHandler

        req = b"PORT \r\n"
        clientSocket = self._setupClientConnection(proxyTunnel)
        message, clientAddress, passedProcessing, relayMessage = mockDataConnHandler._validatePORTRequest(req, proxyTunnel)
        self._assertValidatePortRequestFailure(message, clientAddress, passedProcessing, relayMessage, req)

    def test_validatePORTRequest_PORTCommand_InvalidIPv4Address_InvalidPriviledgedPort(self, setupMockDataConnHandler):
        proxyServer, proxyTunnel, mockDataConnHandler = setupMockDataConnHandler
        ## ip=127,0,0,x port=0,x (where x is missing octect)
        req = b"PORT 127,0,0,0\r\n"
        clientSocket = self._setupClientConnection(proxyTunnel)
        message, clientAddress, passedProcessing, relayMessage = mockDataConnHandler._validatePORTRequest(req, proxyTunnel)
        self._assertValidatePortRequestFailure(message, clientAddress, passedProcessing, relayMessage, req)

    def test_validatePORTRequest_PORTCommand_validIPv4Address_InvalidPriviledgedPort(self, setupMockDataConnHandler):
        proxyServer, proxyTunnel, mockDataConnHandler = setupMockDataConnHandler
        ## ip=127,0,0,1 port=0,x (where x is missing octect)
        req = b"PORT 127,0,0,1,0\r\n"
        clientSocket = self._setupClientConnection(proxyTunnel)
        message, clientAddress, passedProcessing, relayMessage = mockDataConnHandler._validatePORTRequest(req, proxyTunnel)
        self._assertValidatePortRequestFailure(message, clientAddress, passedProcessing, relayMessage, req)

    def test_validatePORTRequest_PORTCommand_InvalidIPv4Address_ValidPriviledgedPort(self, setupMockDataConnHandler):
        ## This test is effectively the same as test_validatePORTRequest_PORTCommand_validIPv4Address_InvalidPriviledgedPort (but we consider it from a different perspective)
        proxyServer, proxyTunnel, mockDataConnHandler = setupMockDataConnHandler
        ## ip=127,0,0,x port=1,0 (where x is missing octect)
        req = b"PORT 127,0,0,1,0\r\n"
        clientSocket = self._setupClientConnection(proxyTunnel)
        message, clientAddress, passedProcessing, relayMessage = mockDataConnHandler._validatePORTRequest(req, proxyTunnel)
        self._assertValidatePortRequestFailure(message, clientAddress, passedProcessing, relayMessage, req)

    def test_validatePORTRequest_PORTCommand_ValidIPv4Address_ValidPriviledgedPort(self, setupMockDataConnHandler):
        proxyServer, proxyTunnel, mockDataConnHandler = setupMockDataConnHandler
        req = b"PORT 127,0,0,1,4,4\r\n"
        validIPv4 = b"127.0.0.1"
        validPort = 256*4 + 4
        clientSocket = self._setupClientConnection(proxyTunnel)
        message, clientAddress, passedProcessing, relayMessage = mockDataConnHandler._validatePORTRequest(req, proxyTunnel)
        self._assertValidatePortRequestSuccess(message, clientAddress, passedProcessing, relayMessage, req, validIPv4, validPort)


    # def test_validatePORTRequest_PORTCommand_ValidLoopbackIPv4Address_ValidUnpriviledgedPort(self): ...
    # def test_validatePORTRequest_PORTCommand_ValidLoopbackIPv4Address_InvalidPriviledgedPort(self): ...
    # def test_validatePORTRequest_PORTCommand_ValidLoopbackIPv4Address_NegativePort(self): ...
    # def test_validatePORTRequest_PORTCommand_ValidLoopbackIPv4Address_ZeroPort(self): ...

    # def test_validatePORTRequest_PORTCommand_InvalidIPv4Address_ValidUnpriviledgedPort(self): ...
    # def test_validatePORTRequest_PORTCommand_InvalidIPv4Address_InvalidPriviledgedPort(self): ...
    # def test_validatePORTRequest_PORTCommand_InvalidIPv4Address_NegativePort(self): ...
    # def test_validatePORTRequest_PORTCommand_InvalidIPv4Address_ZeroPort(self): ...


    ## NOTE: ASSUMPTION - The ipv4 and port values have been validated for these tests
    ## NOTE: ASSUMPTION - The ipv4 address in the PORT command matches the client's IPv4
    ## NOTE: ASSUMPTION - The port in the PORT command is an unprivileged port 1024 <= x <= 65535
    def test_initiatePORTconnectionToClient_availableLoopbackClientIPv4EndpointListening(self, setupMockDataConnHandler, setupLocalListener):
        proxyServer, controlProxyTunnel, mockDataConnHandler = setupMockDataConnHandler
        clientIP, clientPort, clientSock = setupLocalListener ## creates a local listener on an unused unpriviledged port
        req = b"PORT " + mockDataConnHandler._IPByteStringToFTPByteFormat(clientIP) + b"," + mockDataConnHandler._portIntToFTPByteFormat(clientPort) + b"\r\n"

        outputStorageInstance = OutputStorage()
        args = (req, clientIP, clientPort, controlProxyTunnel)
        def subgenerator_wrapper(req, clientIP, clientPort, controlProxyTunnel):
            nonlocal outputStorageInstance, mockDataConnHandler
            modifiedRequest, activeClientToProxySock, passedProcessing, relayMessage = yield from mockDataConnHandler._initiatePORTconnectionToClient(req, clientIP, clientPort, controlProxyTunnel)
            outputStorageInstance.results = {"modifiedRequest": modifiedRequest, "activeClientToProxySock": activeClientToProxySock, "passedProcessing": passedProcessing, "relayMessage": relayMessage}

        def stepCallback(message, relayMessage):
            nonlocal req
            assert message == req
            assert relayMessage == False

        maxYieldCount = 10000
        messages = [None] * maxYieldCount ## A high number of values than will be yielded in the generator
        generatorCompletedExecution = stepThroughGenerator(subgenerator_wrapper, stepCallback, messages, timeout=1.0, generatorFunctionArgs=args)
        
        assert generatorCompletedExecution is True
        ## NOTE: Remember, our client sock is still a listener in which we need to execute accept() on
        acceptedClientSock = clientSock.accept()[0]
        assert outputStorageInstance.results["modifiedRequest"] == req
        assert outputStorageInstance.results["passedProcessing"] is True
        assert outputStorageInstance.results["relayMessage"] is True
        assert outputStorageInstance.results["activeClientToProxySock"].getpeername() == acceptedClientSock.getsockname()


    def test_initiatePORTconnectionToClient_availaleLoopbackClientIPv4EndpointNotListening(self, setupMockDataConnHandler,):
        proxyServer, controlProxyTunnel, mockDataConnHandler = setupMockDataConnHandler
        clientIP = b"127.0.0.1"
        clientPort = 2^16-1 ## This is not a special port, but it is unlikely some other program is listening on this
        req = b"PORT " + mockDataConnHandler._IPByteStringToFTPByteFormat(clientIP) + b"," + mockDataConnHandler._portIntToFTPByteFormat(clientPort) + b"\r\n"

        outputStorageInstance = OutputStorage()
        args = (req, clientIP, clientPort, controlProxyTunnel)
        def subgenerator_wrapper(req: bytes, clientIP: bytes, clientPort: int, controlProxyTunnel: ProxyTunnel):
            nonlocal outputStorageInstance, mockDataConnHandler
            modifiedRequest, activeClientToProxySock, passedProcessing, relayMessage = yield from mockDataConnHandler._initiatePORTconnectionToClient(req, clientIP, clientPort, controlProxyTunnel)
            outputStorageInstance.results = {"modifiedRequest": modifiedRequest, "activeClientToProxySock": activeClientToProxySock, "passedProcessing": passedProcessing, "relayMessage": relayMessage}

        def stepCallback(message, relayMessage):
            nonlocal req
            assert message == req
            assert relayMessage == False

        maxYieldCount = 10000
        messages = [None] * maxYieldCount ## A high number of values than will be yielded in the generator
        generatorCompletedExecution = stepThroughGenerator(subgenerator_wrapper, stepCallback, messages, timeout=1.0, generatorFunctionArgs=args)

        assert generatorCompletedExecution is True
        assert outputStorageInstance.results["modifiedRequest"] == req
        assert outputStorageInstance.results["passedProcessing"] is False
        assert outputStorageInstance.results["relayMessage"] is True
        assert outputStorageInstance.results["activeClientToProxySock"].fileno() == -1 ## i.e. the socket is closed


    ## NOTE: ASSUMPTION - The server host is controlled by the developer so we assume that the server IPv4 is set correctly
    ## TODO: We will be developing a quick dry-run functionality to ensure that everything is configured correctly
    def test_setupPORTRequestToServer_availableLoopbackServerIPv4EndpointListening(self, setupMockDataConnHandler):
        proxyServer, controlProxyTunnel, mockDataConnHandler = setupMockDataConnHandler
        HOST = b"127.0.0.1"
        proxyPortCommand, (proxyToServerIP, proxyToServerPort), activeProxyToServerSock = mockDataConnHandler._setupPORTRequestToServer(HOST)

        assert proxyToServerIP == b"127.0.0.1"
        assert 1024 <= proxyToServerPort <= 65535
        assert activeProxyToServerSock.getsockname()[1] != 0 ## assigned a port means the socket is bound BUG: THis is insufficient to say that it is bound, AND subsequently listening!!!!
        assert proxyPortCommand == b"PORT " + mockDataConnHandler._IPByteStringToFTPByteFormat(proxyToServerIP) + b"," + mockDataConnHandler._portIntToFTPByteFormat(proxyToServerPort) + b"\r\n"


    ## NOTE: ASSUMPTION - At this point, our entrypoint to the function is the serverPORT command and the proxy socket listener
    ## The program should immediately yield the serverPORTcommand so that it can be relayed to the server
    ## and then the program should wait until it receives a connection. (if it timesout, the the socket should be shut)
    def test_finalizePORTDataConnection_ServerConnects(self, setupMockDataConnHandler, setupPORTRequestForServer):
        proxyServer, controlProxyTunnel, mockDataConnHandler = setupMockDataConnHandler
        proxyIP, proxyPort, proxySockListener, portCommand = setupPORTRequestForServer

        # modifiedRequest, passedProcessing, relayMessage = yield from self._finalizePORTDataConnection(portCommand, ephemeralProxyListener)
        outputStorageInstance = OutputStorage()
        args = (portCommand, proxySockListener)
        def subgenerator_wrapper(portCommand: bytes, proxySockListener: socket.socket):
            nonlocal outputStorageInstance, mockDataConnHandler
            modifiedRequest, activeProxyToServerSock, passedProcessing, relayMessage = yield from mockDataConnHandler._finalizePORTDataConnection(portCommand, proxySockListener)
            outputStorageInstance.results = {"modifiedRequest": modifiedRequest, "activeProxyToServerSock": activeProxyToServerSock, "passedProcessing": passedProcessing, "relayMessage": relayMessage}

        sentMessages = [
            (None, b"200 Success\r\n"),
        ]

        def _stepCallbackGenSetup():
            nonlocal portCommand, sentMessages
            counter = 0
            message, relayMessage = yield
            assert message == portCommand
            assert relayMessage is True
            while True:
                message, relayMessage = yield
                if sentMessages[counter][0] is not None: ## then it is a request
                    assert message == sentMessages[counter][1]
                    assert relayMessage is False
                else: ## then it is a response
                    assert message == sentMessages[counter][1]
                    assert relayMessage is True

        gen = _stepCallbackGenSetup()
        next(gen)
        def stepCallback(message, relayMessage):
            nonlocal gen
            gen.send((message, relayMessage))

        timeout = 1.0
        serverSock = socket.socket()
        def mockServerConnect(proxyIP, proxyPort):
            serverSock.connect((proxyIP, proxyPort))
        
        threading.Timer(timeout/4, mockServerConnect, args=(proxyIP, proxyPort)).start()
        generatorCompletedExecution = stepThroughGenerator(subgenerator_wrapper, stepCallback, sentMessages, timeout=timeout, generatorFunctionArgs=args)

        assert generatorCompletedExecution is True
        assert outputStorageInstance.results["modifiedRequest"] == b"" ## We don't want to send the original message (as we have already sent a modified proxyPort message already!)
        assert outputStorageInstance.results["relayMessage"] is True
        assert outputStorageInstance.results["passedProcessing"] is True
        assert outputStorageInstance.results["activeProxyToServerSock"].getpeername() == serverSock.getsockname()  ## i.e. the socket is connected


class Test_FTPDataConnInterceptor_Integration:
    ## System Test setup
    ## - We need on the system side:
    ##      - a proxy server
    ##      - a data conn interceptor hooked into proxy server
    ##      - a real ftp server
    ## - We need on the client side:
    ##      - a client conn socket
    ##      - a data conn socket

    ## We can make this a unit test setup
    ## - We would need to replace on the system side:
    ##      - a proxyTunnel (control)
    ##          - buffer
    ##          - data conn hook
    ##      - a selector (proxyServer)
    ##      - query the selector to get the proxyTunnel (data)
    ##          - proxyTunnel (data)
    ##              - buffer
    ##              - no data conn hook

    # def _simulateCommSequence(self, commSquence: Tuple[bytes], fpi: FTPDataConnectionHandler) -> List[bytes]:

    #     cs = FTPClientSimulator()
    #     clientSock = socket.socket()
    #     clientSock.connect(("127.0.0.1", 21))
    #     password = os.environ["SI_FTP_PASSWORD"]
    #     pprint.pprint(cs.simulateCommSequence(clientSock, commSequence, dataSequence, 0.25))



    ## Here we are going to test both pasv and port connections
    ## let's consider the test cases

    ## - issue a port command
    ##      - are connections valid?
    ## - issue a pasv command
    ##      - are connections made?
    
    ## - issue a abort command

    ## - issue a port then abort
    ## - issue a pasv then abort

    ## - for each of the above, execute a port (2x)
    ## - for each of the above, execute a pasv (2x)

    ## - issue a port, then a pasv (replace)
    ## - issue a pasv, then a port (replace)
    ## - issue a port, then a port (double)
    ## - issue a pasv, then a pasv (double)

    ## - for each of the above, execute a abort afterwards (4x)

    ## - for each of the above, we want to insert random data commands between data commands


    ## NOTE: Honestly, we can fuzz this and have the test cases call the fuzzer
    ## - It's quite easy to figure out what the answer should be
    ## - Since we act as the client, it's easier to track what is sequentially called
    ## - e.g. a pasv and port should cancel out the previous connection

    ## - for each sequence of port/pasv/command
    ...


class Test_FTPDataConnInterceptor_E2E:
    ...