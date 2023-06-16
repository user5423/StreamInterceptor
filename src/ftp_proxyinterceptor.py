import re
import logging
import collections
from typing import Optional, Tuple, Dict, Generator

from _proxyDS import StreamInterceptor, Buffer

from abc import abstractmethod, ABCMeta


class FTPProxyInterceptor(StreamInterceptor, metaclass=ABCMeta):
    def __init__(self) -> None:
        super().__init__()
        ## Here are the requests
        self._requestQueue = collections.deque()
        self._responseQueue = collections.deque()
        self._stateGenerator = self._createStateGenerator()
        self.REQUEST_DELIMITERS = [b"\r\n", b"\r"]

    ## NOTE: These methods assume that the there is at least one delimited reqeust in buffer
    ## NOTE: These methods assume that the correct buffer has been passed as an argument
    def clientToServerRequestHook(self, buffer: Buffer) -> None:
        ## we retrieve a request from the buffer
        request, _ = buffer.popFromQueue()
        self.ftpMessageHook(request=request)

    def serverToClientRequestHook(self,  buffer: Buffer) -> None:
      ## we retrieve a request from the buffer
        response, _ = buffer.popFromQueue()
        self.ftpMessageHook(response=response)


    def ftpMessageHook(self, request: Optional[str] = None, response: Optional[str] = None) -> None:
        ## FTP is intended to have an alternating communication
        ## -- We cannot control the adversary
        ## -- But we control our FTP server,

        ## RFC 959 Page 37
        ## 1yz Replies
        ## "(The user-process sending another command before the
        ## completion reply would be in violation of protocol; but
        ## server-FTP processes should queue any commands that
        ## arrive while a preceding command is in progress.)"

        ## ==> Therefore, even if the adversary spams multiple requests in the same chunk
        ## the FTP will most likely
        ## --> 1. parse one request up until a delimeter
        ## --> 2. process that request
        ## --> 3. send response
        ## --> 4. then again try 1. (and will wait until it can retrieve the data from the socket)

        ## In our solution we alternate between consuming requests, and then replies

        ## Validates that the method was only called with one argument, not both
        self._validateHookArgs(request, response)

        ## We add the request or response to their corresponding queues
        if request:
            self._requestQueue.append(request)
        else:
            self._responseQueue.append(response)

        ## We then check if there exists a request with a corresponding response
        if min(len(self._requestQueue), len(self._responseQueue)) > 0:
            ## execute a generator (that maintains the state of the login mechanism)
            next(self._stateGenerator)

        return None


    def _validateHookArgs(self, request: Optional[str] = None, response: Optional[str] = None) -> None:
        if not (bool(request) ^ bool(response)):
            raise Exception(f"Cannot only pass a request OR response, not both - request={request}, response={response}")

    def _getResponseCode(self, response: str) -> int:
        ## All reply codes have a length of 3
        ## Reply code xyz
        ## 1 <= x <= 5
        ## 0 <= y <= 5
        ## 0 <= z <= 9 ## not specified on FRC and servers may provide custom replies so we take up the whole range 0-9
        ## NOTE: Multiline replies may do \d\d\d-firstline ... instead of \d\d\d only line (space vs hyphen)
        ret = re.search("^([1-5][0-5][0-9])[ -]", response)
        return int(ret.groups()[0])

    @abstractmethod
    def _createStateGenerator(self) -> Generator:
        ...

    @abstractmethod
    def _executeSuccessHook(self, *args, **kwargs) -> None:
        ...




