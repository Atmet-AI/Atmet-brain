"""Host/Join security and user-flow regressions, using isolated company data."""

import contextlib
import io
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
import unittest

from atmet_brain import BrainError
from atmet_brain.cli import execute, parser
from atmet_brain.connections import load_connection
from atmet_brain.mcp import MCPServer
from atmet_brain.sharing import create_share, join_share, read_share
from atmet_brain.ssh import SSHClient, tunnel, validate_ssh
from tests import test_terminal_team as fixtures


class GuidedSharingCase(unittest.TestCase):
    setUp = fixtures.TerminalTeamCase.setUp
    server = fixtures.TerminalTeamCase.server
    cli = fixtures.TerminalTeamCase.cli

    def share(self, **options):
        output = options.pop("output", self.root / "sales.atmet-join.json")
        return create_share(self.brain, self.actor, "Sales employee", ["sales"], "reader", output, **options)

    def test_short_commands_and_legacy_modes_have_independent_defaults(self):
        self.assertIsNone(parser().parse_args(["setup"]).mode)
        self.assertEqual("host", parser().parse_args(["host"]).setup_entry)
        self.assertEqual("join", parser().parse_args(["join"]).setup_entry)
        result = self.cli(self.root / "legacy", "setup", "--mode", "team", "--organization", "legacy")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_host_reuses_existing_company_and_selects_spaces_by_name(self):
        before = (self.home / "owner.token").read_bytes()
        output = self.root / "member.json"
        run = self.cli(self.home, "host", "--transport", "https", "--endpoint", "https://brain.example.com",
                       "--member", "Sales employee", "--member-spaces", "sales", "--output", str(output))
        self.assertEqual(0, run.returncode, run.stderr)
        result = json.loads(run.stdout)
        self.assertTrue(result["reused"])
        self.assertFalse(result["server"]["network_verified"])
        record = read_share(output)
        self.assertEqual(["sales"], record["workspaces"])
        self.assertEqual([self.sales], self.brain.whoami(self.brain.authenticate(record["token"]))["credential_spaces"])
        self.assertEqual(before, (self.home / "owner.token").read_bytes())
        self.assertEqual(0o600, output.stat().st_mode & 0o777)
        self.assertNotIn(record["token"], run.stdout + run.stderr)
        self.assertNotEqual(record["token"], self.owner["token"])

    def test_join_https_verifies_scope_and_never_creates_local_brain(self):
        result = self.share(endpoint=self.server(tls=True))
        home = self.root / "employee"
        run = self.cli(home, "join", "--file", result["connection_file"], "--ca-file", str(self.root / "ca.pem"))
        self.assertEqual(0, run.returncode, run.stderr)
        data = json.loads(run.stdout)
        self.assertTrue(data["verified"])
        self.assertEqual([self.sales], [s["id"] for s in data["spaces"]])
        self.assertFalse((home / "brain.sqlite3").exists())
        client, actor = load_connection(home, "company")
        with self.assertRaises(BrainError):
            client.call("search", space_id=self.finance, query="private")
        self.assertEqual(0o600, (home / "client-tokens/company.token").stat().st_mode & 0o777)
        self.assertNotIn(read_share(result["connection_file"])["token"], run.stdout + run.stderr)
        self.brain.revoke_credential(self.actor, result["credential_id"])
        with self.assertRaises(BrainError):
            load_connection(home, "company")

    def test_expired_revoked_or_wrong_identity_does_not_save_connection(self):
        result = self.share(endpoint=self.server(tls=True))
        path = Path(result["connection_file"])
        original = json.loads(path.read_text())
        ca = self.root / "ca.pem"
        expired = {**original, "expires_at": 1}
        path.write_text(json.dumps(expired))
        with self.assertRaises(BrainError) as caught:
            join_share(self.root / "expired", path, ca_file=ca)
        self.assertEqual("join_expired", caught.exception.code)
        wrong = {**original, "identity": {**original["identity"], "organization_id": "other"}}
        path.write_text(json.dumps(wrong))
        with self.assertRaises(BrainError) as caught:
            join_share(self.root / "wrong", path, ca_file=ca)
        self.assertEqual("identity_changed", caught.exception.code)
        path.write_text(json.dumps(original))
        self.brain.revoke_credential(self.actor, result["credential_id"])
        with self.assertRaises(BrainError):
            join_share(self.root / "revoked", path, ca_file=ca)
        for name in ["expired", "wrong", "revoked"]:
            self.assertFalse((self.root / name).exists())

    def test_untrusted_ca_and_duplicate_connection_leave_original_untouched(self):
        result = self.share(endpoint=self.server(tls=True))
        home = self.root / "employee"
        with self.assertRaises(BrainError):
            join_share(home, result["connection_file"])
        self.assertFalse(home.exists())
        join_share(home, result["connection_file"], ca_file=self.root / "ca.pem")
        before = (home / "connections/company.json").read_bytes()
        with self.assertRaises(BrainError):
            join_share(home, result["connection_file"], ca_file=self.root / "ca.pem")
        self.assertEqual(before, (home / "connections/company.json").read_bytes())

    def test_bad_host_answers_leave_new_home_uninitialized(self):
        for suffix in [["--member-spaces", "missing"], ["--member-spaces", "sales,sales"]]:
            home = self.root / "fresh"
            run = self.cli(home, "host", "--organization", "new", "--spaces", "sales,finance", "--transport", "https",
                           "--endpoint", "https://brain.example.com", "--member", "Employee", *suffix)
            self.assertEqual(1, run.returncode)
            self.assertFalse(home.exists())
        run = self.cli(self.root / "insecure", "host", "--organization", "new", "--transport", "https",
                       "--endpoint", "http://192.168.1.2:7310")
        self.assertEqual(1, run.returncode)
        self.assertFalse((self.root / "insecure").exists())

    def test_interactive_host_confirmations_and_join_cancel(self):
        output = self.root / "interactive.json"
        args = parser().parse_args(["--home", str(self.home), "host", "--transport", "https", "--endpoint",
                                    "https://brain.example.com", "--member", "Employee", "--member-spaces", "sales", "--output", str(output)])
        screen = io.StringIO()
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["reader", "yes", "no"]), contextlib.redirect_stderr(screen):
            execute(args)
        self.assertIn("Reuse your existing Brain", screen.getvalue())
        args = parser().parse_args(["--home", str(self.root / "cancelled"), "join", "--file", str(output)])
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["company", "no"]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(BrainError) as caught:
                execute(args)
        self.assertEqual("setup_cancelled", caught.exception.code)
        self.assertFalse((self.root / "cancelled").exists())

    def test_bundle_validation_and_changed_file_precede_network(self):
        result = self.share(endpoint="https://brain.example.com")
        path = Path(result["connection_file"])
        original = read_share(path)
        bad_cases = [{**original, "ssh": {"destination": "x@host", "port": 7310}},
                     {**original, "expires_at": float("inf")}, {**original, "unknown": "field"},
                     {**original, "endpoint": "http://127.0.0.1:7310"}, {**original, "token": "short"}]
        for record in bad_cases:
            path.write_text(json.dumps(record))
            with patch("atmet_brain.client.Client.call") as request:
                with self.assertRaises(BrainError):
                    join_share(self.root / "bad", path)
                request.assert_not_called()
        path.write_text(json.dumps({**original, "role": "publisher"}))
        with self.assertRaises(BrainError) as caught:
            join_share(self.root / "changed", path, expected_record=original)
        self.assertEqual("join_file_changed", caught.exception.code)
        symlink = self.root / "link.json"
        symlink.symlink_to(path)
        with self.assertRaises(BrainError):
            read_share(symlink)
        path.write_bytes(b"x" * 65537)
        with self.assertRaises(BrainError):
            read_share(path)

    def test_failed_file_write_revokes_new_credential_and_removes_reservation(self):
        from atmet_brain.util import private_write
        output = self.root / "failed.json"
        with patch("atmet_brain.sharing.private_write", side_effect=[private_write(output, "", overwrite=False), OSError("disk full")]):
            with self.assertRaises(OSError):
                self.share(endpoint="https://brain.example.com", output=output)
        self.assertFalse(output.exists())
        with self.brain.store.transaction() as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM credentials WHERE revoked=1").fetchone()[0])

    def test_existing_output_prevents_provisioning(self):
        output = self.root / "exists.json"
        output.write_text("keep")
        with self.brain.store.transaction() as conn:
            before = conn.execute("SELECT COUNT(*) FROM principals").fetchone()[0]
        with self.assertRaises(BrainError):
            self.share(endpoint="https://brain.example.com", output=output)
        with self.brain.store.transaction() as conn:
            self.assertEqual(before, conn.execute("SELECT COUNT(*) FROM principals").fetchone()[0])
        self.assertEqual("keep", output.read_text())

    def test_ssh_profile_and_mcp_bridge_use_current_core_permissions(self):
        endpoint = self.server()
        result = self.share(ssh={"destination": "forward@brain.example.com", "port": 7310})
        home = self.root / "ssh-client"
        with patch("atmet_brain.ssh.tunnel", side_effect=lambda _: contextlib.nullcontext(endpoint)):
            joined = join_share(home, result["connection_file"])
            self.assertTrue(joined["verified"])
            client, _ = load_connection(home, "company")
            self.assertEqual([self.sales], [space["id"] for space in client.call("spaces.list")])
            bridge = MCPServer(None, None, client=client)
            bridge.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
            response = bridge.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                      "params": {"name": "brain_list_spaces", "arguments": {}}})
            self.assertFalse(response["result"]["isError"])
            self.assertEqual([self.sales], [space["id"] for space in json.loads(response["result"]["content"][0]["text"])])
            with self.assertRaises(BrainError):
                client.call("search", space_id=self.finance, query="private")
            self.brain.revoke_credential(self.actor, result["credential_id"])
            with self.assertRaises(BrainError):
                load_connection(home, "company")

    def test_service_requires_explicit_choice_and_uses_requested_port(self):
        args = parser().parse_args(["--home", str(self.home), "host", "--transport", "later", "--start-service", "--port", "7350"])
        with patch("atmet_brain.services.manage_service", return_value={"started": True}) as manage:
            result = execute(args)
        self.assertTrue(result["service"]["started"])
        self.assertIn("7350", str(manage.call_args))


