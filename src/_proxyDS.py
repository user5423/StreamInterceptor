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


    ################## Write Hook  ######################
    def _writeHook(self, chunk: bytearray) -> None:
        """This is a hook that should execute whenever a new chunk has been received"""

        ## NOTE: In here, we are able to split up the streams/chunks into requests

        ## If a delimeter is greater than size 1, then it is possible that it is spread over
        ## multiple chunks (so we need to check this by adding bytes from previous chunks)
        offset = 0
        if self.MAX_DELIMETER_LENGTH > 1:
            chunk = self._data[-(self.MAX_DELIMETER_LENGTH+1):] + self._data
            offset = self.MAX_DELIMETER_LENGTH-1

        ## NOTE: Great potential for optimization here
        ## --> This only works if the list of strings are ordred
        ## --> e.g. if an expression is encapsulating, then `\r\n` must come before `\r`
        ## BUG: There are unexplored cases that the below search would likely fail
        ## --> e.g. overlapping strings potentially:??
        ## TODO: Re-evaluate the search mechanism for correctness
        delimiters = [m.end() for m in re.finditer(self.REQUEST_DELIMETER_REGEX, chunk)]
        
        ## If multiple delimeters were found in the chunk, then
        ## -- only the first request can be over multiple chunks
        ## -- the rest that have delimeters are not spread over multiple chunks
        ## -- the final piece of the chunk that has no delimeter can be spread over
        ##      --> this will be case 1 when the next chunk is recv()

        ## NOTE: It is important to take care of the index pointers
        ## -- as we pop from the buffer to send it to the target destination
        ## --> We need to readjust the pointer
        leftIndex = 0
        for index in delimiters:
            ## we have the offset stored that we subtract
            rightIndex = (index - offset)
            ## we store the substring into the queue
            self.pushToQueue(chunk[leftIndex:rightIndex+1], True)
            ## we update the leftIndex
            leftIndex = rightIndex + 1

        ## If there is any remaining piece of the chunk that isn't delimited
        if (len(chunk) - leftIndex) > 1:
            self.pushToQueue(chunk[leftIndex:], False)

        ## At this point we must have SOMETHING in the queue
        ## All elements below the top have been delimited, so we can pass it to the requestHook
        while len(self._requests) - 1:
            request, _ = self._requests.pop()
            self._requestHook(request)

        ## The top element isn't guaranteed to be finished
        ## --> Therefore we need to determine if it has been delimited
        _, isDelimited = self.peakFromQueue()
        if isDelimited:
            self.peakFromQueue()
            self._requestHook(request)

        return None


    ##################### Request Hook ###################
    def _requestHook(self, request: bytearray) -> None:
        ...