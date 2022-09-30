import collections
import os
import sys
import functools
import pytest

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from _proxyDS import Buffer

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
        
    
    

    ## write() tests
    
    def test_write_zeroBytes(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        testBytes = b""
        b.write(testBytes)

        assert b._data == testBytes
        assert len(b._requests) == 0
        
    def test_write_oneByte(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        testBytes = b"t"
        b.write(testBytes)
        
        assert len(b._data) == len(testBytes)
        assert len(b._requests) == 0
        
    def test_write_manyBytes(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        testBytes = bytearray(b"testdata")
        b.write(testBytes)
        
        assert len(b._data) == len(testBytes)
        assert len(b._requests) == 0

    def test_write_zeroBytes_nonEmptyBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        b._data += b""
        testBytes = b"data"
        b.write(testBytes)
        
        assert b._data == bytearray(b"data")
        assert len(b._requests) == 0

    def test_write_oneByte_nonEmptyBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        b._data += b"t"
        testBytes = b"data"
        b.write(testBytes)
        
        assert b._data == bytearray(b"tdata")
        assert len(b._requests) == 0

    def test_write_manyBytes_nonEmptyBuffer(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        b._data += b"test"
        testBytes = b"data"
        b.write(testBytes)

        assert b._data == bytearray(bytearray(b"testdata"))
        assert len(b._requests) == 0



class Test_Buffer_RequestQueueOperations:
    ## peakFromQueue()
    def test_peakFromQueue_empty(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        with pytest.raises(IndexError) as excInfo:
            b.peakFromQueue()

        assert "Cannot peak" in str(excInfo.value)
        assert len(b._data) == 0
        assert len(b._requests) == 0


    def test_peakFromQueue_singleUndelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        request = [bytearray(b"testdata"), False]
        b._requests.append(request)

        assert request == b.peakFromQueue()
        assert len(b._data) == 0
        assert len(b._requests) == 1

    def test_peakFromQueue_singleDelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        request = [bytearray(b"testdata"), True]
        b._requests.append(request)

        assert request == b.peakFromQueue()
        assert len(b._data) == 0
        assert len(b._requests) == 1


    def test_peakFromQueue_manyUndelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        b._requests.append([bytearray(b"testdata1"), True])
        b._requests.append([bytearray(b"testdata2"), True])
        b._requests.append([bytearray(b"testdata3"), True])
        request = [bytearray(b"testdata"), False]
        b._requests.append(request)

        assert request == b.peakFromQueue()
        assert len(b._data) == 0
        assert len(b._requests) == 4


    def test_peakFromQueue_manyDelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        b._requests.append([bytearray(b"testdata1"), True])
        b._requests.append([bytearray(b"testdata2"), True])
        b._requests.append([bytearray(b"testdata3"), True])
        request = [bytearray(b"testdata"), True]
        b._requests.append(request)

        assert request == b.peakFromQueue()
        assert len(b._data) == 0
        assert len(b._requests) == 4


    ## pushToQueue()
    def test_pushToQueue_empty_Undelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        request = [bytearray(b"testdata"), False]
        b.pushToQueue(*request)

        assert len(b._requests) == 1
        assert b._requests[-1] == request
        assert len(b._data) == 0


    def test_pushToQueue_empty_Delimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        request = [bytearray(b"testdata"), True]
        b.pushToQueue(*request)

        assert len(b._requests) == 1
        assert b._requests[-1] == request
        assert len(b._data) == 0


    def test_pushToQueue_single_PrevUndelimited_CurrentDelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

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
        b.execWriteHook = lambda *args, **kwargs: None

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
        b.execWriteHook = lambda *args, **kwargs: None

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
        b.execWriteHook = lambda *args, **kwargs: None

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
        b.execWriteHook = lambda *args, **kwargs: None

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
        b.execWriteHook = lambda *args, **kwargs: None

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
        b.execWriteHook = lambda *args, **kwargs: None

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
        b.execWriteHook = lambda *args, **kwargs: None

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
        b.execWriteHook = lambda *args, **kwargs: None

        with pytest.raises(IndexError) as excInfo:
            b.popFromQueue()

        assert "Cannot pop" in str(excInfo.value)
        assert "empty" in str(excInfo.value)
        assert len(b._requests) == 0


    def test_popFromQueue_single_Undelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

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
        b.execWriteHook = lambda *args, **kwargs: None
        
        request = [bytearray(b"testdata"), True]
        b.pushToQueue(*request)

        assert b.popFromQueue() == request
        assert len(b._requests) == 0


    def test_popFromQueue_many_Undelimited(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None
        
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
        b.execWriteHook = lambda *args, **kwargs: None
        
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



class Test_Buffer_Hooks:
    ## TODO:
    ## execWriteHook()
    ## setHook()
    ## _requestHook()
    ## _writeHook()

    def _setupRequestHookMock(self, buffer: Buffer) -> collections.deque:
        ## NOTE: The return queue returns the requests that were passed to the requestHook (in LIFO order)
        queue = collections.deque([])
        def requestHook(self, request):
            nonlocal queue
            queue.appendleft(request)

        buffer._requestHook = functools.partial(requestHook, buffer)
        return queue

    def test_hookSettingAndCalling(self):
        delimiters = [b"\r\n"]
        b = Buffer(delimiters)
        chunk = bytearray(b"test")
        
        isRan = False
        def func(buffer, chunkBytes):
            nonlocal isRan
            isRan = True
        
        b.setHook(func)
        b._writeHook(chunk)
        assert isRan == True


        isRan = False
        b.execWriteHook(chunk)
        assert isRan == True

    def test_defaultWriteHook(self):
        raise NotImplementedError()

    ## TODO: Test if write() method calls hook

    ## TODO: Write methods for Buffer()._requestHook

    ## Scenarios
    

    ## starts
    ## - req starts on first byte of chunk
    ## - req starts on a middle byte of chunk
    ## - req starts on the end byte of chunk (should defer to next chunk)


    ## ends
    ## - delimiter (size 1) ends on last byte of chunk
    ## - delimiter (size 1) ends on first byte of chunk
    ## - delimiter (size 1) ends on middle byte of chunk

    ## - delimiter (size > 1) ends over two or more chunks
    ## - delimiter (size > 1) ends on last byte of chunk
    ## - delimiter (size > 1) ends on first bytes of chunk
    ## - delimiter (size > 1) ends on middle bytes of chunk

    ## chunks iterated
    ## - req is contained inside a single chunk
    ## - req is spread out over two chunks
    ## - req is spread out over many chunks

    

    ## Single Chunks (> 1 requests)
    def test_defaultWriteHook_SingleChunk_OnePartialRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        req1 = bytearray(b"incompleteR")
        chunk = req1
        b.write(chunk)

        assert b._data == chunk
        assert len(b._requests) == 1
        assert b._requests[-1] == [req1, False]
        
        assert len(queue) == 0


    def test_defaultWriteHook_SingleChunk_OneCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        req1 = bytearray(b"completeReq\r\n")
        chunk = req1
        b.write(chunk)

        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == req1


    def test_defaultWriteHook_SingleChunk_OneCompleteRequest_OnePartialRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"incompleteR")
        chunk = req1 + req2
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == req2
        assert len(b._requests) == 1
        assert b._requests[-1] == [req2, False]
        
        assert len(queue) == 1
        assert queue.pop() == req1


    def test_defaultWriteHook_SingleChunk_TwoCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        chunk = req1 + req2
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 2
        assert queue.pop() == req1
        assert queue.pop() == req2


    def test_defaultWriteHook_SingleChunk_TwoCompleteRequest_OnePartialRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        req3 = bytearray(b"incompleteR")
        chunk = req1 + req2 + req3
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == req3
        assert len(b._requests) == 1
        assert b._requests[-1] == [req3, False]
        
        assert len(queue) == 2
        assert queue.pop() == req1
        assert queue.pop() == req2


    def test_defaultWriteHook_SingleChunk_ManyCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        req3 = bytearray(b"completeReq3\r\n")
        req4 = bytearray(b"completeReq4\r\n")
        req5 = bytearray(b"completeReq5\r\n")
        chunk = req1 + req2 + req3 + req4 + req5
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 5
        assert queue.pop() == req1
        assert queue.pop() == req2
        assert queue.pop() == req3
        assert queue.pop() == req4
        assert queue.pop() == req5
    

    def test_defaultWriteHook_SingleChunk_ManyCompleteRequest_OnePartialRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        req3 = bytearray(b"completeReq3\r\n")
        req4 = bytearray(b"completeReq4\r\n")
        req5 = bytearray(b"incompleteR")
        chunk = req1 + req2 + req3 + req4 + req5
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == req5
        assert len(b._requests) == 1
        assert b._requests[-1] == [req5, False]
        
        assert len(queue) == 4
        assert queue.pop() == req1
        assert queue.pop() == req2
        assert queue.pop() == req3
        assert queue.pop() == req4

    
    ## Tests for request spreading over chunks (spread from start chunk 1 to mid chunk 2)
    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_OneCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 2
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_OneCompleteRequest_OnePartialRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\nincompleteR")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"incompleteR")
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 2
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_TwoCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 3
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_TwoCompleteRequest_OnePartialRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\nincompleteR")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"incompleteR")
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 3
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_ManyCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 5
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")
        assert queue.pop() == bytearray(b"completeReq5\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_ManyCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\nincompleteR")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"incompleteR")
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 5
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")
        assert queue.pop() == bytearray(b"completeReq5\r\n")


    ## Tests for request spreading over chunks (spread from start from mid chunk 1 to mid chunk 2)
    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 2
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_OneParitalRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\nincompleteR")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"incompleteR")
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 2
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_OneCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 3
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_OneCompleteRequest_OnePartialRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\nincompleteR")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"incompleteR")
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 3
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_TwoCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 4
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_TwoCompleteRequest_OnePartialRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\nincompleteR")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"incompleteR")
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 4
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_ManyCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\ncompleteReq6\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 6
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")
        assert queue.pop() == bytearray(b"completeReq5\r\n")
        assert queue.pop() == bytearray(b"completeReq6\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_ManyCompleteRequest_OnePartial(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\ncompleteReq6\r\nincompleteR")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"incompleteR")
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 6
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")
        assert queue.pop() == bytearray(b"completeReq5\r\n")
        assert queue.pop() == bytearray(b"completeReq6\r\n")

    
    ## TODO: Tests for request spreading over chunks (spread from start from mid chunk 1 to end chunk 2)
    ## The number of combos are too much


    ## Tests for request delimiter spreading over chunks
    def test_defaultWriteHook_TwoChunk_OneSpreadDelimiterCompleteRequest(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq")
        chunk2 = bytearray(b"\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_SizeTwoDelimiter(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_OnePartialRequest_SizeTwoDelimiter(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"\nincompleteR")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"incompleteR")
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_OneCompleteRequest_SizeTwoDelimiter(self):
        delimiters = [b"\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq1\r")
        chunk2 = bytearray(b"\ncompleteReq2\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 2
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_SizeFourDelimiter_Option1(self):
        delimiters = [b"\r\n\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"\n\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_SizeFourDelimiter_Option2(self):
        delimiters = [b"\r\n\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq\r\n")
        chunk2 = bytearray(b"\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_SizeFourDelimiter_Option3(self):
        delimiters = [b"\r\n\r\n"]
        delimiter = delimiters[0]
        b = Buffer(delimiters)
        queue = self._setupRequestHookMock(b)

        chunk1 = bytearray(b"completeReq\r\n\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == bytearray(b"")
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n\r\n")


    ## TODO: Consider restructuring delimiter chunk-split tests


    ## TODO: Consider adding ManyChunk tests cases
    

    # def test_defaultWriteHook_TwoChunks_OneCompleteRequest(self):
    #     delimiters = [b"\r\n"]
    #     delimiter = delimiters[0]
    #     b = Buffer(delimiters)

    #     testBytes1 = bytearray(b"complete")
    #     testBytes2 = bytearray(b"Req\r\n")
        
    #     queue = collections.deque([])
    #     def requestHook(self, request):
    #         nonlocal queue
    #         queue.appendleft(request)

    #     b._requestHook = functools.partial(requestHook, b)
    #     b.write(testBytes1)
    #     b.write(testBytes2)

    #     ## Data should be removed buffer()._data once popped from buffer()._requests
    #     assert b._data == bytearray(b"")
    #     assert len(b._requests) == 0
        
    #     assert len(queue) == 1
    #     assert queue.pop() == bytearray(b"completeReq\r\n")

    # def test_defaultWriteHook_TwoChunks_OneCompleteRequest_OnePartialRequest(self):
    #     delimiters = [b"\r\n"]
    #     delimiter = delimiters[0]
    #     b = Buffer(delimiters)

    #     testBytes1 = bytearray(b"complete")
    #     testBytes2 = bytearray(b"Req\r\nincompleteR")
        
    #     queue = collections.deque([])
    #     def requestHook(self, request):
    #         nonlocal queue
    #         queue.appendleft(request)

    #     b._requestHook = functools.partial(requestHook, b)
    #     b.write(testBytes1)
    #     b.write(testBytes2)

    #     ## Data should be removed buffer()._data once popped from buffer()._requests
    #     assert b._data == bytearray(b"")
    #     assert len(b._requests) == 0
        
    #     assert len(queue) == 1
    #     assert queue.pop() == bytearray(b"completeReq\r\n")

    # def test_defaultWriteHook_TwoChunks_TwoCompleteRequest(self):
    #     raise NotImplementedError()

    # def test_defaultWriteHook_TwoChunks_TwoCompleteRequest_OnePartialRequest(self):
    #     raise NotImplementedError()

    # def test_defaultWriteHook_TwoChunks_ManyCompleteRequest(self):
    #     raise NotImplementedError()

    # def test_defaultWriteHook_TwoChunks_ManyCompleteRequest_OnePartialRequest(self):
    #     raise NotImplementedError()


    ## Many Chunks (> 1 requests)




    ## Single Chunk (completes only)

    ## 1a.
    ##  - chunk contains exactly 1 request
    ##  - request starts at chunk start
    ##  - request ends at chunk end

    ## 3a.
    ##  - chunk contains exactly 2 requests
    ##  - first complete req starts at chunk start
    ##  - last complete req ends at chunk end

    ## 5a.
    ##  - chunk contains > 2 request
    ##  - first complete req starts at chunk start
    ##  - last complete req ends at chunk end


    ## Single Chunk (partial at start)

    ## 2a.
    ##  - chunk contains exactly 1 request and 1 partial request
    ##  - complete req starts at chunk start
    ##  - complete req ends before chunk end
    ##  - partial req starts immediately after

    ## 4a.
    ##  - chunk contains exactly 2 request and 1 partial request
    ##  - first complete req starts at chunk start
    ##  - last complete req ends before chunk end
    ##  - partial req starts immediately after

    ## 6a.
    ##  - chunk contains > 2 request and 1 partial request
    ##  - first complete req starts at chunk start
    ##  - last complete req ends before chunk end
    ##  - partial req starts immediately after


    ## Single Chunk (partial at end)

    ## 2b.
    ##  - chunk contains 1 request and 1 partial request
    ##  - complete req starts at chunk start
    ##  - complete req ends before chunk end
    ##  - partial req starts immediately after

    ## 4b.
    ##  - chunk contains exactly 2 request and 1 partial request
    ##  - first complete req starts at chunk start
    ##  - last complete req ends before chunk end
    ##  - partial req starts immediately after

    ## 6b.
    ##  - chunk contains > 2 request and 1 partial request
    ##  - first complete req starts at chunk start
    ##  - last complete req ends before chunk end
    ##  - partial req starts immediately after


    ## Single Chunk (partial at start and at end)

    ## 0.
    ##  - chunk contains 
    ##      - 1 partial request (starts at current chunk, does not complete)
    ##  - request starts at chunk start

    ## 1.
    ##  - chunk contains 
    ##      - 1 partial (starts in prev chunk, does NOT complete)

    ## 2.
    ##  - chunk contains
    ##      - 1 partial (starts in prev x 2 chunk, does NOT complete)

