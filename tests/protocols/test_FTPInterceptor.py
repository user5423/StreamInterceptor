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



## NOTE: caplog is a pytest fixture for capturing logs

class FTPProxyTestResources:
    @classmethod
    def createUnabstractedFTPInterceptor(cls):
        class TestFTPProxyInterceptor(FTPProxyInterceptor):
            def _createStateGenerator(self) -> typing.Generator:
                yield
                return

            def _executeSuccessHook(self) -> None:
                raise NotImplementedError()

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

            # def _createStateGenerator(self) -> typing.Generator:
            #     yield
            #     return

            def _executeSuccessHook(self, username: str = None, password: str = None, account: str = None) -> None:
                self.calledExecuteSuccessHook = True
                self.successUsername = username
                self.successPassword = password
                self.successAccount = account
                return

        return TestFTPLoginProxyInterceptor()
    
    ## NOTE: View RFC 959 - Page 57 for the state diagrams for the Login sequence
    @classmethod
    def _setupParseUSERtests(cls, request, response):
        messages = {}
        messages["USERrequest"] = request
        messages["USERresponse"] = response
        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        return fpi, messages

    @classmethod
    def _setupParsePASStests(cls, request, response):
        messages = {}
        username = "user5423"
        messages["USERrequest"] = f"USER {username}\r\n"
        messages["USERresponse"] = "331 Please specify the password.\r\n"
        messages["PASSrequest"] = request
        messages["PASSresponse"] = response
        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        return fpi, messages, username
    @classmethod

    def _setupParseACCTtests(cls, request, response):
        messages = {}
        username = "user5423"
        password = "password123"
        messages["USERrequest"] = f"USER {username}\r\n"
        messages["USERresponse"] = "331 Please specify the password.\r\n"
        messages["PASSrequest"] = f"PASS {password}\r\n"
        messages["PASSresponse"] = "331 Please specify the account.\r\n"
        messages["ACCTrequest"] = request
        messages["ACCTresponse"] = response
        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        return fpi, messages, username, password


    ## TODO: Generalize the below into a larger function that can test by deriving expected behavior from the control and data sequences


    ## NOTE: I'm not creating any extensive tests for logging as this should be
    ## overhauled in the future, by using field specific logging (more easy to search)
    @classmethod
    def _assertSingleExceptionLog(cls, returnType: str, command: str, request, response, caplog):
        assert len(caplog.records) == 1
        msg = list(caplog.records)[0].msg
        assert returnType in msg
        assert f"@ftp.cmds.{command}" in msg
        assert repr(request) in msg
        assert repr(response) in msg

    @classmethod
    def _assertSingleSuccessLog(cls, command: str, caplog, *args):
        assert len(caplog.records) == 1
        msg = list(caplog.records)[0].msg
        assert "SUCCESS" in msg
        assert f"@ftp.cmds.{command}" in msg
        for arg in args:
            assert arg in msg

    ## TODO: Consider modifying the below code so that it actually tests multiple messages
    @classmethod
    def _assertDoubleSuccessLog(cls, command: str, caplog, *args):
        assert len(caplog.records) == 2
        msg = list(caplog.records)[-1].msg
        assert "SUCCESS" in msg
        assert f"@ftp.cmds.{command}" in msg
        for arg in args:
            assert arg in msg

    @classmethod
    def _assertNoLogs(cls, caplog):
        assert len(caplog.records) == 0


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

    ## Tests for _getUsername(raise NotImplementedError())
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


    ## Tests for _getPassword(raise NotImplementedError())
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


    ## Tests for _getAccount(raise NotImplementedError())
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

    

