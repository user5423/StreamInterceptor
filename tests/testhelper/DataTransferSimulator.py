import pprint
import os
import socket
import abc
import random
import datetime
import string
import re
import collections
import time
from typing import List, Callable, Optional, Tuple, Union, FrozenSet, Dict

## TODO: Have not added 120 vs 220 checks on connection initiation
## TODO: Have not considered ABORT and REIN commands
## TODO: Have not considered STOU and storage type commands

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





## TODO: Cleanup class and naming
## TODO: Replace basic exceptions with custome one
class TelnetClientSimulator:
    def _createClientConnection(self, HOST: str, PORT: int) -> socket.socket:
        s = socket.socket()
        s.connect((HOST, PORT))
        return s

    def _simulateCommSequence(self, clientSock: socket.socket, commandSequence: Tuple[bytes], dtsTimeout: Optional[Union[float, int]] = 0.2) -> None:
        recvBuffer = bytearray()
        responseSequence = []
        responseProccessedCounter = 0
        respondedCommandsCounter = 0
        flattenedCommandSequence = []

        for commands in commandSequence:
            print(f"commands: {commands}")
            ## We execute a request callback on each command before we send them
            for command in commands:
                self._requestCallback(command)

            ## We send all of the commands jointly
            clientSock.settimeout(None)
            clientSock.sendall(b"".join(commands))
            flattenedCommandSequence.extend(commands)

            clientSock.settimeout(dtsTimeout)
            messages = []
            while True:
                ## make this recv mechnaism more robust for below nested for loopnt
                try:
                    chunk = clientSock.recv(4096)
                except socket.timeout:
                    break

                ## Need to check if the client has received an exit connection empty string b""
                if len(chunk) == 0:
                    raise Exception("Unexpected clientSock exit")
            
                recvBuffer += chunk
                
                messages = recvBuffer.splitlines(True)
                ## messages must be at least length 1 (assuming recv() is blocking)
                if messages[-1][-2:] == b"\r\n":
                    responseSequence.extend(messages)
                    recvBuffer = b""
                else:
                    responseSequence.extend(messages[:-1])
                    recvBuffer = messages[-1]

            if len(messages) == 0:
                raise Exception("Did not receive any response from the server")
            
            commandIndex = respondedCommandsCounter
            # pprint.pprint(f"responses: {responseSequence}")

            ## Now we process the responses alongside their commands
            for commandIndex, command in enumerate(flattenedCommandSequence[respondedCommandsCounter:], start=respondedCommandsCounter):
                ## We iterate over the response index (until we find the response that matches the expectations of executing the command)
                for _, response in enumerate(responseSequence[responseProccessedCounter:], start=responseProccessedCounter):
                    ## process responses
                    callbackResult = self._responseCallback(command, response)
                    ## increment counter
                    responseProccessedCounter += 1

                    ## if the response callback was sucecssful, we process the next command
                    if callbackResult:
                        break

                ## if we have processed all requests, then we should not process any commands
                ## - this is because of the sequential nature of commands and corresponding responses
                if responseProccessedCounter == len(responseSequence):
                    break

            ## If we exited the outer for loop early, then we have unprocessed commands
            respondedCommandsCounter = commandIndex

            ## If the last callback was unsuccesful, that means the last command processed wasn't satisifed
            ## - so next time, we want to process that command
            ## - However, if the last callback was successful, then the command was satisified, so we do NOT want to process it next time
            if callbackResult:
                respondedCommandsCounter += 1

        clientSock.settimeout(None)
        self._cleanup()
        return (flattenedCommandSequence, respondedCommandsCounter), (responseSequence, responseProccessedCounter)

    @abc.abstractmethod
    def _responseCallback(self, request: bytes, response: bytes) -> None:
        return None

    @abc.abstractmethod
    def _requestCallback(self, request: bytes) -> None:
        return None

    @abc.abstractmethod
    def _cleanup(self) -> None:
        return None


