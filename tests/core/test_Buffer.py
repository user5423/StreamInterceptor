import collections
import os
import sys

import functools
import pytest
from typing import Tuple, Dict

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from _proxyDS import Buffer, CommsDirection
from _exceptions import *

## Buffer Initiatialization

@pytest.fixture()
def defaultBuffer() -> Buffer:
    delimiters = [b"\r\n"]
    b = Buffer(delimiters, CommsDirection.CLIENT_TO_SERVER)
    return b


@pytest.fixture()
def nonparsingBuffer() -> Buffer:
    delimiters = [b"\r\n"]
    b = Buffer(delimiters, CommsDirection.CLIENT_TO_SERVER)
    b._execMessageParsing = lambda *args, **kwargs: None
    return b


## TODO: Write more tests for CommsDirection parameter
class Test_Buffer_Init:
    def test_default(self) -> None:
        ## NOTE: A default constructor is not allowed
        with pytest.raises(TypeError) as excInfo:
            Buffer()
            
        assert "MESSAGE_DELIMITERS" in str(excInfo.value)
        assert "COMMUNICATION_DIRECTION" in str(excInfo.value)
        
        
    def test_MessageDelimiters_incorrectType(self) -> None:
        MESSAGE_DELIMITERS = None
        with pytest.raises(IncorrectDelimitersTypeError) as excInfo:
            Buffer(MESSAGE_DELIMITERS, CommsDirection.CLIENT_TO_SERVER)
            
        assert "Incorrect type" in str(excInfo.value)
        assert "[i]" not in str(excInfo.value)   
        
        
    def test_MessageDelimiters_empty(self) -> None:
        MESSAGE_DELIMITERS = []
        with pytest.raises(EmptyDelimitersTypeError) as excInfo:
            Buffer(MESSAGE_DELIMITERS, CommsDirection.CLIENT_TO_SERVER)
            
        assert "Cannot pass empty" in str(excInfo.value)
        

    def test_MessageDelimiters_single(self) -> None:
        MESSAGE_DELIMITERS = [b"\r\n"]
        b = Buffer(MESSAGE_DELIMITERS, CommsDirection.CLIENT_TO_SERVER)
        assert b.MESSAGE_DELIMITERS == MESSAGE_DELIMITERS
        assert isinstance(b._incomingData, bytearray) and len(b._incomingData) == 0
        assert isinstance(b._outgoingData, bytearray) and len(b._outgoingData) == 0
        assert isinstance(b._messages, collections.deque) and len(b._messages) == 0
        
        
    def test_MessageDelimiters_many(self) -> None:
        ## NOTE: The order of the delimiters is important for when message can have multiple potential delimiters
        MESSAGE_DELIMITERS = [b"\r\n", b"\r"]
        b = Buffer(MESSAGE_DELIMITERS, CommsDirection.CLIENT_TO_SERVER)
        assert b.MESSAGE_DELIMITERS == MESSAGE_DELIMITERS
        assert isinstance(b._incomingData, bytearray) and len(b._incomingData) == 0
        assert isinstance(b._outgoingData, bytearray) and len(b._outgoingData) == 0
        assert isinstance(b._messages, collections.deque) and len(b._messages) == 0 
        
        
    def test_MessageDelimiters_duplicate(self) -> None:
        ## NOTE: Duplicates delimitesr are bad practice
        MESSAGE_DELIMITERS = [b"\r\n", b"\r", b"\r\n"]
        with pytest.raises(DuplicateDelimitersError) as excInfo:
            Buffer(MESSAGE_DELIMITERS, CommsDirection.CLIENT_TO_SERVER)
        
        assert "Duplicate" in str(excInfo.value)
        

    def test_MessageDelimiters_subsets(self) -> None:
        ## TODO: Our Buffer may reorder delimiters that are subsets of each other (need to evaluate feature)
        raise NotImplementedError()
    
    

