import re
import sys
import types
import inspect
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, NamedTuple, Sequence, Tuple, Any, Union, Optional

from _exceptions import *
proxyHandlerDescriptor = NamedTuple("ProxyHandlerData", [("PROXY_HOST", str), ("PROXY_PORT", int), ("StreamInterceptor", object)])


## TODO: Use ABCs to create abstract class
## NOTE: We will subclass this for the Stream Interceptor
## NOTE: This should be performed on a per protocol basis!!!
class StreamInterceptor:
    ## NOTE: This needs to rewrite any requests to the real server

    class Hook:
        def __init__(self, server: Optional["TCPProxyServer"] = None, buffer: Optional["Buffer"] = None):
            self.buffer = buffer
            self.server = server

        def __call__(self, chunk: bytes) -> Any:
            raise NotImplementedError

    class ClientToServerHook(Hook): ...

    class ServerToClientHook(Hook): ...


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

## TODO: We will rewrite this Buffer so that it has the functionality to be non-transparent
## - We will have two new values _incomingData, and _outgoingData,
## - The pop() and read() methods will read from _outgoingData,
## - The write() method will write to _incomingData
## ==> write() will exec a method _execMessageParsing() which
##      - splits up messages (if necessary) - already done
##      - executes a processing and user hook on each of the parsed messages - already done
##          - These hooks need to be modified to allow manipulation of data!
##          - The processing hook should be used to manipulate
##      - when popping() from the message queue, we need to write this to _outgoingData - NOT Done


## TODO: Fix mixing between bytearray and byte types!!!
## TODO: Fix incorrectly assigned methods of being private vs public
@dataclass
class Buffer:
    MESSAGE_DELIMITERS: List[bytes] = field(init=True)
    _incomingData: bytearray = field(init=False, default_factory=bytearray)
    _outgoingData: bytearray = field(init=False, default_factory=bytearray)
    _messages: deque[bytes] = field(init=False, default_factory=deque)
    _releasableBytes: int = sys.maxsize ## As long as _releasableBytes is larger than _MAX_BUFFER_SIZE, then any integer value should be ok
    _MAX_BUFFER_SIZE: int = 1024 * 128 ## 128Kb
    _nonTransparentHook: Callable[[bytes], Union[bytes, bool]] = lambda message: message
    _transparentHook: Callable[[bytes], None] = lambda message: None

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
        `buffer()._incomingData` (without popping)"""
        ## With the FTP proxy server, we want to slow-down replies (to force ordering)
        ## Therefore, we might read less bytes than anticipated
        ## We will still read from _incomingData, but we perform self._incomingData[:min(count, self._releasable)]
        ## This self._releasable enables proxies handlings protocols greater than L4 to slow the flow
        if count < 0:
            return self._outgoingData
        return self._outgoingData[:min(count, self._releasableBytes)]


    def pop(self, count: int = 0) -> bytes:
        """This pops bytes from the intercepted data stream
        buffer `buffer()._outgoingData` (from the left)"""
        if count < 0:
            count = len(self._outgoingData)
        ret = self.read(min(count, self._releasableBytes))
        del self._outgoingData[:min(count, self._releasableBytes)]
        return ret


    def write(self, chunk: bytearray) -> None:
        """Writes the received chunk to a intercepted data
        stream buffer - `buffer()._outgoingData`"""
        self._incomingData += chunk
        self._execMessageParsing()
        ## NOTE: In the future, we may want to provide an alternative method called _execStreamParsing()
        ## - This allows library users to bypass forcing parsing of streams into messages


    ############## Message Queue Operations ########################
    def pushToQueue(self, data: bytearray) -> None:
        """Pushes data as a currently parsed or a new message onto
        the message queue `buffer()._messages`"""
        ## NOTE: Added copies in case bytearray "data" is used in other manipulation
        ## if the messages queue is empty
        self._messages.append(data[:])
        return None
        

    def popFromQueue(self) -> bytearray:
        """This pops a complete message from the bottom of the queue 
        (if a complete message exists)"""
        if not len(self._messages):
            raise PopFromEmptyQueueError()
        return self._messages.popleft()


    def peakFromQueue(self) -> bytearray:
        """This peaks the message (complete/incomplete) at the top of
        the queue"""
        if not len(self._messages):
            raise PeakFromEmptyQueueError()
        return self._messages[-1]

    ############ Message Parsing and Hook Mechanisms ################
    def _execMessageParsing(self):
        ## Split up incoming data buffer into messages onto a queue
        delimiters = [m.end() for m in re.finditer(self.MESSAGE_DELIMITER_REGEX, self._incomingData)]
        leftIndex = 0
        for index in delimiters:
            rightIndex = index
            self.pushToQueue(self._incomingData[leftIndex:rightIndex])
            leftIndex = rightIndex

        ## Remove data that was parsed into messages on a queue (data will flow from the queue to Buffer._outgoingData)
        self._incomingData = self._incomingData[leftIndex:]

        ## Execute hooks on each message on this queue (all messages are delimited on this queue)
        for _ in range(len(self._messages)):
            message = self._messages[0]
            ## we execute the message hook
            modifiedMessage, continueProcessing = self._executeHooks(message)
            if continueProcessing:
                ## we pop the message from queue
                self._messages.popleft()
                ## we write it to the outgoing byte stream
                self._outgoingData += modifiedMessage
            else:
                ## otherwise we stop processing and sending out messages
                break
        
        return None

    def _executeHooks(self, message) -> Tuple[Optional[bytes], bool]:
        continueProcessing = False
        modifiedMessage = self._executeHook(self._nonTransparentHook, message)
        if modifiedMessage is None:
            return modifiedMessage, continueProcessing
        self._executeHook(self._transparentHook, message)
        ## True means execute userHook on message and continue
        ## to execute hooks on subsequent messages in the queue
        continueProcessing = True
        return modifiedMessage, True


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

    def setNonTransparentHook(self, hook: Callable[["Buffer"], None], server: Optional["TCPProxyServer"] = None) -> None:
        """ This message hook returns true if the message should be consumed in the buffer, otherwise
        if it returns false, then the current message is not processed and neither are future messages.
        This works well for protocols that we wish to install hooks that benefit from forcing ordering of messages being sent
        NOTE: Depending on the protocols we end up supporting, we may need to redesign this system."""
        self._nonTransparentHook = hook(server=server, buffer=self)
        ## If it is a generator, we need to execute a single next() statement before we can perform .send() later
        ## This essentially execute the setup code which would correspond to __init__() in a functor
        if isinstance(self._nonTransparentHook, types.GeneratorType):
            next(self._nonTransparentHook)
        return None

    def setTransparentHook(self, hook: Callable[["Buffer"], None], server: Optional["TCPProxyServer"] = None) -> None:
        """This adds a message hook which is executed whenever a message is completely parsed from
        the message queue AND  is allowed by the transparent hook (which may order replies and responses
        between the client and server and manipulate incoming/outgoing data"""
        ## TODO: Find a better way to bind the hook function to this self obj instance
        self._transparentHook = hook(server=server, buffer=self)
        if isinstance(self._transparentHook, types.GeneratorType):
            next(self._transparentHook)
        return None
