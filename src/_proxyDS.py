import re
import functools
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, NamedTuple, Sequence, Tuple

from _exceptions import *
proxyHandlerDescriptor = NamedTuple("ProxyHandlerData", [("PROXY_HOST", str), ("PROXY_PORT", int), ("StreamInterceptor", object)])


## TODO: Use ABCs to create abstract class
## NOTE: We will subclass this for the Stream Interceptor
## NOTE: This should be performed on a per protocol basis!!!
class StreamInterceptor:
    ## NOTE: This needs to rewrite any requests to the real server
    def clientToServerHook(self, requestChunk: bytes, buffer: "Buffer") -> None:
        raise NotImplementedError

    ## NOTE: This needs to rewrite any responses back to the client
    def serverToClientHook(self, responseChunk: bytes, buffer: "Buffer") -> None:
        raise NotImplementedError


## The Buffer needs to be rewritten
## - It needs to be **aware** of the higher-level layer 7 requests


## NOTE: ERROR!!!!!
## NOTE: WARNING!!!!
## BUG: There exist methods that manipulate both buffer._data and buffer._requests
## -- This should NOT be the case
## TODO: Fix these instances
## --> Request parsing related methods should not manipulate the buffer._data
## NOTE: Additionally, it should not USE it
## --> Other methods (e.g. in ProxyTunnel class) will manipulate it
## Therefore there may be a race condition, where PT pops buffer._data
## before user 
## --> any data previous to the received argument chunk should not be retrieved
## directly using buffer._data

