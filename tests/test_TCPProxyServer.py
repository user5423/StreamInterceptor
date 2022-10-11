import os
import sys
import pytest

sys.path.insert(0, os.path.join("..", "src"))
sys.path.insert(0, "src")
from tcp_proxyserver import TCPProxyServer
from _exceptions import *



class Test_ProxyServer_Init:
    pass


class Test_ProxyServer_connectionSetup:
    pass


class Test_ProxyServer_connectionHandling:
    pass


class Test_ProxyServer_connectionTeardown:
    pass


class Test_ProxyServer_shutdown:
    pass
