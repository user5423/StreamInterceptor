from dataclasses import dataclass, field
from typing import Callable, NamedTuple

proxyHandlerDescriptor = NamedTuple("ProxyHandlerData", [("PROXY_HOST", str), ("PROXY_PORT", int), ("StreamInterceptor", object)])


## TODO: Use ABCs to create abstract class
## NOTE: We will subclass this for the Stream Interceptor
## NOTE: This should be performed on a per protocol basis!!!
class ProxyInterceptor:
    ## NOTE: This needs to rewrite any requests to the real server
    def clientToServerHook(self, requestChunk: bytes, buffer: "Buffer") -> None:
         ...

    ## NOTE: This needs to rewrite any responses back to the client
    def serverToClientHook(self, responseChunk: bytes, buffer: "Buffer") -> None:
         ...


@dataclass
class Buffer:
    _data: bytearray = field(init=False, default_factory=bytearray)


    def read(self, bytes: int = 0) -> bytes:
        if bytes <= 0:
            return self._data
        return self._data[max(len(self._data) - bytes, 0):]


    def pop(self, bytes: int = 0) -> bytes:
        if bytes <= 0:
            self._data = bytearray()
        self._data = self._data[:min(len(self._data) - bytes, 0)]


    def write(self, chunk: bytearray) -> None:
        self._data += chunk
        self.execWriteHook(chunk)


    def execWriteHook(self, chunk: bytearray) -> None:
        return self._writeHook(chunk, self)


    def setHook(self, hook: Callable[[bytearray, "Buffer"], None]) -> None:
        self._writeHook = hook
        

    def _writeHook(chunk: bytearray, buffer: "Buffer") -> None:
        ## NOTE: This method should be overriden by the Buffer.setHook method
        raise NotImplementedError