class FTPLoginProxyInterceptor(FTPProxyInterceptor):
    def _createStateGenerator(self) -> Generator:
        return self._updateLoginState()

    def _updateLoginState(self) -> None:
        print("updating login state")
        ## Now we perform the logic
        ## We continuously track logins until the ftp connection is shut down
        ## We refer to Page 58 of the FTP RFC 959 for the Login Sequence

        ## NOTE: The sequence must be adhered to according to the specification
        ## -- Otherwise the 503 reply code wouldn't exist for PASS and ACCT which have
        ## commands that preceed it

        ## NOTE: There is no need for an else statement for each request below

        while True:
            ## Define variables
            username = None
            password = None
            messages = {}

            ## NOTE: The reason why the first step is different from step 2 and 3 is that we need to wait for the USER command
            ## to trigger a command sequence. This is why we check every request to see if it is a USER request which will trigger
            ## the login command sequence

            ## 1. First Request (USER)
            request = self._requestQueue.pop()
            response = self._responseQueue.pop()
            messages["USERrequest"] = request
            messages["USERresponse"] = response
            if self._isUSERRequest(request):
                completeReq, username = self._parseUSERrequest(request, response, messages)
                yield
                if completeReq is True:
                    continue
            ## otherwise, we didn't get a USER request, so we ignore it, and go back to the top of the while loop
            else:
                yield
                continue

            ## 2. Second Request (PASS)
            request = self._requestQueue.pop()
            response = self._responseQueue.pop()
            messages["PASSrequest"] = request
            messages["PASSresponse"] = response
            completeReq, password = self._parsePASSrequest(request, response, messages, username)
            yield
            if completeReq is True:
                continue

            ## 3. Third Request (ACCT)
            request = self._requestQueue.pop()
            response = self._responseQueue.pop()
            messages["ACCTrequest"] = request
            messages["ACCTresponse"] = response
            completeReq, _ = self._parseACCTrequest(request, response, messages, username, password)
            yield

            ## NOTE: There should be no 3yz reply code (hence to check if completeReq is True)

        return None

    def _parseUSERrequest(self, request, response, messages: Dict[str, str]) -> Optional[str]:
        messages["USERrequest"] = request
        messages["USERresponse"] = response
        responseCode = self._getResponseCode(response)
        if 100 <= responseCode <= 199:
            ## Error
            self._createFTPLoginErrorMessage("ERROR", "USER", (messages["USERrequest"], messages["USERresponse"]))
            return True, None
        elif 200 <= responseCode <= 299:
            ## Success
            ## NOTE: You should not be able to login with just USER command
            username = self._getUsername(request)
            self._createFTPLoginSuccessMessage("USER", username)
            self._executeSuccessHook(username)
            return True, username
        elif 400 <= responseCode <= 599:
            ## Failure
            self._createFTPLoginErrorMessage("FAILURE", "USER", (messages["USERrequest"], messages["USERresponse"]))
            return True, None
        else:
            ## otherwise we got 3yz reply (intermediary positive reply), so we continue with the command sequence
            username = self._getUsername(request)
            return False, username


    def _parsePASSrequest(self, request, response, messages, username) -> Optional[str]:
        responseCode = self._getResponseCode(response)
        if 100 <= responseCode <= 199:
            ## Error
            self._createFTPLoginErrorMessage("ERROR", "PASS", (messages["USERrequest"],
            messages["USERresponse"]), (messages["PASSrequest"], messages["PASSresponse"]))
            return True, None
        elif 200 <= responseCode <= 299:
            ## Success
            password = self._getPassword(request)
            self._createFTPLoginSuccessMessage("PASS", username, password)
            self._executeSuccessHook(username, password)
            return True, password
        elif 400 <= responseCode <= 599:
            ## Failure
            self._createFTPLoginErrorMessage("FAILURE", "PASS", (messages["USERrequest"],
            messages["USERresponse"]), (messages["PASSrequest"], messages["PASSresponse"]))
            return True, None
        else:
            ## otherwise we got 3yz reply, so we continue
            password = self._getPassword(request)
            return False, password


    def _parseACCTrequest(self, request, response, messages, username, password) -> Optional[str]:
        responseCode = self._getResponseCode(response)
        if 100 <= responseCode <= 199 or 300 <= responseCode <= 399:
            ## Error
            self._createFTPLoginErrorMessage("ERROR", "ACCT", (messages["USERrequest"], messages["USERresponse"]),
            (messages["PASSrequest"], messages["PASSresponse"]), (messages["ACCTrequest"], messages["ACCTresponse"]))
            return True, None
        elif 200 <= responseCode <= 299:
            ## Success
            account = self._getAccount(request)
            self._createFTPLoginSuccessMessage("ACCT", username, password, account)
            self._executeSuccessHook(username, password, account)
            return True, account
        elif 400 <= responseCode <= 599:
            ## Failure
            self._createFTPLoginErrorMessage("FAILURE", "ACCT", (messages["USERrequest"], messages["USERresponse"]),
            (messages["PASSrequest"], messages["PASSresponse"]), (messages["ACCTrequest"], messages["ACCTresponse"]))
            return True, None
        else:
            ## I believe there should be no 3yz error if ACCT is received
            ## TODO: Confirm this is True by reviewing RFC959
            self._createFTPLoginErrorMessage("ERROR", "ACCT", (messages["USERrequest"], messages["USERresponse"]),
            (messages["PASSrequest"], messages["PASSresponse"]), (messages["ACCTrequest"], messages["ACCTrequest"]))
            return False, None

    def _executeSuccessHook(self, username: Optional[str] = None, password: Optional[str] = None, account: Optional[str] = None) -> None:
        """This will async communicate with the _database class component to check whether the creds are a bait trap"""
        print("Success!!")
        raise NotImplementedError()


    ## TODO: Restructure Success and Error messages to use Logging fields!!!
    ## NOTE: This makes debugging and sifting through logs so much easier!!!
    def _createFTPLoginSuccessMessage(self, requestVerb: str,
                                        username: Optional[str] = None,
                                        password: Optional[str] = None,
                                        account: Optional[str] = None) -> None:

        ## Validation performed on arguments
        ## Cannot have a empty error being logged
        assert username is not None
        assert requestVerb in ("USER", "PASS", "ACCT")

        ## Create success message
        successMsg = "SUCCESS @ftp.cmds.%s - " % requestVerb
        if username:
            successMsg += "Username: <%s>, " % username
        if password:
            successMsg += "Password: <%s>, " % password
        if account:
            successMsg += "Account: <%s>" % account

        ## Log the success message
        logging.critical(successMsg)


    def _createFTPLoginErrorMessage(self, errorType: str, requestVerb: str,
                                    USERmessages: Optional[Tuple[bytes]] = None,
                                    PASSmessages: Optional[Tuple[bytes]] = None,
                                    ACCTmessages: Optional[Tuple[bytes]] = None) -> None:

        ## Validation performed on arguments
        ## Cannot have a empty error being logged
        assert USERmessages is not None
        assert errorType in ("FAILURE", "ERROR")
        assert requestVerb in ("USER", "PASS", "ACCT")

        ## Create error message
        errorMsg = "%s @ftp.cmds.%s " % (errorType, requestVerb)
        if USERmessages:
            errorMsg += "1) USER-request: <%s>, USER-response: <%s>, \t" % (repr(USERmessages[0]), repr(USERmessages[1]))
        if PASSmessages:
            errorMsg += "2) PASS-request: <%s>, PASS-response: <%s>, \t" % (repr(PASSmessages[0]), repr(PASSmessages[1]))
        if ACCTmessages:
            errorMsg += "2) ACCT-request: <%s>, ACCT-response: <%s>, \t" % (repr(ACCTmessages[0]), repr(ACCTmessages[1]))

        ## Log the error message
        if errorType == "FAILURE":
            logging.error(errorMsg)
        else:
            logging.error(errorMsg)


    def _isUSERRequest(self, request: str) -> bool:
        ## NOTE: We don't need to check if this is a valid request as we'll only process the request arguments if
        ## the reply code is a positive one
        ## NOTE: We are being softer than RFC 959 on the standards by stripping whitespace (in case there are FTP
        ## implementations that have the same behavior)

        ## NOTE: the regex checks if the strings starts with zero or more spaces and then has a USER string succeedeing it
        if re.search("^USER (\w+)(\r\n|\r)", request):
            return True
        return False


    ## TODO: Rewrite these three methods to use regex searches
    ## NOTE: These methods will only be executed assuming that the request received a positive 3xx response
    ## --> This means input validation on the request isn't neccessary
    def _getUsername(self, request: str) -> str:
        ret = re.search("^USER (\w+)(\r\n|\r)", request)
        return ret.groups()[0]
        ## The User request should be delimited with either \r\n or \r at the END of the request, so we strip that on the end (i.e. right of str)
        ## NOTE: Although the RFC 959 defines the commands on 1985, we don't have to adhere to its strictness and can
        ## be lenient in order to interpret requests that would otherwise be incorrect against the standard.
        ## e.g. in the below, the "space" should not be between the last param and the CRLF delimeter

    def _getPassword(self, request: str) -> str:
        ret = re.search("^PASS (\w+)(\r\n|\r)", request)
        return ret.groups()[0]

    def _getAccount(self, request: str) -> str:
        ret = re.search("^ACCT (\w+)(\r\n|\r)", request)
        return ret.groups()[0]





