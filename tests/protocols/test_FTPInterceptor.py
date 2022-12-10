import collections
import typing
import pytest

# from ftp_proxyinterceptor import FTPProxyInterceptor
import inspect
import os
import sys
sys.path.insert(0, os.path.join("src"))
sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, os.path.join("..", "..", "src"))

from ftp_proxyinterceptor import FTPProxyInterceptor, FTPLoginProxyInterceptor


class FTPProxyTestResources:
    @classmethod
    def createUnabstractedFTPInterceptor(cls):
        class TestFTPProxyInterceptor(FTPProxyInterceptor):
            def _createStateGenerator(self) -> typing.Generator:
                yield
                return

            def _executeSuccessHook(self) -> None:
                ...

        return TestFTPProxyInterceptor()


## TODO: Need to restructure the class tests to handle the new
## class hierarchy that I have created to reorganize the code
## for the proxyInterceptor

class Test_FTPProxyInterceptors_Helpers:
            
    ## Tests for _getResponse()
    def test_getResponse_multiline(self) -> None:
        pi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        ## TODO: Find out what the actual delimiter is for lines (within a reply)
        assert pi._getResponseCode("100-firstline\n secondline\n 100 finalline") == 100

    def test_getResponse_singleline(self) -> None:
        pi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        assert pi._getResponseCode("100 firstline") == 100

    def test_getResponseCode_lowerBounds(self) -> None:
        ## NOTE: We only need to check if the bounds are correct
        ## There exist values inside that are not valid response codes (potentially)
        ## But we trust the server
        pi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        assert pi._getResponseCode("100 firstline") == 100
        assert pi._getResponseCode("200 firstline") == 200
        assert pi._getResponseCode("300 firstline") == 300
        assert pi._getResponseCode("400 firstline") == 400
        assert pi._getResponseCode("500 firstline") == 500

    def test_getResponseCode_upperBounds(self) -> None:
        pi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        assert pi._getResponseCode("159 firstline") == 159
        assert pi._getResponseCode("259 firstline") == 259
        assert pi._getResponseCode("359 firstline") == 359
        assert pi._getResponseCode("459 firstline") == 459
        assert pi._getResponseCode("559 firstline") == 559

    def test_getResponseCode_outOfLowerBounds(self) -> None:
        pi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        testCases = ["000", "099", "199", "299", "399", "499"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test + " firstline")

    def test_getResponseCode_OutOfUpperBounds(self):
        pi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        testCases = ["160", "260", "360", "460", "560"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test + " firstline")

    def test_getResponseCode_GreaterSize(self):
        pi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        testCases = ["1000", "10000"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test + " firstline")

    def test_getResponseCode_SmallerSize(self):
        pi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        testCases = ["10", "1"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test + " firstline")


    def test_getResponse_badStart(self) -> None:
        pi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        testCases = ["sometext 100", " 100", "some100"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test + " firstline")

    def test_getResponse_badAfter(self) -> None:
        pi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        testCases = ["100x someline", "100someline", "100=someline"]
        for test in testCases:
            with pytest.raises(Exception) as excInfo:
                pi._getResponseCode(test)


    ## Testing argument validation
    def test_validateHookArgs_NoArguments(self) -> None:
        fpi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        with pytest.raises(Exception) as excInfo:
            fpi._validateHookArgs()
        assert "Cannot only pass a request OR response" in str(excInfo.value)
            
    def test_validateHookArgs_RequestOnly(self) -> None:
        fpi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        req = "USER username\r\n"
        fpi._validateHookArgs(request=req)

    def test_validateHookArgs_ResponseOnly(self) -> None:
        fpi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        resp = "200 OK\r\n"
        fpi._validateHookArgs(response=resp)

    def test_validateHookArgs_RequestAndResponse(self) -> None:
        fpi = FTPProxyTestResources.createUnabstractedFTPInterceptor()
        req = "USER username\r\n"
        resp = "200 OK\r\n"
        with pytest.raises(Exception) as excInfo:
            fpi._validateHookArgs(request=req, response=resp)
        assert "Cannot only pass a request OR response" in str(excInfo.value)


