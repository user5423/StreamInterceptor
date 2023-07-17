import socket
import queue
import random
import datetime
import string

from typing import List, Callable, Optional, Tuple, Union

class DataTransferSimulator:
    @classmethod
    def sendMultiConnMultiMessage(cls, connections: List[socket.socket],
                                        completeConnSender: Optional[Callable] = None,
                                        dataSizeSelector: Optional[Callable] = None,
                                        messageCountSelector: Optional[Callable] = None,
                                        chunkCountSelector: Optional[Callable] = None,
                                        datetimesSelector: Optional[Callable] = None,
                                        delimitersSelector: Optional[Callable] = None,
                                        isEndDelimited: bool = None
                                        ) -> List[bytes]:

        ## Validate and prepare a completeConnSender function
        completeConnSender = cls._validateArguments(completeConnSender, dataSizeSelector, messageCountSelector,
                             chunkCountSelector, datetimesSelector, delimitersSelector, isEndDelimited)

        ## we have the connectionData arr where connection[i] has sent connectionData[i]
        connectionData = []

        ## we iterate over each connection, adding to the chunkQueue
        for index, conn in enumerate(connections):
            ## unpack the arguments for the compeleteConnSender function call
            dataSize, messageCount, chunkCount, delimiters, datetimes, isEndDelimited = completeConnSender()

            ## we generate data
            generatedData = cls._generateData(dataSize)

            ## we then make the data into message (by inserting delimiters)
            dataMessages = cls._convertStreamIntoMessages(generatedData, messageCount, delimiters, isEndDelimited)
   
            ## we add the new generated data to the connectionData list
            connectionData.append(dataMessages)

            ## we then select what indexes the data will be chunked at
            dataChunks = cls._convertMessagesIntoChunks(dataMessages, chunkCount)

            ## the datetimes array must be in sorted in ascending order
            ## TODO: We are not waiting for datetime Timestamp before sending (we only respect the orderings)
            dt = datetimes[0] - datetime.timedelta(seconds=1)
            for index, chunk in enumerate(dataChunks):
                ## we finally select the datetime for each index (  datetime_i <= datetime_i+1)
                assert dt <= datetimes[index]
                dt = datetimes[index]
                conn.sendall(chunk)

        return connectionData

    @classmethod
    def _validateArguments(cls, completeConnSender: Optional[Callable] = None,
                                dataSizeSelector: Optional[Callable] = None,
                                messageCountSelector: Optional[Callable] = None,
                                chunkCountSelector: Optional[Callable] = None,
                                datetimesSelector: Optional[Callable] = None,
                                delimitersSelector: Optional[Callable] = None,
                                isEndDelimited: bool = None
                                ) -> Callable:

        ## We validate the arguments
        someSubMethodsProvided = bool(dataSizeSelector or messageCountSelector or chunkCountSelector
                                     or datetimesSelector or delimitersSelector or (isEndDelimited is not None))

        allSubMethodsProvided = bool(dataSizeSelector and messageCountSelector and chunkCountSelector
                                     and datetimesSelector and delimitersSelector and (isEndDelimited is not None))

        if someSubMethodsProvided is True and allSubMethodsProvided is False:
            return Exception("You need to provide all submethods, if you are using submethods as your choice")
        elif bool(allSubMethodsProvided and completeConnSender) is True:
            return Exception("You need to either provide a completeConnSender or all the submethods, not both")
        elif bool(allSubMethodsProvided or completeConnSender) is False:
            return Exception("You need to either provide a completeConnSender or all the submethods, not None for both")

        ## we selecting either DO_ALL method or combine singular parameter methods into a DO_ALL method
        ## The DO_ALL method is completeConnSender
        ## TODO: Rename to more appropriate method name
        if allSubMethodsProvided:
            def completeConnSender():
                nonlocal dataSizeSelector, messageCountSelector, chunkCountSelector
                nonlocal datetimesSelector, delimitersSelector, isEndDelimited
                dataSize = dataSizeSelector()
                messageCount = messageCountSelector()
                chunkCount = chunkCountSelector()
                delimiters = delimitersSelector()
                ## datetime needs to be a generator (that keeps on pulling values when needed)
                datetimes = datetimesSelector(chunkCount)
                return (dataSize, messageCount, chunkCount, delimiters, datetimes, isEndDelimited)
        
        return completeConnSender

    @classmethod
    def _convertStreamIntoMessages(cls, data: bytes, messageCount: int, delimiters: List[bytes], isEndDelimited: bool) -> bytes:
        if len(data) == 0:
            raise Exception("Data needs to have at least length 1")
        
        ## we make sure that the last char is reserved for "isEndLimited" bool
        delimiters = iter(delimiters)
        delimitableMessageLen = len(data) - 1
        if delimitableMessageLen < messageCount - int(isEndDelimited):
            raise Exception("Cannot perform stream into messages as data size is to small for messageCount value specified")

        indexes = sorted(random.sample(range(1, len(data)), messageCount - int(isEndDelimited)))

        ## we then insert the delimiters at index to create messages
        ## NOTE: This should work where delimiter >= 0
        ## NOTE: indexes is required to be sorted
        newData = bytearray()
        left = 0
        for right in indexes:
            newData += data[left:right] + next(delimiters)
            left = right

        newData += data[left:]

        ## In case we have an end delimiter, we add it
        if isEndDelimited:
            newData += next(delimiters)

        return newData


    @classmethod
    def _convertMessagesIntoChunks(cls, dataMessages: bytes, chunkCount: int) -> List[bytes]:
        if chunkCount > len(dataMessages):
            raise Exception("Cannot have more chunks than size of data")

        chunkIndexes = sorted(random.sample(range(1, len(dataMessages)-1), chunkCount-1))
        dataChunks = []
        left = 0
        for right in chunkIndexes:
            dataChunks.append(dataMessages[left:right])
            left = right

        dataChunks.append(dataMessages[left:])
        return dataChunks


    @classmethod
    def _generateData(cls, dataSize: int) -> bytes:
        charset = string.ascii_letters + string.digits
        return bytes("".join((random.choice(charset) for _ in range(dataSize))), "utf-8")


    @classmethod
    def _datetimesSelector(cls, testTimeRange, chunkCount) -> List[datetime.datetime]:
        ## NOTE: The list of datetimes needs to be sorted from small to high
        startTime = datetime.datetime.now()
        resolution = 0.01
        sendTimes = sorted(random.choices(range(0, int(testTimeRange/resolution)+1), k=chunkCount))
        sendTimes = [startTime + datetime.timedelta(seconds=sendTime*resolution) for sendTime in sendTimes] ## we normalize for the resolution
        return sendTimes


    @classmethod
    def _delimitersSelector(cls, delimiters, messageCount):
        return random.choices(delimiters, k=messageCount)


    @classmethod
    def _awaitRoundaboutConnection(cls, connections: List[socket.socket], timeout: Optional[Union[int, float]]) -> None:
        for conn in connections:
            conn.setblocking(True) ## we block so that we can let other threads work
            conn.settimeout(timeout)
            try:
                conn.recv(1024, socket.MSG_PEEK) ## peeks at data without consuming it
            except socket.error:
                # print("Socket Timeout Error - Continuing test...")
                pass
            conn.setblocking(False)


    @classmethod
    def createRandomConnSender(cls, dataSizeRange: Tuple[int, int],
                                    messageCountRange: Tuple[int, int],
                                    chunkCountRange: Tuple[int, int],
                                    delimiterList: List[bytes],
                                    isEndDelimited: bool,
                                    testTimeRange: int    ## The range is (0, X) where 0 is constant
                            ) -> Callable:
        def completeConnSender():
            nonlocal delimiterList, testTimeRange, dataSizeRange, isEndDelimited
            dataSize = random.randint(*dataSizeRange)
            messageCount = random.randint(*messageCountRange)
            chunkCount = random.randint(*chunkCountRange)
            delimiters = DataTransferSimulator._delimitersSelector(delimiterList, messageCount) ## creates a sequence of delimiters
            datetimes = DataTransferSimulator._datetimesSelector(testTimeRange, chunkCount) ## creates a sequence of ordered datetime
            return (dataSize, messageCount, chunkCount, delimiters, datetimes, isEndDelimited)

        return completeConnSender