## NOTES ----------------------------------------------------------------------------------------------


## Defined behavior for
## -- Success
##      - Reset all variables in generator and start at top of while loop (I.E. REEST TO INITIAL STATE)
## -- Error
##      - TODO: No Idea
## -- Failure
##      - TODO: No idea

## My interpretation of RFC 595 is that error and failure results in the same action in our case

## For 5yz and 4yz, RFC 959 (page 37/38) specifies that:
##  - "reinitiate the command sequence"
## 4yz and 5yz directly correspond to FAILURE

## From context it seems that
## -- Failure: means an expected problem arose (e.g. someone sent incorrect creds)
## -- Error: means an unexpected problem arose (e.g. some internal error arose resulting in an unexpected return value)

## Error is worse than Failure
## --> So I assume that the measures taken by error should be stricter than failure
## --> Failure has maximum measure (i.e. restart the command sequence)
## --> Therefore Error should have this (at least)
## --> Alternatively, it causes the FTP client to drop the connection

# ReplyCodes
# User:
#   230
#   530
#   500, 501, 421
#   331, 332
# Password:
#   230
#   202
#   530
#   500, 501, 503, 421
#   332

# 202 - Command not implemented, superfluous at this site (how does this differ to 502?)
# 230 - User Logged in
# 331 - Username Okay, need password
# 332 - Need account for login
# 421 - Service is not available
# 530 - Not Logged in
# 500 - Syntax error, command unrecognized
# 501 - Syntax error in parameters or arguments
# 503 - Bad sequence of commands (maybe executed PASS command without USER command first??)


