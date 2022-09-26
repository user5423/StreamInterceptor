from http.client import REQUEST_URI_TOO_LONG
import re
import logging
import collections
from typing import Generator, Optional, Tuple

from _proxyDS import ProxyInterceptor, Buffer


class IMAPProxyInterceptor(ProxyInterceptor):
    def __init__(self) -> None:
        super().__init__()

        ## Here are the requests
        self._requestQueue = collections.deque()
        self._responseQueue = collections.deque()

        ## Here's the generator that holds the state
        self._loginStateGenerator: Generator[None, Tuple[str, str], None] = self._updateLoginState()
        next(self._loginStateGenerator)

        ## Check if the serverGreeting was received
        self._serverGreetingReceived = False


    ## NOTE: These methods assume that the there is at least one delimited reqeust in buffer
    ## NOTE: These methods assume that the correct buffer has been passed as an argument
    def clientToServerRequestHook(self, buffer: Buffer) -> None:
        ## we retrieve a request from the buffer
        request, delimited = buffer.popFromQueue()
        if not delimited:
            raise ValueError("Cannot perform request hook on a request that isn't delimited (i.e. not complete)")

        self.imapMessageHook(request=request)


    def serverToClientRequestHook(self,  buffer: Buffer) -> None:
      ## we retrieve a request from the buffer
        response, delimited = buffer.popFromQueue()
        if not delimited:
            raise ValueError("Cannot perform request hook on a request that isn't delimited (i.e. not complete)")

        self.imapMessageHook(response=response)


    def imapMessageHook(self, request: Optional[str] = None, response: Optional[str] = None) -> None:
        ## Unlike protocol such as FTP, IMAP allows for concurrent requests from a singular client
        ## --> This results in a messaging system that isn't alternating (++complexity)
        ## Furthermore, the data and control content are sent over the SAME connection
        ## --> This results in more posibilities to mess up (++complexity)

        ## Validates that the method was only called with one argument, not both
        self._validateHookArgs(request, response)

        ## We are mainly here for tracking authentication commands
        ## -- these requests are tagged which will help us to track
        ## -- we do care about untagged command
        ## --> e.g. those for "command continuation request" reponses from the server (e.g. prefixed with +)
        ##          --> Continued commands are performed synchrnously (otherwise we receive BAD response)
        ## 

        ## FTP used a request and response queue
        ## --> Do we want to use the same data structuer

        ## Due to FTP's alternating request structure, we were able to say that
        ## req[i] == resp[i]

        ## However, this is not possible in IMAP for a few reasons
        ## 1. concurrent requests are allowed 
        ## 2. a single command can result in multiple response messages

        ## We need a mechanism to be able to pickup on
        ## -- tagged commands
        ## -- the whole sequence for a continuated command (e.g. responses starting with token `+`)
        ## -- tagged responses

        self._loginStateGenerator.send((request, response))
        return None
    

    def _updateLoginState(self) -> None:
        # How to use: Initiate the generator object, execute it, and then all later request and
        # responses that are passed need to be executed by calling generator.send(args...) call
        # This will pass values to the yield calls and allow continuation of flow of execution
        # NOTE: Typically, .send() will return a StopIteration error in the case where the function
        # has completely been executed. But due to the structure of the generator having a while loop,
        # we don't need to worry about that


        ## There are three ways to login
        ## - PREAUTH
        ## - LOGIN or AUTHENTICATE

        ## The server greeting MUST preceed LOGIN and AUTHENTICATE
        ## PREAUTH (should be one time) whereas LOGIN/AUTHENTICATE can be exec multiple times during connection
        queue = collections.deque()
        tagMatcher = {}
        RESPONSE = 0
        REQUEST = 1

        ## NOTE: Only response calls should be processed by _updateLoginState until server greeting received
        while self._serverGreetingReceived is False:
            ## We retrieve the request/response
            request, response = yield
            queue.append((REQUEST, request) if request else (RESPONSE, response))

            ## First we check if the server-greeting has been received
            if response is not None:
                ## Server Greeting structure are defined in RFC 3501 commands sections
                ## Valid Greetings are OK, BYE, and PREAUTH
                search = re.search('\*\s+(OK|BYE|PREAUTH)(\s+\[\w+\])?(\s[\w\s]+)', response)

                if search is None:
                    ## The first message SHOULD be a greeting from the Server Protocol Handler
                    ## Therefore we log non-compliance with RFC3501 as an ERROR
                    logging.debug("The first message from the IMAP Server was not an expected Server greeting \
                                - Server Greeting: %s", response)
                else:
                    
                    greetingType, greetingStatus, greetingText = search.groups()
                    self._serverGreetingReceived = True

                    if greetingType == "PREAUTH":
                        ## Authentication was bypassed unexpectedly - Client should be unable to initiate 
                        ## PREAUTH connections with Server Protocol Handler in a BeeLurer environment
                        logging.critical("PREAUTH connection should NOT be allowed - Server Greeting: %s", response)
                    elif greetingType == "BYE":
                        ## The connection was CLOSED immediately (in this greeting context)
                        logging.debug("Connection immediately closed by IMAP Server - Server Greeting: %s", response)
                    elif greetingType == "OK":
                        ## The connection was properly initiated
                        logging.info("Connection accepted successfully by IMAP Server - Server Greeting: %s", response)

                    ## No else statement due to regex search (must be one of three greetings - OK, BYE, PREAUTH)
        
        ## At this point we have received the server greeting
        while True:
            ## Now we work through these requests (in case we have a buffer from previously)
            while len(queue):
                isRequest, message = queue.popleft()
                if isRequest:
                    search = re.search('(\w+)\s+([a-zA-Z]+)(\s+[\w\s]+)?', request)
                    if search is None:
                        ## Then the regex is not correct - log an error
                        logging.critical("Regex search string did not match the request: %s", message)

                    tag, command, args = search.groups()
                    if command == "LOGIN":
                        tagMatcher[tag] = (command, args)
                    ## No support for AUTHENTICATE as of now

                else:
                    ## tagged response
                    taggedStatusResponse = re.search('(\w+)\s+(OK|NO|BAD)\s+([a-zA-Z]+)(\s+[\w\s]+)?', request)
                    if taggedStatusResponse is None:
                        continue

                    tag, response, command, humanText = taggedStatusResponse.groups()
                    request = tagMatcher.pop(tag)
                    
                    if command == "LOGIN":
                        command, args = request
                        username, password = args.strip(" ").split(" ")
                        self._executeIMAPLoginSuccessHook(username, password)

                    ## No support for AUTHENTICATE as of now

            ## We retrieve the yield
            request, response = yield
            queue.append((REQUEST, request) if request else (RESPONSE, response))

        
    def _executeIMAPLoginSuccessHook(self, username: str, password: str) -> None:
        raise NotImplementedError()   


    def _validateHookArgs(self, request: Optional[str] = None, response: Optional[str] = None) -> None:
        raise NotImplementedError()   