class Test_FTPProxyInterceptor_Init:
    def test_init(self):
        ## We check if there is only a default initializer
        initSig = inspect.signature(FTPProxyInterceptor.__init__)
        assert len(initSig.parameters) == 1 and bool(initSig.parameters["self"])


        ## We create a subclass to test (since we need to fill in the
        ## abstract methods from the parent class)
        class subclassFTPProxyInterceptor(FTPProxyInterceptor):
            def _createStateGenerator(self) -> typing.Generator:
                yield
                return

            def _executeSuccessHook(self) -> None:
                raise NotImplementedError()

        ## We check if the proxy interceptor has a request
        ## and response queue
        fpi = subclassFTPProxyInterceptor()
        assert isinstance(fpi._requestQueue, collections.deque)
        assert len(fpi._requestQueue) == 0
        assert isinstance(fpi._responseQueue, collections.deque)
        assert len(fpi._requestQueue) == 0

        ## We 
        hookSig = inspect.signature(FTPProxyInterceptor.clientToServerRequestHook)
        assert len(hookSig.parameters) == 2
        assert "self" in hookSig.parameters
        assert "buffer" in hookSig.parameters

        hookSig = inspect.signature(FTPProxyInterceptor.serverToClientRequestHook)
        assert len(hookSig.parameters) == 2
        assert "self" in hookSig.parameters
        assert "buffer" in hookSig.parameters

        ## We check if the ftp hook exists
        msgHookSig = inspect.signature(FTPProxyInterceptor.ftpMessageHook)
        assert len(msgHookSig.parameters) == 3
        assert "self" in msgHookSig.parameters
        assert "request" in msgHookSig.parameters
        assert "response" in msgHookSig.parameters

        ## We also need to check if the ftp success hook exists
        with pytest.raises(NotImplementedError) as excInfo:
            fpi._executeSuccessHook() ## *args, **kwargs

        ## Finally, we check if the generator exists to track ftp comms
        assert isinstance(fpi._stateGenerator, typing.Generator)



