import collections
import os
import sys
import functools
import pytest

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from _proxyDS import Buffer




@pytest.fixture()
def oneLenDelimiterTestSetup():
    delimiters = [b"\r"]
    delimiter = delimiters[0]
    b = Buffer(delimiters)
    queue = BufferReqParsingHelpers._setupRequestHookMock(b)
    yield b, queue

@pytest.fixture()
def twoLenDelimiterTestSetup():
    delimiters = [b"\r\n"]
    delimiter = delimiters[0]
    b = Buffer(delimiters)
    queue = BufferReqParsingHelpers._setupRequestHookMock(b)
    yield b, queue

@pytest.fixture()
def manyLenDelimiterTestSetup():
    delimiters = [b"\r\n\r\n"]
    delimiter = delimiters[0]
    b = Buffer(delimiters)
    queue = BufferReqParsingHelpers._setupRequestHookMock(b)
    yield b, queue



class BufferReqParsingHelpers:
    @classmethod
    def _setupRequestHookMock(cls, buffer: Buffer) -> collections.deque:
        ## NOTE: The return queue returns the requests that were passed to the requestHook (in LIFO order)
        queue = collections.deque([])
        def requestHook(self, request):
            nonlocal queue
            queue.appendleft(request)

        buffer._requestHook = functools.partial(requestHook, buffer)
        return queue

