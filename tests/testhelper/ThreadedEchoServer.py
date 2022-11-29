import threading
import socket
import selectors

class EchoServer:
    def __init__(self, HOST: str, PORT: int) -> None:
        self._threads = []
        self._threadExit = []
        self._threadLock = threading.Lock()

        self._exitFlag = False
        self._mainThread = threading.Thread(target=self._run, args=(HOST, PORT,))
        self._selector = selectors.DefaultSelector()
        self._counterEvent = threading.Event()
        self._counterLock = threading.Lock()
        self._counterTarget = 0
        self._counterCurrent = 0

    def _run(self, HOST: str, PORT: int) -> None:
        # print(f"Starting Echo Server @ {HOST}:{PORT}")
        with socket.socket() as serverSock:
            try:
                serverSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                serverSock.setblocking(False)
                serverSock.bind((HOST, PORT))
                serverSock.listen()
            except Exception as e:
                print(f"EchoServer server Exception: {e}")
                raise e
            print(f"Running Echo Server @ {HOST}:{PORT}")

            try:
                while self._exitFlag is False:
                    try:
                        conn, addr = serverSock.accept()
                    except BlockingIOError:
                        continue

                    self._instantiateNewThread(conn)
                    self._updateCounterEvent(1)
            except Exception as e:
                print(f"EchoServer exception: {e}")
                raise e

    def _serviceConnection(self, conn: socket.socket, index: int) -> None:
        with conn:
            try:
                conn.setblocking(False)
                while self._exitFlag is False and self._threadExit[index] is False:
                    try:
                        data = conn.recv(1024)
                    except OSError:
                        continue
                    if not data:
                        break
                    conn.sendall(data)
                    # print(f"Echoed data: {data}")
            except Exception as e:
                print(f"EchoServer - Exception raised when servicing echo connection: {conn} - {e}")
                raise e
            finally:
                self._updateCounterEvent(-1)

    def run(self) -> None:
        return self._mainThread.start()

    def close(self) -> None:
        ## set exitFlag to exit eventLoop in self._run
        self._exitFlag = True
        ## close mainThread
        self._mainThread.join()
        ## close connection threads
        with self._threadLock:
            for thread in self._threads:
                # print("EchoServer - Closing child thread")
                ## socket closing are handled by context managers
                thread.join()

    def _updateCounterEvent(self, val: int) -> None:
        with self._counterLock:
            self._counterCurrent += val
            # print(f"current counter: {self._counterCurrent}")
            if self._counterCurrent == self._counterTarget:
                self._counterEvent.set()

    def _instantiateNewThread(self, conn: socket.socket) -> None:
        with self._threadLock:
            with self._counterLock:
                connThread = threading.Thread(target=self._serviceConnection, args=(conn, self._counterCurrent))
            self._threads.append(connThread)
            self._threadExit.append(False)
        
        connThread.start()

    def awaitConnectionCount(self, count: int) -> None:
        with self._counterLock:
            self._counterTarget = count
            if self._counterCurrent == self._counterTarget:
                self._counterEvent.set()
        
        self._counterEvent.wait()
        self._counterEvent.clear()