class Test_Buffer_ByteOperations:
    ## read() tests
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be read is LESS than the number of current bytes stored in the buffer
    def test_read_negativeBytes(self, defaultBuffer):
        b = defaultBuffer
        b._outgoingData += bytearray(b"testdata")
        bufferLength = len(b._outgoingData)
        assert b.read(-1) == b._outgoingData
        assert bufferLength == len(b._outgoingData)

        
    def test_read_zeroBytes(self, defaultBuffer):
        b = defaultBuffer  
        b._outgoingData += bytearray(b"testdata")
        bufferLength = len(b._outgoingData)
        assert b.read(0) == b._outgoingData[0:0]
        assert bufferLength == len(b._outgoingData)

        
    def test_read_oneByte(self, defaultBuffer):
        b = defaultBuffer
        b._outgoingData += bytearray(b"testdata")
        bufferLength = len(b._outgoingData)
        assert b.read(1) == b._outgoingData[0:1]
        assert bufferLength == len(b._outgoingData)
        
        
    def test_read_manyBytes(self, defaultBuffer):
        b = defaultBuffer
        b._outgoingData += bytearray(b"testdata")
        bufferLength = len(b._outgoingData)
        readLength = bufferLength // 2
        assert b.read(readLength) == b._outgoingData[0:readLength]
        assert bufferLength == len(b._outgoingData)
        

    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be read EXCEEDS the number of current bytes stored in the buffer
    def test_read_negativeBytes_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        # b._outgoingData is initialized as empty bytearray()
        bufferLength = len(b._outgoingData)
        assert b.read(-1) == b._outgoingData
        assert bufferLength == len(b._outgoingData)


    def test_read_zeroBytes_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        ## NOTE: b._outgoingData is initialized as empty bytearray()
        bufferLength = len(b._outgoingData)
        assert b.read(0) == bytearray()
        assert bufferLength == 0
        

    def test_read_oneByte_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        ## NOTE: b._outgoingData is initialized as empty bytearray()
        bufferLength = len(b._outgoingData)
        assert b.read(1) == bytearray()
        assert bufferLength == 0
        
        
    def test_read_manyBytes_oneBuffer(self, defaultBuffer):
        b = defaultBuffer        
        b._outgoingData += b"t"
        bufferLength = len(b._outgoingData)
        assert b.read(bufferLength + 1) == b._outgoingData
        assert bufferLength == len(b._outgoingData)
        
   
    ## pop() tests
 
    ## NOTE: The comparisons with for b._data and b.pop() / b.read() has been swapped
    ## -- this is so that b._data is evaluated before the operation for the pop() ops
    ## -- this literal order shouldn't matter for the above read() ops
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be read is LESS than the number of current bytes stored in the buffer
    def test_pop_negativeBytes(self, defaultBuffer):
        b = defaultBuffer
        testBytes = bytearray(bytearray(b"testdata"))
        b._outgoingData += testBytes

        assert testBytes == b.pop(-1)
        assert len(b._outgoingData) == 0
        assert len(b._messages) == 0

        
    def test_pop_zeroBytes(self, defaultBuffer):
        b = defaultBuffer        
        testBytes = bytearray(bytearray(b"testdata"))
        b._outgoingData += testBytes
        bufferLength = len(b._outgoingData)
        
        assert testBytes[0:0] == b.pop(0)
        assert bufferLength == len(b._outgoingData)
        assert len(b._messages) == 0

        
    def test_pop_oneByte(self, defaultBuffer):
        b = defaultBuffer        
        testBytes = bytearray(bytearray(b"testdata"))
        b._outgoingData += testBytes
        bufferLength = len(b._outgoingData)
        popLength = 1
        
        assert testBytes[0:1] == b.pop(1) 
        assert bufferLength - popLength == len(b._outgoingData)
        assert len(b._messages) == 0
        
        
    def test_pop_manyBytes(self, defaultBuffer):
        b = defaultBuffer        
        testBytes = bytearray(bytearray(b"testdata"))
        b._outgoingData += testBytes
        bufferLength = len(testBytes)
        popLength = bufferLength // 2
        
        assert testBytes[0:popLength] == b.pop(popLength)
        assert bufferLength - popLength == len(b._outgoingData)
        assert len(b._messages) == 0
        
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be pop EXCEEDS the number of current bytes stored in the buffer
    def test_pop_negativeBytes_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        # b._outgoingData is initialized as empty bytearray()
        assert b._outgoingData == b.pop(-1)
        assert len(b._outgoingData) == 0
        assert len(b._messages) == 0
        

    def test_pop_zeroBytes_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        # b._outgoingData is initialized as empty bytearray()
        assert bytearray() == b.pop(0)
        assert len(b._outgoingData) == 0
        assert len(b._messages) == 0


    def test_pop_oneByte_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        # b._outgoingData is initialized as empty bytearray()ran
        assert bytearray() == b.pop(1)
        assert len(b._outgoingData) == 0
        assert len(b._messages) == 0
        
        
    def test_pop_manyBytes_oneBuffer(self, defaultBuffer):
        b = defaultBuffer
        testBytes = b"t"
        b._outgoingData += testBytes
        bufferLength = len(b._outgoingData) + 1
        
        assert testBytes == b.pop(bufferLength)
        assert len(b._outgoingData) == 0
        assert len(b._messages) == 0
    

    ## write() tests (with stubbed _execMessageParsing)
    def test_write_stubbedParsing_zeroBytes(self, nonparsingBuffer):
        b = nonparsingBuffer
        testBytes = b""
        b.write(testBytes)

        assert b._incomingData == testBytes
        assert len(b._messages) == 0

    def test_write_stubbedParsing_oneByte(self, nonparsingBuffer):
        b = nonparsingBuffer
        testBytes = b"t"
        b.write(testBytes)
        
        assert b._incomingData == testBytes
        assert b._outgoingData == b""
        assert len(b._messages) == 0
        
    def test_write_stubbedParsing_manyBytes(self, nonparsingBuffer):
        b = nonparsingBuffer
        testBytes = bytearray(b"testdata")
        b.write(testBytes)
        
        assert b._incomingData == testBytes
        assert b._outgoingData == b""
        assert len(b._messages) == 0

    def test_write_stubbedParsing_zeroBytes_nonEmptyBuffer(self, nonparsingBuffer):
        b = nonparsingBuffer
        testBytes1 = b""
        testBytes2 = b"data"
        b.write(testBytes1)
        b.write(testBytes2)
        
        assert b._incomingData == testBytes1 + testBytes2
        assert b._outgoingData == b""
        assert len(b._messages) == 0

    def test_write_stubbedParsing_oneByte_nonEmptyBuffer(self, nonparsingBuffer):
        b = nonparsingBuffer
        testBytes1 = b"t"
        testBytes2 = b"data"
        b.write(testBytes1)
        b.write(testBytes2)
        
        assert b._incomingData == testBytes1 + testBytes2
        assert b._outgoingData == b""
        assert len(b._messages) == 0

    def test_write_stubbedParsing_manyBytes_nonEmptyBuffer(self, nonparsingBuffer):
        b = nonparsingBuffer
        testBytes1 = b"test"
        testBytes2 = b"data"
        b.write(testBytes1)
        b.write(testBytes2)

        assert b._incomingData == testBytes1 + testBytes2
        assert b._outgoingData == b""
        assert len(b._messages) == 0

    def test_write_stubbedParsing_manyBytes_fullBuffer(self, nonparsingBuffer):
        b = nonparsingBuffer
        b.write(b"A" * b._MAX_BUFFER_SIZE)
        testBytes = b"data"
        with pytest.raises(BufferOverflowError) as excInfo:
            b.write(testBytes)

        assert "exceeded max buffer size" in str(excInfo.value)