## NOTE: This command simulator only implements default data connection transfer

## TODO: Cleanup class and naming
class FTPClientSimulator(TelnetClientSimulator):
    dataConnInitiationCommands: FrozenSet[bytes] = frozenset({b"PORT", b"PASV"})
    dataConnControlCommands: FrozenSet[bytes] = frozenset({b"PORT", b"PASV", b"ABORT"})
    dataConnReliantCommands: FrozenSet[bytes] = frozenset({b"RETR", b"STOR", b"STOU", b"APPEND", b"LIST", b"NLST"})
    dataRecvCommands: FrozenSet[bytes] = frozenset({b"RETR", b"LIST", b"NLST"})
    dataSendCommands: FrozenSet[bytes] = frozenset({b"STOR", b"STOU", b"APPEND"})

    ## TODO; Verify with RFC that these are correct
    acceptableCommandFollowThrough: Dict[bytes, Dict[bytes, Tuple[bytes]]] = {
        ## Logout
        b"REIN": {
            b"120": (b"220",)
        },
        ## File action commands
        b"STOR": {
            ## TODO: In the rfc, 110 is specified in brackets - is this optional? figure out if it makes a difference
            b"125": (b"110", b"226", b"250", b"425", b"426", b"451", b"551", b"552"),
            b"150": (b"110", b"226", b"250", b"425", b"426", b"451", b"551", b"552"),
        },
        b"STOU": {
            ## TODO: In the rfc, 110 is specified in brackets - is this optional? figure out if it makes a difference
            b"125": (b"110", b"226", b"250", b"425", b"426", b"451", b"551", b"552"),
            b"150": (b"110", b"226", b"250", b"425", b"426", b"451", b"551", b"552"),
        },
        b"RETR": {
            ## TODO: In the rfc, 110 is specified in brackets - is this optional? figure out if it makes a difference
            b"125": (b"110", b"226", b"250", b"425", b"426", b"451"),
            b"150": (b"110", b"226", b"250", b"425", b"426", b"451"),
        },
        b"LIST": {
            b"125": (b"226", b"250", b"425", b"426", b"451"),
            b"150": (b"226", b"250", b"425", b"426", b"451"),
        },
        b"NLIST": {
            b"125": (b"226", b"250", b"425", b"426", b"451"),
            b"150": (b"226", b"250", b"425", b"426", b"451"),
        },
        b"APPE": {
            ## TODO: In the rfc, 110 is specified in brackets - is this optional? figure out if it makes a difference
            b"125": (b"110", b"226", b"250", b"425", b"426", b"451", b"551", b"552"),
            b"150": (b"110", b"226", b"250", b"425", b"426", b"451", b"551", b"552"),
        }

    }

    ## TODO; Verify with RFC that these are correct
    acceptableCommandResponses: Dict[bytes, bytes] = {
        ## Login
        b"USER": {b"230", b"530", b"500", b"501", b"421", b"331", b"332"},
        b"PASS": {b"230", b"202", b"530", b"500", b"501", b"503", b"421", b"332"},
        b"ACCT": {b"230", b"202", b"530", b"500", b"501", b"503", b"421"},
        b"CWD": {b"250", b"500", b"501", b"502", b"421", b"530", b"550"},
        b"CDUP": {b"200", b"500", b"501", b"502", b"421", b"530", b"550"},
        b"SMNT": {b"202", b"250", b"500", b"501", b"502", b"421", b"530", b"550"},
        ## Logout
        b"REIN": {b"120", b"220", b"421", b"500", b"502"}, ## TODO: Has follow through response
        b"QUIT": {b"221", b"500"},
        ## Transfer parameters
        b"PORT": {b"200", b"500", b"501", b"421", b"530"},
        b"PASV": {b"227", b"500", b"501", b"503" b"421", b"530"},
        b"MODE": {b"200", b"500", b"501", b"503" b"421", b"530"},
        b"TYPE": {b"200", b"500", b"501", b"503" b"421", b"530"},
        b"STRU": {b"200", b"500", b"501", b"503" b"421", b"530"},
        ## File Action Commands
        b"ALLO": {b"200", b"202", b"500", b"501", b"504", b"421", b"530"},
        b"REST": {b"500", b"501", b"502", b"421", b"530", b"350"},
        b"STOR": {b"125", b"150", b"532", b"450", b"452", b"553", b"500", b"501", b"421", b"530"}, ## TODO: Has follow through response
        b"STOU": {b"125", b"150", b"532", b"450", b"452", b"553", b"500", b"501", b"421", b"530"}, ## TODO: Has follow through response
        b"RETR": {b"125", b"150", b"450", b"550", b"500", b"501", b"421", b"530"}, ## TODO: Has follow through response
        b"LIST": {b"125", b"150", b"450", b"500", b"501", b"421", b"530"}, ## TODO: Has follow through response
        b"NLIST": {b"125", b"150", b"450", b"500", b"501", b"421", b"530"}, ## TODO: Has follow through response
        b"APPE": {b"125", b"150", b"532", b"450", b"452", b"550" b"553", b"500", b"501", b"502", b"421", b"530"}, ## TODO: Has follow through response
        b"RNFR": {b"450", b"550",  b"500", b"501", b"502", b"421", b"530",  b"350"},
        b"RNTO": {b"250",  b"532", b"553",  b"500", b"501", b"502", b"503", b"421", b"530"},
        b"DELE": {b"250",  b"450", b"550",  b"500", b"501", b"502", b"421", b"530"},
        b"RMD": {b"250",  b"500", b"501", b"502", b"421", b"530", b"550"},
        b"MKD": {b"257",  b"500", b"501", b"502", b"421", b"530", b"550"},
        b"PWD": {b"257",  b"500", b"501", b"502", b"421", b"550"},
        b"ABOR": {b"225", b"226",  b"500", b"501", b"502", b"421"},
        ## Informational commands
        b"SYST": {b"215", b"500", b"501", b"502", b"421"},
        b"STAT": {b"211", b"212", b"213", b"450", b"500", b"501", b"502", b"421", b"530"},
        b"HELP": {b"211", b"214", b"500", b"501", b"502", b"421"},
        ## Miscellaneous commands
        b"SITE": {b"200", b"202", b"500", b"501", b"530"},
        b"NOOP": {b"200", b"500", b"421"}

    }

    def __init__(self):
        ## The last conn in this deque is the most recent PASV/PORT issued
        ## Once a data connection has been completed or aborted, it is popleft() from this ds
        self.dataConnSockets = []
        self.dataConnTypes = []
        self.transferDirections = []
        self.dataConnCounter = 0
        
        self.totalDataMessages = []
        self.dataConnSetupMessages = []
        self.dataMessageCounter = 0
        
        self.dataSendMessages = []
        self.dataSendMessageCounter = 0

        self.dataConnSelector = [-1]
        self.dataConnSelectorCounter = 0


    def simulateCommSequence(self, clientSock: socket.socket, commandSequence: Tuple[bytes], dataSendMessageSequence: Tuple[bytes], dtsTimeout: Optional[Union[float, int]] = 0.2) -> None:
        self.dataSendMessages = dataSendMessageSequence
        (flattenedCommandSequence, respondedCommandsCounter), (responseSequence, responseProccessedCounter) = self._simulateCommSequence(clientSock, commandSequence, dtsTimeout)
        return (flattenedCommandSequence, respondedCommandsCounter), (responseSequence, responseProccessedCounter), (self.totalDataMessages, self.dataConnTypes)


    def _recvData(self, dataConnCounter) -> bytes:
        s = self.dataConnSockets[dataConnCounter]
        msg = b""
        while True:
            recv = s.recv(1024)
            if recv == b"":
                break
            msg += recv
        return msg

    def _sendData(self, dataConnCounter) -> bytes:
        s = self.dataConnSockets[dataConnCounter]
        msg = self.dataSendMessages[self.dataSendMessageCounter]
        s.sendall(msg)
        s.close()
        self.dataSendMessageCounter += 1
        return msg

    def _responseCallback(self, request: bytes, response: bytes) -> bool:
        ## We are a ftp client here, we need to respond accordingly
        req = re.search(b"^\w+", request).group(0)
        resp = re.search(b"^\d+", response).group(0)
        # print(f"responseCallback: req -> {str(request)}, resp_potential -> {str(response)}")
        if req in self.dataConnControlCommands:
            if req == b"PASV" and resp == b"227":
                ## If the client has already issued this command in the chunk sent
                ## - then we do not attempt to setup a connection to this

                ## then we create a connection using resp detailss
                pasvArgs = re.search(b"(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)", response)
                host = b".".join(pasvArgs.group(1,2,3,4))
                port = int(pasvArgs.group(5)) * 256 + int(pasvArgs.group(6))

                s = socket.socket()
                ## We cannot connect here in-case the server has dropped this PASV conn for a new one
                ## e.g. PASV, PASV, LIST (The first PASV cannot be used to connect
                # s.connect((host, port))

                self.dataConnSockets.append(s)
                self.totalDataMessages.append(None)
                self.dataConnTypes.append("PASV")
                self.dataConnSetupMessages.append((host, port))
                return True
            elif req == b"PORT" and resp == b"200":
                ## A 200 means the server recognizes our PORT successfuly
                ## - It does NOT mean that it will connect at this time however
                ## - It can wait to connect until just before a data reliant command is issued
                return True
            elif req == b"ABORT" and resp in (b"225", b"226"):
                ## TODO: What do we do if we recieve a failure on the ABORT command
                raise NotImplementedError()
                return True


        ## Check if it is an acceptable respone
        if resp not in self.acceptableCommandResponses[req]:

            ## If not, we check if it is an acceptable follow through
            valid = False
            acceptableFollowThroughs = self.acceptableCommandFollowThrough.get(req, {})
            for acceptableResps in acceptableFollowThroughs.values():
                if resp in acceptableResps:
                    valid = True

            ## if it's not a acceptable response or acceptable followthrough, we return false
            if valid is False:
                return False


        ## In case we haven't validated in the data connection initiation session, we do a standard valiation below
        if req in self.dataConnReliantCommands:
            ## First we check if the command has been accepted (via the informational 1x responses)
            if resp in (b"125", b"150"):
                dataConnCounter = self.dataConnSelector[self.dataConnSelectorCounter]
                connType = self.dataConnTypes[dataConnCounter]
                transferDirection = self.transferDirections[self.dataMessageCounter - 1]
                
                if connType == "PORT":
                    self.dataConnSockets[dataConnCounter] = self.dataConnSockets[dataConnCounter].accept()[0] ## (socket, peerinfo)

                ## NOTE/TODO: If we add different data transfer methods (e.g. Stream, Block, ...), we will need to modify the below logic
                ## including _recvData() _sendData(), and when to increment the connections (maybe) and socket handling/creation (maybe)

                if transferDirection == "RECV":
                    self.totalDataMessages[dataConnCounter] = self._recvData(dataConnCounter)
                else:
                    self.totalDataMessages[dataConnCounter] = self._sendData(dataConnCounter)

            ## Here, we assume we have a complete response that satisifies our connection
            if resp.startswith(b"2") or resp in (b"426"):
                self.dataConnSelectorCounter += 1

            ## otherwise, it failed to be used, so data connection hasn't been consumed
        else:
            ## if this is a control only command, so we do nothing
            pass


        ## All informational messages 1x are followed through by a 2x or 4x, or 5x message
        if resp.startswith(b"1"):
            ## Therefore, we can skip these (if non-File action commands) and check if the follow through message (or an original reply is observed)
            return False

        return True


    def _requestCallback(self, request: bytes) -> None:
        req = re.search(b"^\w+", request).group(0)

        if req in self.dataConnControlCommands:
            ## then we setup a connection
            if req == b"PASV":
                ## we sort this out when we receive a response (and the responseCallback is executed)
                self.dataConnSelector[-1] += 1
            elif req == b"PORT":
                ## We retrieve the PORT args for host, port values
                portArgs = re.search(b"^PORT (\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\r\n", request)
                if portArgs is not None:
                    host = b".".join(portArgs.group(1,2,3,4))
                    port = int(portArgs.group(5)) * 256 + int(portArgs.group(6))

                    ## we setup a new connection
                    s = socket.socket()
                    ## NOTE: Avoid spending time testing reusage of PORT commands on same source endpoint
                    # s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                    ## NOTE: Enables socket to bind to a source endpoint where a previous socket is in TIME_WAIT
                    ## state. Test re-execution can fail if sockets in a previous execution are in this state, and we attempt
                    ## to bind to the same address in the current execution
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind((host, port))
                    s.listen()

                    ## we then add it to the list
                    self.dataConnSockets.append(s)
                    self.totalDataMessages.append(None)
                    self.dataConnTypes.append("PORT")
                    self.dataConnSetupMessages.append((host, port))
                    self.dataConnSelector[-1] += 1

            elif req == b"ABORT":
                ## I need to read the ftp rfc to understand meticulously the behavior of ABORT
                raise NotImplementedError()

        elif req in self.dataConnReliantCommands:
            ## At this point if we have preceeded this with a PORT command, we perform a accept()
            self.dataMessageCounter += 1
            if req in self.dataSendCommands:
                self.transferDirections.append("SEND")
            else:
                self.transferDirections.append("RECV")

            ## NOTE: This doesn't work if a batch containing a data-command that uses PASV conn
            dataConnCounter = self.dataConnSelector[self.dataConnSelectorCounter]
            connType = self.dataConnTypes[dataConnCounter]

            if connType == "PASV":
                ## otherwise we need to connect to the client
                host, port = self.dataConnSetupMessages[dataConnCounter]
                self.dataConnSockets[dataConnCounter].connect((host, port))

            self.dataConnSelector.append(self.dataConnSelector[-1])

        return None

    def _cleanup(self):
        for sock in self.dataConnSockets:
            sock.close()


