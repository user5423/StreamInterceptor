import collections
import os
import sys
import functools
import pytest

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from _proxyDS import Buffer

from typing import Optional

class BufferReqParsingHelpers:
    @classmethod
    def _setupTransparentHookMock(cls, buffer: Buffer) -> collections.deque:
        userQueue = collections.deque([])
        def userHook(buffer, request) -> None:
            nonlocal userQueue
            userQueue.appendleft(request)
            return None

        buffer._transparentHook = functools.partial(userHook, buffer)
        return userQueue

    @classmethod
    def _setupNonTransparentHookMock(cls, buffer: Buffer) -> collections.deque:
        processingQueue = collections.deque([])
        def processingHook(buffer, request) -> Optional[bytes]:
            nonlocal processingQueue
            processingQueue.appendleft(request)
            return request

        buffer._nonTransparentHook = functools.partial(processingHook, buffer)
        return processingQueue


@pytest.fixture()
def oneLenDelimiterTestSetup():
    delimiters = [b"\r"]
    delimiter = delimiters[0]
    b = Buffer(delimiters)
    userQueue = BufferReqParsingHelpers._setupTransparentHookMock(b)
    processingQueue = BufferReqParsingHelpers._setupNonTransparentHookMock(b)
    yield b, userQueue, processingQueue

@pytest.fixture()
def twoLenDelimiterTestSetup():
    delimiters = [b"\r\n"]
    delimiter = delimiters[0]
    b = Buffer(delimiters)
    userQueue = BufferReqParsingHelpers._setupTransparentHookMock(b)
    processingQueue = BufferReqParsingHelpers._setupNonTransparentHookMock(b)
    yield b, userQueue, processingQueue

