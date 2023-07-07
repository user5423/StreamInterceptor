import os
import sys
import socket
import collections
from typing import Tuple, List

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import ProxyTunnel, StreamInterceptor
from _proxyDS import Buffer
## TODO: At some point in the future we want to 
## perform UDP and TCP tests

## TODO: Add resources for UDP and TCP connections
## Consider testing for UDP and TCP on proxyTunnel
class PTTestResources:

    @staticmethod
    def createMockStreamInterceptor():
        clientToServerDeque = collections.deque([])
        serverToClientDeque = collections.deque([])
        
        class mockStreamInterceptor(StreamInterceptor):
            MESSAGE_DELIMITERS = [b"\r\n"]

            class ClientToServerHook(StreamInterceptor.Hook):
                def __call__(self, message: bytes) -> None:
                    nonlocal clientToServerDeque
                    clientToServerDeque.append(message)

            class ServerToClientHook(StreamInterceptor.Hook):
                def __call__(self, message: bytes) -> None:
                    nonlocal serverToClientDeque
                    serverToClientDeque.append(message)

        return mockStreamInterceptor, (clientToServerDeque, serverToClientDeque)

    @staticmethod
    def createClientSocket() -> socket.socket:
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.setblocking(True)
        return clientSocket

    @staticmethod
    def createServerSocket() -> socket.socket:
        ## TODO: We need a method of setting up ephemeral server sockets
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ## NOTE: socket.bind(("",0)) passes response of PORT selection on localhost
        ## for binding to the host operating system
        serverSocket.setblocking(True)
        serverSocket.bind(("", 0))
        serverSocket.listen()
        return serverSocket

    @staticmethod
    def acceptConnection(serverSocket: socket.socket) -> socket.socket:
        clientToProxySocket, (hostname, port) = serverSocket.accept()
        return clientToProxySocket

    @staticmethod
    def closeSocket(s: socket) -> None:
        s.close()


    @staticmethod
    def connect(client: socket.socket, server: socket.socket) -> socket.socket:
        serverHost, serverPort = server.getsockname()
        client.connect((serverHost, serverPort))
        ephemeralSocket, _ = server.accept()
        return ephemeralSocket

    @staticmethod
    def _setupPT() -> Tuple[ProxyTunnel, List[socket.socket]]:
        ## Setup Client <--> Proxy connection
        proxyServerSocket = PTTestResources.createServerSocket()
        clientSocket = PTTestResources.createClientSocket()
        ephemeralProxyServerSocket = PTTestResources.connect(clientSocket, proxyServerSocket)

        ## Setup Proxy <--> Server connection
        serverSocket = PTTestResources.createServerSocket()
        proxyClientSocket = PTTestResources.createClientSocket()
        ephemeralServerSocket = PTTestResources.connect(proxyClientSocket, serverSocket)

        ## Rename the sockets
        clientToProxySocket = ephemeralProxyServerSocket
        proxyToServerSocket = proxyClientSocket

        ## Create ProxyTunnel
        streamInterceptor, interceptorDeques = PTTestResources.createMockStreamInterceptor()
        pt = ProxyTunnel(clientToProxySocket, proxyToServerSocket, streamInterceptor)
        hopList = [clientSocket, clientToProxySocket, proxyToServerSocket, ephemeralServerSocket]
        return pt, hopList, interceptorDeques

    @staticmethod
    def _closePT(socketList: List[socket.socket]) -> None:
        for sock in socketList:
            sock.close()

