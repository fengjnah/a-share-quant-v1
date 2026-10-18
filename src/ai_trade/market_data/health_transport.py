"""Serial, temporary Requests controls for explicitly enabled health checks only."""

from contextlib import contextmanager
import math
import threading
from urllib.parse import urlsplit
import hashlib

import requests
from urllib3.util.retry import Retry


_SERIAL_CHECK = threading.Lock()


class BudgetBlocked(RuntimeError):
    """A send was blocked before the HTTP adapter could dispatch it."""


class HealthTransport:
    def __init__(self, allowed_targets: frozenset[tuple[str, str]], max_requests: int, timeout: float):
        if type(max_requests) is not int or not 1 <= max_requests <= 3:
            raise ValueError("explicit request budget must be 1..3")
        if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError("timeout must be finite and within (0,30]")
        self.allowed_targets = allowed_targets
        self.max_requests = max_requests
        self.timeout = timeout
        self.count = 0
        self.blocked = False
        self.responses: list[int] = []
        self._sent_fingerprints: set[str] = set()

    @contextmanager
    def installed(self):
        if not _SERIAL_CHECK.acquire(blocking=False):
            raise BudgetBlocked("parallel health transports are forbidden")
        original_session = requests.Session.send
        original_adapter = requests.adapters.HTTPAdapter.send

        def verified(value):
            return value is True or (isinstance(value, str) and bool(value.strip()))

        def session_send(session, request, **kwargs):
            parsed = urlsplit(request.url)
            if (request.method != "GET" or parsed.scheme != "https"
                    or parsed.port not in (None, 443) or parsed.username or parsed.password
                    or (parsed.hostname, parsed.path) not in self.allowed_targets
                    or not verified(kwargs.get("verify", True))):
                self.blocked = True
                raise BudgetBlocked("unapproved target/method or disabled TLS verification")
            kwargs["allow_redirects"] = False
            # Includes Tencent's SDK start-date requests which omit timeout.
            kwargs["timeout"] = self.timeout
            return original_session(session, request, **kwargs)

        def adapter_send(adapter, request, **kwargs):
            # Count all approved SDK HTTP sends, not merely SDK function calls.
            parsed = urlsplit(request.url)
            fingerprint = hashlib.sha256(request.url.encode("utf-8")).hexdigest()
            if (request.method != "GET" or parsed.scheme != "https"
                    or parsed.port not in (None, 443) or parsed.username or parsed.password
                    or (parsed.hostname, parsed.path) not in self.allowed_targets
                    or self.count >= self.max_requests or fingerprint in self._sent_fingerprints
                    or not verified(kwargs.get("verify", True))):
                self.blocked = True
                raise BudgetBlocked("send budget or transport policy blocked request")
            self.count += 1
            self._sent_fingerprints.add(fingerprint)
            previous_retry = adapter.max_retries
            adapter.max_retries = Retry(total=0, connect=0, read=0, redirect=0, status=0)
            try:
                response = original_adapter(adapter, request, **kwargs)
                self.responses.append(response.status_code)
                if response.status_code != 200:
                    # Do not let SDK JSON parsing hide an observed HTTP failure.
                    response.close()
                    raise requests.HTTPError("health HTTP status rejected", response=response)
                return response
            finally:
                adapter.max_retries = previous_retry

        requests.Session.send = session_send
        requests.adapters.HTTPAdapter.send = adapter_send
        try:
            yield self
        finally:
            requests.Session.send = original_session
            requests.adapters.HTTPAdapter.send = original_adapter
            _SERIAL_CHECK.release()