# 1x - Postiive Preliminary (e.g. Action initiated, waiting for another reply)
# 2x - Postive Completion (e.g. Action success)
# 3x - Postivei intermediate reply (e.g. a set in the action was performed successfully, requires additional input data)
# 4x - Transient Negative Completion Reply (Temporary)
# 5x - Permenant Negative Completion reply


## The FTP request format is as follows
## - VERB PARAM \015\012 (CLRF)

## The FTP reply format is as follows:
## - STATUS-CODE STATUS-MESSAGE (CLRF I guess??)

## What we are really looking for is:
## - USER <username>
## - PASS <password>

## Once this is satisfied, we then check these username, password combo against the database


## So according to the article,
## - https://cr.yp.to/ftp/request.html
## some client-PI fail to send CR, so it recommends to only look for \n (as this isn't allowed in the param value)


## Instead of the rereading the buffer every time something is added
## - we store incoming data into the buffer
## - ADDITIONALLY, we store into a new temp location
##      - we iterate over the received bytes for the delimeter
##      - for each one we find
##          - we split the temp buffer into several Layer 7 requests (maybe in something like a queue)
##          - i.e. and then perform the hook for each complete request
##          - each call to the hook consumes request

## NOTE: One issue is that delimeters may have multiples bytes
##  - HOWEVER, the goal of delimeters to seperate two entities
##  - this goal request a contiguous delimeter
##      - i.e. the delimeter is a set of contiguous bytes
##  - If the delimeter is of multiple bytes,
##      - then its possible that it can be spread out over multiple request recv() calls
##  - If we only scan the new request recv()
##      - it's possible that there is the prev chunk ended in \r\n\r and the new chunk starts as \n

