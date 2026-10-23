"""Actual HTTP/TLS account delivery, private CLI state and wizard recovery."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from atmet_brain import BrainError
from atmet_brain.cli import execute, parser, read_token
from atmet_brain.client import Client
from atmet_brain.connections import load_connection
from atmet_brain.feedback import LocalClient
from atmet_brain.invitations import ANONYMOUS, read_invitation, save_invitation
from atmet_brain.rpc import openapi
from tests import test_terminal_team as fixtures
from tests.test_accounts import PASSWORD, NEW_PASSWORD


class AccountUICase(unittest.TestCase):
    setUp = fixtures.TerminalTeamCase.setUp
    server = fixtures.TerminalTeamCase.server
    cli = fixtures.TerminalTeamCase.cli

    def fails(self, code, function, *args, **kwargs):
        with self.assertRaises(BrainError) as caught:
            function(*args, **kwargs)
        self.assertEqual(code, caught.exception.code)
        return caught.exception

    def invitation(self, endpoint=None, username="alex@example.test"):
        path = self.root / (username.replace("@", "-") + ".atmet-invite.json")
        result = save_invitation(LocalClient(self.brain, self.owner["token"]), path,
                                 username_value=username, name="Alex", access=[{"space_id": self.sales, "role": "reporter"}],
                                 route={"endpoint": endpoint or self.server(tls=True), "ssh": None})
        return path, result

    def join(self, path, home=None, name="company"):
        args = parser().parse_args(["--home", str(home or self.root / "employee"), "--json", "--ca-file", str(self.root / "ca.pem"),
                                    "join", "--file", str(path), "--name", name, "--password-stdin"])
        with patch("sys.stdin", io.StringIO(PASSWORD + "\n")):
            return execute(args)

    def test_tls_invitation_enrollment_stores_only_private_session_and_no_company_database(self):
        path, receipt = self.invitation()
        record = read_invitation(path)
        result = self.join(path)
        self.assertTrue(result["invitation_consumed"])
        self.assertEqual("alex@example.test", result["username"])
        home = self.root / "employee"
        self.assertFalse((home / "brain.sqlite3").exists())
        self.assertEqual(0o600, path.stat().st_mode & 0o777)
        for filename in [home / "connections/company.json", home / "client-tokens/company.token"]:
            self.assertEqual(0o600, filename.stat().st_mode & 0o777)
        for value in [PASSWORD, record["secret"], (home / "client-tokens/company.token").read_text().strip()]:
            self.assertNotIn(value, json.dumps(result))
        self.assertNotIn(record["secret"], json.dumps(receipt))
        client, identity = load_connection(home, "company")
        self.assertEqual([self.sales], [s["id"] for s in client.call("spaces.list")])
        self.fails("forbidden", client.call, "context.get", space_id=self.finance, query="salary")

    def test_untrusted_tls_does_not_consume_invite_or_save_client_state(self):
        path, _ = self.invitation()
        args = parser().parse_args(["--home", str(self.root / "untrusted"), "--json", "join", "--file", str(path), "--password-stdin"])
        with patch("sys.stdin", io.StringIO(PASSWORD + "\n")):
            self.fails("connection_failed", execute, args)
        self.assertFalse((self.root / "untrusted").exists())
        self.assertEqual("pending", self.brain.list_invites(self.actor)[0]["state"])
        self.assertTrue(self.join(path)["signed_in"])

    def test_existing_connection_is_rejected_before_consuming_another_invite(self):
        endpoint = self.server(tls=True)
        path, _ = self.invitation(endpoint)
        self.join(path)
        other, _ = self.invitation(endpoint, "other@example.test")
        self.fails("already_exists", self.join, other)
        self.assertTrue(any(i["username"] == "other@example.test" and i["state"] == "pending" for i in self.brain.list_invites(self.actor)))

    def test_edited_invite_cannot_assign_a_different_username_or_permissions(self):
        path, _ = self.invitation()
        record = json.loads(path.read_text())
        path.write_text(json.dumps({**record, "role": "owner"}))
        self.fails("invalid_invite_file", read_invitation, path)
        path.write_text(json.dumps({**record, "username": "owner@example.test"}))
        self.fails("identity_changed", self.join, path)
        self.assertFalse((self.root / "employee/connections/company.json").exists())
        issued = self.brain.login("company", "alex@example.test", PASSWORD)
        self.assertEqual("Alex", self.brain.whoami(self.brain.authenticate(issued["token"]))["name"])

    def test_expired_remote_session_can_login_again_using_retained_verified_route(self):
        path, _ = self.invitation()
        first = self.join(path)
        with self.brain.store.transaction(write=True) as conn:
            conn.execute("UPDATE credentials SET expires_at=1 WHERE id=?", (first["identity"]["credential_id"],))
        self.fails("unauthenticated", load_connection, self.root / "employee", "company")
        args = parser().parse_args(["--home", str(self.root / "employee"), "--json", "--connection", "company", "login", "--password-stdin"])
        with patch("sys.stdin", io.StringIO(PASSWORD + "\n")):
            second = execute(args)
        self.assertNotEqual(first["identity"]["credential_id"], second["identity"]["credential_id"])
        self.assertTrue(load_connection(self.root / "employee", "company")[1])

    def test_remote_logout_revokes_session_children_and_keeps_signin_address(self):
        path, _ = self.invitation()
        result = self.join(path)
        home = self.root / "employee"
        client, actor = load_connection(home, "company")
        child = client.call("credentials.create", operations=["read"], space_ids=[self.sales])
        args = parser().parse_args(["--home", str(home), "--connection", "company", "logout"])
        self.assertTrue(execute(args)["session_revoked"])
        self.assertTrue((home / "connections/company.json").exists())
        self.assertFalse((home / "client-tokens/company.token").exists())
        self.fails("sign_in_required", load_connection, home, "company")
        self.fails("unauthenticated", self.brain.authenticate, child["token"])
        self.assertTrue(execute(args)["signed_out"])

    def test_local_logout_does_not_silently_fall_back_to_owner_key(self):
        self.brain.setup_account(self.actor, "owner", PASSWORD)
        args = parser().parse_args(["--home", str(self.home), "--json", "login", "--username", "owner", "--password-stdin"])
        with patch("sys.stdin", io.StringIO(PASSWORD + "\n")):
            self.assertTrue(execute(args)["signed_in"])
        execute(parser().parse_args(["--home", str(self.home), "logout"]))
        self.fails("sign_in_required", execute, parser().parse_args(["--home", str(self.home), "status"]))
        explicit = parser().parse_args(["--home", str(self.home), "--token-file", str(self.home / "owner.token"), "status"])
        self.assertEqual(self.actor.principal_id, execute(explicit)["identity"]["principal_id"])

    def test_login_retries_bad_password_without_repeating_username_or_company(self):
        self.brain.setup_account(self.actor, "owner", PASSWORD)
        args = parser().parse_args(["--home", str(self.home), "login", "--username", "owner"])
        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", side_effect=[NEW_PASSWORD, PASSWORD]) as passwords, \
                patch("builtins.input", return_value="yes") as answers, contextlib.redirect_stderr(io.StringIO()) as screen:
            result = execute(args)
        self.assertTrue(result["signed_in"])
        self.assertEqual(2, passwords.call_count)
        self.assertEqual(1, answers.call_count)
        self.assertNotIn(PASSWORD, screen.getvalue())

    def test_cli_subprocess_owner_enrollment_login_and_password_change_keep_secrets_off_output(self):
        for command, payload in [(["account", "setup", "--username", "owner", "--password-stdin"], PASSWORD + "\n"),
                                 (["login", "--username", "owner", "--password-stdin"], PASSWORD + "\n"),
                                 (["account", "password", "--password-stdin"], PASSWORD + "\n" + NEW_PASSWORD + "\n")]:
            result = self.cli(self.home, "--json", *command, input=payload)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn(PASSWORD, result.stdout + result.stderr)
            self.assertNotIn(NEW_PASSWORD, result.stdout + result.stderr)
            self.assertNotIn("\"token\":", result.stdout)
        self.assertEqual(self.actor.principal_id, self.brain.authenticate((self.home / "session.token").read_text().strip()).principal_id)

    def test_employee_workspace_review_changes_scope_and_invalidates_old_session(self):
        invitation = self.brain.create_invite(self.actor, "alex", "Alex", [{"space_id": self.sales, "role": "reader"}, {"space_id": self.finance, "role": "reader"}])
        issued = self.brain.accept_invite(invitation["organization_id"], invitation["id"], invitation["secret"], PASSWORD)
        args = parser().parse_args(["--home", str(self.home), "team", "access", "--principal", issued["principal_id"]])
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["sales", "reader", "yes"]), contextlib.redirect_stderr(io.StringIO()) as screen:
            changed = execute(args)
        self.assertEqual([{"space_id": self.sales, "role": "reader"}], changed["access"])
        self.assertIn("sales", screen.getvalue())
        self.assertIn("Revoked", screen.getvalue())
        self.fails("unauthenticated", self.brain.authenticate, issued["token"])
        actor = self.brain.authenticate(self.brain.login("company", "alex", PASSWORD)["token"])
        self.fails("forbidden", self.brain.get_context, actor, self.finance, "payroll")

    def test_team_menu_cancel_returns_to_menu_without_issuing_invite(self):
        args = parser().parse_args(["--home", str(self.home), "team"])
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["invite", "alex", "Alex", "/cancel", "yes", "done"]), contextlib.redirect_stderr(io.StringIO()):
            self.assertTrue(execute(args)["done"])
        self.assertEqual([], self.brain.list_invites(self.actor))

    def test_invalid_ssh_input_retries_same_field_and_preserves_existing_brain(self):
        args = parser().parse_args(["--home", str(self.home), "host", "--transport", "ssh"])
        before = (self.home / "owner.token").read_bytes()
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["yyyy1111", "forward@brain.example.test", "no", "no"]), contextlib.redirect_stderr(io.StringIO()) as screen:
            result = execute(args)
        self.assertTrue(result["reused"])
        self.assertIn("Try again", screen.getvalue())
        self.assertEqual(2, screen.getvalue().count("Forwarding-only SSH user@host"))
        self.assertEqual(before, (self.home / "owner.token").read_bytes())

    def test_host_interactive_default_creates_password_invite_not_reusable_bearer(self):
        args = parser().parse_args(["--home", str(self.home), "host", "--transport", "https", "--endpoint", "https://brain.example.test"])
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["yes", "Alex", "alex@example.test", "sales", "reader", "yes", "no"]), contextlib.redirect_stderr(io.StringIO()):
            result = execute(args)
        self.assertTrue(result["team"]["single_use"])
        record = read_invitation(result["team"]["private_file"])
        self.assertNotIn("token", record)
        with self.brain.store.transaction() as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM principals").fetchone()[0])

    def test_invitation_write_failure_revokes_it_without_leaving_secret_file(self):
        from atmet_brain.invitations import private_write
        path = self.root / "failed.atmet-invite.json"
        first = private_write(path, "", overwrite=False)
        with patch("atmet_brain.invitations.private_write", side_effect=[first, OSError("fixture disk full")]):
            self.fails("invite_save_failed", save_invitation, LocalClient(self.brain, self.owner["token"]), path,
                       username_value="alex", name="Alex", access=[{"space_id": self.sales, "role": "reader"}],
                       route={"endpoint": "https://brain.example.test", "ssh": None})
        self.assertFalse(path.exists())
        self.assertEqual("revoked", self.brain.list_invites(self.actor)[0]["state"])

    def test_http_auth_endpoints_reject_identity_injection_origins_and_unauthenticated_rpc(self):
        endpoint = self.server()
        self.brain.setup_account(self.actor, "owner", PASSWORD)
        client = Client(endpoint, ANONYMOUS)
        result = client.auth("login", organization="company", username_value="owner", password=PASSWORD)
        self.assertEqual(self.actor.principal_id, result["principal_id"])
        self.fails("unauthenticated", client.call, "members.list")
        self.fails("invalid_auth", client.auth, "login", organization="company", username_value="owner", password=PASSWORD, actor="owner")
        body = json.dumps({"organization": "company", "username_value": "owner", "password": PASSWORD}).encode()
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(endpoint + "/v1/auth/login", body, {"Content-Type": "application/json", "Origin": "https://evil.example"}))
        self.assertEqual(403, error.exception.code)
        schema = openapi(self.brain)
        self.assertEqual([], schema["paths"]["/v1/auth/login"]["post"]["security"])
        fields = schema["paths"]["/v1/auth/login"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]
        self.assertTrue(fields["password"]["writeOnly"])

    def test_password_auth_uses_ssh_forwarding_before_any_http_request(self):
        endpoint = self.server()
        self.brain.setup_account(self.actor, "owner", PASSWORD)
        from atmet_brain.ssh import SSHClient
        client = SSHClient({"destination": "forward@example.test", "port": 7310}, ANONYMOUS)
        with patch("atmet_brain.ssh.tunnel", side_effect=lambda _: contextlib.nullcontext(endpoint)) as forwarding:
            result = client.auth("login", organization="company", username_value="owner", password=PASSWORD)
        self.assertEqual(self.actor.principal_id, result["principal_id"])
        forwarding.assert_called_once()

    def test_owner_recovery_requires_explicit_local_operator_action_and_saves_private_key(self):
        self.brain.setup_account(self.actor, "owner", PASSWORD)
        values = ["--home", str(self.home), "--json", "account", "recover", "--username", "owner", "--password-stdin"]
        with patch("sys.stdin", io.StringIO(NEW_PASSWORD + "\n")):
            self.fails("owner_confirmation_required", execute, parser().parse_args(values))
        with patch("sys.stdin", io.StringIO(NEW_PASSWORD + "\n")):
            result = execute(parser().parse_args(values + ["--confirm-local-owner"]))
        self.assertNotIn("token", result)
        self.assertEqual(0o600, Path(result["operator_file"]).stat().st_mode & 0o777)
        self.assertEqual(self.actor.principal_id, self.brain.authenticate(Path(result["operator_file"]).read_text().strip()).principal_id)
        remote = parser().parse_args(["--home", str(self.home), "--endpoint", "https://brain.example.test", "account", "recover", "--username", "owner", "--confirm-local-owner"])
        self.fails("local_only", execute, remote)

    def test_password_request_never_follows_a_redirect(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        captured = []
        class Target(BaseHTTPRequestHandler):
            def do_POST(self):
                captured.append(True)
                self.send_response(200); self.end_headers()
            def log_message(self, *args):
                pass
        target = ThreadingHTTPServer(("127.0.0.1", 0), Target)
        destination = "http://127.0.0.1:" + str(target.server_port)
        class Redirect(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(307); self.send_header("Location", destination); self.end_headers()
            def log_message(self, *args):
                pass
        redirect = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in [target, redirect]]
        for thread in threads:
            thread.start()
        try:
            client = Client("http://127.0.0.1:" + str(redirect.server_port), ANONYMOUS)
            self.fails("provider_redirect", client.auth, "login", organization="company", username_value="owner", password=PASSWORD)
            self.assertEqual([], captured)
        finally:
            for server in [target, redirect]:
                server.shutdown(); server.server_close()
            for thread in threads:
                thread.join(2)

    def test_password_prompt_refuses_echo_fallback_and_stdin_flag_on_a_terminal(self):
        import getpass
        import warnings
        from atmet_brain.account_cli import secret
        args = parser().parse_args(["login"])
        def unsafe(*args):
            warnings.warn("fixture echo fallback", getpass.GetPassWarning)
            raise AssertionError("Must stop before reading an echoed password")
        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", side_effect=unsafe):
            self.fails("private_prompt_unavailable", secret, args, "Password")
        args.password_stdin = True
        with patch("sys.stdin.isatty", return_value=True):
            self.fails("private_input_required", secret, args, "Password")

    def test_employee_login_never_upgrades_an_existing_scoped_agent_profile(self):
        from atmet_brain.connections import connect
        self.brain.setup_account(self.actor, "owner", PASSWORD)
        token = self.brain.create_credential(self.actor, operations=["read"], space_ids=[self.sales])
        token_path = self.root / "agent.token"; token_path.write_text(token["token"])
        home = self.root / "agent-client"
        connect(home, "agent", self.server(), token_path)
        before = (home / "client-tokens/agent.token").read_bytes()
        args = parser().parse_args(["--home", str(home), "--connection", "agent", "login", "--username", "owner", "--password-stdin"])
        with patch("sys.stdin", io.StringIO(PASSWORD + "\n")):
            self.fails("not_password_session", execute, args)
        self.assertEqual(before, (home / "client-tokens/agent.token").read_bytes())
        client, _ = load_connection(home, "agent")
        self.fails("forbidden", client.call, "context.get", space_id=self.finance, query="payroll")

    def test_one_off_remote_password_change_never_opens_a_local_database(self):
        home = self.root / "remote-only"
        args = parser().parse_args(["--home", str(home), "--endpoint", "https://unreachable.example.test", "--token-file", str(self.home / "owner.token"),
                                    "account", "password", "--password-stdin"])
        with patch("sys.stdin", io.StringIO(PASSWORD + "\n" + NEW_PASSWORD + "\n")):
            self.fails("saved_login_required", execute, args)
        self.assertFalse(home.exists())