## I don't know how pre-authenticated connections work in IMAP
## --> Ctrl+F to find in RFC doesn't provide any meaningful results to instantiate this
## --> One stack overflow post states that they can use a imap binary to locally connect
## to the imap server (and states it can be used for debugging). Maybe the server binary
## can double down and be used as a client aswell? Therefore if you have rwx perms for the
## imap files, then you don't need to authenticate??

## There are two ways to get into an authentictated state
## 1. PREAUTH connection
## 2. successful LOGIN or AUTHENTICATE command
##      -- what is the difference between LOGIN and AUTHENTICATE??

## What is the difference between LOGIN and AUTHENTICATE
## 1. LOGIN
##      - Uses traditional username:password
##      - 

## We'll start by disabling AUTHENTICATE and only allowing tadditional LOGIN


## There are four ways to go from authenticate to unauthenticate state
## 1. CLOSE command
## 2. Failed SELECT/EXAMINE command
## 3. LOGOUT command
## 4. server shutdown / connection closed

## QUESTION: Can you login into a new account from an authenicated account?
## -- (e.g. in FTP we can login into a new account without logging out)


## We'll add logging in case this is every met

## we check server greeting
## if server.greeting received && response contains (* PREAUTH)
## --- LOGGING.CRITICAL(unexpected login detected)
## --- SUCCESSFULLY LOGGED IN
## if request contains (tag LOGIN|AUTHENTICATE params)
## -- LOGGING.INFO (someone has trigged a LOGIN command continuation sequence)
## -- read continuation sequence

## LOGIN is used for basic username:password

## AUTHENTICATE will be disabled for now