class Test_FTPLoginProxyInterceptor_Helpers:
    def test_parseUSERrequest_1xx(self, caplog):
        ## "Error"
        request = "USER user5423\r\n"
        response = "150 File status okay; about to open data connection.\r\n"
        fpi, messages = FTPProxyTestResources._setupParseUSERtests(request, response)

        completeReq, username = fpi._parseUSERrequest(request, response, messages)
        assert completeReq is True
        assert username is None
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("ERROR", "USER", request, response, caplog)

    def test_parseUSERrequest_2xx(self, caplog):
        ## "Success"
        testUsername = "user5423"
        request = f"USER {testUsername}\r\n"
        response = "200 Command ok.\r\n"
        fpi, messages = FTPProxyTestResources._setupParseUSERtests(request, response)

        completeReq, username = fpi._parseUSERrequest(request, response, messages)
        assert completeReq is True
        assert username == testUsername
        assert fpi.calledExecuteSuccessHook is True
        assert fpi.successUsername == testUsername
        assert fpi.successPassword is None and fpi.successAccount is None
        FTPProxyTestResources._assertSingleSuccessLog("USER", caplog, username)

    def test_parseUSERrequest_3xx(self, caplog):
        ## "Incomplete" - waiting for more (i.e. password)
        testUsername = "user5423"
        request = f"USER {testUsername}\r\n"
        response = "331 Please specify the password.\r\n"
        fpi, messages = FTPProxyTestResources._setupParseUSERtests(request, response)

        completeReq, username = fpi._parseUSERrequest(request, response, messages)
        assert completeReq is False
        assert username == testUsername
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertNoLogs(caplog)

    def test_parseUSERrequest_4xx(self, caplog):
        ## "Failure"
        request = "USER user5423\r\n"
        response = "451 Requested action aborted: local error in processing.\r\n"
        fpi, messages = FTPProxyTestResources._setupParseUSERtests(request, response)

        completeReq, username = fpi._parseUSERrequest(request, response, messages)
        assert completeReq is True
        assert username is None
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "USER", request, response, caplog)

    def test_parseUSERrequest_5xx(self, caplog):
        ## "Failure"
        request = "USER user5423\r\n"
        response = "502 Command not implemented\r\n"
        fpi, messages = FTPProxyTestResources._setupParseUSERtests(request, response)

        completeReq, username = fpi._parseUSERrequest(request, response, messages)
        assert completeReq is True
        assert username is None
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "USER", request, response, caplog)
    
    

    def test_parsePASSrequest_1xx(self, caplog):
        ## "Error"
        request = "PASS password\r\n"
        response = "150 File status okay; about to open data connection.\r\n"
        fpi, messages, username = FTPProxyTestResources._setupParsePASStests(request, response)

        completeReq, password = fpi._parsePASSrequest(request, response, messages, username)
        assert completeReq is True
        assert password is None
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("ERROR", "PASS", request, response, caplog)

    def test_parsePASSrequest_2xx(self, caplog):
        ## "Success"
        testPassword = "password"
        request = f"PASS {testPassword}\r\n"
        response = "230 Login successful.\r\n"
        fpi, messages, username = FTPProxyTestResources._setupParsePASStests(request, response)

        completeReq, password = fpi._parsePASSrequest(request, response, messages, username)
        assert completeReq is True
        assert password == testPassword
        assert fpi.calledExecuteSuccessHook is True
        assert fpi.successUsername == username and fpi.successPassword == testPassword
        assert fpi.successAccount is None
        FTPProxyTestResources._assertSingleSuccessLog("PASS", caplog, username, testPassword)

    def test_parsePASSrequest_3xx(self, caplog):
        ## "Incomplete"
        testPassword = "password"
        request = f"PASS {testPassword}\r\n"
        response = "331 Please specify the account.\r\n"
        fpi, messages, username = FTPProxyTestResources._setupParsePASStests(request, response)

        completeReq, password = fpi._parsePASSrequest(request, response, messages, username)
        assert completeReq is False
        assert password == testPassword
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertNoLogs(caplog)

    def test_parsePASSrequest_4xx(self, caplog):
        ## "Failure"
        request = "PASS password\r\n"
        response = "451 Requested action aborted: local error in processing.\r\n"
        fpi, messages, username = FTPProxyTestResources._setupParsePASStests(request, response)

        completeReq, password = fpi._parsePASSrequest(request, response, messages, username)
        assert completeReq is True
        assert password is None
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "PASS", request, response, caplog)

    def test_parsePASSrequest_5xx(self, caplog):
        ## "Failure"
        request = "PASS password\r\n"
        response = "502 Command not implemented\r\n"
        fpi, messages, username = FTPProxyTestResources._setupParsePASStests(request, response)

        completeReq, password = fpi._parsePASSrequest(request, response, messages, username)
        assert completeReq is True
        assert password is None
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "PASS", request, response, caplog)

    def test_parseACCTrequest_1xx(self, caplog):
        ## "Error"
        request = "ACCT account\r\n"
        response = "150 File status okay; about to open data connection.\r\n"
        fpi, messages, username, password = FTPProxyTestResources._setupParseACCTtests(request, response)

        completeReq, account = fpi._parseACCTrequest(request, response, messages, username, password)
        assert completeReq is True
        assert account is None
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("ERROR", "ACCT", request, response, caplog)

    def test_parseACCTrequest_2xx(self, caplog):
        ## "Success"
        testAccount = "account"
        request = f"ACCT {testAccount}\r\n"
        response = "230 Login successful.\r\n"
        fpi, messages, username, password = FTPProxyTestResources._setupParseACCTtests(request, response)

        completeReq, account = fpi._parseACCTrequest(request, response, messages, username, password)
        assert completeReq is True
        assert account == testAccount
        assert fpi.calledExecuteSuccessHook is True
        assert fpi.successUsername == username and fpi.successPassword == password and fpi.successAccount == testAccount
        FTPProxyTestResources._assertSingleSuccessLog("ACCT", caplog, username, password, testAccount)

    def test_parseACCTrequest_3xx(self, caplog):
        ## "Error" -- Cannot have a incomplete req here (at end of login sequence!!)
        request = "ACCT account"
        response = "331 Please specify the account.\r\n" ## ERROR!!!
        fpi, messages, username, password = FTPProxyTestResources._setupParseACCTtests(request, response)

        completeReq, account = fpi._parseACCTrequest(request, response, messages, username, password)
        assert completeReq is True ## 3xx is true here (as the incomplete req is an Error)
        assert account is None
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("ERROR", "ACCT", request, response, caplog)

    def test_parseACCTrequest_4xx(self, caplog):
        ## "Failure"
        request = "ACCT account\r\n"
        response = "451 Requested action aborted: local error in processing.\r\n"
        fpi, messages, username, password = FTPProxyTestResources._setupParseACCTtests(request, response)

        completeReq, account = fpi._parseACCTrequest(request, response, messages, username, password)
        assert completeReq is True
        assert account is None
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "ACCT", request, response, caplog)

    def test_parseACCTrequest_5xx(self, caplog):
        ## "Failure"
        request = "ACCT account\r\n"
        response = "502 Command not implemented\r\n"
        fpi, messages, username, password = FTPProxyTestResources._setupParseACCTtests(request, response)

        completeReq, account = fpi._parseACCTrequest(request, response, messages, username, password)
        assert completeReq is True
        assert account is None
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "ACCT", request, response, caplog)


