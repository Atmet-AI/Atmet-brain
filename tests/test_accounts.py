"""Account identity, company isolation, invite lifecycle and recovery boundaries."""

import concurrent.futures
import io
import json
from pathlib import Path
import sqlite3
import time
import unittest
from unittest.mock import patch

from atmet_brain import Brain, BrainError
from atmet_brain.accounts import SESSION_SECONDS, hash_password, recover_owner, verify_password
from atmet_brain.auth import ROLES
from atmet_brain.backups import generate_backup_key
from atmet_brain.db import SCHEMA_VERSION, Store
from atmet_brain.rpc import dispatch, dispatch_auth
from tests import test_terminal_team as fixtures

PASSWORD = "Distinct fictional passphrase 2026!"
NEW_PASSWORD = "Another fictional passphrase 2026!"


class AccountCase(unittest.TestCase):
    setUp = fixtures.TerminalTeamCase.setUp

    def fails(self, code, operation, *args, **kwargs):
        with self.assertRaises(BrainError) as caught:
            operation(*args, **kwargs)
        self.assertEqual(code, caught.exception.code)
        return caught.exception

    def invite(self, login="alex@example.test", access=None, **kwargs):
        return self.brain.create_invite(self.actor, login, "Alex",
                                       access or [{"space_id": self.sales, "role": "reader"}], **kwargs)

    def accept(self, invitation=None, password=PASSWORD):
        invitation = invitation or self.invite()
        return self.brain.accept_invite(invitation["organization_id"], invitation["id"], invitation["secret"], password)

    def member(self, principal):
        return next(m for m in self.brain.list_members(self.actor) if m["id"] == principal)

    def test_owner_enrolls_and_password_login_retains_admin_with_explicit_content_grants(self):
        self.brain.setup_account(self.actor, "Owner@Example.test", PASSWORD)
        issued = self.brain.login("company", "OWNER@example.test", PASSWORD)
        actor = self.brain.authenticate(issued["token"])
        self.assertEqual(self.actor.principal_id, actor.principal_id)
        self.assertEqual("owner@example.test", self.brain.whoami(actor)["username"])
        self.assertGreater(issued["expires_at"], time.time())
        self.assertLessEqual(issued["expires_at"], time.time() + SESSION_SECONDS)
        self.assertTrue(self.brain.check_access(actor, self.sales)["can_add_members"])
        self.assertEqual(2, len(self.brain.list_spaces(actor)))

    def test_passwords_and_invite_secrets_are_not_in_database_or_audit(self):
        invitation = self.invite()
        self.accept(invitation)
        with self.brain.store.transaction() as conn:
            encoded = conn.execute("SELECT password_hash FROM user_accounts").fetchone()[0]
            audit = " ".join(r[0] for r in conn.execute("SELECT details FROM audit_events"))
            stored = conn.execute("SELECT secret_hash FROM company_invites").fetchone()[0]
        self.assertNotIn(PASSWORD, encoded + audit)
        self.assertNotIn(invitation["secret"], stored + audit)
        self.assertTrue(verify_password(PASSWORD, encoded))
        self.assertNotEqual(encoded, hash_password(PASSWORD))

    def test_single_use_invite_enrolls_only_bound_principal_and_scopes(self):
        invitation = self.invite()
        self.fails("invalid_login", self.brain.login, "company", "alex@example.test", PASSWORD)
        issued = self.accept(invitation)
        actor = self.brain.authenticate(issued["token"])
        self.assertEqual([self.sales], [s["id"] for s in self.brain.list_spaces(actor)])
        self.fails("forbidden", self.brain.get_context, actor, self.finance, "salaries")
        self.fails("invalid_invite", self.accept, invitation)
        with self.brain.store.transaction() as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM user_accounts").fetchone()[0])

    def test_concurrent_accept_has_one_winner(self):
        invitation = self.invite()
        def accept():
            try:
                return self.accept(invitation)["principal_id"]
            except BrainError as error:
                return error.code
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            values = list(pool.map(lambda _: accept(), range(2)))
        self.assertEqual(1, values.count("invalid_invite"))
        with self.brain.store.transaction() as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM user_accounts").fetchone()[0])

    def test_invite_expiry_revocation_wrong_secret_and_issuer_revocation(self):
        first = self.invite()
        self.fails("invalid_invite", self.brain.accept_invite, first["organization_id"], first["id"], "wrong-secret-with-valid-length", PASSWORD)
        self.brain.revoke_invite(self.actor, first["id"])
        self.fails("invalid_invite", self.accept, first)
        second = self.invite("second")
        with self.brain.store.transaction(write=True) as conn:
            conn.execute("UPDATE company_invites SET expires_at=1 WHERE id=?", (second["id"],))
        self.fails("invalid_invite", self.accept, second)
        third = self.invite("third")
        self.brain.revoke_credential(self.actor, self.actor.credential_id)
        self.fails("unauthenticated", self.accept, third)

    def test_reissuing_invitation_invalidates_the_old_one(self):
        first, second = self.invite(), self.invite()
        self.fails("invalid_invite", self.accept, first)
        self.assertTrue(self.accept(second)["token"])

    def test_invitations_cannot_grant_owner_foreign_spaces_or_outlive_issuer(self):
        self.fails("invalid_access", self.invite, access=[{"space_id": self.sales, "role": "owner"}])
        other = self.brain.provision_organization("other")
        actor = self.brain.authenticate(other["token"])
        foreign = self.brain.create_space(actor, "private")["id"]
        self.fails("not_found", self.invite, access=[{"space_id": foreign, "role": "reader"}])
        self.fails("invalid_expiry", self.invite, expires_at=time.time() + 8 * 86400)
        with self.brain.store.transaction(write=True) as conn:
            conn.execute("UPDATE credentials SET expires_at=? WHERE id=?", (time.time() + 60, self.actor.credential_id))
        self.fails("invalid_expiry", self.invite, expires_at=time.time() + 120)
        self.assertLessEqual(self.invite()["expires_at"], time.time() + 60)

    def test_non_admin_cannot_enroll_owner_invite_or_list_employees(self):
        issued = self.accept()
        actor = self.brain.authenticate(issued["token"])
        self.fails("forbidden", self.brain.setup_account, actor, "reader", PASSWORD)
        self.fails("forbidden", self.brain.create_invite, actor, "other", "Other", [{"space_id": self.sales, "role": "reader"}])
        self.fails("forbidden", self.brain.list_members, actor)
        self.fails("forbidden", self.brain.list_invites, actor)

    def test_wrong_and_unknown_passwords_have_generic_errors_and_no_account_creation(self):
        self.accept()
        for login, password in [("alex@example.test", "Wrong fictional passphrase 2026!"), ("unknown", PASSWORD)]:
            error = self.fails("invalid_login", self.brain.login, "company", login, password)
            self.assertEqual("Invalid company, username or password.", error.message)
            self.assertNotIn(login, error.message)
        self.fails("invalid_login", self.brain.login, "unknown-company", "alex@example.test", PASSWORD)

    def test_attempt_limits_persist_across_restart_and_company_aliases(self):
        self.accept()
        for attempt in range(8):
            company = "company" if attempt % 2 else self.actor.org_id
            self.fails("invalid_login", self.brain.login, company, "alex@example.test", NEW_PASSWORD)
        restarted = Brain(self.home)
        self.fails("auth_rate_limited", restarted.login, "company", "alex@example.test", PASSWORD)
        with restarted.store.transaction(write=True) as conn:
            conn.execute("UPDATE auth_attempts SET window_start=1")
        self.assertTrue(restarted.login("company", "alex@example.test", PASSWORD)["token"])

    def test_weak_short_and_overlong_passwords_are_rejected_without_consuming_invite(self):
        invitation = self.invite()
        for password in ["short", "a" * 30, "passwordpassword", "x" * 129]:
            with self.assertRaises(BrainError):
                self.accept(invitation, password)
        self.assertTrue(self.accept(invitation)["token"])

    def test_identical_usernames_in_different_companies_do_not_cross_authenticate(self):
        first = self.accept()
        other = self.brain.provision_organization("other")
        admin = self.brain.authenticate(other["token"])
        space = self.brain.create_space(admin, "finance")["id"]
        invitation = self.brain.create_invite(admin, "alex@example.test", "Other Alex", [{"space_id": space, "role": "reader"}])
        second = self.accept(invitation, NEW_PASSWORD)
        self.assertNotEqual(first["principal_id"], second["principal_id"])
        self.fails("invalid_login", self.brain.login, "other", "alex@example.test", PASSWORD)
        self.fails("forbidden", self.brain.set_member_access, self.actor, second["principal_id"], [], 1)
        self.fails("forbidden", self.brain.disable_member, self.actor, second["principal_id"])

    def test_per_workspace_roles_do_not_cross_elevate_and_payroll_stays_private(self):
        invitation = self.invite(access=[{"space_id": self.sales, "role": "reader"}, {"space_id": self.finance, "role": "publisher"}])
        issued = self.accept(invitation)
        actor = self.brain.authenticate(issued["token"])
        self.assertNotIn("publish", self.brain.check_access(actor, self.sales)["operations"])
        self.assertIn("publish", self.brain.check_access(actor, self.finance)["operations"])
        secret = self.brain.put_source(self.actor, self.finance, "payroll", "Payroll", "Fictional payroll", audience=["principal:" + self.actor.principal_id])
        self.fails("not_found", self.brain.get_source, actor, secret["id"])
        self.assertNotIn(secret["id"], [s["id"] for s in self.brain.list_sources(actor, self.finance)])

    def test_membership_change_revokes_old_sessions_and_agent_children_then_login_uses_new_scope(self):
        issued = self.accept()
        actor = self.brain.authenticate(issued["token"])
        child = self.brain.create_credential(actor, operations=["read"], space_ids=[self.sales])
        record = self.member(actor.principal_id)
        updated = self.brain.set_member_access(self.actor, actor.principal_id, [{"space_id": self.finance, "role": "reporter"}], record["revision"])
        self.assertTrue(updated["sessions_revoked"])
        self.fails("unauthenticated", self.brain.authenticate, issued["token"])
        self.fails("unauthenticated", self.brain.authenticate, child["token"])
        fresh = self.brain.login("company", "alex@example.test", PASSWORD)
        actor = self.brain.authenticate(fresh["token"])
        self.assertEqual([self.finance], [s["id"] for s in self.brain.list_spaces(actor)])
        self.fails("forbidden", self.brain.get_context, actor, self.sales, "old")

    def test_empty_membership_blocks_login_and_cannot_modify_admin(self):
        issued = self.accept()
        self.brain.set_member_access(self.actor, issued["principal_id"], [], 1)
        self.fails("no_access", self.brain.login, "company", "alex@example.test", PASSWORD)
        self.fails("forbidden", self.brain.set_member_access, self.actor, self.actor.principal_id, [], 0)
        self.fails("forbidden", self.brain.disable_member, self.actor, self.actor.principal_id)

    def test_manual_grant_updates_invalidate_stale_membership_and_reset_reviews(self):
        issued = self.accept()
        invitation = self.invite(reset_principal=issued["principal_id"])
        grant = self.brain.grant(self.actor, issued["principal_id"], self.finance, ["read"])
        self.fails("revision_conflict", self.brain.set_member_access, self.actor, issued["principal_id"], [], 1)
        self.fails("invalid_invite", self.accept, invitation)
        before = self.member(issued["principal_id"])["revision"]
        self.brain.revoke_grant(self.actor, grant["id"])
        self.assertGreater(self.member(issued["principal_id"])["revision"], before)

    def test_password_change_revokes_every_old_credential_and_requires_new_password(self):
        issued = self.accept()
        actor = self.brain.authenticate(issued["token"])
        other = self.brain.login("company", "alex@example.test", PASSWORD)
        changed = self.brain.change_password(actor, PASSWORD, NEW_PASSWORD)
        for value in [issued, other]:
            self.fails("unauthenticated", self.brain.authenticate, value["token"])
        self.assertEqual(actor.principal_id, self.brain.authenticate(changed["token"]).principal_id)
        self.fails("invalid_login", self.brain.login, "company", "alex@example.test", PASSWORD)
        self.assertTrue(self.brain.login("company", "alex@example.test", NEW_PASSWORD)["token"])

    def test_reset_keeps_principal_and_replaces_password_sessions_and_access(self):
        first = self.accept()
        invitation = self.invite(access=[{"space_id": self.finance, "role": "reader"}], reset_principal=first["principal_id"])
        second = self.accept(invitation, NEW_PASSWORD)
        self.assertEqual(first["principal_id"], second["principal_id"])
        self.fails("unauthenticated", self.brain.authenticate, first["token"])
        self.assertEqual([self.finance], [s["id"] for s in self.brain.list_spaces(self.brain.authenticate(second["token"]))])

    def test_legacy_human_is_enrolled_without_duplicate_identity(self):
        member = self.brain.add_team_member(self.actor, "Legacy employee", [self.sales], "reader")
        invitation = self.invite(reset_principal=member["principal_id"])
        result = self.accept(invitation)
        self.assertEqual(member["principal_id"], result["principal_id"])
        self.fails("unauthenticated", self.brain.authenticate, member["token"])

    def test_disabled_employee_cannot_login_or_use_old_keys_and_needs_explicit_reinvite(self):
        first = self.accept()
        group = self.brain.create_group(self.actor, "Restricted payroll", [first["principal_id"], self.actor.principal_id])
        private = self.brain.put_source(self.actor, self.sales, "payroll", "Payroll", "Fictional payroll", audience=["group:" + group["id"]])
        pending = self.invite(reset_principal=first["principal_id"])
        self.brain.disable_member(self.actor, first["principal_id"])
        self.fails("invalid_login", self.brain.login, "company", "alex@example.test", PASSWORD)
        self.fails("unauthenticated", self.brain.authenticate, first["token"])
        self.fails("invalid_invite", self.accept, pending)
        renewed = self.invite(reset_principal=first["principal_id"])
        refreshed = self.accept(renewed)
        self.assertEqual(first["principal_id"], refreshed["principal_id"])
        self.assertEqual([], self.member(first["principal_id"])["groups"])
        self.fails("not_found", self.brain.get_source, self.brain.authenticate(refreshed["token"]), private["id"])

    def test_expiry_and_grant_revocation_apply_to_existing_login_actor(self):
        issued = self.accept()
        actor = self.brain.authenticate(issued["token"])
        with self.brain.store.transaction(write=True) as conn:
            conn.execute("UPDATE credentials SET expires_at=1 WHERE id=?", (actor.credential_id,))
        self.fails("unauthenticated", self.brain.list_spaces, actor)

    def test_auth_dispatch_rejects_forged_identity_role_and_wrong_endpoints(self):
        self.accept()
        for extra in [{"actor": "owner"}, {"role": "owner"}, {"principal_id": self.actor.principal_id}]:
            self.fails("invalid_auth", dispatch_auth, self.brain, "login", {"organization": "company", "username_value": "alex@example.test", "password": PASSWORD, **extra})
        self.fails("invalid_auth", dispatch_auth, self.brain, "members.list", {})
        self.fails("unknown_method", dispatch, self.brain, self.actor, "login", {})

    def test_schema_two_upgrade_preserves_existing_sources_tokens_and_members(self):
        source = self.brain.put_source(self.actor, self.sales, "catalogue", "Catalogue", "Fictional catalogue")
        with self.brain.store.transaction(write=True) as conn:
            for table in ["user_accounts", "company_invites", "member_versions", "auth_attempts"]:
                conn.execute("DROP TABLE " + table)
            conn.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
        restarted = Brain(self.home)
        actor = restarted.authenticate(self.owner["token"])
        self.assertEqual(source["id"], restarted.get_source(actor, source["id"])["id"])
        with restarted.store.transaction() as conn:
            self.assertEqual(str(SCHEMA_VERSION), conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])

    def test_restore_disables_passwords_invites_and_sessions_before_and_after_recovery(self):
        first = self.accept()
        invitation = self.invite("pending")
        key = self.root / "backup.key"; backup = self.root / "backup.atmet"
        generate_backup_key(key)
        self.brain.create_backup(backup, key)
        self.brain.disable_member(self.actor, first["principal_id"])
        journal = self.brain.flush_recovery_journal()["path"]
        destination = self.root / "restored"
        Brain.restore_backup(backup, destination, key)
        restored = Brain(destination)
        self.fails("unavailable", restored.login, "company", "alex@example.test", PASSWORD)
        restored.finish_recovery(journal, "Recovery owner", True)
        self.fails("invalid_login", restored.login, "company", "alex@example.test", PASSWORD)
        self.fails("invalid_invite", restored.accept_invite, invitation["organization_id"], invitation["id"], invitation["secret"], PASSWORD)
        self.fails("unauthenticated", restored.authenticate, first["token"])
        with restored.store.transaction() as conn:
            self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM user_accounts WHERE enabled=1 OR password_hash!=''").fetchone()[0])

    def test_schema_three_migration_rolls_back_if_auth_table_creation_fails(self):
        with self.brain.store.transaction(write=True) as conn:
            for table in ["user_accounts", "company_invites", "member_versions", "auth_attempts"]:
                conn.execute("DROP TABLE " + table)
            conn.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
        def denied(store):
            conn = sqlite3.connect(store.path, isolation_level=None); conn.row_factory = sqlite3.Row
            conn.set_authorizer(lambda action, name, *rest: sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_TABLE and name == "user_accounts" else sqlite3.SQLITE_OK)
            return conn
        with patch.object(Store, "connect", denied), self.assertRaises(sqlite3.DatabaseError):
            Store(self.home)
        with sqlite3.connect(self.home / "brain.sqlite3") as conn:
            self.assertEqual("2", conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
            self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='user_accounts'").fetchone())

    def test_local_owner_recovery_is_not_rpc_and_replaces_password_and_operator_authority(self):
        self.brain.setup_account(self.actor, "owner", PASSWORD)
        login = self.brain.login("company", "owner", PASSWORD)
        self.fails("unknown_method", dispatch, self.brain, self.actor, "accounts.recover", {})
        result = recover_owner(self.brain, "owner", NEW_PASSWORD)
        self.fails("unauthenticated", self.brain.authenticate, self.owner["token"])
        self.fails("unauthenticated", self.brain.authenticate, login["token"])
        operator = self.brain.authenticate(result["token"])
        self.assertIsNone(self.brain.whoami(operator)["expires_at"])
        self.assertTrue(self.brain.check_access(operator, self.sales)["can_add_members"])
        self.assertTrue(self.brain.login("company", "owner", NEW_PASSWORD)["token"])

    def test_reset_invitation_cannot_enroll_admin_service_or_rename_existing_login(self):
        service = self.brain.add_team_member(self.actor, "Service", [self.sales], "reader", kind="service")
        self.brain.setup_account(self.actor, "owner", PASSWORD)
        for target in [self.actor.principal_id, service["principal_id"]]:
            self.fails("account_exists", self.invite, reset_principal=target)
        first = self.accept()
        self.fails("account_exists", self.invite, "renamed", reset_principal=first["principal_id"])

    def test_concurrent_membership_reviews_have_one_atomic_winner(self):
        issued = self.accept()
        def update(space):
            try:
                return self.brain.set_member_access(self.actor, issued["principal_id"], [{"space_id": space, "role": "reader"}], 1)["revision"]
            except BrainError as error:
                return error.code
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(update, [self.sales, self.finance]))
        self.assertCountEqual([2, "revision_conflict"], results)
        self.assertEqual(1, len(self.member(issued["principal_id"])["access"]))
