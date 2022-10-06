from atexit import register
import os
import selectors
import sys
import socket
from matplotlib import collections
import pytest

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyConnections, ProxyTunnel
from _proxyDS import StreamInterceptor
from _exceptions import *


class MockStreamInterceptor(StreamInterceptor):
    def __init__(self) -> None:
        self.REQUEST_DELIMITERS = [b"\r\n"]
    def clientToServerHook(self, requestChunk: bytes, buffer: "Buffer") -> None:
        return None

    def serverToClientHook(self, responseChunk: bytes, buffer: "Buffer") -> None:
        return None



class Test_ProxyConnections_Init:
    def test_default(self):
        with pytest.raises(TypeError) as excInfo:
            ProxyConnections()

        assert "PROXY_HOST" in str(excInfo.value)
        assert "PROXY_PORT" in str(excInfo.value)
        assert "streamInterceptor" in str(excInfo.value)

    def _assertValidInitialization(self, pc, PROXY_HOST, PROXY_PORT):
        assert pc.PROXY_HOST == PROXY_HOST
        assert pc.PROXY_PORT == PROXY_PORT
        assert StreamInterceptor in pc.streamInterceptor.__mro__
        assert pc.streamInterceptor.__mro__[0] != StreamInterceptor
        
    def test_proxyHost_validFQDN(self):
        PROXY_HOST, PROXY_PORT = "host.localhost", 80
        interceptor = MockStreamInterceptor
        with pytest.raises(ValueError) as excInfo:
            ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        
        assert "does not appear to be an IPv4 or IPv6 address" in str(excInfo.value)

    def test_proxyHost_invalidIPv4(self):
        PROXY_HOST, PROXY_PORT = "8.8.8", 80 ## Missing octect from address
        interceptor = MockStreamInterceptor
        with pytest.raises(ValueError) as excInfo:
            ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        assert "does not appear to be an IPv4 or IPv6 address" in str(excInfo.value)

    def test_proxyHost_validIPv4_publicAddress(self):
        PROXY_HOST, PROXY_PORT = "8.8.8.8", 80 ## Google DNS IPv4
        interceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv4_publicLocalInterface(self):
        PROXY_HOST, PROXY_PORT = "0.0.0.0", 80
        interceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPV4_localhostInterface(self):
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
        interceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv4_privateClassA(self): 
        PROXY_HOST, PROXY_PORT = "10.0.0.0", 80
        interceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv4_privateClassB(self):
        PROXY_HOST, PROXY_PORT = "172.16.0.0", 80
        interceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv4_privateClassC(self):
        PROXY_HOST, PROXY_PORT = "192.168.0.0", 80
        interceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)

    def test_proxyHost_invalidIPv6(self):
        PROXY_HOST, PROXY_PORT = "0:0:0:0:0:0", 80 ## missing octects from address
        interceptor = MockStreamInterceptor
        with pytest.raises(ValueError) as excInfo:
            ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        assert "does not appear to be an IPv4 or IPv6 address" in str(excInfo.value)

    def test_proxyHost_validIPv6_localhostAddress(self):
        PROXY_HOST, PROXY_PORT = "0:0:0:0:0:0:0:1", 80
        interceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv6_publicInterface(self):
        PROXY_HOST, PROXY_PORT = "0:0:0:0:0:0:0:0", 80
        interceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv6_publicAddress(self):
        PROXY_HOST, PROXY_PORT = "2001:4860:4860::8888", 80 ## Google DNS IPv6
        interceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv6_privateAddress(self):
        PROXY_HOST, PROXY_PORT = "fc00::", 80
        interceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)


    # def test_proxyPort_incorrectType(self):
    #     raise NotImplementedError()

    # def test_proxyPort_incorrectValue(self):
    #     raise NotImplementedError()



    def test_streamInterceptor_baseClass(self):
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
        streamInterceptor = StreamInterceptor
        with pytest.raises(TypeError) as excInfo:
            ProxyConnections(PROXY_HOST, PROXY_PORT, streamInterceptor)
        assert "A subclass of StreamInterceptor is required" in str(excInfo.value)

    def test_streamInterceptor_abstractSubclass_clientToServerHook(self):
        ## NOTE: There are still incomplete methods that haven't been overriden
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80

        class StreamInterceptor_incompleteClientToServerHook(MockStreamInterceptor):
            def __init__(self) -> None:
                self.serverToClientChunks = collections.deque([])

            def serverToClientHook(self, requestChunk: bytes, buffer: "Buffer") -> None:
                self.serverToClientChunks.append(requestChunk)

        streamInterceptor = StreamInterceptor
        with pytest.raises(TypeError) as excInfo:
            ProxyConnections(PROXY_HOST, PROXY_PORT, streamInterceptor)

        assert "Incomplete subclass" in str(excInfo.value)
        assert "clientToServerHook()" in str(excInfo.value)

    def test_streamInterceptor_abstractSubclass_ServerToClientHook(self):
        ## NOTE: There are still incomplete methods that haven't been overriden
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80

        class StreamInterceptor_incompleteServerToClientHook(MockStreamInterceptor):
            def __init__(self) -> None:
                self.clientToServerChunks = collections.deque([])

            def clientToServerHook(self, requestChunk: bytes, buffer: "Buffer") -> None:
                self.clientToServerChunks.append(requestChunk)

        streamInterceptor = StreamInterceptor_incompleteServerToClientHook
        with pytest.raises(TypeError) as excInfo:
            ProxyConnections(PROXY_HOST, PROXY_PORT, streamInterceptor)

        assert "Incomplete subclass" in str(excInfo.value)
        assert "clientToServerHook()" in str(excInfo.value)

    def test_streamInterceptor_completeSubclass(self):
        ## NOTE: There are no incomplete request hooks
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
        streamInterceptor = MockStreamInterceptor
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, streamInterceptor)
        self._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT)