@pytest.fixture()
def manyLenDelimiterTestSetup():
    delimiters = [b"\r\n\r\n"]
    delimiter = delimiters[0]
    b = Buffer(delimiters)
    userQueue = BufferReqParsingHelpers._setupTransparentHookMock(b)
    processingQueue = BufferReqParsingHelpers._setupNonTransparentHookMock(b)
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

        message1 = bytearray(b"incompletem")
        b.write(message1)

        assert b._incomingData == message1
        assert b._outgoingData == b""
        assert len(b._messages) == 0
        assert len(processingQueue) == 0
        assert userQueue == processingQueue


    def test_defaultWriteHook_SingleChunk_OneCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        message1 = bytearray(b"completeMessage\r\n")
        b.write(message1)

        assert userQueue == processingQueue
        assert b._incomingData == b""
        assert b._outgoingData == message1
        assert len(b._messages) == 0
        assert len(processingQueue) == 1
        assert processingQueue.pop() == message1


    def test_defaultWriteHook_SingleChunk_OneCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        message1 = bytearray(b"completemessage1\r\n")
        message2 = bytearray(b"incompletem")
        chunk = message1 + message2
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert userQueue == processingQueue
        assert b._incomingData == message2
        assert len(b._messages) == 0
        assert len(processingQueue) == 1
        assert processingQueue.pop() == message1

    def test_defaultWriteHook_SingleChunk_TwoCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        message1 = bytearray(b"completemessage1\r\n")
        message2 = bytearray(b"completemessage2\r\n")
        chunk = message1 + message2
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert userQueue == processingQueue
        assert b._incomingData == b""
        assert b._outgoingData == chunk
        assert len(b._messages) == 0
        assert len(processingQueue) == 2
        assert processingQueue.pop() == message1
        assert processingQueue.pop() == message2

    def test_defaultWriteHook_SingleChunk_TwoCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        message1 = bytearray(b"completemessage1\r\n")
        message2 = bytearray(b"completemessage2\r\n")
        message3 = bytearray(b"incompletem")
        chunk = message1 + message2 + message3
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert userQueue == processingQueue
        assert b._incomingData == message3
        assert b._outgoingData == message1 + message2
        assert len(b._messages) == 0
        assert len(processingQueue) == 2
        assert processingQueue.pop() == message1
        assert processingQueue.pop() == message2

    def test_defaultWriteHook_SingleChunk_ManyCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        message1 = bytearray(b"completemessage1\r\n")
        message2 = bytearray(b"completemessage2\r\n")
        message3 = bytearray(b"completemessage3\r\n")
        message4 = bytearray(b"completemessage4\r\n")
        message5 = bytearray(b"completemessage5\r\n")
        chunk = message1 + message2 + message3 + message4 + message5
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert userQueue == processingQueue
        assert b._incomingData == b""
        assert b._outgoingData == chunk
        assert len(b._messages) == 0
        assert len(processingQueue) == 5
        assert processingQueue.pop() == message1
        assert processingQueue.pop() == message2
        assert processingQueue.pop() == message3
        assert processingQueue.pop() == message4
        assert processingQueue.pop() == message5

    def test_defaultWriteHook_SingleChunk_ManyCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        message1 = bytearray(b"completemessage1\r\n")
        message2 = bytearray(b"completemessage2\r\n")
        message3 = bytearray(b"completemessage3\r\n")
        message4 = bytearray(b"completemessage4\r\n")
        message5 = bytearray(b"incompletem")
        chunk = message1 + message2 + message3 + message4 + message5
        b.write(chunk)

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert userQueue == processingQueue
        assert b._incomingData == message5
        assert b._outgoingData == message1 + message2 + message3 + message4
        assert len(b._messages) == 0
        assert len(processingQueue) == 4
        assert processingQueue.pop() == message1
        assert processingQueue.pop() == message2
        assert processingQueue.pop() == message3
        assert processingQueue.pop() == message4

    
    ## Tests for request spreading over chunks (spread from start chunk 1 to mid chunk 2)
    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_OneCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"message1\r\ncompletemessage2\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == chunk1 + chunk2
        assert len(b._messages) == 0
        assert len(processingQueue) == 2
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_OneCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"message1\r\ncompletemessage2\r\nincompletem")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b"incompletem"
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 2
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_TwoCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"message1\r\ncompletemessage2\r\ncompletemessage3\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\ncompletemessage3\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 3
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage3\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_TwoCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"message1\r\ncompletemessage2\r\ncompletemessage3\r\nincompletem")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b"incompletem"
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\ncompletemessage3\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 3
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage3\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_ManyCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"message1\r\ncompletemessage2\r\ncompletemessage3\r\ncompletemessage4\r\ncompletemessage5\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\ncompletemessage3\r\ncompletemessage4\r\ncompletemessage5\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 5
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage3\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage4\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage5\r\n")


    def test_defaultWriteHook_TwoChunk_OneSpreadCompleteMessage_ManyCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"complete")
        chunk2 = bytearray(b"message1\r\ncompletemessage2\r\ncompletemessage3\r\ncompletemessage4\r\ncompletemessage5\r\nincompletem")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b"incompletem"
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\ncompletemessage3\r\ncompletemessage4\r\ncompletemessage5\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 5
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage3\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage4\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage5\r\n")


    ## Tests for request spreading over chunks (spread from start from mid chunk 1 to mid chunk 2)
    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completemessage1\r\ncomp")
        chunk2 = bytearray(b"letemessage2\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 2
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_OneParitalMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completemessage1\r\ncomp")
        chunk2 = bytearray(b"letemessage2\r\nincompletem")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b"incompletem"
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 2
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_OneCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completemessage1\r\ncomp")
        chunk2 = bytearray(b"letemessage2\r\ncompletemessage3\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\ncompletemessage3\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 3
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage3\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_OneCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completemessage1\r\ncomp")
        chunk2 = bytearray(b"letemessage2\r\ncompletemessage3\r\nincompletem")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b"incompletem"
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\ncompletemessage3\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 3
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage3\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_TwoCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completemessage1\r\ncomp")
        chunk2 = bytearray(b"letemessage2\r\ncompletemessage3\r\ncompletemessage4\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\ncompletemessage3\r\ncompletemessage4\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 4
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage3\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage4\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_TwoCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completemessage1\r\ncomp")
        chunk2 = bytearray(b"letemessage2\r\ncompletemessage3\r\ncompletemessage4\r\nincompletem")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b"incompletem"
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\ncompletemessage3\r\ncompletemessage4\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 4
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage3\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage4\r\n")
        

    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_ManyCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completemessage1\r\ncomp")
        chunk2 = bytearray(b"letemessage2\r\ncompletemessage3\r\ncompletemessage4\r\ncompletemessage5\r\ncompletemessage6\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\ncompletemessage3\r\ncompletemessage4\r\ncompletemessage5\r\ncompletemessage6\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 6
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage3\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage4\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage5\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage6\r\n")


    def test_defaultWriteHook_TwoChunk_OneCompleteMessage_OneSpreadCompleteMessage_ManyCompleteMessage_OnePartialMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completemessage1\r\ncomp")
        chunk2 = bytearray(b"letemessage2\r\ncompletemessage3\r\ncompletemessage4\r\ncompletemessage5\r\ncompletemessage6\r\nincompletem")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b"incompletem"
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\ncompletemessage3\r\ncompletemessage4\r\ncompletemessage5\r\ncompletemessage6\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 6
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage3\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage4\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage5\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage6\r\n")
    
    ## TODO: Tests for request spreading over chunks (spread from start from mid chunk 1 to end chunk 2)
    ## The number of combos are too much


    ## Tests for request delimiter spreading over chunks
    def test_defaultWriteHook_TwoChunk_OneSpreadDelimiterCompleteMessage(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeMessage")
        chunk2 = bytearray(b"\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completeMessage\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeMessage\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_SizeTwoDelimiter(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeMessage\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completeMessage\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeMessage\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_OnePartialMessage_SizeTwoDelimiter(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completeMessage\r")
        chunk2 = bytearray(b"\nincompletem")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b"incompletem"
        assert b._outgoingData == b"completeMessage\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeMessage\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_OneCompleteMessage_SizeTwoDelimiter(self, twoLenDelimiterTestSetup):
        b, userQueue, processingQueue = twoLenDelimiterTestSetup

        chunk1 = bytearray(b"completemessage1\r")
        chunk2 = bytearray(b"\ncompletemessage2\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completemessage1\r\ncompletemessage2\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 2
        assert processingQueue.pop() == bytearray(b"completemessage1\r\n")
        assert processingQueue.pop() == bytearray(b"completemessage2\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_SizeFourDelimiter_Option1(self, manyLenDelimiterTestSetup):
        b, userQueue, processingQueue = manyLenDelimiterTestSetup

        chunk1 = bytearray(b"completeMessage\r")
        chunk2 = bytearray(b"\n\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completeMessage\r\n\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeMessage\r\n\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_SizeFourDelimiter_Option2(self, manyLenDelimiterTestSetup):
        b, userQueue, processingQueue = manyLenDelimiterTestSetup

        chunk1 = bytearray(b"completeMessage\r\n")
        chunk2 = bytearray(b"\r\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completeMessage\r\n\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeMessage\r\n\r\n")


    def test_defaultWriteHook_TwoChunk_OneSplitDelimiterCompleteMessage_SizeFourDelimiter_Option3(self, manyLenDelimiterTestSetup):
        b, userQueue, processingQueue = manyLenDelimiterTestSetup

        chunk1 = bytearray(b"completeMessage\r\n\r")
        chunk2 = bytearray(b"\n")
        b.write(chunk1)
        assert userQueue == processingQueue

        b.write(chunk2)
        assert userQueue == processingQueue

        ## Data should be removed buffer()._data once popped from buffer()._messages
        assert b._incomingData == b""
        assert b._outgoingData == b"completeMessage\r\n\r\n"
        assert len(b._messages) == 0
        assert len(processingQueue) == 1
        assert processingQueue.pop() == bytearray(b"completeMessage\r\n\r\n")