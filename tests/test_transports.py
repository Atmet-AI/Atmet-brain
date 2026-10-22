import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from atmet_brain import Brain, BrainError
from atmet_brain.auth import ROLES
from atmet_brain.client import Client
from atmet_brain.mcp import MCPServer
from atmet_brain.rpc import openapi
from atmet_brain.server import make_server


class TransportCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brain = Brain(Path(self.tmp.name) / "home")
        self.owner = self.brain.bootstrap("example")
        self.actor = self.brain.authenticate(self.owner["token"])
        self.space = self.brain.create_space(self.actor, "sales")["id"]
        principal = self.brain.create_principal(self.actor, "Reader")
        self.brain.grant(self.actor, principal["id"], self.space, ROLES["reader"])
        self.reader_key = self.brain.create_credential(self.actor, principal["id"])

    def server(self):
        server = make_server(self.brain, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def close():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.addCleanup(close)
        return "http://127.0.0.1:" + str(server.server_port)

    def test_http_python_and_mcp_return_same_allowed_evidence(self):
        self.brain.put_source(self.actor, self.space, "request", "Request", "Customer requests three products.")
        actor = self.brain.authenticate(self.reader_key["token"])
        local = self.brain.search(actor, self.space, "products")
        remote = Client(self.server(), self.reader_key["token"]).call("search", space_id=self.space, query="products")
        mcp = MCPServer(self.brain, self.reader_key["token"])
        mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        result = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "brain_search", "arguments": {"space_id": self.space, "query": "products"}}})
        self.assertEqual(local, remote)
        self.assertEqual(local, json.loads(result["result"]["content"][0]["text"]))

    def test_http_rejects_missing_credentials_and_origin(self):
        endpoint = self.server()
        with self.assertRaises(HTTPError) as result:
            urlopen(endpoint + "/v1/me")
        self.assertEqual(401, result.exception.code)
        with self.assertRaises(HTTPError) as result:
            urlopen(Request(endpoint + "/health", headers={"Origin": "https://untrusted.example"}))
        self.assertEqual(403, result.exception.code)

    def test_http_ignores_forged_identity_headers_and_rejects_body_identity(self):
        endpoint = self.server()
        data = json.dumps({"method": "sources.put", "params": {"space_id": self.space, "external_id": "attempt", "title": "Attempt", "content": "x"}}).encode()
        request = Request(endpoint + "/v1/rpc", data, {"Content-Type": "application/json", "Authorization": "Bearer " + self.reader_key["token"], "X-User-Role": "owner"})
        with self.assertRaises(HTTPError) as result:
            urlopen(request)
        self.assertEqual(403, result.exception.code)
        client = Client(endpoint, self.reader_key["token"])
        with self.assertRaises(BrainError) as result:
            client.call("search", space_id=self.space, query="x", actor="owner")
        self.assertEqual("invalid_params", result.exception.code)

    def test_http_does_not_expose_operator_methods(self):
        client = Client(self.server(), self.owner["token"])
        for method in ["bootstrap", "create_backup", "restore_backup", "register_connector"]:
            with self.assertRaises(BrainError) as result:
                client.call(method)
            self.assertEqual("unknown_method", result.exception.code)

    def test_mcp_notifications_do_not_produce_stdout(self):
        mcp = MCPServer(self.brain, self.reader_key["token"])
        lines = [json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                 json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                 json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})]
        output = io.StringIO()
        mcp.serve(io.StringIO("\n".join(lines) + "\n"), output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([1, 2], [r["id"] for r in responses])
        self.assertTrue(all(tool["annotations"]["readOnlyHint"] for tool in responses[1]["result"]["tools"]))

    def test_mcp_revocation_is_checked_after_initialize(self):
        mcp = MCPServer(self.brain, self.reader_key["token"])
        mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.brain.revoke_credential(self.actor, self.reader_key["credential_id"])
        response = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(-32001, response["error"]["code"])

    def test_mcp_writes_are_disabled_by_default(self):
        mcp = MCPServer(self.brain, self.owner["token"])
        mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        response = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "brain_propose_memory", "arguments": {}}})
        self.assertEqual(-32602, response["error"]["code"])

    def test_openapi_enumerates_the_real_public_operations(self):
        schema = openapi(self.brain)
        options = schema["paths"]["/v1/rpc"]["post"]["requestBody"]["content"]["application/json"]["schema"]["oneOf"]
        methods = {o["properties"]["method"]["const"] for o in options}
        self.assertIn("context.get", methods)
        self.assertNotIn("bootstrap", methods)

    def test_cli_init_and_stdio_are_real_subprocesses(self):
        home = Path(self.tmp.name) / "cli"
        command = [sys.executable, "-m", "atmet_brain", "--home", str(home)]
        initialized = subprocess.run(command + ["init", "--organization", "cli-example"], capture_output=True, text=True, check=True)
        result = json.loads(initialized.stdout)
        self.assertTrue(Path(result["token_file"]).exists())
        self.assertNotIn("\"token\"", initialized.stdout)
        messages = '\n'.join([json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
                                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})]) + '\n'
        server = subprocess.run(command + ["mcp"], input=messages, capture_output=True, text=True, check=True)
        self.assertEqual(2, len([json.loads(line) for line in server.stdout.splitlines()]))
