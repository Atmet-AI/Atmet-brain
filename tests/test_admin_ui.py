"""Human terminal approval and usable administration bundles."""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from atmet_brain import BrainError
from atmet_brain.cli import execute, parser
from atmet_brain.mcp import MCPServer
from tests import test_administration as fixtures
PASSWORD = fixtures.PASSWORD


class AdminUICase(unittest.TestCase):
    setUp = fixtures.AdministrationCase.setUp
    propose = fixtures.AdministrationCase.propose
    source = fixtures.AdministrationCase.source
    fails = fixtures.AdministrationCase.fails
    approve = fixtures.AdministrationCase.approve

    def args(self, *values):
        from atmet_brain.util import private_write
        private_write(self.home / "human.token", self.session["token"] + "\n")
        return parser().parse_args(["--home",str(self.home),"--token-file",str(self.home / "human.token"),*values])

    def test_review_requires_actual_human_interaction_and_hidden_password(self):
        change=self.propose("spaces.create",{"name":"marketing"})
        with patch("sys.stdin.isatty",return_value=True),patch("builtins.input",side_effect=["yes"]),patch("getpass.getpass",return_value=PASSWORD) as password,contextlib.redirect_stderr(io.StringIO()) as screen:
            result=execute(self.args("admin","review",change["id"]))
        self.assertEqual("applied",result["state"]);self.assertEqual(1,password.call_count)
        self.assertNotIn(PASSWORD,screen.getvalue());self.assertIn("marketing",screen.getvalue())

    def test_no_noninteractive_approval_flag_and_no_agent_self_approval(self):
        change=self.propose("spaces.create",{"name":"marketing"})
        self.fails("human_review_required",execute,self.args("--json","admin","review",change["id"]))
        token=self.home/"control.token";token.write_text(self.control["token"])
        with patch("sys.stdin.isatty",return_value=True),patch("builtins.input",return_value="yes"),patch("getpass.getpass",return_value=PASSWORD),contextlib.redirect_stderr(io.StringIO()):
            self.fails("forbidden",execute,self.args("--token-file",str(token),"admin","review",change["id"]))
        self.assertEqual("pending",self.brain.get_admin_change(self.human,change["id"])["state"])

    def test_cancel_leaves_request_pending_without_reading_password(self):
        change=self.propose("spaces.create",{"name":"marketing"})
        with patch("sys.stdin.isatty",return_value=True),patch("builtins.input",return_value="cancel"),patch("getpass.getpass") as password,contextlib.redirect_stderr(io.StringIO()):
            result=execute(self.args("admin","review",change["id"]))
        self.assertFalse(result["applied"]);password.assert_not_called()

    def test_classification_wizard_reviews_the_exact_source(self):
        source=self.source("Reviewed fictional budget","budget")
        with patch("sys.stdin.isatty",return_value=True),patch("builtins.input",side_effect=["Reviewed budget","space","yes"]),patch("getpass.getpass",return_value=PASSWORD),contextlib.redirect_stderr(io.StringIO()) as screen:
            result=execute(self.args("admin","classify",source["id"]))
        self.assertEqual("applied",result["state"])
        self.assertIn("Reviewed fictional budget",screen.getvalue())
        self.assertEqual("Reviewed fictional budget",self.brain.get_source(self.reader,source["id"])["content"])

    def test_agent_bundle_has_narrowed_private_token_and_live_admin_tools(self):
        result=execute(self.args("--json","admin","agent","--name","company-helper"))
        self.assertTrue(result["approval_required"])
        entry=result["mcp_entry"]["mcpServers"]["atmet-admin"]
        self.assertIn("--allow-admin",entry["args"])
        folder=Path(result["directory"]);token=(folder/"control.token").read_text().strip()
        self.assertEqual(0o600,(folder/"control.token").stat().st_mode&0o777)
        actor=self.brain.authenticate(token);self.fails("forbidden",self.brain.create_space,actor,"forged")
        messages='\n'.join(json.dumps(x) for x in [{"jsonrpc":"2.0","id":1,"method":"initialize"},{"jsonrpc":"2.0","id":2,"method":"tools/list"}])+'\n'
        process=subprocess.run([entry["command"],*entry["args"]],input=messages,text=True,capture_output=True,timeout=20)
        self.assertEqual(0,process.returncode,process.stderr)
        replies=[json.loads(x) for x in process.stdout.splitlines()]
        self.assertIn("brain_propose_admin_change",[t["name"] for t in replies[-1]["result"]["tools"]])
        self.assertIn("Never request the human's password",(folder/"agent-instructions.md").read_text())
        self.assertNotIn(token,json.dumps(result));self.assertNotIn(PASSWORD,json.dumps(result))

    def test_readers_cannot_prepare_administration_bundle(self):
        file=self.home/"reader.token";file.write_text(self.employee["token"])
        self.fails("forbidden",execute,self.args("--token-file",str(file),"--json","admin","agent","--name","forged"))
        self.assertFalse((self.home/"agents/forged").exists())

    def test_admin_mcp_opt_in_does_not_grant_reader_privileges(self):
        mcp=MCPServer(self.brain,self.employee["token"],allow_admin=True)
        mcp.handle({"jsonrpc":"2.0","id":1,"method":"initialize"})
        response=mcp.handle({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"brain_admin_overview","arguments":{}}})
        self.assertTrue(response["result"]["isError"])

    def test_overview_exposes_only_validated_host_route_and_no_private_key(self):
        (self.home/"hosting.json").write_text(json.dumps({"endpoint":None,"ssh":{"destination":"forward@brain.example.test","port":7310},"private_key":"fictional-should-not-be-returned"}))
        result=self.brain.admin_overview(self.agent)
        self.assertEqual("forward@brain.example.test",result["hosting"]["ssh"]["destination"])
        self.assertNotIn("fictional-should-not-be-returned",json.dumps(result))

    def test_mcp_schema_has_document_submission_without_review_password(self):
        server=MCPServer(self.brain,self.control["token"],allow_admin=True,allow_writes=True)
        server.handle({"jsonrpc":"2.0","id":1,"method":"initialize"})
        result=server.handle({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"brain_submit_document","arguments":{"space_id":self.finance,"external_id":"new-source","title":"Budget","content":"Fictional invoice"}}})
        self.assertFalse(result["result"]["isError"])
        receipt=json.loads(result["result"]["content"][0]["text"])
        self.assertEqual("pending_classification",receipt["status"])
        self.assertEqual([],self.brain.list_sources(self.reader,self.finance))