class SSHTransportCase(unittest.TestCase):
    def test_rejects_option_injection_and_invalid_ports(self):
        for destination in ["-oProxyCommand=bad", "x@host;bad", "x@host\n", "x@-host", "x@host path", "host"]:
            with self.assertRaises(BrainError):
                validate_ssh({"destination": destination, "port": 7310})
        for port in [True, 0, 65536, "7310"]:
            with self.assertRaises(BrainError):
                validate_ssh({"destination": "forward@host", "port": port})

    def test_failed_ssh_never_sends_a_brain_request(self):
        process = Mock()
        process.poll.return_value = 1
        with patch("atmet_brain.ssh.shutil.which", return_value="/usr/bin/ssh"), patch("atmet_brain.ssh.subprocess.Popen", return_value=process), patch("atmet_brain.client.Client.call") as request:
            with self.assertRaises(BrainError) as caught:
                SSHClient({"destination": "forward@host", "port": 7310}, "test-credential-with-valid-length").call("identity.me")
            self.assertEqual("ssh_failed", caught.exception.code)
            request.assert_not_called()
        process.wait.assert_called_once()

    def test_ssh_is_strict_bounded_and_cleaned_up_even_when_request_fails(self):
        process = Mock()
        process.poll.return_value = None
        def launched(command, **options):
            port = command[command.index("-L") + 1].split(":")[1]
            Path(command[command.index("-E") + 1]).write_text(f"debug1: Local forwarding listening on 127.0.0.1 port {port}.\n")
            return process
        with patch("atmet_brain.ssh.shutil.which", return_value="/usr/bin/ssh"), patch("atmet_brain.ssh.subprocess.Popen", side_effect=launched) as launch, patch("atmet_brain.ssh.socket.create_connection", return_value=contextlib.nullcontext()):
            with self.assertRaises(RuntimeError):
                with tunnel({"destination": "forward@host", "port": 7310}) as endpoint:
                    self.assertTrue(endpoint.startswith("http://127.0.0.1:"))
                    raise RuntimeError("request failed")
        command = launch.call_args.args[0]
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertIn("BatchMode=yes", command)
        self.assertIn("ExitOnForwardFailure=yes", command)
        self.assertFalse(launch.call_args.kwargs["shell"])
        self.assertNotIn("test-credential", " ".join(command))
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=3)

    def test_open_port_without_ssh_bind_confirmation_never_receives_credentials(self):
        process = Mock()
        process.poll.return_value = None
        with patch("atmet_brain.ssh.shutil.which", return_value="/usr/bin/ssh"), patch("atmet_brain.ssh.subprocess.Popen", return_value=process), patch("atmet_brain.ssh.time.monotonic", side_effect=[0, 0, 13]), patch("atmet_brain.ssh.time.sleep"), patch("atmet_brain.ssh.socket.create_connection") as probe, patch("atmet_brain.client.Client.call") as request:
            with self.assertRaises(BrainError):
                SSHClient({"destination": "forward@host", "port": 7310}, "test-credential-with-valid-length").call("identity.me")
            probe.assert_not_called()
            request.assert_not_called()
        process.terminate.assert_called_once()
