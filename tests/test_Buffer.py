import collections
import os
import sys
import functools
import pytest

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from _proxyDS import Buffer
from _exceptions import *
## Buffer Initiatialization

class Test_Buffer_Init:
    def test_default(self) -> None:
        ## NOTE: A default constructor is not allowed
        with pytest.raises(TypeError) as excInfo:
            Buffer()
            
        assert "REQUEST_DELIMITERS" in str(excInfo.value)
        
        
    def test_RequestDelimiters_incorrectType(self) -> None:
        REQUEST_DELIMITERS = None
        with pytest.raises(TypeError) as excInfo:
            Buffer(REQUEST_DELIMITERS)
            
        assert "Incorrect type" in str(excInfo.value)
        assert "[i]" not in str(excInfo.value)   
        
        
    def test_RequestDelimeters_empty(self) -> None:
        REQUEST_DELIMITERS = []
        with pytest.raises(ValueError) as excInfo:
            Buffer(REQUEST_DELIMITERS)
            
        assert "Cannot pass empty" in str(excInfo.value)
        

    def test_RequestDelimiters_single(self) -> None:
        REQUEST_DELIMITERS = [b"\r\n"]
        b = Buffer(REQUEST_DELIMITERS)
        
        assert b.REQUEST_DELIMITERS == REQUEST_DELIMITERS
        assert isinstance(b._data, bytearray) and len(b._data) == 0
        assert isinstance(b._requests, collections.deque) and len(b._requests) == 0
        
        
    def test_RequestDelimiters_many(self) -> None:
        ## NOTE: The order of the delimiters is important for when message can have multiple potential delimiters
        REQUEST_DELIMITERS = [b"\r\n", b"\r"]
        b = Buffer(REQUEST_DELIMITERS)
        
        assert b.REQUEST_DELIMITERS == REQUEST_DELIMITERS
        assert isinstance(b._data, bytearray) and len(b._data) == 0
        assert isinstance(b._requests, collections.deque) and len(b._requests) == 0 
        
        
    def test_RequestDelimiters_duplicate(self) -> None:
        ## NOTE: Duplicates delimitesr are bad practice
        REQUEST_DELIMITERS = [b"\r\n", b"\r", b"\r\n"]
        with pytest.raises(ValueError) as excInfo:
            Buffer(REQUEST_DELIMITERS)
        
        assert "Duplicate" in str(excInfo.value)
        

    def test_RequestDelimiters_subsets(self) -> None:
        ## TODO: Our Buffer may reorder delimiters that are subsets of each other (need to evaluate feature)
        raise NotImplementedError()
    
    

