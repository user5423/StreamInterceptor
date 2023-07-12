import os
import selectors
import sys
import socket
import pytest
import collections
from typing import List
sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyConnections, ProxyTunnel
from _proxyDS import StreamInterceptor
from tests.testhelper.TestResources import PTTestResources
from _exceptions import *



class PCTestResources:
    @classmethod
    def _assertValidInitialization(cls, pc, PROXY_HOST, PROXY_PORT, selector) -> None:
        assert pc.PROXY_HOST == PROXY_HOST
        assert pc.PROXY_PORT == PROXY_PORT
        assert StreamInterceptor in pc.streamInterceptorType.__mro__
        assert pc.streamInterceptorType.__mro__[0] != StreamInterceptor
        assert pc.selector == selector

    @classmethod
    def _assertConstantAttributes(cls, pc, PROXY_HOST, PROXY_PORT, selector) -> None:
        cls._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT, selector)

    @classmethod
    def _assertClosedProxyConnections(cls, pc: ProxyConnections) -> None:
        ## All fd should not be registered
        assert len(pc._sock) == 0
        assert len(pc.selector.get_map()) == 0

    @classmethod
    def _assertOpenProxyConnections(cls, pc: ProxyConnections, pcDict: dict) -> None:
        assert len(pc._sock) == len(pcDict) * 2 
        for socket1, socket2 in pcDict.items():
            assert pc.get(socket1) == pc.get(socket2)

    @classmethod
    def _assertRegisteredProxySockets(cls, pc: ProxyConnections, registeredSocks: List[socket.socket]):
        assert len(pc._sock) == len(pc.selector.get_map()) == len(registeredSocks)
        expectedSelectorEvent = selectors.EVENT_READ | selectors.EVENT_WRITE
        for sock in registeredSocks:
            selectorKey = pc.selector.get_key(sock)
            assert selectorKey.data == "connection"
            assert selectorKey.events == expectedSelectorEvent

    @classmethod
    def _createTunnel(cls):
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

    @classmethod
    def _closeSockets(cls, *sockets):
        for socket in sockets:
            socket.close()