def main() -> None:
    cs = FTPClientSimulator()
    clientSock = socket.socket()
    clientSock.connect(("127.0.0.1", 21))
    password = os.environ["SI_FTP_PASSWORD"]

    ## Commands to issue to the server
    commSequence = [
        [b"USER SI_FTPTestUser1\r\n"],
        [bytes(f"PASS {password}\r\n", "utf-8")],
        [b"PASV\r\n", b"PASV\r\n", b"PASV\r\n"],
        [b"LIST\r\n"],
        [b"PASV\r\n"],
        [b"PASV\r\n"],
        [b"PORT 127,0,0,1,10,0\r\n"],
        [b"PORT 127,0,0,1,10,1\r\n"],
        [b"LIST\r\n"],
        [b"PASV\r\n"],
        [b"PORT 127,0,0,1,10,2\r\n", b"PORT 127,0,0,1,10,3\r\n", b"LIST\r\n"],
        [b"DELE test.txt\r\n"],
        [b"PORT 127,0,0,1,10,5\r\n", b"PORT 127,0,0,1,10,6\r\n"],
        [b"STOR test.txt\r\n"],
        [b"DELE test.txt\r\n"]

    ]

    ## Data to send to the client
    dataSequence = [
        b"testing123"
    ]

    pprint.pprint(cs.simulateCommSequence(clientSock, commSequence, dataSequence, 0.25))
    return None

if __name__ == "__main__":
    main()