class Test_Buffer_MessageQueueOperations:
    ## peakFromQueue()
    def test_peakFromQueue_empty(self, nonparsingBuffer):
        b = nonparsingBuffer
        with pytest.raises(PeakFromEmptyQueueError) as excInfo:
            b.peakFromQueue()

    def test_peakFromQueue_nonempty(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = b"message1\r\n"
        b._messages.append(message1)
        assert b.peakFromQueue() == message1
        assert len(b._messages) == 1
    
    def test_peakFromQueue_full(self, nonparsingBuffer):
        b = nonparsingBuffer
        assert b._messages.maxlen == None ## a None value means the queue unbounded

    ## pushToQueue()
    def test_pushToQueue_empty(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = b"message1\r\n"
        b.pushToQueue(message1)
        assert len(b._messages) == 1
        assert b._messages[0] == message1

    def test_pushToQueue_nonempty(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = b"message1\r\n"
        message2 = b"message2\r\n"
        message3 = b"message3\r\n"
        b.pushToQueue(message1)
        b.pushToQueue(message2)
        b.pushToQueue(message3)
        assert len(b._messages) == 3
        assert b._messages[0] == message1
        assert b._messages[1] == message2
        assert b._messages[2] == message3
        
    def test_pushToQueue_full(self, nonparsingBuffer):
        b = nonparsingBuffer
        assert b._messages.maxlen == None ## None value means the queue is unbounded

    ## popFromQueue()
    def test_popFromQueue_empty(self, nonparsingBuffer):
        b = nonparsingBuffer
        with pytest.raises(PopFromEmptyQueueError) as excInfo:
            b.popFromQueue()

    def test_popFromQueue_nonempty(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = b"message1\r\n"
        message2 = b"message2\r\n"
        message3 = b"message3\r\n"
        b.pushToQueue(message1)
        b.pushToQueue(message2)
        b.pushToQueue(message3)
        assert len(b._messages) == 3
        assert b.popFromQueue() == message1
        assert b.popFromQueue() == message2
        assert b.popFromQueue() == message3
        
    def test_popFromQueue_full(self, nonparsingBuffer):
        b = nonparsingBuffer
        assert b._messages.maxlen == None ## None value means the queue is unbounded



class _flag:
    def __init__(self): self.isRan = False
    def setFlag(self): self.isRan = True
    def isSet(self): return self.isRan


@pytest.fixture()
def hookTestResources(defaultBuffer):
    b = defaultBuffer
    flag = _flag()
    message = bytearray(b"completeMessage\r\n") ## messageHook only called on completeMessages
    return b, flag, message


 
class Test_Buffer_Hooks:
    ## TODO: Need to test whether execmessageParsing is being executed correctly!!
    ## TODO: Need to assert whether the state of the buffer doesn't change

    def _simulateHook(self, buffer: Buffer, proxyTunnel: "ProxyTunnel", server: "TCPProxyServer", message: bytes, flag: "Type[self._flag]", hookType: "Type[self._hook]", hookStr: str, hookArgs: Tuple = (), hookKwargs: Dict = {}) -> None:
        if hookStr == "transparent":
            buffer.setTransparentHook(hookType, proxyTunnel, server, hookArgs, hookKwargs)
        else:
            buffer.setNonTransparentHook(hookType, proxyTunnel, server, hookArgs, hookKwargs)
        
        new_message, continueProcessing = buffer._executeHooks(message)
        ## TODO: Run assertion tests on output of executeHooks()

        isRan = False
        buffer.write(message)
        assert flag.isSet()

        

    def test_transparentHookDefault(self, hookTestResources):
        b, flag, message = hookTestResources
        new_message, continueProcessing = b._executeHooks(message)
        assert new_message == message
        assert continueProcessing is True
                

    def test_transparentHookFunctor_noParams(self, hookTestResources):
        b, flag, message = hookTestResources
        class UserHook:
            def __init__(self, server=None, proxyTunnel=None, buffer=None):
                self.buffer = buffer

            def __call__(self, message: bytearray) -> bool:
                nonlocal flag
                flag.setFlag()
                return True

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, UserHook, "transparent")


    def test_transparentHookFunctor_args(self, hookTestResources):
        b, flag, message = hookTestResources
        proxyTunnel = None
        proxyServer = None
        args = ("arg1", "arg2")
        class UserHook:
            def __init__(self, arg1, arg2, server=None, proxyTunnel=None, buffer=None):
                self.arg1 = arg1
                self.arg2 = arg2
                self.buffer = buffer

            def __call__(self, message: bytearray) -> None:
                nonlocal flag
                flag.setFlag()
                return True

        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, UserHook, "transparent", args)
        assert b._hooks[0].streamInterceptor.arg1 == args[0]
        assert b._hooks[0].streamInterceptor.arg2 == args[1]


    def test_transparentHookFunctor_kwargs(self, hookTestResources):
        b, flag, message = hookTestResources
        kwargs = {"kwarg1": "val1", "kwarg2": "val2"}

        class UserHook:
            def __init__(self, kwarg1=None, kwarg2=None, server=None, proxyTunnel=None, buffer=None):
                self.kwarg1 = kwarg1
                self.kwarg2 = kwarg2
                self.buffer = buffer

            def __call__(self, message: bytearray) -> None:
                nonlocal flag
                flag.setFlag()
                return True

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, UserHook, "transparent", hookKwargs = kwargs)
        assert b._hooks[0].streamInterceptor.kwarg1 == kwargs["kwarg1"]
        assert b._hooks[0].streamInterceptor.kwarg2 == kwargs["kwarg2"]

    def test_transparentHookFunctor_argsAndKwargs(self, hookTestResources):
        b, flag, message = hookTestResources
        kwargs = {"kwarg1": "val1", "kwarg2": "val2"}
        args = ("arg1", "arg2")
        class UserHook:
            def __init__(self, arg1, arg2, kwarg1=None, kwarg2=None, server=None, proxyTunnel=None, buffer=None):
                self.arg1 = arg1
                self.arg2 = arg2
                self.kwarg1 = kwarg1
                self.kwarg2 = kwarg2
                self.buffer = buffer

            def __call__(self, message: bytearray) -> None:
                nonlocal flag
                flag.setFlag()
                return True

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, UserHook, "transparent", args, kwargs)
        assert b._hooks[0].streamInterceptor.kwarg1 == kwargs["kwarg1"]
        assert b._hooks[0].streamInterceptor.kwarg2 == kwargs["kwarg2"]
        assert b._hooks[0].streamInterceptor.arg1 == args[0]
        assert b._hooks[0].streamInterceptor.arg2 == args[1]


    def test_transparentHookGenerator_noParams(self, hookTestResources):
        b, flag, message = hookTestResources
        def UserHook(server=None, proxyTunnel=None, buffer=None):
            nonlocal flag
            mesage = yield
            while True:
                flag.setFlag()
                message = yield True
            return None

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, UserHook, "transparent")


    def test_transparentHookGenerator_args(self, hookTestResources):
        b, flag, message = hookTestResources
        args = ("arg1", "arg2")
        _arg1 = None; _arg2 = None
        def UserHook(arg1, arg2, server=None, proxyTunnel=None, buffer=None):
            nonlocal _arg1, _arg2
            _arg1 = arg1; _arg2 = arg2
            nonlocal flag
            message = yield True
            while True:
                flag.setFlag()
                message = yield True
            return True

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, UserHook, "transparent", args)
        assert _arg1 == args[0]
        assert _arg2 == args[1]

    def test_transparentHookGenerator_kwargs(self, hookTestResources):
        b, flag, message = hookTestResources
        kwargs = {"kwarg1": "val1", "kwarg2": "val2"}
        _kwarg1 = None; _kwarg2 = None
        def UserHook(kwarg1, kwarg2, server=None, proxyTunnel=None, buffer=None):
            nonlocal _kwarg1, _kwarg2
            _kwarg1 = kwarg1; _kwarg2 = kwarg2
            nonlocal flag
            while True:
                message = yield
                flag.setFlag()
            return True

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, UserHook, "transparent", hookKwargs=kwargs)
        assert _kwarg1 == kwargs["kwarg1"]
        assert _kwarg2 == kwargs["kwarg2"]


    def test_transparentHookGenerator_argsAndKwargs(self, hookTestResources):
        b, flag, message = hookTestResources
        args = ("arg1", "arg2")
        kwargs = {"kwarg1": "val1", "kwarg2": "val2"}
        _arg1 = None; _arg2 = None
        _kwarg1 = None; _kwarg2 = None
        def UserHook(arg1, arg2, kwarg1=None, kwarg2=None, server=None, proxyTunnel=None, buffer=None):
            nonlocal _arg1, _arg2, _kwarg1, _kwarg2
            _arg1 = arg1; _arg2 = arg2; _kwarg1 = kwarg1; _kwarg2 = kwarg2
            nonlocal flag
            while True:
                message = yield
                flag.setFlag()
            return True

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, UserHook, "transparent", args, kwargs)
        assert _arg1 == args[0]
        assert _arg2 == args[1]
        assert _kwarg1 == kwargs["kwarg1"]
        assert _kwarg2 == kwargs["kwarg2"]


    def test_nonTransparentHookDefault(self, hookTestResources):
        b, flag, message = hookTestResources
        new_message, continueProcessing = b._executeHooks(message)
        assert new_message == message
        assert continueProcessing is True



    def test_nonTransparentHookFunctor_noParams(self, hookTestResources):
        b, flag, message = hookTestResources
        class ProcessingHook:
            def __init__(self, server=None, proxyTunnel=None, buffer=None):
                self.server = server
                self.buffer = buffer

            def __call__(self, message: bytearray) -> None:
                nonlocal flag
                flag.setFlag()
                return message, True

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, ProcessingHook, "processing")


    def test_nonTransparentHookFunctor_args(self, hookTestResources):
        b, flag, message = hookTestResources
        args = ("arg1", "arg2")
        class ProcessingHook:
            def __init__(self, arg1, arg2, server=None, proxyTunnel=None, buffer=None):
                self.arg1 = arg1
                self.arg2 = arg2
                self.buffer = buffer

            def __call__(self, message: bytearray) -> None:
                nonlocal flag
                flag.setFlag()
                return message, True

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, ProcessingHook, "processing", args)
        assert b._hooks[0].streamInterceptor.arg1 == args[0]
        assert b._hooks[0].streamInterceptor.arg2 == args[1]


    def test_nonTransparentHookFunctor_kwargs(self, hookTestResources):
        b, flag, message = hookTestResources
        kwargs = {"kwarg1": "val1", "kwarg2": "val2"}

        class ProcessingHook:
            def __init__(self, kwarg1=None, kwarg2=None, server=None, proxyTunnel=None, buffer=None):
                self.kwarg1 = kwarg1
                self.kwarg2 = kwarg2
                self.buffer = buffer

            def __call__(self, message: bytearray) -> None:
                nonlocal flag
                flag.setFlag()
                return message, True

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, ProcessingHook, "processing", hookKwargs = kwargs)
        assert b._hooks[0].streamInterceptor.kwarg1 == kwargs["kwarg1"]
        assert b._hooks[0].streamInterceptor.kwarg2 == kwargs["kwarg2"]


    def test_nonTransparentHookFunctor_argsAndKwargs(self, hookTestResources):
        b, flag, message = hookTestResources
        kwargs = {"kwarg1": "val1", "kwarg2": "val2"}
        args = ("arg1", "arg2")
        class ProcessingHook:
            def __init__(self, arg1, arg2, kwarg1=None, kwarg2=None, server=None, proxyTunnel=None, buffer=None):
                self.arg1 = arg1
                self.arg2 = arg2
                self.kwarg1 = kwarg1
                self.kwarg2 = kwarg2
                self.buffer = buffer

            def __call__(self, message: bytearray) -> None:
                nonlocal flag
                flag.setFlag()
                return message, True

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, ProcessingHook, "processing", args, kwargs)
        assert b._hooks[0].streamInterceptor.kwarg1 == kwargs["kwarg1"]
        assert b._hooks[0].streamInterceptor.kwarg2 == kwargs["kwarg2"]
        assert b._hooks[0].streamInterceptor.arg1 == args[0]
        assert b._hooks[0].streamInterceptor.arg2 == args[1]


    def test_nonTransparentHookGenerator_noParams(self, hookTestResources):
        b, flag, message = hookTestResources
        def ProcessingHook(server=None, proxyTunnel=None, buffer=None):
            nonlocal flag
            message = yield None
            while True:
                flag.setFlag()
                message = yield message, True
            return None

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, ProcessingHook, "processing")


    def test_nonTransparentHookGenerator_args(self, hookTestResources):
        b, flag, message = hookTestResources
        args = ("arg1", "arg2")
        _arg1 = None; _arg2 = None
        def ProcessingHook(arg1, arg2, server=None, proxyTunnel=None, buffer=None):
            nonlocal _arg1, _arg2, args
            _arg1 = arg1; _arg2 = arg2
            nonlocal flag
            message = yield None
            while True:
                flag.setFlag()
                message = yield message, True
            return None

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, ProcessingHook, "processing", args)
        assert _arg1 == args[0]
        assert _arg2 == args[1]


    def test_nonTransparentHookGenerator_kwargs(self, hookTestResources):
        b, flag, message = hookTestResources
        kwargs = {"kwarg1": "val1", "kwarg2": "val2"}
        _kwarg1 = None; _kwarg2 = None
        def ProcessingHook(kwarg1=None, kwarg2=None, server=None, proxyTunnel=None, buffer=None):
            nonlocal _kwarg1, _kwarg2, kwargs
            _kwarg1 = kwarg1; _kwarg2 = kwarg2
            nonlocal flag
            message = yield None
            while True:
                flag.setFlag()
                message = yield message, True
            return None

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, ProcessingHook, "processing", hookKwargs=kwargs)
        assert _kwarg1 == kwargs["kwarg1"]
        assert _kwarg2 == kwargs["kwarg2"]

    def test_nonTransparentHookGenerator_argsAndKwargs(self, hookTestResources):
        b, flag, message = hookTestResources
        args = ("arg1", "arg2")
        kwargs = {"kwarg1": "val1", "kwarg2": "val2"}
        _arg1 = None; _arg2 = None
        _kwarg1 = None; _kwarg2 = None
        def ProcessingHook(arg1, arg2, kwarg1 = None, kwarg2 = None, server=None, proxyTunnel=None, buffer=None):
            nonlocal _arg1, _arg2, _kwarg1, _kwarg2
            _arg1 = arg1; _arg2 = arg2; _kwarg1 = kwarg1; _kwarg2 = kwarg2
            nonlocal flag
            message = yield None
            while True:
                flag.setFlag()
                message = yield message, True
            return None

        proxyTunnel = None
        proxyServer = None
        self._simulateHook(b, proxyTunnel, proxyServer, message, flag, ProcessingHook, "processing", args, kwargs)
        assert _arg1 == args[0]
        assert _arg2 == args[1]
        assert _kwarg1 == kwargs["kwarg1"]
        assert _kwarg2 == kwargs["kwarg2"]