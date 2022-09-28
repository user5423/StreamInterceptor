from argparse import ArgumentError
import collections
from multiprocessing.sharedctypes import Value
import os
import sys

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
        REQUEST_DELIMITERS = ["\r\n"]
        b = Buffer(REQUEST_DELIMITERS)
        
        assert b.REQUEST_DELIMITERS == REQUEST_DELIMITERS
        assert isinstance(b._data, bytearray) and len(b._data) == 0
        assert isinstance(b._requests, collections.deque) and len(b._requests) == 0
        
        
    def test_RequestDelimiters_many(self) -> None:
        ## NOTE: The order of the delimiters is important for when message can have multiple potential delimiters
        REQUEST_DELIMITERS = ["\r\n", "\r"]
        b = Buffer(REQUEST_DELIMITERS)
        
        assert b.REQUEST_DELIMITERS == REQUEST_DELIMITERS
        assert isinstance(b._data, bytearray) and len(b._data) == 0
        assert isinstance(b._requests, collections.deque) and len(b._requests) == 0 
        
        
    def test_RequestDelimiters_duplicate(self) -> None:
        ## NOTE: Duplicates delimitesr are bad practice
        REQUEST_DELIMITERS = ["\r\n", "\r", "\r\n"]
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
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        b._data += b"testdata"
        bufferLength = len(b._data)
        
        assert b.read(-1) == b._data
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0

        
    def test_read_zeroBytes(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        b._data += b"testdata"
        bufferLength = len(b._data)
        
        assert b.read(0) == b._data[0:0]
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0

        
    def test_read_oneByte(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        b._data += b"testdata"
        bufferLength = len(b._data)
        
        assert b.read(1) == b._data[0:1]
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0
        
        
    def test_read_manyBytes(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        b._data += b"testdata"
        bufferLength = len(b._data)
        readLength = bufferLength // 2
        
        assert b.read(readLength) == b._data[0:readLength]
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0
        
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be read EXCEEDS the number of current bytes stored in the buffer
    def test_read_negativeBytes_zeroBuffer(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        bufferLength = len(b._data)
        
        assert b.read(-1) == b._data
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0
        
    def test_read_zeroBytes_zeroBuffer(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        bufferLength = len(b._data)
        
        assert b.read(0) == bytearray()
        assert bufferLength == 0
        assert len(b._requests) == 0
        
    def test_read_oneByte_zeroBuffer(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        bufferLength = len(b._data)
        
        assert b.read(1) == bytearray()
        assert bufferLength == 0
        assert len(b._requests) == 0
        
        
    def test_read_manyBytes_oneBuffer(self):
        delimiters = ["\r\n"]
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
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        testBytes = bytearray(b"testdata")
        b._data += testBytes

        assert testBytes == b.pop(-1)
        assert len(b._data) == 0
        assert len(b._requests) == 0

        
    def test_pop_zeroBytes(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        testBytes = bytearray(b"testdata")
        b._data += testBytes
        bufferLength = len(b._data)
        
        assert testBytes[0:0] == b.pop(0)
        assert bufferLength == len(b._data)
        assert len(b._requests) == 0

        
    def test_pop_oneByte(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        testBytes = bytearray(b"testdata")
        b._data += testBytes
        bufferLength = len(b._data)
        popLength = 1
        
        assert testBytes[0:1] == b.pop(1) 
        assert bufferLength - popLength == len(b._data)
        assert len(b._requests) == 0
        
        
    def test_pop_manyBytes(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        testBytes = bytearray(b"testdata")
        b._data += testBytes
        bufferLength = len(testBytes)
        popLength = bufferLength // 2
        
        assert testBytes[0:popLength] == b.pop(popLength)
        assert bufferLength - popLength == len(b._data)
        assert len(b._requests) == 0
        
    
    ## NOTE: These tests are in the scenario where the number of desired bytes
    ## to be pop EXCEEDS the number of current bytes stored in the buffer
    def test_pop_negativeBytes_zeroBuffer(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        
        assert b._data == b.pop(-1)
        assert len(b._data) == 0
        assert len(b._requests) == 0
        
    def test_pop_zeroBytes_zeroBuffer(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        
        assert bytearray() == b.pop(0)
        assert len(b._data) == 0
        assert len(b._requests) == 0
        
    def test_pop_oneByte_zeroBuffer(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        
        # b._data is initialized as empty bytearray()
        
        assert bytearray() == b.pop(1)
        assert len(b._data) == 0
        assert len(b._requests) == 0
        
        
    def test_pop_manyBytes_oneBuffer(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)

        testBytes = b"t"
        b._data += testBytes
        bufferLength = len(b._data) + 1
        
        assert testBytes == b.pop(bufferLength)
        assert len(b._data) == 0
        assert len(b._requests) == 0
        
    
    

    ## write() tests
    
    def test_write_zeroBytes(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        testBytes = b""
        b.write(testBytes)

        assert b._data == testBytes
        assert len(b._requests) == 0
        
    def test_write_oneByte(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        testBytes = b"t"
        b.write(testBytes)
        
        assert len(b._data) == len(testBytes)
        assert len(b._requests) == 0
        
    def test_write_manyBytes(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        testBytes = b"testdata"
        b.write(testBytes)
        
        assert len(b._data) == len(testBytes)
        assert len(b._requests) == 0

    def test_write_zeroBytes_nonEmptyBuffer(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        b._data += b""
        testBytes = b"data"
        b.write(testBytes)
        
        assert b._data == bytearray(b"data")
        assert len(b._requests) == 0

    def test_write_oneByte_nonEmptyBuffer(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        b._data += b"t"
        testBytes = b"data"
        b.write(testBytes)
        
        assert b._data == bytearray(b"tdata")
        assert len(b._requests) == 0

    def test_write_manyBytes_nonEmptyBuffer(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        b._data += b"test"
        testBytes = b"data"
        b.write(testBytes)

        assert b._data == bytearray(b"testdata")
        assert len(b._requests) == 0



    
class Test_Buffer_Hooks:
    ## TODO:
    ## execWriteHook()
    ## setHook()
    ## _requestHook()
    ## _writeHook()
    ...



class Test_Buffer_RequestQueueOperations:
    ## pushToQueue()

    ## popFromQueue()

    ## peakFromQueue()
    def test_peakFromQueue_empty(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        with pytest.raises(IndexError) as excInfo:
            b.peakFromQueue()

        assert "Cannot peak" in str(excInfo.value)


    def test_peakFromQueue_singleUndelimited(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        request = [b"testdata", False]
        b._requests.append(request)

        assert request == b.peakFromQueue()


    def test_peakFromQueue_singleDelimited(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        request = [b"testdata", True]
        b._requests.append(request)

        assert request == b.peakFromQueue()


    def test_peakFromQueue_manyUndelimited(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        b._requests.append([b"testdata1", True])
        b._requests.append([b"testdata2", True])
        b._requests.append([b"testdata3", True])
        request = [b"testdata", False]
        b._requests.append(request)

        assert request == b.peakFromQueue()


    def test_peakFromQueue_manyDelimited(self):
        delimiters = ["\r\n"]
        b = Buffer(delimiters)
        b.execWriteHook = lambda *args, **kwargs: None

        b._requests.append([b"testdata1", True])
        b._requests.append([b"testdata2", True])
        b._requests.append([b"testdata3", True])
        request = [b"testdata", True]
        b._requests.append(request)

        assert request == b.peakFromQueue()

    ## peak empty queue
    ## peak single queue
    ## peak multiple queue




