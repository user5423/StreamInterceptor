import re
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, List, NamedTuple, Tuple

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


## The Buffer needs to be rewritten
## - It needs to be **aware** of the higher-level layer 7 requests



@dataclass
class RequestBuffer:
    _data: bytearray = field(init=False, default_factory=bytearray)
    _requests: deque = field(init=False, default_factory=deque)

    CR: str = "\r"
    LF: str = "\n"
    REQUEST_DELIMITERS = [] ## This needs to be overriden by a subclass

    def __post_init__(self):
        ## NOTE: We'll likely change the structure later
        if len(self.REQUEST_DELIMITERS):
            raise NotImplementedError("Cannot instantiate a requestBuffer object without subclassing")

        self.REQUEST_DELIMETER_REGEX: str = "(" + "|".join(self.REQUEST_DELIMITERS) + ")"
        self.MAX_DELIMETER_LENGTH = len(self.REQUEST_DELIMETERS)

    
    ############### Bytes Operations #######################
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
        ## NOTE: This isn't entirely correct anymore as this setHook should be handled by a subclass
        raise NotImplementedError


    ############## Request Queue Operations ########################
    def pushToQueue(self, data: bytearray, delimited: bool) -> None:
        ## if the requests queue is empty
        if len(self._requests):
            self._requests.append([data, delimited])
            return None

        ## if the requests queue is non-empty
        if self._requests[-1][1]:
            self._requests.append([data, delimited])
        else:
            self._requests[-1][0] += data
            self._requests[-1][1] = delimited
        return None
        

    def popFromQueue(self) -> List[bytearray, bool]:
        if not len(self._requests):
            raise IndexError("Cannot pop a request from empty buffer._requests deque")

        return self._requests.pop()

    def peakFromQueue(self) -> List[bytearray, bool]:
        if not len(self._requests):
            raise IndexError("Cannot peak a request from empty buffer._requests deque")
        
        return self._requests[-1]
