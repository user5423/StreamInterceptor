import os
import signal
import sys
import re
import subprocess
import socket
import selectors
import threading

sys.path.insert(0, os.path.join("src"))
sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, os.path.join("..", "..", "src"))

import pytest
from typing import Tuple, List, Optional

from tests.testhelper.TestResources import TPSTestResources
from tcp_proxyserver import ProxyConnections, TCPProxyServer, SharedStreamInterceptorRegister
from ftp_proxyserver import FTPProxyServer
from ftp_proxyinterceptor import FTPLoginProxyInterceptor, FTPDataConnectionHandler, FTPInterceptorHelperMixin

## TODO: Pull net interface out of a constant and into an env variable
testedNetInterf = "wlp0s20f3"

## TODO: Refactor with DataTransferSimulator class in testhelper
class FTPTestClient:
    def __init__(self, HOST: str, PORT: int) -> None:
        self.HOST = HOST
        self.PORT = PORT


    def connectToFTPProxy(self) -> socket.socket:
        clientSock = socket.socket()
        clientSock.connect((self.HOST, self.PORT))
        return clientSock


    def _setupPasvConnection(self, pasvMessage):
        captureGroups = re.search(b"227 [\w+\s]+ \((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\).\r\n", pasvMessage).groups()
        hostname = b".".join(captureGroups[:4]).decode()
        port = int(captureGroups[4]) * 256 + int(captureGroups[5])
        s = socket.socket()
        s.connect((hostname, port))
        return s


    def _setupActiveSocketListener(self, activeMessage: bytes) -> socket.socket:
        captureGroups = re.search(b"PORT (\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\r\n", activeMessage).groups()
        hostname = b".".join(captureGroups[:4]).decode()
        port = int(captureGroups[4]) * 256 + int(captureGroups[5])
        ephemeralSock = socket.socket()
        # print(f"Binding to ({hostname}, {port})")
        ephemeralSock.bind((hostname, port))
        ephemeralSock.listen()
        return ephemeralSock


    def _recvControlStream(self, clientSock: socket.socket, buffer: bytes) -> bool:
        while True:
            recv = clientSock.recv(1024)
            buffer += recv
            if len(recv) == 0:
                return b"", False
            if b"\r\n" in buffer:
                x, buffer = buffer.split(b"\r\n", 1)
                message = x + b"\r\n"
                return message, True


    def _extractDataConnSocketData(self, clientSock: socket.socket, timeout: Optional[float] = 0.10) -> None:
        clientSock.setblocking(True)
        clientSock.settimeout(timeout)
        data = b""
        error = None
        while True:
            try:
                recv = clientSock.recv(1024)
            except socket.error as e:
                return b"", e

            if len(recv) == 0:
                break
            data += recv
        return data, error


    ## TODO: Replace 'messages' with 'replies' to provide a more accurate description
    def simulateFTPSequence(self, sequence: List[bytes]) -> Tuple[List[bytes], List[bytes]]:
        # breakpoint()
        controlMessages = []
        dataMessages = []
        controlBuffer = bytes()
        ## NOTE: There is no dataBuffer because multiple command data outputs are not shared
        ## on a single connection (unlike the control conn which does this)
        clientControlSock = self.connectToFTPProxy()
        clientDataSocks = []
        clientDataSocksCounter = 0
        
        message, connectionAlive = self._recvControlStream(clientControlSock, controlBuffer)
        if connectionAlive is False:
            controlMessages.append((message, None))

        for msg in sequence:
            # print(f"handling msg: {msg}")
            if re.search(b"^PORT", msg):
                listener = self._setupActiveSocketListener(msg)
                # print("setup data sock (PORT)")
                clientControlSock.sendall(msg)
                # print("sent connection open msg (PORT)")
                clientDataSocks.append((listener, "PORT"))
                message, connectionAlive = self._recvControlStream(clientControlSock, controlBuffer)
                controlMessages.append(message)
                if connectionAlive is False:
                    break
                # print("received control message")
            elif re.search(b"^PASV", msg):
                clientControlSock.sendall(msg)
                message, connectionAlive = self._recvControlStream(clientControlSock, controlBuffer)
                controlMessages.append(message)
                if connectionAlive is False:
                    break
                resp = controlMessages[-1]
                clientDataSocks.append((self._setupPasvConnection(resp), "PASV"))
            else:
                clientControlSock.sendall(msg)
                command = msg.split(b" ")[0]
                # print(f"command: {command}")
                if command in FTPInterceptorHelperMixin._dataTransferCommands:
                    if clientDataSocksCounter < len(clientDataSocks):
                        listener, connType = clientDataSocks[clientDataSocksCounter]
                        if connType == "PORT":
                            clientDataSock = listener.accept()[0]
                            clientDataSocks[clientDataSocksCounter] = clientDataSock
                            listener.close()
                        ## we are not evaluating clientDataSock currently, so we can ignore it for PASV
                    ## if we do not have sufficient sockets, then we allow the client to fail in its comms with the ftp server
                    clientDataSocksCounter = min(clientDataSocksCounter+1, len(clientDataSocks))

                message, connectionAlive = self._recvControlStream(clientControlSock, controlBuffer)
                controlMessages.append(message)
                if connectionAlive is False:
                    break
                # print("received connection (PORT)")

        ## We try to capture any remaining data if it exists on the control connection
        try:
            clientControlSock.settimeout(1.0)
            message, connectionAlive = self._recvControlStream(clientControlSock, controlBuffer)
            if len(message) > 0:
                controlMessages.append(message)
        except socket.error:
            pass

        ## NOTE: We don't know how many messages after establishing a connection port, will the user send a command that uses the data conn
        ## -- Therefore, it is easier to maintain a sequence of data conn and then receive them at the end
        for clientDataSock, _ in clientDataSocks:
            dataMessages.append(self._extractDataConnSocketData(clientDataSock))

        return controlMessages, dataMessages