@pytest.fixture
def createPC():
    PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
    streamInterceptor = MockStreamInterceptor
    pc = ProxyConnections(PROXY_HOST, PROXY_PORT, streamInterceptor)
    return pc, PROXY_HOST, PROXY_PORT, streamInterceptor



class Test_ProxyConnections_operations:
    ## NOTE: At the point of creation of ProxyTunnel
    ## the sockets are bound and connected

    def _createTunnel(self):
        s1 = socket.socket()
        server2 = socket.create_server(("127.0.0.1", 8888))
        s1.connect(("127.0.0.1", 8888))
        s2, _ = server2.accept()
        server2.close()

        s3 = socket.socket()
        server4 = socket.create_server(("127.0.0.1", 8889))
        s3.connect(("127.0.0.1", 8889))
        s4, _ = server4.accept()
        server4.close()

        return s1, s2, s3, s4

    def _closeSockets(self, *sockets):
        for socket in sockets:
            socket.close()


    def _createPT(self, pc, socks):
        s1, s2, s3, s4 = self._createTunnel()
        socks.extend([s1,s2,s3,s4])
        pt = ProxyTunnel(s2, s3, MockStreamInterceptor)
        pc._put(s2, pt)
        pc._put(s3, pt)
        return pt, s2, s3

    ## get() request
    def test_get_noTunnelRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        s = socket.socket()
        assert pc.get(s) == None
        assert pc.PROXY_HOST == PROXY_HOST
        assert pc.PROXY_PORT == PROXY_PORT
        assert pc.streamInterceptor == streamInterceptor

    def test_get_singleTunnelRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        s1, s2, s3, s4 = self._createTunnel()

        try:
            pt = ProxyTunnel(s2, s3, MockStreamInterceptor)
            
            pc._sock[s2] = pt
            pc._sock[s3] = pt

            assert pc.get(s2) == pt
            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
        except Exception as e:
            self._closeSockets(s1, s2, s3, s4)
            raise e

    def test_get_multipleTunnelsRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        
        tunnelsNo = 5
        socks = []
        managedSocks = []
        proxyTunnels = []
        try:
            for _ in range(tunnelsNo):
                s1, s2, s3, s4 = self._createTunnel()
                pt = ProxyTunnel(s2, s3, MockStreamInterceptor)
            
                pc._sock[s2] = pt
                pc._sock[s3] = pt

                socks.extend([s1,s2,s3,s4])
                managedSocks.extend([s2,s3])
                proxyTunnels.append(pt)

            assert len(managedSocks) == tunnelsNo * 2
            for index, sock in enumerate(managedSocks):
                pt = proxyTunnels[index//2]
                assert pc.get(sock) == pt
                assert pc.PROXY_HOST == PROXY_HOST
                assert pc.PROXY_PORT == PROXY_PORT
                assert pc.streamInterceptor == streamInterceptor

        except Exception as e:
            self._closeSockets(*socks)
            raise e



    def test_createTunnel_noTunnelsRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        socks = []

        try:
            s1, s2, s3, s4 = self._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pt = pc.createTunnel(s2, s3)
            assert isinstance(pt, ProxyTunnel)

            assert len(pc._sock) == 2
            assert len(pc.selector.get_map()) == 2
            assert pc.get(s2) == pc.get(s3)

            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
        except Exception as e:
            self._closeSockets(*socks)
            raise e

        

    def test_createTunnel_singleTunnelRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        expectedSelectorEvent = selectors.EVENT_READ | selectors.EVENT_WRITE
        socks = []

        try:
            s1, s2, s3, s4 = self._createTunnel()
            socks.extend([s1,s2,s3,s4])
            s1, s2_new, s3_new, s4 = self._createTunnel()
            socks.extend([s1,s2_new,s3_new,s4])

            pt = pc.createTunnel(s2, s3)
            assert isinstance(pt, ProxyTunnel)

            pt = pc.createTunnel(s2_new, s3_new)
            assert isinstance(pt, ProxyTunnel)

            assert len(pc._sock) == 4
            assert len(pc.selector.get_map()) == 4
            assert pc.get(s2) == pc.get(s3)
            assert pc.get(s2_new) == pc.get(s3_new)

            for sock in (s2, s3, s2_new, s3_new):
                selectorKey = pc.selector.get_key(sock)
                assert selectorKey.data == "connection"
                assert selectorKey.events == expectedSelectorEvent

            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
        except Exception as e:
            self._closeSockets(*socks)
            raise e


    def test_createTunnel_multipleTunnelsRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        expectedSelectorEvent = selectors.EVENT_READ | selectors.EVENT_WRITE
        socks = []
        registeredSocks = []
        tunnels = 10

        try:
            for _ in range(tunnels):
                s1, s2, s3, s4 = self._createTunnel()
                socks.extend([s1,s2,s3,s4])
                registeredSocks.extend([s2,s3])
                pt = pc.createTunnel(s2, s3)
                assert isinstance(pt, ProxyTunnel)
                assert pc.get(s2) == pc.get(s3)

            for sock in registeredSocks:
                selectorKey = pc.selector.get_key(sock)
                assert selectorKey.data == "connection"
                assert selectorKey.events == expectedSelectorEvent

            assert len(pc._sock) == tunnels*2
            assert len(pc.selector.get_map()) == tunnels*2

            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
        except Exception as e:
            self._closeSockets(*socks)
            raise e


    def test_createTunnel_alreadyRegisteredSocket_clientToProxy(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        expectedSelectorEvent = selectors.EVENT_READ | selectors.EVENT_WRITE
        socks = []

        try:
            s1, s2, s3, s4 = self._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pc.createTunnel(s2, s3)

            s1, _, s3_new, s4 = self._createTunnel()
            socks.extend([s1,s2,s3,s4])

            with pytest.raises(AlreadyRegisteredSocketError) as excInfo:
                pc.createTunnel(s2, s3_new)

            assert "already registered" in str(excInfo.value)
            assert "clientToProxy" in str(excInfo.value)
            
            ## This should be registered in the original successful createTunnel call
            for sock in (s2, s3):
                selectorKey = pc.selector.get_key(sock)
                assert selectorKey.data == "connection"
                assert selectorKey.events == expectedSelectorEvent

            ## Since createTunnel call failed, it should never register this socket
            with pytest.raises(KeyError):
                pc.selector.get_key(s3_new)

            assert len(pc._sock) == 2
            assert len(pc.selector.get_map()) == 2

            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
        except Exception as e:
            self._closeSockets(*socks)
            raise e


    def test_createTunnel_alreadyRegisteredSocket_proxyToServer(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        socks = []

        try:
            s1, s2, s3, s4 = self._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pc.createTunnel(s2, s3)

            s1, s2, _, s4 = self._createTunnel()
            socks.extend([s1,s2,s3,s4])

            with pytest.raises(AlreadyRegisteredSocketError) as excInfo:
                pc.createTunnel(s2, s3)

            assert "already registered" in str(excInfo.value)
            assert "proxyToServer" in str(excInfo.value)
            
            assert len(pc._sock) == 2
            assert len(pc.selector.get_map()) == 2

            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
        except Exception as e:
            self._closeSockets(*socks)
            raise e


    def test_closeTunnel_notRegisteredTunnel(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        socks = []

        try:
            s1, s2, s3, s4 = self._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pt = ProxyTunnel(s2, s3, streamInterceptor)

            with pytest.raises(KeyError) as excInfo:
                pc.closeTunnel(pt)

            assert "not registered" in str(excInfo.value)
            assert "ProxyTunnel" in str(excInfo.value)

            assert len(pc._sock) == 0
            assert len(pc.selector.get_map()) == 0

            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
        except Exception as e:
            self._closeSockets(*socks)
            raise e

    def test_closeTunnel_registeredTunnel(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        socks = []

        try:
            s1, s2, s3, s4 = self._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pt = pc.createTunnel(s2, s3)

            ret = pc.closeTunnel(pt)

            assert ret is None
            assert pt.clientToProxySocket not in pc._sock
            assert pt.proxyToServerSocket not in pc._sock
            
            ## These sockets should be unregistered 
            ## NOTE: The sockets are closed so attempting to get key
            ## results in .get(fd=-1) which is invalid value
            ## --> hence ValueError is raised instead of KeyError
            for sock in (s2, s3):
                with pytest.raises(ValueError):
                    pc.selector.get_key(sock)

            assert len(pc._sock) == 0
            assert len(pc.selector.get_map()) == 0

            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
            
        except Exception as e:
            self._closeSockets(*socks)
            raise e

    def test_closeAllTunnels_noTunnel(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        socks = []

        try:
            pc.closeAllTunnels()

            assert len(pc._sock) == 0
            assert len(pc.selector.get_map()) == 0

            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
        except Exception as e:
            self._closeSockets(*socks)
            raise e

    def test_closeAllTunnels_singleTunnel(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        socks = []

        try:
            s1, s2, s3, s4 = self._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pc.createTunnel(s2,s3)

            ret = pc.closeAllTunnels()

            assert ret is None

            assert len(pc._sock) == 0
            assert len(pc.selector.get_map()) == 0

            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
        except Exception as e:
            self._closeSockets(*socks)
            raise e

    def test_closeAllTunnels_manyTunnels(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor = createPC
        socks = []
        tunnels = 10
        try:
            for _ in range(tunnels):
                s1, s2, s3, s4 = self._createTunnel()
                socks.extend([s1,s2,s3,s4])
                pc.createTunnel(s2,s3)

            pc.closeAllTunnels()

            assert len(pc._sock) == 0
            assert len(pc.selector.get_map()) == 0

            assert pc.PROXY_HOST == PROXY_HOST
            assert pc.PROXY_PORT == PROXY_PORT
            assert pc.streamInterceptor == streamInterceptor
        except Exception as e:
            self._closeSockets(*socks)
            raise e

    

## TODO: Take a look at the method ProxyConnections.setupProxyToServerSocket
## -- Should this be here??
## Isn't the whole point of ProxyConnections to be a dict-like object
## ==> Therefore it probably shouldn't handle connection setup
## NOTE: Maybe move it over to TCPProxyServer class
    

