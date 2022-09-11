
from multiprocessing.sharedctypes import Value
from tkinter import N
from _proxyDS import ProxyInterceptor, Buffer

## NOTE: We should be ok vs Slow

CR = "\r"
LF = "\n"

## NOTE: This is not intended to work robustly - this is just a code that is meant to show an example
class HTTPProxyInterceptor(ProxyInterceptor):
    def clientToServerHook(self, requestChunk: bytes, buffer: "Buffer") -> None:
        buffer._data = buffer._data.replace(b"0.0.0.0:8080", b"127.0.0.1:80")

    def serverToClientHook(self, requestChunk: bytes, buffer: "Buffer") -> bytes:
        buffer._data = buffer._data.replace(b"127.0.0.1:80", b"0.0.0.0:8080")


class FTPProxyInterceptor(ProxyInterceptor):
    def clientToServerHook(self, requestChunk: bytes, buffer: "Buffer") -> None:
        ...

    def serverToClientHook(self, responseChunk: bytes, buffer: "Buffer") -> None:
        ...


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