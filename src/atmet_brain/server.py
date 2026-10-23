"""A bounded local HTTP adapter. Production ingress is an explicit deployment concern."""

from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from urllib.parse import urlparse

from ._version import __version__
from .errors import BrainError, require
from .rpc import AUTH_METHODS, dispatch, dispatch_auth, openapi
from .util import dumps


def make_server(brain, host="127.0.0.1", port=7310, allow_network=False):
    require(host in {"127.0.0.1", "localhost"} or allow_network,
            "network_binding", "Non-loopback binding requires --allow-network and a private trusted ingress.")
    arrivals, rate_lock = defaultdict(deque), threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "AtmetBrain/" + __version__
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def log_message(self, format, *args):
            # No request bodies, query strings, tokens or business text in logs.
            return

        def respond(self, status, body):
            encoded = dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(encoded)

        def guard(self):
            require(not self.headers.get("Origin"), "origin_denied", "Browser-origin requests are not supported by this local adapter.", 403)
            hostname = self.headers.get("Host", "").split(":")[0].lower()
            require(allow_network or hostname in {"127.0.0.1", "localhost"}, "host_denied", "Unrecognized local host.", 403)
            with rate_lock:
                records = arrivals[self.client_address[0]]
                cutoff = time.monotonic() - 60
                while records and records[0] < cutoff:
                    records.popleft()
                require(len(records) < 120, "rate_limited", "Local request limit reached.", 429)
                records.append(time.monotonic())

        def actor(self):
            header = self.headers.get("Authorization", "")
            require(header.startswith("Bearer ") and len(self.headers.get_all("Authorization", [])) == 1,
                    "unauthenticated", "Use a bearer credential.", 401)
            return brain.authenticate(header[7:])

        def payload(self, maximum=1_000_000):
            require(not self.headers.get("Transfer-Encoding") and len(self.headers.get_all("Content-Length", [])) == 1,
                    "invalid_body", "Use one Content-Length header.")
            length = int(self.headers.get("Content-Length", "0"))
            require(0 < length <= maximum, "invalid_body", "Request body exceeds the endpoint limit.", 413)
            require(self.headers.get_content_type() == "application/json", "invalid_body", "Use application/json.", 415)
            return json.loads(self.rfile.read(length), parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))

        def run_request(self):
            try:
                self.guard()
                path = urlparse(self.path).path
                if self.command == "GET" and path == "/health":
                    self.respond(200, {"status": "ok", "engine": "atmet-brain", "version": __version__})
                    return
                if self.command == "GET" and path == "/openapi.json":
                    self.respond(200, openapi(brain))
                    return
                if self.command == "POST" and path.startswith("/v1/auth/"):
                    action = path.removeprefix("/v1/auth/")
                    require(action in AUTH_METHODS, "not_found", "Sign-in endpoint not found.", 404)
                    self.respond(200, {"result": dispatch_auth(brain, action, self.payload(16384))})
                    return
                actor = self.actor()
                if self.command == "GET" and path == "/v1/me":
                    self.respond(200, {"result": brain.whoami(actor)})
                    return
                require(self.command == "POST" and path == "/v1/rpc", "not_found", "Endpoint not found.", 404)
                payload = self.payload()
                require(isinstance(payload, dict) and set(payload) <= {"method", "params"}, "invalid_body", "Invalid RPC request.")
                result = dispatch(brain, actor, payload.get("method"), payload.get("params"))
                self.respond(200, {"result": result})
            except BrainError as error:
                self.respond(error.status, {"error": error.as_dict()})
            except (ValueError, UnicodeError, RecursionError):
                self.respond(400, {"error": {"code": "invalid_body", "message": "Invalid JSON or request framing."}})
            except Exception:
                self.respond(500, {"error": {"code": "internal_error", "message": "The operation could not be completed."}})

        do_GET = run_request
        do_POST = run_request

    return ThreadingHTTPServer((host, port), Handler)
