import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import ipaddress
import json
import os
from pathlib import Path
import plistlib
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from atmet_brain import Brain, BrainError
from atmet_brain.cli import execute, parser
from atmet_brain.client import Client
from atmet_brain.connections import connect, load_connection, remove_connection
from atmet_brain.mcp import MCPServer
from atmet_brain.server import make_server
from atmet_brain.services import manage_service, service_spec
from atmet_brain.terminal import Console, clean


class TerminalTeamCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "server"
        self.brain = Brain(self.home)
        self.owner = self.brain.bootstrap("company")
        (self.home / "owner.token").write_text(self.owner["token"])
        self.actor = self.brain.authenticate(self.owner["token"])
        self.sales = self.brain.create_space(self.actor, "sales")["id"]
        self.finance = self.brain.create_space(self.actor, "finance")["id"]

    def cli(self, home, *args, input=None):
        env = {key: value for key, value in os.environ.items() if key not in {"ATMET_TOKEN", "ATMET_TOKEN_FILE", "ATMET_HOME"}}
        return subprocess.run([sys.executable, "-m", "atmet_brain", "--home", str(home), *args],
                              input=input, capture_output=True, text=True, env=env, timeout=20)

    def server(self, tls=False):
        server = make_server(self.brain, port=0)
        if tls:
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Atmet test")])
            cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
                    .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
                    .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
                    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                    .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
                    .sign(key, hashes.SHA256()))
            certificate, secret = self.root / "ca.pem", self.root / "test.key"
            certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            secret.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                serialization.NoEncryption()))
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certificate, secret)
            server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def close():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.addCleanup(close)
        return ("https" if tls else "http") + "://127.0.0.1:" + str(server.server_port)

    def member(self, role="reader"):
        return self.brain.add_team_member(self.actor, "Sales reader", [self.sales], role)

    def test_welcome_and_status_do_not_create_a_database(self):
        home = self.root / "empty"
        result = self.cli(home)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(json.loads(result.stdout)["initialized"])
        self.assertEqual("not_initialized", json.loads(self.cli(home, "status").stdout)["state"])
        self.assertFalse(home.exists())

    def test_setup_creates_explicit_spaces_and_rejects_reinitialization(self):
        home = self.root / "new"
        result = self.cli(home, "setup", "--mode", "team", "--organization", "new-company", "--spaces", "shared,sales")
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(["shared", "sales"], [s["slug"] for s in data["spaces"]])
        self.assertNotIn(self.owner["token"], result.stdout)
        self.assertNotIn("token", data)
        self.assertEqual(0o600, Path(data["token_file"]).stat().st_mode & 0o777)
        repeated = self.cli(home, "setup", "--mode", "local", "--organization", "other")
        self.assertEqual(1, repeated.returncode)
        self.assertEqual("already_initialized", json.loads(repeated.stderr)["error"]["code"])

    def test_bad_or_missing_setup_answers_leave_no_state(self):
        for arguments in [[], ["--mode", "local"], ["--mode", "local", "--organization", "okay", "--spaces", "sales,sales"]]:
            home = self.root / "no-write"
            result = self.cli(home, "setup", *arguments)
            self.assertEqual(1, result.returncode)
            self.assertFalse((home / "brain.sqlite3").exists())

    def test_interactive_wizard_asks_then_initializes(self):
        args = parser().parse_args(["--home", str(self.root / "interactive"), "setup"])
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["local", "example", "Owner", "shared,sales"]), contextlib.redirect_stderr(io.StringIO()):
            result = execute(args)
        self.assertEqual(2, len(result["spaces"]))

    def test_terminal_removes_escape_sequences_and_honors_plain(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"NO_COLOR": "1"}), patch.object(output, "isatty", return_value=True):
            console = Console(output)
            console.banner()
            console.result({"name": "unsafe\x1b[2J\x07"})
        self.assertNotIn("\x1b", output.getvalue())
        self.assertNotIn("\x07", clean("x\x07"))

    def test_team_provision_is_scoped_expiring_and_denies_finance(self):
        member = self.member()
        actor = self.brain.authenticate(member["token"])
        self.assertEqual([self.sales], [s["id"] for s in self.brain.list_spaces(actor)])
        self.assertGreater(member["expires_at"], datetime.now(timezone.utc).timestamp())
        with self.assertRaises(BrainError):
            self.brain.search(actor, self.finance, "private")
        with self.assertRaises(BrainError):
            self.brain.add_team_member(actor, "Another", [self.sales])

    def test_invalid_team_request_is_atomic(self):
        with self.brain.store.transaction() as conn:
            before = conn.execute("SELECT COUNT(*) FROM principals").fetchone()[0]
        for role, spaces in [("owner", [self.sales]), ("reader", [self.sales, self.finance + "-missing"])]:
            with self.assertRaises(BrainError):
                self.brain.add_team_member(self.actor, "Nobody", spaces, role)
        with self.brain.store.transaction() as conn:
            self.assertEqual(before, conn.execute("SELECT COUNT(*) FROM principals").fetchone()[0])

    def test_connection_and_cli_remote_access_do_not_create_local_brain(self):
        endpoint = self.server()
        member = self.member()
        token_file = self.root / "reader.token"
        token_file.write_text(member["token"])
        home = self.root / "client"
        result = self.cli(home, "connect", "company", "--endpoint", endpoint, "--token-file", str(token_file))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn(member["token"], result.stdout)
        listed = self.cli(home, "--connection", "company", "space")
        self.assertEqual([self.sales], [s["id"] for s in json.loads(listed.stdout)])
        self.assertFalse((home / "brain.sqlite3").exists())
        denied = self.cli(home, "--connection", "company", "search", "private", "--space", self.finance)
        self.assertEqual(1, denied.returncode)
        self.assertNotIn(member["token"], denied.stderr)
        self.brain.revoke_credential(self.actor, member["credential_id"])
        self.assertEqual(1, self.cli(home, "--connection", "company", "space").returncode)

    def test_failed_connect_does_not_save_and_unsafe_urls_are_rejected(self):
        token_file = self.root / "reader.token"
        token_file.write_text(self.owner["token"])
        for endpoint in ["http://192.168.1.5:7310", "https://user:pass@example.com", "https://example.com/?token=x", "https://example.com/path", "https://example.com:bad", "https://example.com\n"]:
            with self.assertRaises(BrainError):
                connect(self.root / "failed", "company", endpoint, token_file)
        self.assertFalse((self.root / "failed").exists())

    def test_https_requires_trusted_ca_and_validates_hostname(self):
        endpoint = self.server(tls=True)
        with self.assertRaises(BrainError) as error:
            Client(endpoint, self.owner["token"]).call("identity.me")
        self.assertEqual("connection_failed", error.exception.code)
        client = Client(endpoint, self.owner["token"], self.root / "ca.pem")
        self.assertEqual(self.actor.principal_id, client.call("identity.me")["principal_id"])
        with self.assertRaises(BrainError):
            Client(endpoint.replace("127.0.0.1", "localhost"), self.owner["token"], self.root / "ca.pem").call("identity.me")

    def test_remote_operator_commands_never_fall_back(self):
        home = self.root / "client"
        key = self.root / "owner.token"
        key.write_text(self.owner["token"])
        result = self.cli(home, "--endpoint", self.server(), "--token-file", str(key), "doctor")
        self.assertEqual("local_only", json.loads(result.stderr)["error"]["code"])
        self.assertFalse(home.exists())

    def test_remote_ingest_context_and_team_cli(self):
        endpoint = self.server()
        source = self.root / "facts.md"
        source.write_text("Fact[delivery]: Delivery takes five days.")
        options = ["--endpoint", endpoint, "--token-file", str(self.home / "owner.token")]
        result = self.cli(self.root / "client", *options, "ingest", str(source), "--space", self.sales)
        self.assertEqual(0, result.returncode, result.stderr)
        self.brain.run_jobs(self.actor, self.sales)
        context = self.cli(self.root / "client", *options, "context", "delivery", "--space", self.sales)
        self.assertEqual(0, context.returncode, context.stderr)
        output = self.root / "team.token"
        result = self.cli(self.root / "client", *options, "team-add", "Employee", "--space", self.sales, "--output", str(output))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0o600, output.stat().st_mode & 0o777)
        self.assertNotIn(output.read_text().strip(), result.stdout)
        with self.brain.store.transaction() as conn:
            before = conn.execute("SELECT COUNT(*) FROM principals").fetchone()[0]
        self.assertEqual(1, self.cli(self.root / "client", *options, "team-add", "Duplicate", "--space", self.sales, "--output", str(output)).returncode)
        with self.brain.store.transaction() as conn:
            self.assertEqual(before, conn.execute("SELECT COUNT(*) FROM principals").fetchone()[0])

    def test_remote_mcp_subprocess_keeps_protocol_clean_and_scope_current(self):
        key = self.root / "reader.token"
        member = self.member()
        key.write_text(member["token"])
        endpoint = self.server()
        messages = '\n'.join(json.dumps(r) for r in [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "brain_search", "arguments": {"space_id": self.finance, "query": "x"}}},
        ]) + '\n'
        result = self.cli(self.root / "client", "--endpoint", endpoint, "--token-file", str(key), "mcp", input=messages)
        self.assertEqual(0, result.returncode, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([1, 2, 3], [r["id"] for r in responses])
        self.assertTrue(responses[2]["result"]["isError"])
        self.assertNotIn(member["token"], result.stdout)
        proxy = MCPServer(None, None, client=Client(endpoint, member["token"]))
        proxy.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.brain.revoke_credential(self.actor, member["credential_id"])
        self.assertEqual(-32001, proxy.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["error"]["code"])

    def test_connection_identity_change_and_removal(self):
        endpoint = self.server()
        token_file = self.root / "reader.token"
        token_file.write_text(self.owner["token"])
        home = self.root / "client"
        connect(home, "company", endpoint, token_file)
        profile = home / "connections/company.json"
        data = json.loads(profile.read_text())
        data["organization_id"] = "wrong"
        profile.write_text(json.dumps(data))
        with self.assertRaises(BrainError) as error:
            load_connection(home, "company")
        self.assertEqual("identity_changed", error.exception.code)
        remove_connection(home, "company")
        self.assertFalse((home / "client-tokens/company.token").exists())
        self.brain.authenticate(self.owner["token"])  # Local removal is not server revocation.

    def test_service_render_preserves_paths_and_loopback(self):
        home = self.root / 'Company "brain" $x %x'
        with patch("atmet_brain.services.sys.executable", "/a venv/bin/python"):
            mac = service_spec(home, platform="darwin")
            linux = service_spec(home, platform="linux")
        payload = plistlib.loads(mac["content"].encode())
        self.assertEqual("/a venv/bin/python", payload["ProgramArguments"][0])
        self.assertIn("127.0.0.1", payload["ProgramArguments"])
        self.assertNotIn("--allow-network", linux["content"])
        self.assertIn("%%x", linux["content"])
        self.assertIn("$$x", linux["content"])
        self.assertNotIn(self.owner["token"], mac["content"])
        self.assertNotEqual(mac["label"], service_spec(self.root / "other", platform="darwin")["label"])

    def test_service_install_controls_and_modified_file_protection(self):
        with patch("atmet_brain.services.Path.home", return_value=self.root / "user"):
            spec = service_spec(self.home, platform="linux")
        good = subprocess.CompletedProcess([], 0, "active", "")
        with patch("atmet_brain.services.run_control", return_value=good) as control:
            manage_service("install", spec, start=True)
            self.assertTrue(Path(spec["path"]).exists())
            self.assertTrue(any(call.args[0][0:4] == ["systemctl", "--user", "enable", "--now"] for call in control.call_args_list))
            self.assertEqual("active", manage_service("status", spec)["state"])
            Path(spec["path"]).write_text("changed")
            with self.assertRaises(BrainError) as error:
                manage_service("remove", spec)
            self.assertEqual("service_modified", error.exception.code)
            Path(spec["path"]).write_text(spec["content"])
            manage_service("remove", spec)
            self.assertFalse(Path(spec["path"]).exists())
        self.assertTrue((self.home / "brain.sqlite3").exists())

    def test_service_mac_lifecycle_without_touching_host_manager(self):
        with patch("atmet_brain.services.Path.home", return_value=self.root / "user"):
            spec = service_spec(self.home, platform="darwin")
        good = subprocess.CompletedProcess([], 0, "", "")
        with patch("atmet_brain.services.run_control", return_value=good):
            manage_service("install", spec)
            self.assertEqual("loaded", manage_service("status", spec)["state"])
            manage_service("start", spec)
            manage_service("stop", spec)
            manage_service("remove", spec)

    def test_service_refuses_unsupported_platform_and_missing_worker_scope(self):
        for kwargs in [{"platform": "win32"}, {"platform": "linux", "kind": "worker"}, {"platform": "linux", "port": 0}]:
            with self.assertRaises(BrainError):
                service_spec(self.home, **kwargs)

    def test_redirect_never_receives_the_credential(self):
        received = []
        class Target(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
            def log_message(self, *args):
                pass
        target = ThreadingHTTPServer(("127.0.0.1", 0), Target)
        class Redirect(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(307)
                self.send_header("Location", f"http://127.0.0.1:{target.server_port}/capture")
                self.end_headers()
            def log_message(self, *args):
                pass
        origin = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        for server in (target, origin):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
        with self.assertRaises(BrainError):
            Client(f"http://127.0.0.1:{origin.server_port}", self.owner["token"]).call("identity.me")
        self.assertEqual([], received)

    def test_generated_mcp_config_uses_profile_without_inline_credentials(self):
        key = self.root / "reader.token"
        member = self.member()
        key.write_text(member["token"])
        home = self.root / "client"
        connect(home, "company", self.server(), key)
        result = self.cli(home, "--connection", "company", "mcp-config")
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads(result.stdout)["mcpServers"]["atmet-brain"]
        self.assertEqual("mcp", data["args"][-1])
        self.assertIn("company", data["args"])
        self.assertNotIn(member["token"], result.stdout)
        self.assertFalse((home / "brain.sqlite3").exists())

    def test_installer_verifies_checksum_before_invoking_uv(self):
        tools = self.root / "tools"
        tools.mkdir()
        fixture = self.root / "atmet_brain-0.2.0-py3-none-any.whl"
        fixture.write_bytes(b"fictional release wheel")
        sums = self.root / "SHA256SUMS.txt"
        sums.write_text(hashlib.sha256(fixture.read_bytes()).hexdigest() + "  " + fixture.name + "\n")
        curl = tools / "curl"
        curl.write_text('#!/bin/sh\nwhile [ "$#" -gt 0 ]; do\ncase "$1" in\nhttps://*SHA256SUMS.txt) src="$FIXTURE_SUMS";;\nhttps://*.whl) src="$FIXTURE_WHEEL";;\n-o) shift; dest="$1";;\nesac\nshift\ndone\ncp "$src" "$dest"\n')
        uv = tools / "uv"
        uv.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$UV_CAPTURE"\n')
        for path in (curl, uv):
            path.chmod(0o700)
        capture = self.root / "installed"
        env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"], "FIXTURE_SUMS": str(sums),
               "FIXTURE_WHEEL": str(fixture), "UV_CAPTURE": str(capture)}
        result = subprocess.run(["sh", "install.sh"], env=env, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("tool\ninstall", capture.read_text())
        capture.unlink()
        fixture.write_bytes(b"tampered")
        result = subprocess.run(["sh", "install.sh"], env=env, capture_output=True, text=True)
        self.assertEqual(1, result.returncode)
        self.assertFalse(capture.exists())
