from _proxyDS import ProxyInterceptor, Buffer


## NOTE: This is not intended to work robustly - this is just a code that is meant to show an example
class HTTPProxyInterceptor(ProxyInterceptor):
    def clientToServerHook(self, requestChunk: bytes, buffer: "Buffer") -> None:
        buffer._data = buffer._data.replace(b"0.0.0.0:8080", b"127.0.0.1:80")

    def serverToClientHook(self, requestChunk: bytes, buffer: "Buffer") -> bytes:
        buffer._data = buffer._data.replace(b"127.0.0.1:80", b"0.0.0.0:8080")

