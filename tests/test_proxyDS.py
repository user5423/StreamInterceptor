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
        
    
   
