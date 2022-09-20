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
        ## In our solution we alternate between consuming requests, and then replies

        ## Validates that the method was only called with one argument, not both
        self._validateHookArgs(request, response)

        ## We add the request or response to their corresponding queues
        ...


        ## We then check if there exists a request with a corresponding response and execute _updateLoginState() generator
        ...
        return None


    def _validateHookArgs(self, request: Optional[str] = None, response: Optional[str] = None) -> None:
        ...        


    def _updateLoginState(self) -> None:
        ...


    def _executeFTPLoginSuccessHook(self, username: str, password: str) -> None:
        """This will async communicate with the _database class component to check whether the creds are a bait trap"""
        raise NotImplementedError()


    def _getResponseCode(self, request: str) -> Optional[int]:
        ...

