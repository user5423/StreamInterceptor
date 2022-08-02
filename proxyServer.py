import socket
import socketserver
from typing import NamedTuple

##TODO: Accomodate large post requestse that are greater than 1024 bytes

class proxyHandler(socketserver.BaseRequestHandler):
    def setup(self) -> None:
        ## We create a new connection with the http server on the local machine
        self._setupConnToProxy()

        ## We then need to setup a streamer ontop of it

    def _setupConnToProxy(self) -> None:
        self.proxyConn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.proxyConn.settimeout(5)
        self.proxyConn.connect(("127.0.0.1", 80))


    def handle(self) -> None:
        ...

    def finish(self) -> None:
        self.proxyConn.close()


proxyHandlerDescriptor = NamedTuple("ProxyHandlerData", [("PROXY_HOST", str), ("PROXY_PORT", int), ("StreamInterceptor", object)])

class proxyServer(socketserver.ThreadingTCPServer):
    def __init__(self, HOST: str, PORT: int, PROXY_HOST: str, PROXY_PORT: int, streamInterceptor: object) -> None:
        self._proxyHandlerDescriptor = proxyHandlerDescriptor(PROXY_HOST, PROXY_PORT, streamInterceptor)
        socketserver.ThreadingTCPServer((HOST, PORT), proxyHandler)


def main():
    HOST, PORT = "127.0.0.1", 9999
    PROXY_HOST, PROXY_PORT = "127.0.0.1", 80
    streamInterceptor = None
    with proxyServer(HOST, PORT, PROXY_HOST, PROXY_PORT, streamInterceptor) as s:
        s.serve_forever()


if __name__ == "__main__":
    main()