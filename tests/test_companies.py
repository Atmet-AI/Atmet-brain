"""Independent company data homes and explicit selection, including concurrent catalog writes."""

import concurrent.futures
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from atmet_brain import Brain, BrainError
from atmet_brain.cli import execute, parser
from atmet_brain.companies import catalog, remember
from tests import test_terminal_team as fixtures


class CompanyCase(unittest.TestCase):
    setUp = fixtures.TerminalTeamCase.setUp

    def command(self, *values):
        return execute(parser().parse_args(["--home", str(self.home), "--json", *values]))

    def fails(self, code, *values):
        with self.assertRaises(BrainError) as caught:
            self.command(*values)
        self.assertEqual(code, caught.exception.code)

    def test_multiple_company_creation_keeps_original_owner_and_data_separate(self):
        before = (self.home / "owner.token").read_bytes()
        self.command("setup", "--mode", "local")
        result = self.command("brains", "create", "second", "--owner", "Second owner", "--spaces", "sales,payroll")
        self.assertEqual("second", result["brain"])
        self.assertEqual(before, (self.home / "owner.token").read_bytes())
        first = self.command("--brain", "company", "status")
        second = self.command("--brain", "second", "status")
        self.assertNotEqual(first["identity"]["organization_id"], second["identity"]["organization_id"])
        target = Path(second["home"])
        other = Brain(target)
        with self.assertRaises(BrainError):
            other.authenticate(self.owner["token"])
        self.assertEqual({"company", "second"}, set(catalog(self.home)))

    def test_selected_brain_scope_reaches_all_cli_operations_without_changing_default(self):
        self.command("brains", "create", "second", "--spaces", "shared")
        result = self.command("--brain", "second", "space", "marketing")
        selected = self.command("--brain", "second", "space")
        self.assertIn(result["id"], [s["id"] for s in selected])
        self.assertNotIn("marketing", [s["slug"] for s in self.command("space")])

    def test_creating_existing_label_never_overwrites_company(self):
        first = self.command("brains", "create", "second")
        token = (Path(first["home"]) / "owner.token").read_bytes()
        self.fails("already_exists", "brains", "create", "second")
        self.assertEqual(token, (Path(first["home"]) / "owner.token").read_bytes())

    def test_existing_company_registration_requires_explicit_valid_home(self):
        self.command("brains", "add", "original", "--path", str(self.home))
        self.assertEqual(str(self.home.resolve()), catalog(self.home)["original"])
        self.fails("brain_missing", "brains", "add", "missing", "--path", str(self.root / "absent"))
        self.assertFalse((self.root / "absent").exists())

    def test_local_company_and_remote_connection_cannot_be_selected_together(self):
        self.command("setup", "--mode", "local")
        self.fails("invalid_company", "--brain", "company", "--connection", "remote", "status")

    def test_catalog_writes_preserve_concurrent_additions_and_private_mode(self):
        def add(index):
            return remember(self.home, "label-" + str(index), self.home)
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            list(pool.map(add, range(8)))
        self.assertEqual(8, len(catalog(self.home)))
        self.assertEqual(0o600, (self.home / "brains.json").stat().st_mode & 0o777)

    def test_setup_recovery_registers_new_company_without_changing_original_mapping(self):
        self.command("setup", "--mode", "local")
        target = self.root / "another-home"
        args = parser().parse_args(["--home", str(self.home), "setup", "--mode", "local"])
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["new", str(target), "company", "Second owner", "shared"]), contextlib.redirect_stderr(io.StringIO()):
            result = execute(args)
        self.assertEqual("company-2", result["company_catalog"]["brain"])
        self.assertEqual(str(self.home.resolve()), catalog(self.home)["company"])
        self.assertEqual(str(target.resolve()), catalog(self.home)["company-2"])

    def test_invalid_company_slug_retries_field_without_restarting_setup(self):
        home = self.root / "fresh"
        args = parser().parse_args(["--home", str(home), "setup"])
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["local", "INVALID NAME", "second", "Owner", "bad, bad", "shared"]), contextlib.redirect_stderr(io.StringIO()) as screen:
            result = execute(args)
        self.assertEqual("second", result["company_catalog"]["brain"])
        self.assertIn("Try again", screen.getvalue())
        self.assertEqual(1, screen.getvalue().count("Choose a setup"))
