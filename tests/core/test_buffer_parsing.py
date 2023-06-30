import collections
import os
import sys
import functools
import pytest

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from _proxyDS import Buffer


class BufferReqParsingHelpers:
    @classmethod
    def _setupUserHookMock(cls, buffer: Buffer) -> collections.deque:
        userQueue = collections.deque([])
        def userHook(buffer, request):
            nonlocal userQueue
            userQueue.appendleft(request)
            return None

        buffer._userHook = functools.partial(userHook, buffer)
        return userQueue

    @classmethod
    def _setupProcessingHookMock(cls, buffer: Buffer) -> collections.deque:
        processingQueue = collections.deque([])
        def processingHook(buffer, request):
            nonlocal processingQueue
            processingQueue.appendleft(request)
            return True

        buffer._processingHook = functools.partial(processingHook, buffer)
        return processingQueue


@pytest.fixture()
def oneLenDelimiterTestSetup():
    delimiters = [b"\r"]
    delimiter = delimiters[0]
    b = Buffer(delimiters)
    userQueue = BufferReqParsingHelpers._setupUserHookMock(b)
    processingQueue = BufferReqParsingHelpers._setupProcessingHookMock(b)
    yield b, userQueue, processingQueue

@pytest.fixture()
def twoLenDelimiterTestSetup():
    delimiters = [b"\r\n"]
    delimiter = delimiters[0]
    b = Buffer(delimiters)
    userQueue = BufferReqParsingHelpers._setupUserHookMock(b)
    processingQueue = BufferReqParsingHelpers._setupProcessingHookMock(b)
    yield b, userQueue, processingQueue

@pytest.fixture()
def manyLenDelimiterTestSetup():
    delimiters = [b"\r\n\r\n"]
    delimiter = delimiters[0]
    b = Buffer(delimiters)
    userQueue = BufferReqParsingHelpers._setupUserHookMock(b)
    processingQueue = BufferReqParsingHelpers._setupProcessingHookMock(b)
    yield b, userQueue, processingQueue



