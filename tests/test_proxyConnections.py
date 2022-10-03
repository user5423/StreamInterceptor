import os
import sys
import pytest

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyConnections
from _proxyDS import StreamInterceptor


class MockStreamInterceptor(StreamInterceptor):
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
        raise NotImplementedError()

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



    # def test_streamInterceptor_incorrectType(self):
    #     raise NotImplementedError()


    # def test_streamInterceptor_abstractBase(self):
    #     raise NotImplementedError()


    # def test_streamInterceptor_subclass(self):
    #     raise NotImplementedError()



    

