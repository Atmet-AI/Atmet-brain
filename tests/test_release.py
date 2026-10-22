"""Release guards must fail closed before an irreversible registry upload."""

import base64
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.check_npm_registry import after, before, fetch_metadata, wait_after
from scripts.check_release_tag import check_release


class RegistryGuardTests(unittest.TestCase):
    def test_new_version_and_semantic_order(self):
        fetch = lambda key: {"version": "0.2.9"} if key == "latest" else None
        self.assertEqual(before("0.2.10", fetch)["previous_latest"], "0.2.9")
        with self.assertRaisesRegex(ValueError, "downgrade"):
            before("0.2.8", fetch)
        with self.assertRaises(ValueError):
            before("0.2.10rc1", fetch)

    def test_existing_version_and_missing_package_refuse_upload(self):
        with self.assertRaisesRegex(ValueError, "already exists"):
            before("0.2.5", lambda key: {"version": "0.2.5"})
        with self.assertRaisesRegex(ValueError, "existing package"):
            before("0.2.5", lambda key: None)

    def test_only_404_is_an_absent_version(self):
        with patch("scripts.check_npm_registry.urlopen", side_effect=HTTPError("registry", 404, "absent", {}, None)):
            self.assertIsNone(fetch_metadata("0.2.5"))
        for code in (401, 403, 429, 500):
            with self.subTest(code=code), patch("scripts.check_npm_registry.urlopen", side_effect=HTTPError("registry", code, "failed", {}, None)):
                with self.assertRaises(HTTPError):
                    before("0.2.5")

    def test_exact_public_integrity_and_latest(self):
        archive = b"reviewed release archive"
        metadata = {"name": "atmet-brain", "version": "0.2.5", "dist": {
            "integrity": "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode(),
            "shasum": hashlib.sha1(archive).hexdigest()}}
        fetch = lambda key: metadata
        self.assertTrue(after("0.2.5", archive, fetch)["registry_verified"])
        with self.assertRaisesRegex(ValueError, "match"):
            after("0.2.5", b"different archive", fetch)
        with self.assertRaisesRegex(ValueError, "latest"):
            after("0.2.5", archive, lambda key: {"version": "0.2.4"} if key == "latest" else metadata)
        with self.assertRaisesRegex(ValueError, "identity"):
            after("0.2.5", archive, lambda key: None)

    def test_propagation_delay_retries_without_another_publish(self):
        archive = b"reviewed release archive"
        metadata = {"name": "atmet-brain", "version": "0.2.5", "dist": {
            "integrity": "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode(),
            "shasum": hashlib.sha1(archive).hexdigest()}}
        responses = iter([None, metadata, metadata, {"version": "0.2.4"}, metadata, metadata])
        self.assertTrue(wait_after("0.2.5", archive, lambda key: next(responses), attempts=3, interval=0)["registry_verified"])
        with self.assertRaisesRegex(ValueError, "visible"):
            wait_after("0.2.5", archive, lambda key: None, attempts=2, interval=0)

    def test_integrity_mismatch_fails_immediately_without_retry(self):
        calls = []
        def fetch(key):
            calls.append(key)
            return {"name": "atmet-brain", "version": "0.2.5", "dist": {}}
        with self.assertRaisesRegex(ValueError, "match"):
            wait_after("0.2.5", b"archive", fetch, attempts=3, interval=0)
        self.assertEqual(calls, ["0.2.5", "latest"])


class ReleaseTagTests(unittest.TestCase):
    def test_annotation_identity_and_main_ancestry(self):
        with tempfile.TemporaryDirectory(prefix="atmet-release-test-") as folder:
            root = Path(folder)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
            git("init", "-b", "main")
            git("config", "user.name", "Example Maintainer")
            git("config", "user.email", "maintainer@example.invalid")
            (root / "pyproject.toml").write_text('[project]\nversion = "0.2.5"\n')
            git("add", ".")
            git("commit", "-m", "Release fixture")
            git("update-ref", "refs/remotes/origin/main", "HEAD")
            git("tag", "v0.2.5")
            with self.assertRaisesRegex(ValueError, "annotated"):
                check_release(root, "v0.2.5")
            git("tag", "-d", "v0.2.5")
            git("tag", "-a", "v0.2.5", "-m", "Fixture release")
            check_release(root, "v0.2.5")
            with self.assertRaisesRegex(ValueError, "package version"):
                check_release(root, "v0.2.4")
            git("commit", "--allow-empty", "-m", "Unreleased change")
            with self.assertRaisesRegex(ValueError, "Checkout"):
                check_release(root, "v0.2.5")
            git("tag", "-d", "v0.2.5")
            git("tag", "-a", "v0.2.5", "-m", "Side branch fixture")
            with self.assertRaisesRegex(ValueError, "origin/main"):
                check_release(root, "v0.2.5")


if __name__ == "__main__":
    unittest.main()
