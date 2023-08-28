import collections
import typing
import pytest

# from ftp_proxyinterceptor import FTPProxyInterceptor
import inspect
import os
import sys
import socket
import pprint
from typing import Tuple, Generator, List
sys.path.insert(0, os.path.join("src"))
sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, os.path.join("..", "..", "src"))
sys.path.insert(0, os.path.join("tests", "testhelper"))
# sys.path.insert(0, os.path.join("..", "tests", "testhelper"))
from ftp_proxyinterceptor import FTPProxyInterceptor, FTPInterceptorHelperMixin, FTPLoginProxyInterceptor, FTPDataConnectionHandler
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




class Test_FTPDataConnInterceptor_Helpers:
    ## Here we are testing the data conn interceptor which should handle correctly setting up 
    ...

class Test_FTPDataConnInterceptor_E2E:
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