class Test_ProxyConnections_Init:
    ## Helper Method for testing host args
    def _assertValidHostArgs(self, PROXY_HOST, PROXY_PORT) -> None:
        interceptor, _ = PTTestResources.createMockStreamInterceptor()
        selector = selectors.DefaultSelector()
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor, selector)
        PCTestResources._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT, selector)

    ## Helper Method for testing host args
    def _assertInvalidHostArgs(self, PROXY_HOST, PROXY_PORT, errorMessageSnippet) -> None:
        interceptor, _ = PTTestResources.createMockStreamInterceptor()
        selector = selectors.DefaultSelector()
        with pytest.raises(ValueError) as excInfo:
            ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor, selector)
        assert errorMessageSnippet in str(excInfo.value)

    def test_default(self):
        with pytest.raises(TypeError) as excInfo:
            ProxyConnections()

        assert "PROXY_HOST" in str(excInfo.value)
        assert "PROXY_PORT" in str(excInfo.value)
        assert "streamInterceptor" in str(excInfo.value)
        assert "selector" in str(excInfo.value)
        
    def test_proxyHost_validFQDN(self):
        PROXY_HOST, PROXY_PORT = "host.localhost", 80
        errorMessageSnippet = "does not appear to be an IPv4 or IPv6 address"
        self._assertInvalidHostArgs(PROXY_HOST, PROXY_PORT, errorMessageSnippet)

    def test_proxyHost_invalidIPv4(self):
        PROXY_HOST, PROXY_PORT = "8.8.8", 80 ## Missing octect from address
        errorMessageSnippet = "does not appear to be an IPv4 or IPv6 address"
        self._assertInvalidHostArgs(PROXY_HOST, PROXY_PORT, errorMessageSnippet)

    def test_proxyHost_validIPv4_publicAddress(self):
        PROXY_HOST, PROXY_PORT = "8.8.8.8", 80 ## Google DNS IPv4
        self._assertValidHostArgs(PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv4_publicLocalInterface(self):
        PROXY_HOST, PROXY_PORT = "0.0.0.0", 80
        self._assertValidHostArgs(PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPV4_localhostInterface(self):
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
        self._assertValidHostArgs(PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv4_privateClassA(self): 
        PROXY_HOST, PROXY_PORT = "10.0.0.0", 80
        self._assertValidHostArgs(PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv4_privateClassB(self):
        PROXY_HOST, PROXY_PORT = "172.16.0.0", 80
        self._assertValidHostArgs(PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv4_privateClassC(self):
        PROXY_HOST, PROXY_PORT = "192.168.0.0", 80
        self._assertValidHostArgs(PROXY_HOST, PROXY_PORT)

    def test_proxyHost_invalidIPv6(self):
        PROXY_HOST, PROXY_PORT = "0:0:0:0:0:0", 80 ## missing octects from address
        errorMessageSnippet = "does not appear to be an IPv4 or IPv6 address"
        self._assertInvalidHostArgs(PROXY_HOST, PROXY_PORT, errorMessageSnippet)

    def test_proxyHost_validIPv6_localhostAddress(self):
        PROXY_HOST, PROXY_PORT = "0:0:0:0:0:0:0:1", 80
        self._assertValidHostArgs(PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv6_publicInterface(self):
        PROXY_HOST, PROXY_PORT = "0:0:0:0:0:0:0:0", 80
        self._assertValidHostArgs(PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv6_publicAddress(self):
        PROXY_HOST, PROXY_PORT = "2001:4860:4860::8888", 80 ## Google DNS IPv6
        self._assertValidHostArgs(PROXY_HOST, PROXY_PORT)

    def test_proxyHost_validIPv6_privateAddress(self):
        PROXY_HOST, PROXY_PORT = "fc00::", 80
        self._assertValidHostArgs(PROXY_HOST, PROXY_PORT)

    # def test_proxyPort_incorrectType(self):
    #     raise NotImplementedError()

    # def test_proxyPort_incorrectValue(self):
    #     raise NotImplementedError()



    def test_streamInterceptor_baseClass(self):
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
        interceptor = StreamInterceptor
        selector = selectors.DefaultSelector()
        with pytest.raises(AbstractStreamInterceptorError) as excInfo:
            ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor, selector)
        assert "A subclass of StreamInterceptor is required" in str(excInfo.value)

    def test_streamInterceptor_abstractSubclass_clientToServerHook(self):
        ## NOTE: There are still incomplete methods that haven't been overriden
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
        selector = selectors.DefaultSelector()
        serverToClientMessages = collections.deque([])
        class StreamInterceptor_incompleteClientToServerHook(StreamInterceptor):

            class ClientToServerHook(StreamInterceptor.Hook):
                def __call__(self, message):
                    nonlocal serverToClientMessages
                    serverToClientMessages.append(message)

        interceptor = StreamInterceptor_incompleteClientToServerHook
        with pytest.raises(TypeError) as excInfo:
            ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor, selector)

        assert "Incomplete subclass" in str(excInfo.value)
        assert "clientToServerHook()" in str(excInfo.value)

    def test_streamInterceptor_abstractSubclass_ServerToClientHook(self):
        ## NOTE: There are still incomplete methods that haven't been overriden
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
        selector = selectors.DefaultSelector()
        clientToServerMessages = collections.deque([])

        class StreamInterceptor_incompleteServerToClientHook(StreamInterceptor):

            class ClientToServerHook(StreamInterceptor.Hook):
                def __call__(self, message):
                    nonlocal clientToServerMessages
                    clientToServerMessages.append(message)

        interceptor = StreamInterceptor_incompleteServerToClientHook
        with pytest.raises(TypeError) as excInfo:
            ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor, selector)

        assert "Incomplete subclass" in str(excInfo.value)
        assert "clientToServerHook()" in str(excInfo.value)

    def test_streamInterceptor_completeSubclass(self):
        ## NOTE: There are no incomplete request hooks
        PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
        interceptor, _ = PTTestResources.createMockStreamInterceptor()
        selector = selectors.DefaultSelector()
        pc = ProxyConnections(PROXY_HOST, PROXY_PORT, interceptor, selector)
        PCTestResources._assertValidInitialization(pc, PROXY_HOST, PROXY_PORT, selector)


@pytest.fixture
def createPC():
    PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
    streamInterceptor, _ = PTTestResources.createMockStreamInterceptor()
    selector = selectors.DefaultSelector()
    pc = ProxyConnections(PROXY_HOST, PROXY_PORT, streamInterceptor, selector)
    return pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector



class Test_ProxyConnections_operations:
    ## NOTE: At the point of creation of ProxyTunnel
    ## the sockets are bound and connected

    ## get() request
    def test_get_noTunnelRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        PCTestResources._assertOpenProxyConnections(pc, {})
        PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)

    def test_get_singleTunnelRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        s1, s2, s3, s4 = PCTestResources._createTunnel()

        try:
            pt = ProxyTunnel(s2, s3, streamInterceptor)
            pc._sock[s2] = pt
            pc._sock[s3] = pt
            PCTestResources._assertOpenProxyConnections(pc, {s2:s3})
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)
        except Exception as e:
            PCTestResources._closeSockets(s1, s2, s3, s4)
            raise e

    def test_get_multipleTunnelsRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        tunnelsNo = 5
        socks = []
        managedSocks = []
        tunnelDict = {}
        
        try:
            for _ in range(tunnelsNo):
                s1, s2, s3, s4 = PCTestResources._createTunnel()
                pt = ProxyTunnel(s2, s3, streamInterceptor)
                pc._sock[s2] = pt
                pc._sock[s3] = pt
                socks.extend([s1,s2,s3,s4])
                managedSocks.extend([s2,s3])
                tunnelDict[s2] = s3

            PCTestResources._assertOpenProxyConnections(pc, tunnelDict)
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)

        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e

    def test_createTunnel_noTunnelsRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        socks = []

        try:
            s1, s2, s3, s4 = PCTestResources._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pt = pc.createTunnel(s2, s3)

            assert isinstance(pt, ProxyTunnel)
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)
            PCTestResources._assertOpenProxyConnections(pc, {s2:s3})
            PCTestResources._assertRegisteredProxySockets(pc, (s2, s3))
        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e

    def test_createTunnel_singleTunnelRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        socks = []

        try:
            ## Tunnel 1
            s1, s2, s3, s4 = PCTestResources._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pc.createTunnel(s2, s3), ProxyTunnel
            ## Tunnel 2
            s1_new, s2_new, s3_new, s4_new = PCTestResources._createTunnel()
            socks.extend([s1_new,s2_new,s3_new,s4_new])
            pc.createTunnel(s2_new, s3_new), ProxyTunnel
            
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)
            PCTestResources._assertOpenProxyConnections(pc, {s2:s3, s2_new: s3_new})
            PCTestResources._assertRegisteredProxySockets(pc, (s2, s3, s2_new, s3_new))
        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e

    def test_createTunnel_multipleTunnelsRegistered(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        socks = []
        registeredSocks = []
        tunnelDict = {}
        tunnels = 10

        try:
            for _ in range(tunnels):
                s1, s2, s3, s4 = PCTestResources._createTunnel()
                socks.extend([s1,s2,s3,s4])
                registeredSocks.extend([s2,s3])
                tunnelDict[s2] = s3
                assert isinstance(pc.createTunnel(s2, s3), ProxyTunnel)

            PCTestResources._assertOpenProxyConnections(pc, tunnelDict)
            PCTestResources._assertRegisteredProxySockets(pc, registeredSocks)
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)

        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e

    def test_createTunnel_alreadyRegisteredSocket_clientToProxy(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        socks = []

        try:
            ## Tunnel 1
            s1, s2, s3, s4 = PCTestResources._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pc.createTunnel(s2, s3)
            ## Tunnel 2
            s1_new, s2_new, s3_new, s4_new = PCTestResources._createTunnel()
            socks.extend([s1_new, s2_new, s3_new, s4_new])
            with pytest.raises(AlreadyRegisteredSocketError) as excInfo:
                pc.createTunnel(s2_new, s3_new)

            assert "already registered" in str(excInfo.value)
            assert "clientToProxy" in str(excInfo.value)
            ## Since the second createTunnel call failed, it should never register this socket
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)
            PCTestResources._assertOpenProxyConnections(pc, {s2:s3})
            PCTestResources._assertRegisteredProxySockets((s2, s3))

        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e

    def test_createTunnel_alreadyRegisteredSocket_proxyToServer(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        socks = []

        try:
            ## Tunnel 1
            s1, s2, s3, s4 = PCTestResources._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pc.createTunnel(s2, s3)
            ## Tunnel 2
            s1_new, s2_new, s3_new, s4_new = PCTestResources._createTunnel()
            socks.extend([s1_new,s2_new,s3_new,s4_new])
            with pytest.raises(AlreadyRegisteredSocketError) as excInfo:
                pc.createTunnel(s2, s3)

            assert "already registered" in str(excInfo.value)
            assert "proxyToServer" in str(excInfo.value)
            PCTestResources._assertOpenProxyConnections(pc, {s2:s3})
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)
        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e

    def test_closeTunnel_notRegisteredTunnel(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        socks = []

        try:
            s1, s2, s3, s4 = PCTestResources._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pt = ProxyTunnel(s2, s3, streamInterceptor)
            with pytest.raises(UnregisteredProxyTunnelError) as excInfo:
                pc.closeTunnel(pt)

            assert "not registered" in str(excInfo.value)
            assert "ProxyTunnel" in str(excInfo.value)
            PCTestResources._assertClosedProxyConnections(pc)
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)
        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e

    def test_closeTunnel_registeredTunnel(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        socks = []

        try:
            s1, s2, s3, s4 = PCTestResources._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pt = pc.createTunnel(s2, s3)
            ret = pc.closeTunnel(pt)

            assert ret is None
            PCTestResources._assertClosedProxyConnections(pc)
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)
        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e

    def test_closeAllTunnels_noTunnel(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        socks = []

        try:
            ret = pc.closeAllTunnels()
            
            assert ret is None
            PCTestResources._assertClosedProxyConnections(pc)
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)
        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e

    def test_closeAllTunnels_singleTunnel(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        socks = []

        try:
            s1, s2, s3, s4 = PCTestResources._createTunnel()
            socks.extend([s1,s2,s3,s4])
            pc.createTunnel(s2,s3)
            ret = pc.closeAllTunnels()

            assert ret is None
            PCTestResources._assertClosedProxyConnections(pc)
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)
        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e

    def test_closeAllTunnels_manyTunnels(self, createPC):
        pc, PROXY_HOST, PROXY_PORT, streamInterceptor, selector = createPC
        socks = []
        tunnels = 10
        try:
            for _ in range(tunnels):
                s1, s2, s3, s4 = PCTestResources._createTunnel()
                socks.extend([s1,s2,s3,s4])
                pc.createTunnel(s2,s3)

            ret = pc.closeAllTunnels()
            
            assert ret is None
            PCTestResources._assertClosedProxyConnections(pc)
            PCTestResources._assertConstantAttributes(pc, PROXY_HOST, PROXY_PORT, selector)
        except Exception as e:
            PCTestResources._closeSockets(*socks)
            raise e