class Test_FTPLoginProxyInterceptor_Init:
    ## TODO: We need to create additional tests to check that this subclass
    ## is created correctly
    def test_init(self): raise NotImplementedError()

class Test_FTPLoginProxyInterceptor:
    def _simulateCommSequence(self, sequence, fpi):
        isClientSender = True
        for message in sequence:
            if isClientSender:
                fpi.ftpMessageHook(request=message)
            else:
                fpi.ftpMessageHook(response=message)
            isClientSender = not isClientSender

    def test_ftpMessageHook_USER_1xx(self, caplog):
        sequence = [
            "USER user5423\r\n",
            "150 File status okay; about to open data connection.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("ERROR", "USER", sequence[-2], sequence[-1], caplog)

    def test_ftpMessageHook_USER_2xx(self, caplog):
        username = "user5423"
        sequence = [
            f"USER {username}\r\n",
            "230 User logged in, proceed.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is True
        FTPProxyTestResources._assertSingleSuccessLog("USER", caplog, username)

    def test_ftpMessageHook_USER_3xx(self, caplog):
        sequence = [
            "USER user5423\r\n",
            "331 Please specify the password.\r\n"
        ]     

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertNoLogs(caplog)

    def test_ftpMessageHook_USER_4xx(self, caplog):
        sequence = [
            "USER user5423\r\n",
            "451 Requested action aborted: local error in processing.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "USER", sequence[-2], sequence[-1], caplog)

    def test_ftpMessageHook_USER_5xx(self, caplog):
        sequence = [
            "USER user5423\r\n",
            "502 Command not implemented\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "USER", sequence[-2], sequence[-1], caplog)

    def test_ftpMessageHook_PASS_1xx(self, caplog):
        username = "user5423"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            "PASS password\r\n",
            "150 File status okay; about to open data connection.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("ERROR", "PASS", sequence[-2], sequence[-1], caplog)

    def test_ftpMessageHook_PASS_2xx(self, caplog):
        username = "user5423"
        password = "password"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            f"PASS {password}\r\n",
            "230 Login successful.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is True
        FTPProxyTestResources._assertSingleSuccessLog("PASS", caplog, username, password)

    def test_ftpMessageHook_PASS_3xx(self, caplog):
        username = "user5423"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            "PASS password\r\n",
            "331 Please specify the account.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertNoLogs(caplog)

    def test_ftpMessageHook_PASS_4xx(self, caplog):
        username = "user5423"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            "PASS password\r\n",
            "451 Requested action aborted: local error in processing.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "PASS", sequence[-2], sequence[-1], caplog)

    def test_ftpMessageHook_PASS_5xx(self, caplog):
        username = "user5423"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            "PASS password\r\n",
            "502 Command not implemented\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "PASS", sequence[-2], sequence[-1], caplog)

    def test_ftpMessageHook_ACCT_1xx(self, caplog):
        username = "user5423"
        password = "password"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            f"PASS {password}\r\n",
            "331 Please specify the account.\r\n",
            "ACCT account\r\n",
            "150 File status okay; about to open data connection.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("ERROR", "ACCT", sequence[-2], sequence[-1], caplog)

    def test_ftpMessageHook_ACCT_2xx(self, caplog):
        username = "user5423"
        password = "password"
        account = "account"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            f"PASS {password}\r\n",
            "331 Please specify the account.\r\n",
            f"ACCT {account}\r\n",
            "230 Login successful.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is True
        FTPProxyTestResources._assertSingleSuccessLog("ACCT", caplog, username, password, account)

    def test_ftpMessageHook_ACCT_3xx(self, caplog):
        username = "user5423"
        password = "password"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            f"PASS {password}\r\n",
            "331 Please specify the account.\r\n",
            "ACCT account\r\n",
            "331 Please specify the account.\r\n" ## ERROR!!!
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("ERROR", "ACCT", sequence[-2], sequence[-1], caplog)

    def test_ftpMessageHook_ACCT_4xx(self, caplog):
        username = "user5423"
        password = "password"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            f"PASS {password}\r\n",
            "331 Please specify the account.\r\n",
            "ACCT account\r\n",
            "451 Requested action aborted: local error in processing.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "ACCT", sequence[-2], sequence[-1], caplog)

    def test_ftpMessageHook_ACCT_5xx(self, caplog):
        username = "user5423"
        password = "password"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            f"PASS {password}\r\n",
            "331 Please specify the account.\r\n",
            "ACCT account\r\n",
            "502 Command not implemented\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is False
        FTPProxyTestResources._assertSingleExceptionLog("FAILURE", "ACCT", sequence[-2], sequence[-1], caplog)

    ## NOTE: The behavior observed on vsftpd version 3.0.3 is that if you try to login into a session
    ## as the user in the current session, then you can write incorrect PASS (and likely ACCT)
    ## and the client will be in a user session (idk if it the session is restarted or maintained)


    def test_ftpMessageHook_doubleLogin_USER(self, caplog):
        username = "user5423"
        password = "password"
        account = "account"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            f"PASS {password}\r\n",
            "230 Login successful.\r\n",
            f"USER {username}\r\n",
            "230 Already logged in.\r\n"
        ]
        
        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is True
        FTPProxyTestResources._assertDoubleSuccessLog("USER", caplog, username)

    def test_ftpMessageHook_doubleLogin_PASS(self, caplog):
        username = "user5423"
        password = "password"
        secondPassword = "RANDOM_PASSWORD"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            f"PASS {password}\r\n",
            "230 Login successful.\r\n",
            f"USER {username}\r\n",
            "331 Any password will do.\r\n",
            f"PASS {secondPassword}\r\n",
            "230 Already logged in.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is True
        FTPProxyTestResources._assertDoubleSuccessLog("PASS", caplog, username, secondPassword)

    def test_ftpMessageHook_doubleLogin_ACCT(self, caplog):
        username = "user5423"
        password = "password"
        secondPassword = "RANDOM_PASSWORD"
        secondAccount = "RANDOM_ACCOUNT"
        sequence = [
            f"USER {username}\r\n",
            "331 Please specify the password.\r\n",
            f"PASS {password}\r\n",
            "230 Login successful.\r\n",
            f"USER {username}\r\n",
            "331 Any password will do.\r\n",
            f"PASS {secondPassword}\r\n",
            "331 Any account will do.\r\n",
            f"ACCT {secondAccount}\r\n",
            "230 Already logged in.\r\n"
        ]

        fpi = FTPProxyTestResources.createUnabstractedFTPLoginInterceptor()
        self._simulateCommSequence(sequence, fpi)
        assert fpi.calledExecuteSuccessHook is True
        FTPProxyTestResources._assertDoubleSuccessLog("ACCT", caplog, username, secondPassword, secondAccount)


    def test_ftpMessageHook_relogin_USER(self, caplog): 
        ## NOTE: I think that the FTP does not support a client maintaining a session 
        ## with the FTP server while logging into a different account. The only options
        ## I've found is to 'QUIT' = 'BYE' which disconnects the client's connection to
        ## server

        ## NOTE: However, it seems that there may be certain ftp server implementations
        ## that do support this out of the box or via a configurable parameters in a conf
        ## I have been unable to find such a thing for vsftpd
        return None

    def test_ftpMessageHook_relogin_PASS(self, caplog): 
        ## See comment above
        return None

    def test_ftpMessageHook_relogin_ACCT(self, caplog): 
        ## See comment above
        return None

    def test_ftpMessageHook_nonLoginCommands(self, caplog): raise NotImplementedError
    def test_clientToServerHook(self, caplog): raise NotImplementedError()
    def test_serverToProxyHook(self, caplog): raise NotImplementedError()