class Test_Buffer_ByteOperations:
    ## read() tests
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be read is LESS than the number of current bytes stored in the buffer
    def test_read_negativeBytes(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        b._data += bytearray(b"testdata")
        bufferLength = len(b._data)
        
        assert b.read(-1) == b._data
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0

        
    def test_read_zeroBytes(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        b._data += bytearray(b"testdata")
        bufferLength = len(b._data)
        
        assert b.read(0) == b._data[0:0]
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0

        
    def test_read_oneByte(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        b._data += bytearray(b"testdata")
        bufferLength = len(b._data)
        
        assert b.read(1) == b._data[0:1]
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0
        
        
    def test_read_manyBytes(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        b._data += bytearray(b"testdata")
        bufferLength = len(b._data)
        readLength = bufferLength // 2
        
        assert b.read(readLength) == b._data[0:readLength]
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0
        
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be read EXCEEDS the number of current bytes stored in the buffer
    def test_read_negativeBytes_zeroBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        bufferLength = len(b._data)
        
        assert b.read(-1) == b._data
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0
        
    def test_read_zeroBytes_zeroBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        bufferLength = len(b._data)
        
        assert b.read(0) == bytearray()
        assert bufferLength == 0
        assert len(b._requests) == 0
        
    def test_read_oneByte_zeroBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        bufferLength = len(b._data)
        
        assert b.read(1) == bytearray()
        assert bufferLength == 0
        assert len(b._requests) == 0
        
        
    def test_read_manyBytes_oneBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        b._data += b"t"
        bufferLength = len(b._data)

        
        assert b.read(bufferLength + 1) == b._data
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0
        
    
   
    ## pop() tests
 
    ## NOTE: The comparisons with for b._data and b.pop() / b.read() has been swapped
    ## -- this is so that b._data is evaluated before the operation for the pop() ops
    ## -- this literal order shouldn't matter for the above read() ops
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be read is LESS than the number of current bytes stored in the buffer
    def test_pop_negativeBytes(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        testBytes = bytearray(bytearray(b"testdata"))
        b._data += testBytes

        assert testBytes == b.pop(-1)
        assert len(b._data) == 0
        assert len(b._requests) == 0

        
    def test_pop_zeroBytes(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        testBytes = bytearray(bytearray(b"testdata"))
        b._data += testBytes
        bufferLength = len(b._data)
        
        assert testBytes[0:0] == b.pop(0)
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0

        
    def test_pop_oneByte(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        testBytes = bytearray(bytearray(b"testdata"))
        b._data += testBytes
        bufferLength = len(b._data)
        popLength = 1
        
        assert testBytes[0:1] == b.pop(1) 
        assert bufferLength - popLength == len(b._data)
        assert len(b._requests) == 0
        
        
    def test_pop_manyBytes(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        testBytes = bytearray(bytearray(b"testdata"))
        b._data += testBytes
        bufferLength = len(testBytes)
        popLength = bufferLength // 2
        
        assert testBytes[0:popLength] == b.pop(popLength)
        assert bufferLength - popLength == len(b._data)
        assert len(b._requests) == 0
        
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be pop EXCEEDS the number of current bytes stored in the buffer
    def test_pop_negativeBytes_zeroBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        
        assert b._data == b.pop(-1)
        assert len(b._data) == 0
        assert len(b._requests) == 0
        
    def test_pop_zeroBytes_zeroBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        
        assert bytearray() == b.pop(0)
        assert len(b._data) == 0
        assert len(b._requests) == 0
        
    def test_pop_oneByte_zeroBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        
        assert bytearray() == b.pop(1)
        assert len(b._data) == 0
        assert len(b._requests) == 0
        
        
    def test_pop_manyBytes_oneBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)

        testBytes = b"t"
        b._data += testBytes
        bufferLength = len(b._data) + 1
        
        assert testBytes == b.pop(bufferLength)
        assert len(b._data) == 0
        assert len(b._requests) == 0
        
    
    

    ## write() tests (with stubbed _execRequestParsing)
    
    def test_write_stubbedParsing_zeroBytes(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        testBytes = b""
        b.write(testBytes)

        assert b._data == testBytes
        assert len(b._requests) == 0

    def test_write_stubbedParsing_oneByte(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        testBytes = b"t"
        b.write(testBytes)
        
        assert len(b._data) == len(testBytes)
        assert len(b._requests) == 0
        
    def test_write_stubbedParsing_manyBytes(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        testBytes = bytearray(b"testdata")
        b.write(testBytes)
        
        assert len(b._data) == len(testBytes)
        assert len(b._requests) == 0

    def test_write_stubbedParsing_zeroBytes_nonEmptyBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        b._data += b""
        testBytes = b"data"
        b.write(testBytes)
        
        assert b._data == bytearray(b"data")
        assert len(b._requests) == 0

    def test_write_stubbedParsing_oneByte_nonEmptyBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        b._data += b"t"
        testBytes = b"data"
        b.write(testBytes)
        
        assert b._data == bytearray(b"tdata")
        assert len(b._requests) == 0

    def test_write_stubbedParsing_manyBytes_nonEmptyBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        b._data += b"test"
        testBytes = b"data"
        b.write(testBytes)

        assert b._data == bytearray(bytearray(b"testdata"))
        assert len(b._requests) == 0

    def test_write_stubbedParsing_manyBytes_fullBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        b._data += (b"A" * b._MAX_BUFFER_SIZE)
        testBytes = b"data"
        with pytest.raises(BufferOverflowError) as excInfo:
            b.write(testBytes)

        assert "exceeded max buffer size" in str(excInfo.value)



class Test_Buffer_RequestQueueOperations:
    ## peakFromQueue()
    def test_peakFromQueue_empty(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        with pytest.raises(IndexError) as excInfo:
            b.peakFromQueue()

        assert "Cannot peak" in str(excInfo.value)
        assert len(b._data) == 0
        assert len(b._requests) == 0


    def test_peakFromQueue_singleUndelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        req1 = bytearray(b"testdata")
        b._requests.append([req1, False])
        b._data = req1

        assert len(b._requests) == 1
        assert b.peakFromQueue() == [req1, False]
        assert b._data == req1

    def test_peakFromQueue_singleDelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        req1 = bytearray(b"testdata\r\n")
        b._requests.append([req1, True])
        b._data = req1

        assert len(b._requests) == 1
        assert b.peakFromQueue() == [req1, True]
        assert b._data == req1


    def test_peakFromQueue_manyUndelimited(self):
        ## The Queue should not be used in this way when calling public methods
        ## -- but we want as much test coverage on internal state hence the below
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        req1 = bytearray(b"testdata1")
        req2 = bytearray(b"testdata2")
        req3 = bytearray(b"testdata3")
        req4 = bytearray(b"testdata4")
        b._requests.append([req1, False])
        b._requests.append([req2, False])
        b._requests.append([req3, False])
        b._requests.append([req4, False])
        b._data = req1 + req2 + req3 + req4

        assert len(b._requests) == 4
        assert b.peakFromQueue() == [req4, False]
        assert b._data == req1 + req2 + req3 + req4


    def test_peakFromQueue_manyDelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        req1 = bytearray(b"testdata1\r\n")
        req2 = bytearray(b"testdata2\r\n")
        req3 = bytearray(b"testdata3\r\n")
        req4 = bytearray(b"testdata4\r\n")
        b._requests.append([req1, True])
        b._requests.append([req2, True])
        b._requests.append([req3, True])
        b._requests.append([req4, True])
        b._data = req1 + req2 + req3 + req4

        assert len(b._requests) == 4
        assert b.peakFromQueue() == [req4, True]
        assert b._data == req1 + req2 + req3 + req4


    ## pushToQueue()
    def test_pushToQueue_empty_Undelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request = [bytearray(b"testdata"), False]
        b.pushToQueue(*request)

        assert len(b._requests) == 1
        assert b._requests[-1] == request
        assert len(b._data) == 0


    def test_pushToQueue_empty_Delimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request = [bytearray(b"testdata"), True]
        b.pushToQueue(*request)

        assert len(b._requests) == 1
        assert b._requests[-1] == request
        assert len(b._data) == 0


    def test_pushToQueue_single_PrevUndelimited_CurrentDelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request1 = [bytearray(b"testdata1"), False]
        request2 = [bytearray(b"testdata2"), True]
        b.pushToQueue(*request1)
        b.pushToQueue(*request2)

        assert len(b._requests) == 1
        assert b._requests[-1][0] == request1[0] + request2[0]
        assert b._requests[-1][1] == True


    def test_pushToQueue_single_PrevUndelimited_CurrentUndelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request1 = [bytearray(b"testdata1"), False]
        request2 = [bytearray(b"testdata2"), False]
        b.pushToQueue(*request1)
        b.pushToQueue(*request2)

        assert len(b._requests) == 1
        assert b._requests[-1][0] == request1[0] + request2[0]
        assert b._requests[-1][1] == False


    def test_pushToQueue_single_PrevDelimited_currentUndelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request1 = [bytearray(b"testdata1"), True]
        request2 = [bytearray(b"testdata2"), False]
        b.pushToQueue(*request1)
        b.pushToQueue(*request2)

        assert len(b._requests) == 2
        assert b._requests[0] == request1
        assert b._requests[1] == request2
        assert len(b._data) == 0


    def test_pushToQueue_single_PrevDelimited_currentDelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request1 = [bytearray(b"testdata1"), True]
        request2 = [bytearray(b"testdata2"), True]
        b.pushToQueue(*request1)
        b.pushToQueue(*request2)

        assert len(b._requests) == 2
        assert b._requests[0] == request1
        assert b._requests[1] == request2
        assert len(b._data) == 0


    def test_pushToQueue_many_prevDelimited_currentDelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request1 = [bytearray(b"testdata1"), True]
        request2 = [bytearray(b"testdata2"), True]
        request3 = [bytearray(b"testdata3"), True]
        request4 = [bytearray(b"testdata4"), True]
        b.pushToQueue(*request1)
        b.pushToQueue(*request2)
        b.pushToQueue(*request3)
        b.pushToQueue(*request4)

        assert len(b._requests) == 4
        assert b._requests[0] == request1
        assert b._requests[1] == request2
        assert b._requests[2] == request3
        assert b._requests[3] == request4
        assert len(b._data) == 0

    def test_pushToQueue_many_prevDelimited_currentUndelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request1 = [bytearray(b"testdata1"), True]
        request2 = [bytearray(b"testdata2"), True]
        request3 = [bytearray(b"testdata3"), True]
        request4 = [bytearray(b"testdata4"), False]
        b.pushToQueue(*request1)
        b.pushToQueue(*request2)
        b.pushToQueue(*request3)
        b.pushToQueue(*request4)

        assert len(b._requests) == 4
        assert b._requests[0] == request1
        assert b._requests[1] == request2
        assert b._requests[2] == request3
        assert b._requests[3] == request4
        assert len(b._data) == 0


    def test_pushToQueue_many_prevUndelimited_currentUndelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request1 = [bytearray(b"testdata1"), True]
        request2 = [bytearray(b"testdata2"), True]
        request3 = [bytearray(b"testdata3"), False]
        request4 = [bytearray(b"testdata4"), False]
        b.pushToQueue(*request1)
        b.pushToQueue(*request2)
        b.pushToQueue(*request3)
        b.pushToQueue(*request4)

        assert len(b._requests) == 3
        assert b._requests[0] == request1
        assert b._requests[1] == request2
        assert b._requests[2] == [request3[0] + request4[0], False]
        assert len(b._data) == 0

    def test_pushToQueue_many_prevUndelimited_currentDelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request1 = [bytearray(b"testdata1"), True]
        request2 = [bytearray(b"testdata2"), True]
        request3 = [bytearray(b"testdata3"), False]
        request4 = [bytearray(b"testdata4"), True]
        b.pushToQueue(*request1)
        b.pushToQueue(*request2)
        b.pushToQueue(*request3)
        b.pushToQueue(*request4)

        assert len(b._requests) == 3
        assert b._requests[0] == request1
        assert b._requests[1] == request2
        assert b._requests[2] == [request3[0] + request4[0], True]
        assert len(b._data) == 0
    

    ## popFromQueue()
    def test_popFromQueue_empty(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        with pytest.raises(IndexError) as excInfo:
            b.popFromQueue()

        assert "Cannot pop" in str(excInfo.value)
        assert "empty" in str(excInfo.value)
        assert len(b._requests) == 0


    def test_popFromQueue_single_Undelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None

        request = [bytearray(b"testdata"), False]
        b.pushToQueue(*request)

        with pytest.raises(ValueError) as excInfo:
            b.popFromQueue()

        assert "Cannot pop" in str(excInfo.value)
        assert "undelimited" in str(excInfo.value)
        assert len(b._requests) == 1


    def test_popFromQueue_single_Delimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None
        
        request = [bytearray(b"testdata"), True]
        b.pushToQueue(*request)

        assert b.popFromQueue() == request
        assert len(b._requests) == 0


    def test_popFromQueue_many_Undelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None
        
        request1 = [bytearray(b"testdata1"), True]
        request2 = [bytearray(b"testdata2"), True]
        request3 = [bytearray(b"testdata3"), True]
        request4 = [bytearray(b"testdata4"), False]
        b.pushToQueue(*request1)
        b.pushToQueue(*request2)
        b.pushToQueue(*request3)
        b.pushToQueue(*request4)

        assert b.popFromQueue() == request1
        assert b.popFromQueue() == request2
        assert b.popFromQueue() == request3

        with pytest.raises(ValueError) as excInfo:
            b.popFromQueue()

        assert "Cannot pop" in str(excInfo.value)
        assert "undelimited" in str(excInfo.value)
        assert len(b._requests) == 1


    def test_popFromQueue_many_Delimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b._execRequestParsing = lambda *args, **kwargs: None
        
        request1 = [bytearray(b"testdata1"), True]
        request2 = [bytearray(b"testdata2"), True]
        request3 = [bytearray(b"testdata3"), True]
        request4 = [bytearray(b"testdata4"), True]
        b.pushToQueue(*request1)
        b.pushToQueue(*request2)
        b.pushToQueue(*request3)
        b.pushToQueue(*request4)

        assert b.popFromQueue() == request1
        assert b.popFromQueue() == request2
        assert b.popFromQueue() == request3
        assert b.popFromQueue() == request4

        assert len(b._requests) == 0

    ## emptyQueue
    ## singleQueue (undelimited vs delimited)
    ## multiQueue (undelimited vs delimited)



class Test_Buffer_HookSetting:
    def test_hookSettingAndCalling(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        chunk = bytearray(b"completeRequest\r\n") ## requestHook only called on completeRequests
        
        isRan = False
        def func(buffer, chunkBytes):
            nonlocal isRan
            isRan = True
        
        b.setHook(func)
        b._requestHook(chunk)
        assert isRan == True

        isRan = False
        b._execRequestParsing(chunk)
        assert isRan == True


 