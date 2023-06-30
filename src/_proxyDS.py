import re
import sys
import types
import inspect
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, NamedTuple, Sequence, Tuple, Any

from _exceptions import *
proxyHandlerDescriptor = NamedTuple("ProxyHandlerData", [("PROXY_HOST", str), ("PROXY_PORT", int), ("StreamInterceptor", object)])


## TODO: Use ABCs to create abstract class
## NOTE: We will subclass this for the Stream Interceptor
## NOTE: This should be performed on a per protocol basis!!!
class StreamInterceptor:
    ## NOTE: This needs to rewrite any requests to the real server
    @staticmethod
    def clientToServerHook(buffer: "Buffer", requestChunk: bytes) -> None:
        raise NotImplementedError

    ## NOTE: This needs to rewrite any responses back to the client
    @staticmethod
    def serverToClientHook(buffer: "Buffer", responseChunk: bytes) -> None:
        raise NotImplementedError


## The Buffer needs to be rewritten
## - It needs to be **aware** of the higher-level layer 7 messages


## BUG: There exist methods that manipulate both buffer._data and buffer._messages
## -- This should NOT be the case
## TODO: Fix these instances
## --> message parsing related methods should not manipulate the buffer._data
## NOTE: Additionally, it should not USE it
## --> Other methods (e.g. in ProxyTunnel class) will manipulate it
## Therefore there may be a race condition, where PT pops buffer._data
## before user
## --> any data previous to the received argument chunk should not be retrieved
## directly using buffer._data