@dataclass
class Buffer:
    REQUEST_DELIMITERS: List[bytes] = field(init=True)
    _data: bytearray = field(init=False, default_factory=bytearray)
    _requests: deque = field(init=False, default_factory=deque)
    _MAX_BUFFER_SIZE: int = 1024 * 128 ## 128Kb

    def __post_init__(self):
        # ## NOTE: We'll likely change the structure later
        # if len(self.REQUEST_DELIMITERS):
        #     raise NotImplementedError("Cannot instantiate a requestBuffer object without subclassing")
        self._validateDelimiters()
        self.REQUEST_DELIMETER_REGEX: str = b"(" + b"|".join(self.REQUEST_DELIMITERS) + b")"
        self.MAX_DELIMETER_LENGTH = max([len(delimiter) for delimiter in self.REQUEST_DELIMITERS])


    def _validateDelimiters(self) -> None:
        """Validates that the delimiters are a list of bytestrings"""
        if not isinstance(self.REQUEST_DELIMITERS, Sequence):
            raise IncorrectDelimitersTypeError(self.REQUEST_DELIMITERS)

        if len(self.REQUEST_DELIMITERS) == 0:
            raise EmptyDelimitersTypeError(self.REQUEST_DELIMITERS)
        
        for delimiter in self.REQUEST_DELIMITERS:
            if not isinstance(delimiter, bytes):
                raise IncorrectDelimiterTypeErrpr(delimiter)
            
        if len(set(self.REQUEST_DELIMITERS)) != len(self.REQUEST_DELIMITERS):
            raise DuplicateDelimitersError(self.REQUEST_DELIMITERS)
            
        return None
    
    ############### Bytes Operations #######################
    def read(self, bytes: int = 0) -> bytes:
        """This reads bytes from the intercepted data stream
        `buffer()._data` (without popping)"""
        if bytes < 0:
            return self._data
        return self._data[:bytes]


    def pop(self, bytes: int = 0) -> bytes:
        """This pops bytes from the intercepted data stream
        buffer `buffer()._data` (from the left)"""
        if bytes < 0:
            bytes = len(self._data)
        ret = self.read(bytes)
        del self._data[:bytes]
        return ret


    def write(self, chunk: bytearray) -> None:
        """Writes the received chunk to a intercepted data
        stream buffer - `buffer()._data`"""
        self._data += chunk
        self._execRequestParsing(chunk)


    def setHook(self, hook: Callable[["Buffer", bytearray], None]) -> None:
        """This binds a request hook which is executed whenever
        a request is completely parsed from the request queue 
        `buffer()._requests`"""
        ## TODO: Find a better way to bind the hook function to this self obj instance
        self._requestHook = functools.partial(hook, self)
        

    ############## Request Queue Operations ########################
    def pushToQueue(self, data: bytearray, delimited: bool) -> None:
        """Pushes data as a currently parsed or a new request onto
        the request queue `buffer()._requests`"""
        ## NOTE: Added copies in case bytearray "data" is used in other manipulation
        ## if the requests queue is empty
        if len(self._requests) == 0:
            self._requests.append([data[:], delimited])
            return None

        ## if the requests queue is non-empty
        if self._requests[-1][1]:
            self._requests.append([data[:], delimited])
        else:
            self._requests[-1][0] += data
            self._requests[-1][1] = delimited
        return None
        

    def popFromQueue(self) -> Tuple[bytearray, bool]:
        """This pops a complete request from the bottom of the queue 
        (if a complete request exists)"""
        if not len(self._requests):
            raise PopFromEmptyQueueError()
        elif self._requests[0][1] is False:
            raise PopUndelimitedItemFromQueueError()

        return self._requests.popleft()


    def peakFromQueue(self) -> Tuple[bytearray, bool]:
        """This peaks the request (complete/incomplete) at the top of
        the queue"""
        if not len(self._requests):
            raise PeakFromEmptyQueueError()
        
        return self._requests[-1]


    ################## Write Hook  ######################
    def _execRequestParsing(self, chunk: bytearray) -> None:
        """This is a hook that executes whenever a new chunk has 
        been received"""
        ## BUG: There is still an opportunity for a race condition if `buffer.pop`
        ## is called concurrently with the `buffer.write()` method
        ## ==> This needs to be resolved
        
        ## NOTE: In here, we are able to split up the streams/chunks into requests

        ## If a delimeter is greater than size 1, then it is possible that it is spread over
        ## multiple chunks (so we need to check this by adding bytes from previous chunks)
        offset = 0

        if self.MAX_DELIMETER_LENGTH > 1:
            offset = len(self._data[-(self.MAX_DELIMETER_LENGTH+len(chunk)):-len(chunk)])
            chunk = self._data[-(offset+len(chunk)):-len(chunk)] + chunk

        ## NOTE: Great potential for optimization here
        ## --> This only works if the list of strings are ordred
        ## --> e.g. if an expression is encapsulating, then `\r\n` must come before `\r`
        ## BUG: There are unexplored cases that the below search would likely fail
        ## --> e.g. overlapping strings potentially:??
        ## TODO: Re-evaluate the search mechanism for correctness
        delimiters = [m.end() for m in re.finditer(self.REQUEST_DELIMETER_REGEX, chunk)]
        # print(delimiters)
        # if delimiters != []:
        #     print(chunk[delimiters[0] + offset])
        ## If multiple delimeters were found in the chunk, then
        ## -- only the first request can be over multiple chunks
        ## -- the rest that have delimeters are not spread over multiple chunks
        ## -- the final piece of the chunk that has no delimeter can be spread over
        ##      --> this will be case 1 when the next chunk is recv()

        ## NOTE: It is important to take care of the index pointers
        ## -- as we pop from the buffer to send it to the target destination
        ## --> We need to readjust the pointer
        leftIndex = offset
        ## NOTE: The delimiter m.end() returns the char of index + 1 at the end of the search
        ## -- e.g. request\r\nhello would return the index of "h" after \r\n
        for index in delimiters:
            ## we have the offset stored that we subtract
            rightIndex = index
            ## we store the substring into the queue
            self.pushToQueue(chunk[leftIndex:rightIndex], True)
            ## we update the leftIndex
            leftIndex = rightIndex

        ## If there is any remaining piece of the chunk that isn't delimited
        if (len(chunk) - leftIndex) > 0:
            self.pushToQueue(chunk[leftIndex:], False)


        ## At this point we must have SOMETHING in the queue
        ## All elements below the top have been delimited, so we can pass it to the requestHook
        while len(self._requests) - 1:
            ## we pop the request from queue
            request, _ = self._requests.popleft()
            ## we execute the request hook
            self._requestHook(request)

        ## The top element isn't guaranteed to be finished
        ## --> Therefore we need to determine if it has been delimited
        _, isDelimited = self.peakFromQueue()
        if isDelimited:
            ## we pop the request from queue
            request, _ = self._requests.popleft()
            ## we execute the request hook
            self._requestHook(request)

        return None


    ##################### Request Hook ###################
    def _requestHook(self, request: bytearray) -> None:
        ## Method that should be overriden / set depending on protocol
        ...
