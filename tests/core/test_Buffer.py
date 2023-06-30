import collections
import os
import sys

import functools
import pytest
from typing import Tuple, Dict

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from _proxyDS import Buffer
from _exceptions import *
## Buffer Initiatialization

@pytest.fixture()
def defaultBuffer() -> Buffer:
    delimiters = [b"\r\n"]
    b = Buffer(delimiters)
    return b

@pytest.fixture()
def nonparsingBuffer() -> Buffer:
    delimiters = [b"\r\n"]
    b = Buffer(delimiters)
    b._execMessageParsing = lambda *args, **kwargs: None
    return b

class Test_Buffer_Init:
    def test_default(self) -> None:
        ## NOTE: A default constructor is not allowed
        with pytest.raises(TypeError) as excInfo:
            Buffer()
            
        assert "MESSAGE_DELIMITERS" in str(excInfo.value)
        
        
    def test_MessageDelimiters_incorrectType(self) -> None:
        MESSAGE_DELIMITERS = None
        with pytest.raises(IncorrectDelimitersTypeError) as excInfo:
            Buffer(MESSAGE_DELIMITERS)
            
        assert "Incorrect type" in str(excInfo.value)
        assert "[i]" not in str(excInfo.value)   
        
        
    def test_MessageDelimiters_empty(self) -> None:
        MESSAGE_DELIMITERS = []
        with pytest.raises(EmptyDelimitersTypeError) as excInfo:
            Buffer(MESSAGE_DELIMITERS)
            
        assert "Cannot pass empty" in str(excInfo.value)
        

    def test_MessageDelimiters_single(self) -> None:
        MESSAGE_DELIMITERS = [b"\r\n"]
        b = Buffer(MESSAGE_DELIMITERS)
        
        assert b.MESSAGE_DELIMITERS == MESSAGE_DELIMITERS
        assert isinstance(b._data, bytearray) and len(b._data) == 0
        assert isinstance(b._messages, collections.deque) and len(b._messages) == 0
        
        
    def test_MessageDelimiters_many(self) -> None:
        ## NOTE: The order of the delimiters is important for when message can have multiple potential delimiters
        MESSAGE_DELIMITERS = [b"\r\n", b"\r"]
        b = Buffer(MESSAGE_DELIMITERS)
        
        assert b.MESSAGE_DELIMITERS == MESSAGE_DELIMITERS
        assert isinstance(b._data, bytearray) and len(b._data) == 0
        assert isinstance(b._messages, collections.deque) and len(b._messages) == 0 
        
        
    def test_MessageDelimiters_duplicate(self) -> None:
        ## NOTE: Duplicates delimitesr are bad practice
        MESSAGE_DELIMITERS = [b"\r\n", b"\r", b"\r\n"]
        with pytest.raises(DuplicateDelimitersError) as excInfo:
            Buffer(MESSAGE_DELIMITERS)
        
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
        b._data += bytearray(b"testdata")
        bufferLength = len(b._data)
        
        assert b.read(-1) == b._data
        assert bufferLength == len(b._data)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()

        
    def test_read_zeroBytes(self, defaultBuffer):
        b = defaultBuffer  
        b._data += bytearray(b"testdata")
        bufferLength = len(b._data)
        
        assert b.read(0) == b._data[0:0]
        assert bufferLength == len(b._data)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()

        
    def test_read_oneByte(self, defaultBuffer):
        b = defaultBuffer
        b._data += bytearray(b"testdata")
        bufferLength = len(b._data)
        
        assert b.read(1) == b._data[0:1]
        assert bufferLength == len(b._data)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
        
    def test_read_manyBytes(self, defaultBuffer):
        b = defaultBuffer
        b._data += bytearray(b"testdata")
        bufferLength = len(b._data)
        readLength = bufferLength // 2
        assert b._prevEndBuffer == bytearray()
        
        assert b.read(readLength) == b._data[0:readLength]
        assert bufferLength == len(b._data)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be read EXCEEDS the number of current bytes stored in the buffer
    def test_read_negativeBytes_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        # b._data is initialized as empty bytearray()
        bufferLength = len(b._data)
        
        assert b.read(-1) == b._data
        assert bufferLength == len(b._data)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
    def test_read_zeroBytes_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        # b._data is initialized as empty bytearray()
        bufferLength = len(b._data)
        
        assert b.read(0) == bytearray()
        assert bufferLength == 0
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
    def test_read_oneByte_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        # b._data is initialized as empty bytearray()
        bufferLength = len(b._data)
        
        assert b.read(1) == bytearray()
        assert bufferLength == 0
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
        
    def test_read_manyBytes_oneBuffer(self, defaultBuffer):
        b = defaultBuffer        
        b._data += b"t"
        bufferLength = len(b._data)
        
        assert b.read(bufferLength + 1) == b._data
        assert bufferLength == len(b._data)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
    
   
    ## pop() tests
 
    ## NOTE: The comparisons with for b._data and b.pop() / b.read() has been swapped
    ## -- this is so that b._data is evaluated before the operation for the pop() ops
    ## -- this literal order shouldn't matter for the above read() ops
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be read is LESS than the number of current bytes stored in the buffer
    def test_pop_negativeBytes(self, defaultBuffer):
        b = defaultBuffer
        testBytes = bytearray(bytearray(b"testdata"))
        b._data += testBytes

        assert testBytes == b.pop(-1)
        assert len(b._data) == 0
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()

        
    def test_pop_zeroBytes(self, defaultBuffer):
        b = defaultBuffer        
        testBytes = bytearray(bytearray(b"testdata"))
        b._data += testBytes
        bufferLength = len(b._data)
        
        assert testBytes[0:0] == b.pop(0)
        assert bufferLength == len(b._data)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()

        
    def test_pop_oneByte(self, defaultBuffer):
        b = defaultBuffer        
        testBytes = bytearray(bytearray(b"testdata"))
        b._data += testBytes
        bufferLength = len(b._data)
        popLength = 1
        
        assert testBytes[0:1] == b.pop(1) 
        assert bufferLength - popLength == len(b._data)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
        
    def test_pop_manyBytes(self, defaultBuffer):
        b = defaultBuffer        
        testBytes = bytearray(bytearray(b"testdata"))
        b._data += testBytes
        bufferLength = len(testBytes)
        popLength = bufferLength // 2
        
        assert testBytes[0:popLength] == b.pop(popLength)
        assert bufferLength - popLength == len(b._data)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be pop EXCEEDS the number of current bytes stored in the buffer
    def test_pop_negativeBytes_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        # b._data is initialized as empty bytearray()
        
        assert b._data == b.pop(-1)
        assert len(b._data) == 0
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
    def test_pop_zeroBytes_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        # b._data is initialized as empty bytearray()
        
        assert bytearray() == b.pop(0)
        assert len(b._data) == 0
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
    def test_pop_oneByte_zeroBuffer(self, defaultBuffer):
        b = defaultBuffer        
        # b._data is initialized as empty bytearray()
        
        assert bytearray() == b.pop(1)
        assert len(b._data) == 0
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
        
    def test_pop_manyBytes_oneBuffer(self, defaultBuffer):
        b = defaultBuffer
        testBytes = b"t"
        b._data += testBytes
        bufferLength = len(b._data) + 1
        
        assert testBytes == b.pop(bufferLength)
        assert len(b._data) == 0
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
    

    ## write() tests (with stubbed _execMessageParsing)
    def test_write_stubbedParsing_zeroBytes(self, nonparsingBuffer):
        b = nonparsingBuffer
        testBytes = b""
        b.write(testBytes)

        assert b._data == testBytes
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()

    def test_write_stubbedParsing_oneByte(self, nonparsingBuffer):
        b = nonparsingBuffer
        testBytes = b"t"
        b.write(testBytes)
        
        assert len(b._data) == len(testBytes)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()
        
    def test_write_stubbedParsing_manyBytes(self, nonparsingBuffer):
        b = nonparsingBuffer
        testBytes = bytearray(b"testdata")
        b.write(testBytes)
        
        assert len(b._data) == len(testBytes)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()

    def test_write_stubbedParsing_zeroBytes_nonEmptyBuffer(self, nonparsingBuffer):
        b = nonparsingBuffer
        b._data += b""
        testBytes = b"data"
        b.write(testBytes)
        
        assert b._data == bytearray(b"data")
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()

    def test_write_stubbedParsing_oneByte_nonEmptyBuffer(self, nonparsingBuffer):
        b = nonparsingBuffer
        b._data += b"t"
        testBytes = b"data"
        b.write(testBytes)
        
        assert b._data == bytearray(b"tdata")
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()

    def test_write_stubbedParsing_manyBytes_nonEmptyBuffer(self, nonparsingBuffer):
        b = nonparsingBuffer
        b._data += b"test"
        testBytes = b"data"
        b.write(testBytes)

        assert b._data == bytearray(bytearray(b"testdata"))
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()

    def test_write_stubbedParsing_manyBytes_fullBuffer(self, nonparsingBuffer):
        b = nonparsingBuffer
        b._data += (b"A" * b._MAX_BUFFER_SIZE)
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

        assert "Cannot peak" in str(excInfo.value)
        assert len(b._data) == 0
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()



    def test_peakFromQueue_singleUndelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        msg1 = bytearray(b"testdata")
        b._messages.append([msg1, False])
        b._data = msg1

        assert len(b._messages) == 1
        assert b.peakFromQueue() == [msg1, False]
        assert b._data == msg1
        assert b._prevEndBuffer == bytearray()


    def test_peakFromQueue_singleDelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        msg1 = bytearray(b"testdata\r\n")
        b._messages.append([msg1, True])
        b._data = msg1

        assert len(b._messages) == 1
        assert b.peakFromQueue() == [msg1, True]
        assert b._data == msg1
        assert b._prevEndBuffer == bytearray()



    def test_peakFromQueue_manyUndelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        msg1 = bytearray(b"testdata1")
        msg2 = bytearray(b"testdata2")
        msg3 = bytearray(b"testdata3")
        msg4 = bytearray(b"testdata4")
        b._messages.append([msg1, False])
        b._messages.append([msg2, False])
        b._messages.append([msg3, False])
        b._messages.append([msg4, False])
        b._data = msg1 + msg2 + msg3 + msg4

        assert len(b._messages) == 4
        assert b.peakFromQueue() == [msg4, False]
        assert b._data == msg1 + msg2 + msg3 + msg4
        assert b._prevEndBuffer == bytearray()


    def test_peakFromQueue_manyDelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        msg1 = bytearray(b"testdata1\r\n")
        msg2 = bytearray(b"testdata2\r\n")
        msg3 = bytearray(b"testdata3\r\n")
        msg4 = bytearray(b"testdata4\r\n")
        b._messages.append([msg1, True])
        b._messages.append([msg2, True])
        b._messages.append([msg3, True])
        b._messages.append([msg4, True])
        b._data = msg1 + msg2 + msg3 + msg4

        assert len(b._messages) == 4
        assert b.peakFromQueue() == [msg4, True]
        assert b._data == msg1 + msg2 + msg3 + msg4
        assert b._prevEndBuffer == bytearray()


    ## pushToQueue()
    def test_pushToQueue_empty_Undelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message = [bytearray(b"testdata"), False]
        b.pushToQueue(*message)

        assert len(b._messages) == 1
        assert b._messages[-1] == message
        assert len(b._data) == 0
        assert b._prevEndBuffer == bytearray()


    def test_pushToQueue_empty_Delimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message = [bytearray(b"testdata"), True]
        b.pushToQueue(*message)

        assert len(b._messages) == 1
        assert b._messages[-1] == message
        assert len(b._data) == 0
        assert b._prevEndBuffer == bytearray()


    def test_pushToQueue_single_PrevUndelimited_CurrentDelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = [bytearray(b"testdata1"), False]
        message2 = [bytearray(b"testdata2"), True]
        b.pushToQueue(*message1)
        b.pushToQueue(*message2)

        assert len(b._messages) == 1
        assert b._messages[-1][0] == message1[0] + message2[0]
        assert b._messages[-1][1] == True
        assert b._prevEndBuffer == bytearray()


    def test_pushToQueue_single_PrevUndelimited_CurrentUndelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = [bytearray(b"testdata1"), False]
        message2 = [bytearray(b"testdata2"), False]
        b.pushToQueue(*message1)
        b.pushToQueue(*message2)

        assert len(b._messages) == 1
        assert b._messages[-1][0] == message1[0] + message2[0]
        assert b._messages[-1][1] == False
        assert b._prevEndBuffer == bytearray()


    def test_pushToQueue_single_PrevDelimited_currentUndelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = [bytearray(b"testdata1"), True]
        message2 = [bytearray(b"testdata2"), False]
        b.pushToQueue(*message1)
        b.pushToQueue(*message2)

        assert len(b._messages) == 2
        assert b._messages[0] == message1
        assert b._messages[1] == message2
        assert len(b._data) == 0
        assert b._prevEndBuffer == bytearray()


    def test_pushToQueue_single_PrevDelimited_currentDelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = [bytearray(b"testdata1"), True]
        message2 = [bytearray(b"testdata2"), True]
        b.pushToQueue(*message1)
        b.pushToQueue(*message2)

        assert len(b._messages) == 2
        assert b._messages[0] == message1
        assert b._messages[1] == message2
        assert len(b._data) == 0
        assert b._prevEndBuffer == bytearray()


    def test_pushToQueue_many_prevDelimited_currentDelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = [bytearray(b"testdata1"), True]
        message2 = [bytearray(b"testdata2"), True]
        message3 = [bytearray(b"testdata3"), True]
        message4 = [bytearray(b"testdata4"), True]
        b.pushToQueue(*message1)
        b.pushToQueue(*message2)
        b.pushToQueue(*message3)
        b.pushToQueue(*message4)

        assert len(b._messages) == 4
        assert b._messages[0] == message1
        assert b._messages[1] == message2
        assert b._messages[2] == message3
        assert b._messages[3] == message4
        assert len(b._data) == 0
        assert b._prevEndBuffer == bytearray()

    def test_pushToQueue_many_prevDelimited_currentUndelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = [bytearray(b"testdata1"), True]
        message2 = [bytearray(b"testdata2"), True]
        message3 = [bytearray(b"testdata3"), True]
        message4 = [bytearray(b"testdata4"), False]
        b.pushToQueue(*message1)
        b.pushToQueue(*message2)
        b.pushToQueue(*message3)
        b.pushToQueue(*message4)

        assert len(b._messages) == 4
        assert b._messages[0] == message1
        assert b._messages[1] == message2
        assert b._messages[2] == message3
        assert b._messages[3] == message4
        assert len(b._data) == 0
        assert b._prevEndBuffer == bytearray()


    def test_pushToQueue_many_prevUndelimited_currentUndelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = [bytearray(b"testdata1"), True]
        message2 = [bytearray(b"testdata2"), True]
        message3 = [bytearray(b"testdata3"), False]
        message4 = [bytearray(b"testdata4"), False]
        b.pushToQueue(*message1)
        b.pushToQueue(*message2)
        b.pushToQueue(*message3)
        b.pushToQueue(*message4)

        assert len(b._messages) == 3
        assert b._messages[0] == message1
        assert b._messages[1] == message2
        assert b._messages[2] == [message3[0] + message4[0], False]
        assert len(b._data) == 0
        assert b._prevEndBuffer == bytearray()

    def test_pushToQueue_many_prevUndelimited_currentDelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message1 = [bytearray(b"testdata1"), True]
        message2 = [bytearray(b"testdata2"), True]
        message3 = [bytearray(b"testdata3"), False]
        message4 = [bytearray(b"testdata4"), True]
        b.pushToQueue(*message1)
        b.pushToQueue(*message2)
        b.pushToQueue(*message3)
        b.pushToQueue(*message4)

        assert len(b._messages) == 3
        assert b._messages[0] == message1
        assert b._messages[1] == message2
        assert b._messages[2] == [message3[0] + message4[0], True]
        assert len(b._data) == 0
        assert b._prevEndBuffer == bytearray()
    

    ## popFromQueue()
    def test_popFromQueue_empty(self, nonparsingBuffer):
        b = nonparsingBuffer
        with pytest.raises(PopFromEmptyQueueError) as excInfo:
            b.popFromQueue()

        assert "Cannot pop" in str(excInfo.value)
        assert "empty" in str(excInfo.value)
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()


    def test_popFromQueue_single_Undelimited(self, nonparsingBuffer):
        b = nonparsingBuffer
        message = [bytearray(b"testdata"), False]
        b.pushToQueue(*message)

        with pytest.raises(PopUndelimitedItemFromQueueError) as excInfo:
            b.popFromQueue()

        assert "Cannot pop" in str(excInfo.value)
        assert "undelimited" in str(excInfo.value)
        assert len(b._messages) == 1
        assert b._prevEndBuffer == bytearray()


    def test_popFromQueue_single_Delimited(self, nonparsingBuffer):
        b = nonparsingBuffer        
        message = [bytearray(b"testdata"), True]
        b.pushToQueue(*message)

        assert b.popFromQueue() == message
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()


    def test_popFromQueue_many_Undelimited(self, nonparsingBuffer):
        b = nonparsingBuffer        
        message1 = [bytearray(b"testdata1"), True]
        message2 = [bytearray(b"testdata2"), True]
        message3 = [bytearray(b"testdata3"), True]
        message4 = [bytearray(b"testdata4"), False]
        b.pushToQueue(*message1)
        b.pushToQueue(*message2)
        b.pushToQueue(*message3)
        b.pushToQueue(*message4)

        assert b.popFromQueue() == message1
        assert b.popFromQueue() == message2
        assert b.popFromQueue() == message3

        with pytest.raises(PopUndelimitedItemFromQueueError) as excInfo:
            b.popFromQueue()

        assert "Cannot pop" in str(excInfo.value)
        assert "undelimited" in str(excInfo.value)
        assert len(b._messages) == 1
        assert b._prevEndBuffer == bytearray()


    def test_popFromQueue_many_Delimited(self, nonparsingBuffer):
        b = nonparsingBuffer        
        message1 = [bytearray(b"testdata1"), True]
        message2 = [bytearray(b"testdata2"), True]
        message3 = [bytearray(b"testdata3"), True]
        message4 = [bytearray(b"testdata4"), True]
        b.pushToQueue(*message1)
        b.pushToQueue(*message2)
        b.pushToQueue(*message3)
        b.pushToQueue(*message4)

        assert b.popFromQueue() == message1
        assert b.popFromQueue() == message2
        assert b.popFromQueue() == message3
        assert b.popFromQueue() == message4

        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray()

    ## emptyQueue
    ## singleQueue (undelimited vs delimited)
    ## multiQueue (undelimited vs delimited)