class Test_Buffer_RequestParsing:



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
    def test_defaultWriteHook_SingleChunk_OnePartialRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        req1 = bytearray(b"incompleteR")
        chunk = req1
        b.write(chunk)

        assert b._data == chunk
        assert len(b._requests) == 1
        assert b._requests[-1] == [req1, False]
        
        assert len(queue) == 0

        assert b._prevEndBuffer == bytearray(b"R")


    def test_defaultWriteHook_SingleChunk_OneCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq\r\n")
        chunk = req1
        b.write(chunk)

        assert b._data == chunk
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == req1

        assert b._prevEndBuffer == bytearray(b"")


    def test_defaultWriteHook_SingleChunk_OneCompleteRequest_OnePartialRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"incompleteR")
        chunk = req1 + req2
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk
        assert len(b._requests) == 1
        assert b._requests[-1] == [req2, False]
        
        assert len(queue) == 1
        assert queue.pop() == req1

        assert b._prevEndBuffer == bytearray(b"R")

    def test_defaultWriteHook_SingleChunk_TwoCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        chunk = req1 + req2
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk
        assert len(b._requests) == 0
        
        assert len(queue) == 2
        assert queue.pop() == req1
        assert queue.pop() == req2

        assert b._prevEndBuffer == bytearray(b"")

    def test_defaultWriteHook_SingleChunk_TwoCompleteRequest_OnePartialRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        req3 = bytearray(b"incompleteR")
        chunk = req1 + req2 + req3
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk
        assert len(b._requests) == 1
        assert b._requests[-1] == [req3, False]
        
        assert len(queue) == 2
        assert queue.pop() == req1
        assert queue.pop() == req2

        assert b._prevEndBuffer == bytearray(b"R")

    def test_defaultWriteHook_SingleChunk_ManyCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        req3 = bytearray(b"completeReq3\r\n")
        req4 = bytearray(b"completeReq4\r\n")
        req5 = bytearray(b"completeReq5\r\n")
        chunk = req1 + req2 + req3 + req4 + req5
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk
        assert len(b._requests) == 0
        
        assert len(queue) == 5
        assert queue.pop() == req1
        assert queue.pop() == req2
        assert queue.pop() == req3
        assert queue.pop() == req4
        assert queue.pop() == req5
    
        assert b._prevEndBuffer == bytearray(b"")

    def test_defaultWriteHook_SingleChunk_ManyCompleteRequest_OnePartialRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        req3 = bytearray(b"completeReq3\r\n")
        req4 = bytearray(b"completeReq4\r\n")
        req5 = bytearray(b"incompleteR")
        chunk = req1 + req2 + req3 + req4 + req5
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk
        assert len(b._requests) == 1
        assert b._requests[-1] == [req5, False]
        
        assert len(queue) == 4
        assert queue.pop() == req1
        assert queue.pop() == req2
        assert queue.pop() == req3
        assert queue.pop() == req4

        assert b._prevEndBuffer == bytearray(b"R")

    
    ## Tests for request spreading over chunks (spread from start chunk 1 to mid chunk 2)
    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_OneCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 2
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_OneCompleteRequest_OnePartialRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")
        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 2
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_TwoCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 3
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_TwoCompleteRequest_OnePartialRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 3
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")



    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_ManyCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 5
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")
        assert queue.pop() == bytearray(b"completeReq5\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteRequest_ManyCompleteRequest_OnePartialRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 5
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")
        assert queue.pop() == bytearray(b"completeReq5\r\n")


    ## Tests for request spreading over chunks (spread from start from mid chunk 1 to mid chunk 2)
    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 2
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_OneParitalRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 2
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_OneCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 3
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_OneCompleteRequest_OnePartialRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 3
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_TwoCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 4
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_TwoCompleteRequest_OnePartialRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 4
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")
        

    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_ManyCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\ncompleteReq6\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 6
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")
        assert queue.pop() == bytearray(b"completeReq3\r\n")
        assert queue.pop() == bytearray(b"completeReq4\r\n")
        assert queue.pop() == bytearray(b"completeReq5\r\n")
        assert queue.pop() == bytearray(b"completeReq6\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteRequest_OneSpreadCompleteRequest_ManyCompleteRequest_OnePartialRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\ncompleteReq6\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
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
    def test_defaultWriteHook_TwoChunk_OneSpreadDelimiterCompleteRequest(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq")
        chunk2 = bytearray(b"\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"q")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_SizeTwoDelimiter(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"\r")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_OnePartialRequest_SizeTwoDelimiter(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"\r")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_OneCompleteRequest_SizeTwoDelimiter(self, twoLenDelimiterTestSetup):
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r")
        chunk2 = bytearray(b"\ncompleteReq2\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"\r")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 2
        assert queue.pop() == bytearray(b"completeReq1\r\n")
        assert queue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_SizeFourDelimiter_Option1(self, manyLenDelimiterTestSetup):
        b, queue = manyLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"\n\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"eq\r")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_SizeFourDelimiter_Option2(self, manyLenDelimiterTestSetup):
        b, queue = manyLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r\n")
        chunk2 = bytearray(b"\r\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteRequest_SizeFourDelimiter_Option3(self, manyLenDelimiterTestSetup):
        b, queue = manyLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r\n\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        b.write(chunk2)

        ## Data should be removed buffer()._data once popped from buffer()._requests
        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == bytearray(b"completeReq\r\n\r\n")



class Test_DelimiterParsing:
    ## delimiter chunk tests
    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_OneChunk_delimited(self, oneLenDelimiterTestSetup) -> None:
        b, queue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        b.write(chunk1)

        assert b._data == chunk1
        assert len(b._requests) == 0
        assert b._prevEndBuffer == bytearray(b"")

        assert len(queue) == 1
        assert queue.pop() == chunk1

    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_OneChunk_undelimited(self, oneLenDelimiterTestSetup) -> None:
        b, queue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"incompleteReq")
        b.write(chunk1)

        assert b._data == chunk1
        assert len(b._requests) == 1
        assert b._requests[-1] == [chunk1, False]
        assert b._prevEndBuffer == bytearray(b"")
        assert len(queue) == 0

    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_TwoChunk_FirstDelimited_SecondUndelimited(self, oneLenDelimiterTestSetup) -> None:
        b, queue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"incompleteReq")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [chunk2, False]

        assert len(queue) == 1
        assert queue.pop() == chunk1
        
    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_TwoChunk_FirstDelimited_SecondDelimited(self, oneLenDelimiterTestSetup) -> None:
        b, queue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"completeReq\r")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0

        assert len(queue) == 2
        assert queue.pop() == chunk1
        assert queue.pop() == chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_TwoChunk_FirstUndelimited_SecondDelimited(self, oneLenDelimiterTestSetup) -> None:
        b, queue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"incompleteR")
        chunk2 = bytearray(b"eq\r")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == chunk1 + chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_TwoChunk_FirstUndelimited_SecondUndelimited(self, oneLenDelimiterTestSetup) -> None:
        b, queue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"incomplete")
        chunk2 = bytearray(b"Req")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [chunk1+chunk2, False]
        
        assert len(queue) == 0



    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_OneChunk_delimited(self, twoLenDelimiterTestSetup) -> None:
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r\n")
        b.write(chunk1)

        assert b._data == chunk1
        assert len(b._requests) == 0
        assert b._prevEndBuffer == bytearray(b"")

        assert len(queue) == 1
        assert queue.pop() == chunk1

    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_OneChunk_undelimited(self, twoLenDelimiterTestSetup) -> None:
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"incompleteReq")
        b.write(chunk1)

        assert b._data == chunk1
        assert len(b._requests) == 1
        assert b._requests[-1] == [chunk1, False]
        assert b._prevEndBuffer == bytearray(b"q")
        assert len(queue) == 0

    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_TwoChunk_FirstDelimited_SecondUndelimited(self, twoLenDelimiterTestSetup) -> None:
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r\n")
        chunk2 = bytearray(b"incompleteReq")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"q")

        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [chunk2, False]

        assert len(queue) == 1
        assert queue.pop() == chunk1
        
    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_TwoChunk_FirstDelimited_SecondDelimited(self, twoLenDelimiterTestSetup) -> None:
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r\n")
        chunk2 = bytearray(b"completeReq\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0

        assert len(queue) == 2
        assert queue.pop() == chunk1
        assert queue.pop() == chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_TwoChunk_FirstUndelimited_SecondDelimited(self, twoLenDelimiterTestSetup) -> None:
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"incompleteR")
        chunk2 = bytearray(b"eq\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"R")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 0
        
        assert len(queue) == 1
        assert queue.pop() == chunk1 + chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_TwoChunk_FirstUndelimited_SecondUndelimited(self, twoLenDelimiterTestSetup) -> None:
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"incomplete")
        chunk2 = bytearray(b"Req")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"q")

        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [chunk1+chunk2, False]
        
        assert len(queue) == 0

    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_SpreadDelimiter(self, twoLenDelimiterTestSetup) -> None:
        b, queue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"incompleteReq\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"\r")
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")

        assert b._data == chunk1 + chunk2
        assert len(b._requests) == 1
        assert b._requests[-1] == [chunk1+chunk2, False]
        
        assert len(queue) == 0





    # def test_defaultWriteHook_PrevEndBuffer_DLSizeMultiple_OneChunk_delimited(self) -> None:
    #     ...

    # def test_defaultWriteHook_PrevEndBuffer_DLSizeMultiple_OneChunk_undelimited(self) -> None:
    #     ...

    # def test_defaultWriteHook_PrevEndBuffer_DLSizeMultiple_TwoChunk_FirstDelimited_SecondUndelimited(self) -> None:
    #     ...

    # def test_defaultWriteHook_PrevEndBuffer_DLSizeMultiple_TwoChunk_FirstDelimited_SecondDelimited(self) -> None:
    #     ...

    # def test_defaultWriteHook_PrevEndBuffer_DLSizeMultiple_TwoChunk_FirstUndelimited_SecondDelimited(self) -> None:
    #     ...

    # def test_defaultWriteHook_PrevEndBuffer_DLSizeMultiple_TwoChunk_PirstUndelimited_SecondUndelimited(self) -> None:
    #     ...



    ## TODO: Consider restructuring delimiter chunk-split tests


    ## TODO: Consider adding ManyChunk tests cases
    

    # def test_defaultWriteHook_TwoChunks_OneCompleteRequest(self, oneLenDelimiterTestSetup):
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

    # def test_defaultWriteHook_TwoChunks_OneCompleteRequest_OnePartialRequest(self, oneLenDelimiterTestSetup):
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

    # def test_defaultWriteHook_TwoChunks_TwoCompleteRequest(self, oneLenDelimiterTestSetup):
    #     raise NotImplementedError()

    # def test_defaultWriteHook_TwoChunks_TwoCompleteRequest_OnePartialRequest(self, oneLenDelimiterTestSetup):
    #     raise NotImplementedError()

    # def test_defaultWriteHook_TwoChunks_ManyCompleteRequest(self, oneLenDelimiterTestSetup):
    #     raise NotImplementedError()

    # def test_defaultWriteHook_TwoChunks_ManyCompleteRequest_OnePartialRequest(self, oneLenDelimiterTestSetup):
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

