"""Small remote client with no implicit identity or privilege headers."""

import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPSHandler, ProxyHandler

from .errors import BrainError, require
from .extraction import NoRedirect
from .feedback import TaskClientMixin
from .util import dumps


class Client(TaskClientMixin):
    def __init__(self, endpoint, token, ca_file=None):
        require(isinstance(endpoint, str) and not any(ord(c) < 33 for c in endpoint),
                "invalid_endpoint", "Use a valid HTTPS endpoint or loopback HTTP URL.")
        parsed = urlparse(endpoint)
        require(parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}),
                "insecure_endpoint", "Use HTTPS or loopback HTTP.")
        require(parsed.hostname and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                and parsed.path in {"", "/"}, "invalid_endpoint", "Use a root endpoint without credentials, path or query parameters.")
        try:
            parsed.port
        except ValueError:
            raise BrainError("invalid_endpoint", "Invalid endpoint port.") from None
        require(isinstance(token, str) and 20 <= len(token) <= 300 and all(32 < ord(c) < 127 for c in token),
                "invalid_credential", "Use a current Brain credential file.")
        self.endpoint, self.token = endpoint.rstrip("/"), token
        self.opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)))

    def call(self, method, **params):
        return self._request("/v1/rpc", {"method": method, "params": params}, True)

    def auth(self, action, **params):
        require(action in {"login", "accept"}, "invalid_auth", "Choose login or accept.")
        return self._request("/v1/auth/" + action, params, False)

    def _request(self, path, body, authenticated):
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(self.endpoint + path, dumps(body).encode(), headers)
        try:
            with self.opener.open(request, timeout=60) as response:
                data = response.read(4_000_001)
                require(len(data) <= 4_000_000, "invalid_response", "Brain response exceeds the client limit.")
                result = json.loads(data)
            return result["result"]
        except HTTPError as error:
            try:
                value = json.loads(error.read(100_000))["error"]
                raise BrainError(value["code"], value["message"], error.code) from None
            except (ValueError, KeyError, TypeError):
                raise BrainError("http_error", "Brain HTTP request failed.", error.code) from None
        except (URLError, TimeoutError, OSError):
            raise BrainError("connection_failed", "Cannot reach the Brain. Check the address, certificate and private connection.", 503) from None
        except (ValueError, KeyError, TypeError):
            raise BrainError("invalid_response", "The server returned an invalid Brain response.", 502) from None
