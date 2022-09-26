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