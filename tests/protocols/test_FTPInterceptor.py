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


    @classmethod
    def createUnabstractedFTPLoginInterceptor(cls):
        class TestFTPLoginProxyInterceptor(FTPLoginProxyInterceptor):
            def __init__(self) -> None:
                super().__init__()
                self.calledExecuteSuccessHook = False
                self.successUsername = None
                self.successPassword = None
                self.successAccount = None

            def _createStateGenerator(self) -> typing.Generator:
                yield
                return

            def _executeSuccessHook(self, username: str = None, password: str = None, account: str = None) -> None:
                self.calledExecuteSuccessHook = True
                self.successUsername = username
                self.successPassword = password
                self.successAccount = account
                return

        return TestFTPLoginProxyInterceptor()
    

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



class Test_FTPLoginProxyInterceptor_Helpers:

    ## Tests for _getUsername(...)
    def test_getUsername_correctFormat_Delimiter1(self):
        pi = FTPLoginProxyInterceptor()
        req = "USER user5423\r\n"
        assert pi._getUsername(req) == "user5423"

    def test_getUsername_correctFormat_Delimiter2(self):
        pi = FTPLoginProxyInterceptor()
        req = "USER user5423\r"
        assert pi._getUsername(req) == "user5423"

    def test_getUsername_noUserArg(self):
        pi = FTPLoginProxyInterceptor()
        req = "USER\r\n"
        with pytest.raises(Exception) as excInfo:
            pi._getUsername(req)

    def test_getUsername_multipleArgs(self):
        pi = FTPLoginProxyInterceptor()
        req = "USER user5423 user1337\r\n"
        with pytest.raises(Exception) as excInfo:
            pi._getUsername(req)

    def test_getUsername_falseStart(self):
        pi = FTPLoginProxyInterceptor()
        req = " USER user5423\r\n"
        with pytest.raises(Exception) as excInfo:
            pi._getUsername(req)


    ## Tests for _getPassword(...)
    def test_getPassword_correctFormat_Delimiter1(self):
        pi = FTPLoginProxyInterceptor()
        req = "PASS password\r\n"
        assert pi._getPassword(req) == "password"

    def test_getPassword_correctFormat_Delimiter2(self):
        pi = FTPLoginProxyInterceptor()
        req = "PASS password\r"
        assert pi._getPassword(req) == "password"

    def test_getPassword_noUserArg(self):
        pi = FTPLoginProxyInterceptor()
        req = "PASS\r\n"
        with pytest.raises(Exception) as excInfo:
            pi._getPassword(req)

    def test_getPassword_multipleArgs(self):
        pi = FTPLoginProxyInterceptor()
        req = "PASS password1 password2\r\n"
        with pytest.raises(Exception) as excInfo:
            pi._getPassword(req)

    def test_getPassword_falseStart(self):
        pi = FTPLoginProxyInterceptor()
        req = " PASS password\r\n"
        with pytest.raises(Exception) as excInfo:
            pi._getPassword(req)


    ## Tests for _getAccount(...)
    def test_getAccount_correctFormat_Delimiter1(self):
        pi = FTPLoginProxyInterceptor()
        req = "ACCT account\r\n"
        assert pi._getAccount(req) == "account"

    def test_getAccount_correctFormat_Delimiter2(self):
        pi = FTPLoginProxyInterceptor()
        req = "ACCT account\r"
        assert pi._getAccount(req) == "account"

    def test_getAccount_noUserArg(self):
        pi = FTPLoginProxyInterceptor()
        req = "ACCT\r\n"
        with pytest.raises(Exception) as excInfo:
            pi._getAccount(req)

    def test_getAccount_multipleArgs(self):
        pi = FTPLoginProxyInterceptor()
        req = "ACCT account1 account2\r\n"
        with pytest.raises(Exception) as excInfo:
            pi._getAccount(req)

    def test_getAccount_falseStart(self):
        pi = FTPLoginProxyInterceptor()
        req = " ACCT account\r\n"
        with pytest.raises(Exception) as excInfo:
            pi._getAccount(req)


    ## Testing _isUserRequest
    def test_isUserRequest_correctCommand_Delimiter1(self):
        pi = FTPLoginProxyInterceptor()
        req = "USER username\r\n"
        assert pi._isUSERRequest(req) is True
    
    def test_isUserRequest_correctCommand_Delimiter2(self):
        pi = FTPLoginProxyInterceptor()
        req = "USER username\r"
        assert pi._isUSERRequest(req) is True
    
    def test_isUserRequest_noUserArg(self):
        pi = FTPLoginProxyInterceptor()
        req = "USER\r\n"
        assert pi._isUSERRequest(req) is False

    def test_isUserRequest_multipleArgs(self):
        pi = FTPLoginProxyInterceptor()
        req = "USER user5423 user1337\r\n"
        assert pi._isUSERRequest(req) is False

    def test_isUserRequest_falseStart(self):
        pi = FTPLoginProxyInterceptor()
        req = " USER user5423\r\n"
        assert pi._isUSERRequest(req) is False

    