class Test_Buffer_MessageParsing:



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
    def test_defaultWriteHook_SingleChunk_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        req1 = bytearray(b"incompleteR")
        chunk = req1
        b.write(chunk)

        assert b._data == chunk
        assert len(b._messages) == 1
        assert b._messages[-1] == [req1, False]
        
        assert len(processingQueue) == 0

        assert b._prevEndBuffer == bytearray(b"R")
        assert userQueue == processingQueue


    def test_defaultWriteHook_SingleChunk_OneCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq\r\n")
        chunk = req1
        b.write(chunk)

        assert userQueue == processingQueue
        assert b._data == chunk
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == req1

        assert b._prevEndBuffer == bytearray(b"")


    def test_defaultWriteHook_SingleChunk_OneCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"incompleteR")
        chunk = req1 + req2
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert userQueue == processingQueue
        assert b._data == chunk
        assert len(b._messages) == 1
        assert b._messages[-1] == [req2, False]
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == req1

        assert b._prevEndBuffer == bytearray(b"R")

    def test_defaultWriteHook_SingleChunk_TwoCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        chunk = req1 + req2
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert userQueue == processingQueue
        assert b._data == chunk
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 2
        assert processingQueue.pop() == req1
        assert processingQueue.pop() == req2

        assert b._prevEndBuffer == bytearray(b"")

    def test_defaultWriteHook_SingleChunk_TwoCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        req3 = bytearray(b"incompleteR")
        chunk = req1 + req2 + req3
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert userQueue == processingQueue
        assert b._data == chunk
        assert len(b._messages) == 1
        assert b._messages[-1] == [req3, False]
        
        assert len(processingQueue) == 2
        assert processingQueue.pop() == req1
        assert processingQueue.pop() == req2

        assert b._prevEndBuffer == bytearray(b"R")

    def test_defaultWriteHook_SingleChunk_ManyCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        req3 = bytearray(b"completeReq3\r\n")
        req4 = bytearray(b"completeReq4\r\n")
        req5 = bytearray(b"completeReq5\r\n")
        chunk = req1 + req2 + req3 + req4 + req5
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert userQueue == processingQueue
        assert b._data == chunk
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 5
        assert processingQueue.pop() == req1
        assert processingQueue.pop() == req2
        assert processingQueue.pop() == req3
        assert processingQueue.pop() == req4
        assert processingQueue.pop() == req5
    
        assert b._prevEndBuffer == bytearray(b"")

    def test_defaultWriteHook_SingleChunk_ManyCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        req1 = bytearray(b"completeReq1\r\n")
        req2 = bytearray(b"completeReq2\r\n")
        req3 = bytearray(b"completeReq3\r\n")
        req4 = bytearray(b"completeReq4\r\n")
        req5 = bytearray(b"incompleteR")
        chunk = req1 + req2 + req3 + req4 + req5
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert userQueue == processingQueue
        assert b._data == chunk
        assert len(b._messages) == 1
        assert b._messages[-1] == [req5, False]
        
        assert len(processingQueue) == 4
        assert processingQueue.pop() == req1
        assert processingQueue.pop() == req2
        assert processingQueue.pop() == req3
        assert processingQueue.pop() == req4

        assert b._prevEndBuffer == bytearray(b"R")

    
    ## Tests for request spreading over chunks (spread from start chunk 1 to mid chunk 2)
    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_OneCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 2
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_OneCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        assert userQueue == processingQueue
        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(processingQueue) == 2
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_TwoCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 3
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq3\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_TwoCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(processingQueue) == 3
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq3\r\n")



    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_ManyCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 5
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq3\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq4\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq5\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_ManyCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"Req1\r\ncompleteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(processingQueue) == 5
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq3\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq4\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq5\r\n")


    ## Tests for request spreading over chunks (spread from start from mid chunk 1 to mid chunk 2)
    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 2
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_OneParitalMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(processingQueue) == 2
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_OneCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 3
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq3\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_OneCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(processingQueue) == 3
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq3\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_TwoCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 4
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq3\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq4\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_TwoCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(processingQueue) == 4
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq3\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq4\r\n")
        

    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_ManyCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\ncompleteReq6\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 6
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq3\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq4\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq5\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq6\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_ManyCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r\ncomp")
        chunk2 = bytearray(b"leteReq2\r\ncompleteReq3\r\ncompleteReq4\r\ncompleteReq5\r\ncompleteReq6\r\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"p")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(processingQueue) == 6
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq3\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq4\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq5\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq6\r\n")
    
    ## TODO: Tests for request spreading over chunks (spread from start from mid chunk 1 to end chunk 2)
    ## The number of combos are too much



    ## Tests for request delimiter spreading over chunks
    def test_defaultWriteHook_TwoChunk_OneSpreadDelimiterCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq")
        chunk2 = bytearray(b"\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"q")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeReq\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_SizeTwoDelimiter(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"\r")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeReq\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_OnePartialMessage_SizeTwoDelimiter(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"\nincompleteR")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"\r")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"R")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [bytearray(b"incompleteR"), False]
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeReq\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_OneCompleteMessage_SizeTwoDelimiter(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq1\r")
        chunk2 = bytearray(b"\ncompleteReq2\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"\r")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 2
        assert processingQueue.pop() == bytearray(b"completeReq1\r\n")
        assert processingQueue.pop() == bytearray(b"completeReq2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_SizeFourDelimiter_Option1(self, manyLenDelimiterTestSetup):
        b, userQueue, processingQueue = manyLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"\n\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"eq\r")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeReq\r\n\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_SizeFourDelimiter_Option2(self, manyLenDelimiterTestSetup):
        b, userQueue, processingQueue = manyLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r\n")
        chunk2 = bytearray(b"\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeReq\r\n\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_SizeFourDelimiter_Option3(self, manyLenDelimiterTestSetup):
        b, userQueue, processingQueue = manyLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r\n\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue


        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeReq\r\n\r\n")



## delimiter chunk tests
class Test_DelimiterParsing:
    # delimiter size 1
    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_OneChunk_delimited(self, oneLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        b.write(chunk1)
        assert userQueue == processingQueue


        assert b._data == chunk1
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray(b"")

        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1

    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_OneChunk_undelimited(self, oneLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"incompleteReq")
        b.write(chunk1)
        assert userQueue == processingQueue


        assert b._data == chunk1
        assert len(b._messages) == 1
        assert b._messages[-1] == [chunk1, False]
        assert b._prevEndBuffer == bytearray(b"")
        assert len(processingQueue) == 0

    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_TwoChunk_FirstDelimited_SecondUndelimited(self, oneLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"incompleteReq")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [chunk2, False]

        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1
        
    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_TwoChunk_FirstDelimited_SecondDelimited(self, oneLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r")
        chunk2 = bytearray(b"completeReq\r")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0

        assert len(processingQueue) == 2
        assert processingQueue.pop() == chunk1
        assert processingQueue.pop() == chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_TwoChunk_FirstUndelimited_SecondDelimited(self, oneLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"incompleteR")
        chunk2 = bytearray(b"eq\r")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1 + chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeOne_TwoChunk_FirstUndelimited_SecondUndelimited(self, oneLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = oneLenDelimiterTestSetup

        chunk1 = bytearray(b"incomplete")
        chunk2 = bytearray(b"Req")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [chunk1+chunk2, False]
        
        assert len(processingQueue) == 0


    ## Delimiter Size (Two)
    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_OneChunk_delimited(self, twoLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue


        assert b._data == chunk1
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray(b"")

        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1

    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_OneChunk_undelimited(self, twoLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"incompleteReq")
        b.write(chunk1)
        assert userQueue == processingQueue


        assert b._data == chunk1
        assert len(b._messages) == 1
        assert b._messages[-1] == [chunk1, False]
        assert b._prevEndBuffer == bytearray(b"q")
        assert len(processingQueue) == 0

    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_TwoChunk_FirstDelimited_SecondUndelimited(self, twoLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r\n")
        chunk2 = bytearray(b"incompleteReq")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"q")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [chunk2, False]

        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1
        
    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_TwoChunk_FirstDelimited_SecondDelimited(self, twoLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeReq\r\n")
        chunk2 = bytearray(b"completeReq\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0

        assert len(processingQueue) == 2
        assert processingQueue.pop() == chunk1
        assert processingQueue.pop() == chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_TwoChunk_FirstUndelimited_SecondDelimited(self, twoLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"incompleteR")
        chunk2 = bytearray(b"eq\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"R")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1 + chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_TwoChunk_FirstUndelimited_SecondUndelimited(self, twoLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"incomplete")
        chunk2 = bytearray(b"Req")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"e")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"q")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [chunk1+chunk2, False]
        
        assert len(processingQueue) == 0

    def test_defaultWriteHook_PrevEndBuffer_DLSizeTwo_SpreadDelimiter(self, twoLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"incompleteReq\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"\r")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        processingQueue.pop() == chunk1 + chunk2




    ## Delimiter Size (Many)
    def test_defaultWriteHook_PrevEndBuffer_DLSizeMany_OneChunk_delimited(self, manyLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = manyLenDelimiterTestSetup ## size 4

        chunk1 = bytearray(b"completeReq\r\n\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue


        assert b._data == chunk1
        assert len(b._messages) == 0
        assert b._prevEndBuffer == bytearray(b"")

        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1

    def test_defaultWriteHook_PrevEndBuffer_DLSizeMany_OneChunk_undelimited(self, manyLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = manyLenDelimiterTestSetup ## size 4

        chunk1 = bytearray(b"incompleteReq")
        b.write(chunk1)
        assert userQueue == processingQueue


        assert b._data == chunk1
        assert len(b._messages) == 1
        assert b._messages[-1] == [chunk1, False]
        assert b._prevEndBuffer == bytearray(b"Req")
        assert len(processingQueue) == 0

    def test_defaultWriteHook_PrevEndBuffer_DLSizeMany_TwoChunk_FirstDelimited_SecondUndelimited(self, manyLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = manyLenDelimiterTestSetup ## size 4

        chunk1 = bytearray(b"completeReq\r\n\r\n")
        chunk2 = bytearray(b"incompleteReq")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"Req")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [chunk2, False]

        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1
        
    def test_defaultWriteHook_PrevEndBuffer_DLSizeMany_TwoChunk_FirstDelimited_SecondDelimited(self, manyLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = manyLenDelimiterTestSetup ## size 4

        chunk1 = bytearray(b"completeReq\r\n\r\n")
        chunk2 = bytearray(b"completeReq\r\n\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0

        assert len(processingQueue) == 2
        assert processingQueue.pop() == chunk1
        assert processingQueue.pop() == chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeMany_TwoChunk_FirstUndelimited_SecondDelimited(self, manyLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = manyLenDelimiterTestSetup ## size 4

        chunk1 = bytearray(b"incompleteR")
        chunk2 = bytearray(b"eq\r\n\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"teR")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1 + chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeMany_TwoChunk_FirstUndelimited_SecondUndelimited(self, manyLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = manyLenDelimiterTestSetup ## size 4

        chunk1 = bytearray(b"incomplete")
        chunk2 = bytearray(b"Req")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"ete")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"Req")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 1
        assert b._messages[-1] == [chunk1+chunk2, False]
        
        assert len(processingQueue) == 0

    def test_defaultWriteHook_PrevEndBuffer_DLSizeMany_SpreadDelimiter_Option1(self, manyLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = manyLenDelimiterTestSetup ## size 4

        chunk1 = bytearray(b"incompleteReq\r")
        chunk2 = bytearray(b"\n\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"eq\r")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1 + chunk2


    def test_defaultWriteHook_PrevEndBuffer_DLSizeMany_SpreadDelimiter_Option2(self, manyLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = manyLenDelimiterTestSetup ## size 4

        chunk1 = bytearray(b"incompleteReq\r\n")
        chunk2 = bytearray(b"\r\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"q\r\n")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue


        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1 + chunk2

    def test_defaultWriteHook_PrevEndBuffer_DLSizeMany_SpreadDelimiter_Option3(self, manyLenDelimiterTestSetup) -> None:
        b, userQueue, processingQueue = manyLenDelimiterTestSetup ## size 4

        chunk1 = bytearray(b"incompleteReq\r\n\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        assert b._prevEndBuffer == bytearray(b"\r\n\r")
        assert userQueue == processingQueue

        b.write(chunk2)
        assert b._prevEndBuffer == bytearray(b"")
        assert userQueue == processingQueue

        assert b._data == chunk1 + chunk2
        assert len(b._messages) == 0
        
        assert len(processingQueue) == 1
        assert processingQueue.pop() == chunk1 + chunk2






    ## TODO: Consider restructuring delimiter chunk-split tests


    ## TODO: Consider adding ManyChunk tests cases
    

    # def test_defaultWriteHook_TwoChunks_OneCompleteRequest(self, oneLenDelimiterTestSetup):
    #     delimiters = [b"\r\n"]
    #     delimiter = delimiters[0]
    #     b = Buffer(delimiters)

    #     testBytes1 = bytearray(b"complete")
    #     testBytes2 = bytearray(b"Req\r\n")
        
    #     processingQueue = collections.deque([])
    #     def requestHook(self, request):
    #         nonlocal processingQueue
    #         processingQueue.appendleft(request)

    #     b._requestHook = functools.partial(requestHook, b)
    #     b.write(testBytes1)
    #     b.write(testBytes2)

    #     ## Data should be removed buffer()._data once popped from buffer()._messages
    #     assert b._data == bytearray(b"")
    #     assert len(b._messages) == 0
        
    #     assert len(processingQueue) == 1
    #     assert processingQueue.pop() == bytearray(b"completeReq\r\n")

    # def test_defaultWriteHook_TwoChunks_OneCompleteRequest_OnePartialRequest(self, oneLenDelimiterTestSetup):
    #     delimiters = [b"\r\n"]
    #     delimiter = delimiters[0]
    #     b = Buffer(delimiters)

    #     testBytes1 = bytearray(b"complete")
    #     testBytes2 = bytearray(b"Req\r\nincompleteR")
        
    #     processingQueue = collections.deque([])
    #     def requestHook(self, request):
    #         nonlocal processingQueue
    #         processingQueue.appendleft(request)

    #     b._requestHook = functools.partial(requestHook, b)
    #     b.write(testBytes1)
    #     b.write(testBytes2)

    #     ## Data should be removed buffer()._data once popped from buffer()._messages
    #     assert b._data == bytearray(b"")
    #     assert len(b._messages) == 0
        
    #     assert len(processingQueue) == 1
    #     assert processingQueue.pop() == bytearray(b"completeReq\r\n")

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

