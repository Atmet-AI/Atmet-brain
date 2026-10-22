"""Small remote client with no implicit identity or privilege headers."""

import json
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from .errors import BrainError, require
from .extraction import NoRedirect
from .util import dumps


class Client:
    def __init__(self, endpoint, token):
        parsed = urlparse(endpoint)
        require(parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}),
                "insecure_endpoint", "Use HTTPS or loopback HTTP.")
        require(not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,
                "invalid_endpoint", "Use an endpoint without credentials or query parameters.")
        self.endpoint, self.token = endpoint.rstrip("/"), token

    def call(self, method, **params):
        request = Request(self.endpoint + "/v1/rpc", dumps({"method": method, "params": params}).encode(),
                          {"Content-Type": "application/json", "Authorization": "Bearer " + self.token})
        try:
            with build_opener(NoRedirect()).open(request, timeout=60) as response:
                result = json.loads(response.read(4_000_000))
            return result["result"]
        except HTTPError as error:
            try:
                value = json.loads(error.read(100_000))["error"]
                raise BrainError(value["code"], value["message"], error.code) from None
            except (ValueError, KeyError):
                raise BrainError("http_error", "Brain HTTP request failed.", error.code) from None