@dataclass
class Buffer:
    MESSAGE_DELIMITERS: List[bytes] = field(init=True)
    _data: bytearray = field(init=False, default_factory=bytearray)
    _prevEndBuffer: bytearray = field(init=False, default_factory=bytearray)
    _messages: deque = field(init=False, default_factory=deque)
    _releasableBytes: int = sys.maxsize ## As long as _releasableBytes is larger than _MAX_BUFFER_SIZE, then any integer value should be ok
    _MAX_BUFFER_SIZE: int = 1024 * 128 ## 128Kb
    _processingHook: Callable[[bytes], bool] = lambda message: True
    _userHook: Callable[[bytes], None] = lambda message: None

    def __post_init__(self):
        self._validateDelimiters()
        self.MESSAGE_DELIMITER_REGEX: str = b"(" + b"|".join(self.MESSAGE_DELIMITERS) + b")"
        self.MAX_DELIMETER_LENGTH = max([len(delimiter) for delimiter in self.MESSAGE_DELIMITERS])

    def _validateDelimiters(self) -> None:
        """Validates that the delimiters are a list of bytestrings"""
        if not isinstance(self.MESSAGE_DELIMITERS, Sequence):
            raise IncorrectDelimitersTypeError(self.MESSAGE_DELIMITERS)

        if len(self.MESSAGE_DELIMITERS) == 0:
            raise EmptyDelimitersTypeError(self.MESSAGE_DELIMITERS)
        
        for delimiter in self.MESSAGE_DELIMITERS:
            if not isinstance(delimiter, bytes):
                raise IncorrectDelimiterTypeErrpr(delimiter)
            
        if len(set(self.MESSAGE_DELIMITERS)) != len(self.MESSAGE_DELIMITERS):
            raise DuplicateDelimitersError(self.MESSAGE_DELIMITERS)
            
        return None
    
    ############### Bytes Operations #######################
    def read(self, count: int = 0) -> bytes:
        """This reads bytes from the intercepted data stream
        `buffer()._data` (without popping)"""
        ## With the FTP proxy server, we want to slow-down replies (to force ordering)
        ## Therefore, we might read less bytes than anticipated
        ## We will still read from _data, but we perform self._data[:min(count, self._releasable)]
        ## This self._releasable enables proxies handlings protocols greater than L4 to slow the flow
        if count < 0:
            return self._data
        return self._data[:min(count, self._releasableBytes)]


    def pop(self, count: int = 0) -> bytes:
        """This pops bytes from the intercepted data stream
        buffer `buffer()._data` (from the left)"""
        if count < 0:
            count = len(self._data)
        ret = self.read(min(count, self._releasableBytes))
        del self._data[:min(count, self._releasableBytes)]
        return ret


    def write(self, chunk: bytearray) -> None:
        """Writes the received chunk to a intercepted data
        stream buffer - `buffer()._data`"""
        self._data += chunk
        self._execMessageParsing(chunk)


    ############## Message Queue Operations ########################
    def pushToQueue(self, data: bytearray, delimited: bool) -> None:
        """Pushes data as a currently parsed or a new message onto
        the message queue `buffer()._messages`"""
        ## NOTE: Added copies in case bytearray "data" is used in other manipulation
        ## if the messages queue is empty
        if len(self._messages) == 0:
            self._messages.append([data[:], delimited])
            return None

        ## if the messages queue is non-empty
        if self._messages[-1][1]:
            self._messages.append([data[:], delimited])
        else:
            self._messages[-1][0] += data
            self._messages[-1][1] = delimited
        return None
        

    def popFromQueue(self) -> Tuple[bytearray, bool]:
        """This pops a complete message from the bottom of the queue 
        (if a complete message exists)"""
        if not len(self._messages):
            raise PopFromEmptyQueueError()
        elif self._messages[0][1] is False:
            raise PopUndelimitedItemFromQueueError()

        return self._messages.popleft()


    def peakFromQueue(self) -> Tuple[bytearray, bool]:
        """This peaks the message (complete/incomplete) at the top of
        the queue"""
        if not len(self._messages):
            raise PeakFromEmptyQueueError()
        
        return self._messages[-1]


    ### Hooks
        
    def _execMessageParsing(self, chunk: bytearray) -> None:
        """This is a hook that executes whenever a new chunk has 
        been received"""
        ## NOTE: In here, we are able to split up the streams/chunks into messages

        offset = len(self._prevEndBuffer)
        chunk = self._prevEndBuffer + chunk

        ## NOTE: Great potential for optimization here
        ## --> This only works if the list of strings are ordred
        ## --> e.g. if an expression is encapsulating, then `\r\n` must come before `\r`
        ## BUG: There are unexplored cases that the below search would likely fail
        ## --> e.g. overlapping strings potentially:??
        ## TODO: Re-evaluate the search mechanism for correctness
        delimiters = [m.end() for m in re.finditer(self.MESSAGE_DELIMITER_REGEX, chunk)]

        ## If multiple delimeters were found in the chunk, then
        ## -- only the first message can be over multiple chunks
        ## -- the rest that have delimeters are not spread over multiple chunks
        ## -- the final piece of the chunk that has no delimeter can be spread over
        ##      --> this will be case 1 when the next chunk is recv()

        ## NOTE: It is important to take care of the index pointers
        ## -- as we pop from the buffer to send it to the target destination
        ## --> We need to readjust the pointer
        leftIndex = offset
        ## NOTE: The delimiter m.end() returns the char of index + 1 at the end of the search
        ## -- e.g. message\r\nhello would return the index of "h" after \r\n
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
            ## We then need to update the buffer (if the chunk is NOT complete (i.e. not delimited))
            ## NOTE: The buffer max size is MAX_DELIMITER_LEN - 1
            self._prevEndBuffer = chunk[max(len(chunk) - self.MAX_DELIMETER_LENGTH + 1, 0) :len(chunk)]
        else:
            self._prevEndBuffer = bytearray()

        ## At this point we must have SOMETHING in the queue
        ## All elements below the top have been delimited, so we can pass it to the messageHook
        while len(self._messages) - 1:
            message, _ = self._messages[0]
            ## we execute the message hook
            if self._executeHooks(message):
                ## we pop the message from queue
                message, _ = self._messages.popleft()
            else:
                ## if we receive False returned from _processingHook, we stop processing future messages 
                return None

        ## The top element isn't guaranteed to be finished
        ## --> Therefore we need to determine if it has been delimited
        message, isDelimited = self.peakFromQueue()
        if isDelimited:
            ## we execute the message hook
            if self._executeHooks(message):
                ## we pop the message from queue
                message, _ = self._messages.popleft()

        return None

    def _executeHooks(self, message) -> bool:
        if self._executeHook(self._processingHook, message) is False:
            return False
        self._executeHook(self._userHook, message)
        ## True means execute userHook on message and continue
        ## to execute hooks on subsequent messages in the queue
        return True


    def _executeHook(self, hook: Callable, message: bytes) -> Any:
        if isinstance(hook, types.GeneratorType):
            return hook.send(message)
        else:
            return hook(message)

    ## NOTE: Format required for hooks
    ## - Hooks need passed need to be objects that can be initialized with a 'buffer' object argument
    ##      - e.g. functools.partial, class, etc., or a combination of the previous
    ##      - if there are other parameters, ensure that they are filled in (e.g. using a functools.partial)
    ## - Once initialized, they need to accept a argument called 'bytes'

    ## NOTE: Recommended Format:
    ## Define a callable
    ## class hook:
    ##      def __init__(self, param=None, param2=None, param3=None, ..., buffer=None):
    ##          ...
    ##      def __call__(self, message: bytes) -> ...:
    ##          ...
    ##
    ## In program somewhere (outside of "Buffer" or "Tunnel context")
    ##  - h_partial = hook(param1=..., param2=..., param3=...)
    ##  - ... ## many of lines of code later
    ## Then pass it to the Buffer using the set<type>Hook methods provided, which will bind the callable to the buffer
    ##  - buffer.setProcessingHook(h_partial)   ## or
    ##  - buffer.setUserHook(h_partial)

    ## NOTE: Alternative Format
    ## def func(param=None, param2=None, param3=None, ..., buffer=None) -> Generator[None/bool, "bytes", None]:
    ##      ## execute code as you would in init
    ##      message = yield ## setup completes here, and following code executed are calls to the instantiated generator
    ##      while True:
    ##          ## execute some code
    ##           message = yield

    ## NOTE: Why not pass the buffer object upon each execution of the userHook/processingHook?
    ## - We could bind parameters outside tunnel and buffer variables to a basic function, and this would work
    ## - However, using this format allows us to use generators and callables that are more conducive to holding states than typical functions
    ##  in a much more contained manner

    ## NOTE: It is possible that the hook provided is a wrapper to a shared method, function, generator or functor used by multiple buffers
    ## e.g. both buffers in a tunnel can share underlying callables.

    def setProcessingHook(self, hook: Callable[["Buffer"], None]) -> None:
        """ This message hook returns true if the message should be consumed in the buffer, otherwise
        if it returns false, then the current message is not processed and neither are future messages.
        This works well for protocols that we wish to install hooks that benefit from forcing ordering of messages being sent
        NOTE: Depending on the protocols we end up supporting, we may need to redesign this system."""
        ## Method that should be overriden / set depending on protocol
        self._processingHook = hook(buffer=self)
        ## If it is a generator, we need to execute a single next() statement before we can perform .send() later
        ## This essentially execute the setup code which would correspond to __init__() in a functor
        if isinstance(self._processingHook, types.GeneratorType):
            next(self._processingHook)
        return None


    def setUserHook(self, hook: Callable[["Buffer"], None]) -> None:
        """This adds a message hook which is executed whenever a message is completely parsed from
        the message queue AND  is allowed by the protocol hook (which may order replies and responses
        between the client and server, that is conducive for programming with user Hooks)"""
        ## TODO: Find a better way to bind the hook function to this self obj instance
        self._userHook = hook(buffer=self)
        if isinstance(self._userHook, types.GeneratorType):
            next(self._userHook)
        return None
