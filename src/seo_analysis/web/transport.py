"""Connect to an approved numeric endpoint, retaining the origin for Host, SNI and TLS."""
import ipaddress
import socket
import time

from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError


class ScopeError(ValueError):
    pass


class BudgetExceeded(RuntimeError):
    pass


class CrawlBudget:
    def __init__(self, max_requests, seconds):
        self.limit = max_requests
        self.deadline = time.monotonic() + seconds
        self.requests = 0

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise BudgetExceeded("Time budget reached.")
        return remaining

    def charge(self):
        self.remaining()
        if self.requests >= self.limit:
            raise BudgetExceeded("Request budget reached.")
        self.requests += 1


def approved_address(address, local):
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if ip.is_loopback:
        return local
    if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        return False
    if ip.is_global:
        return True
    private_ranges = ("10.0.0.0/8", "192.168.0.0/16", "172.16.0.0/12", "fc00::/7")
    return local and any(ip in ipaddress.ip_network(net) for net in private_ranges)


def scoped_adapter(origin, allow_local, budget):
    class ScopedConnection:
        def _new_conn(self):
            if self.host != origin.host or self.port != origin.port:
                raise ScopeError("Connection outside the selected origin.")
            if not allow_local and self.port not in (80, 443):
                raise ScopeError("Public crawl ports are 80 and 443.")
            endpoints = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)
            if not endpoints or not all(approved_address(item[4][0], allow_local) for item in endpoints):
                raise ScopeError("Resolved address outside the permitted network scope.")
            last_error = None
            for family, kind, protocol, _, sockaddr in endpoints:
                sock = socket.socket(family, kind, protocol)
                try:
                    sock.settimeout(min(self.timeout, budget.remaining()))
                    sock.connect(sockaddr)
                    return sock
                except OSError as exc:
                    last_error = exc
                    sock.close()
                except BaseException:
                    sock.close()
                    raise
            raise NewConnectionError(self, "Could not connect to the selected origin.") from last_error

    class ScopedHTTP(ScopedConnection, HTTPConnection):
        pass

    class ScopedHTTPS(ScopedConnection, HTTPSConnection):
        pass

    class HTTPPool(HTTPConnectionPool):
        ConnectionCls = ScopedHTTP

    class HTTPSPool(HTTPSConnectionPool):
        ConnectionCls = ScopedHTTPS

    adapter = HTTPAdapter()
    adapter.poolmanager.pool_classes_by_scheme = {"http": HTTPPool, "https": HTTPSPool}
    return adapter
