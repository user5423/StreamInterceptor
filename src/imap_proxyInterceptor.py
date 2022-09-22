from http.client import REQUEST_URI_TOO_LONG
import re
import logging
import collections
from typing import Optional, Tuple

from _proxyDS import ProxyInterceptor, Buffer


class IMAPProxyInterceptor(ProxyInterceptor):
    def __init__(self) -> None:
        super().__init__()

        ## Here are the requests
        self._requestQueue = collections.deque()
        self._responseQueue = collections.deque()

        ## Here's the generator that holds the state
        self._loginStateGenerator = self._updateLoginState()


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

        ## 

        ...


        ## We then check if there exists a request with a corresponding response and execute _updateLoginState() generator
        ...
        return None


    def _validateHookArgs(self, request: Optional[str] = None, response: Optional[str] = None) -> None:
        ...        


    def _updateLoginState(self, request: Optional[str] = None, response: Optional[str] = None) -> None:
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
        return None

    def _executeFTPLoginSuccessHook(self, username: str, password: str) -> None:
        """This will async communicate with the _database class component to check whether the creds are a bait trap"""
        raise NotImplementedError()


    def _getResponseCode(self, request: str) -> Optional[int]:
        ...