## SOLUTION:
##      - when reading a new chunk, we read the last len(delimeter) - 1 bytes of the buffer before the recv()
##      - Why len(delimeter) - 1?
##          - if we read len(delimeter) last bytes of the buffer and we find a delimeter
##          - that means our previous code didn't work as it should have found thie delimeter
##          - in the last recv()
## This solution works well enough as we only reread a small constant amount of the content
##  - This helps us avoid huge requests that are chunked into bytes (causing many calls to recv())
##  - which would slow down the system


## Implementation Methods

## Solution 1:
## - We start with a deque
##      - one to hold requests
##      - one to hold replies

## - Whenver we receive a chunk
##      - we iterate over the chunk
##          - (we look back at the last len(delimeter) -1 bytes)
##      - for each character
##          - we add it to the top element in the deque
##      - for each delimeter
##          - we create a new item at the top of the deque


## Analysis

## 1. This solution is OK
##      + Only constant rereading of bytes (instead of rereading entire element)
##      + Splitting request splitting and parsing makes it conceptually decoupled (simpler)
## 2. However, it has some deficitis (that we'll want to overcome)
##      - Strings are immutable, so python reallocates on every + operation (which happpens for EVERY byte)
##      + We could try delaying this until we have reached the delimeter
##      + Potentially using ctypes char arrays could provide a speed up


## Solution 1a:
## - We initialize an empty deque
##      - one for requests
##      - one for replies

## - Whenever we receive a chunk
##      - we iterate over the chunk
##      - once we have reached a delimeter
##          - we add it as a new request/reply into the queue


## How do we determine a delimeter??
## - We perform the following

## this->delimeter = "\r\n\r\n"

## In the above example, we do NOT reset once one letter is out of place neccessarily
## -- creating a FSA


## --\r--> 1 --\n--> 2 --\r--> 3 --\n--> [4]
##        | |
##         \r

## For example, in the above,
##  - if we are at 1 and we see another \r, we stay in the same place
##  - if we are at 3 and we see another \r, we go to 1 instead of 0

## instead of recalculating and iterating over every byte in the delimeter
##  - We could construct a FSA which would have lookups already performed
## - This would be a dictionary int the following form:
##          - Dict[index][char] --> newIndex


## NOTE: IT is imperative that we do NOT allow Smuggling attacks


## FTP Request poisoning

## what if there are multiple USER requests
## - is the next PASS based on the most recent USER request?


## NOTE: We need to be careful with behavior mismatches


## If we took the first USER and first PASS in a request, then that would be terrible
## SOmeone could craft data such that the control connection would look like this


## > USER invaliduser (selected user)
## < Fail
## > USER correctuser
## < Success

## > PASS invalidpass (selected pass)
## < Fail
## > User correctpass
## < Success LoggedIn

## The above would check the database with creds invaliduser:invalidpass
## -- eventhough the adversary would have successfully logged in
## -- our program wouldn't have realized it

## NOTE: We need to be careful to find
## - what is the reference state behvaior for this
##


# USER "test"

# POST ...
# header1: Value\n
# header2: Value\n
# \r\n

# body

# \r\n\r\n


## NOTE: We need to add statefullness on each request received
