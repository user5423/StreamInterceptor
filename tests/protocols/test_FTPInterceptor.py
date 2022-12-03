import collections
import typing
import pytest

# from ftp_proxyinterceptor import FTPProxyInterceptor

import os
import sys
sys.path.insert(0, os.path.join("src"))
sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, os.path.join("..", "..", "src"))

from ftp_proxyinterceptor import FTPProxyInterceptor



class Test_FTPProxyInterceptors_Helpers:
    def test_getResponse_multiline(self) -> None:
        pi = FTPProxyInterceptor()
        ## TODO: Find out what the actual delimiter is for lines (within a reply)
        assert pi._getResponseCode("100-firstline\n secondline\n 100 finalline") == 100

    def test_getResponse_singleline(self) -> None:
        pi = FTPProxyInterceptor()
        assert pi._getResponseCode("100 firstline") == 100

    def test_getResponseCode_lowerBounds(self) -> None:
        ## NOTE: We only need to check if the bounds are correct
        ## There exist values inside that are not valid response codes (potentially)
        ## But we trust the server
        pi = FTPProxyInterceptor()
        assert pi._getResponseCode("100 firstline") == 100
        assert pi._getResponseCode("200 firstline") == 200
        assert pi._getResponseCode("300 firstline") == 300
        assert pi._getResponseCode("400 firstline") == 400
        assert pi._getResponseCode("500 firstline") == 500

    def test_getResponseCode_upperBounds(self) -> None:
        pi = FTPProxyInterceptor()
        assert pi._getResponseCode("159 firstline") == 159
        assert pi._getResponseCode("259 firstline") == 259
        assert pi._getResponseCode("359 firstline") == 359
        assert pi._getResponseCode("459 firstline") == 459
        assert pi._getResponseCode("559 firstline") == 559

    def test_getResponseCode_outOfLowerBounds(self) -> None:
        pi = FTPProxyInterceptor()
        testCases = ["000", "099", "199", "299", "399", "499"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test + " firstline")

    def test_getResponseCode_OutOfUpperBounds(self):
        pi = FTPProxyInterceptor()
        testCases = ["160", "260", "360", "460", "560"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test + " firstline")

    def test_getResponseCode_GreaterSize(self):
        pi = FTPProxyInterceptor()
        testCases = ["1000", "10000"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test + " firstline")

    def test_getResponseCode_SmallerSize(self):
        pi = FTPProxyInterceptor()
        testCases = ["10", "1"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test + " firstline")


    def test_getResponse_badStart(self) -> None:
        pi = FTPProxyInterceptor()
        testCases = ["sometext 100", " 100", "some100"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test + " firstline")

    def test_getResponse_badAfter(self) -> None:
        pi = FTPProxyInterceptor()
        testCases = ["100x someline", "100someline", "100=someline"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test)


# class Test_FTPProxyInterceptor_Init:
#     def test_FTPProxyInterceptor_init(self) -> None:
#         fpi = FTPProxyInterceptor()

#         ## Current class attribute assertions
#         assert isinstance(fpi._loginStateGenerator, typing.Generator)
#         assert isinstance(fpi._requestQueue, collections.deque)
#         assert isinstance(fpi._responseQueue, collections.deque)
#         assert fpi._responseQueue != fpi._requestQueue

#         ## TODO: Assert superclass attribute assertions
#         ## We need to check that the abstract methods have been overriden


# # class Test_FTPProxyInterceptor_Hooks:
# #     ## These methods assume that
# #     ## -- there is at least one delimited request in the queue
# #     ## -- and, the correct buffer has been passed in
# #     def test_clientToServerRequestHook_(self) -> None:
        
# #         ...

    