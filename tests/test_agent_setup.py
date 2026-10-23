"""Guided agent setup, least privilege, private output and real transports."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from atmet_brain import BrainError
from atmet_brain.agent_setup import pick_spaces
from atmet_brain.cli import execute, parser
from atmet_brain.connections import connect
from atmet_brain.feedback import LocalClient
from atmet_brain.rpc import dispatch
from atmet_brain.terminal import Console
from tests import test_terminal_team as fixtures


class AgentSetupCase(unittest.TestCase):
    setUp = fixtures.TerminalTeamCase.setUp
    server = fixtures.TerminalTeamCase.server
    cli = fixtures.TerminalTeamCase.cli

    def args(self, name='test-agent', **changes):
        values=['--json','--home',str(self.home),'agent','--name',name,'--method','mcp',
                '--spaces','sales','--access','learn','--identity','new']
        args=parser().parse_args(values)
        for key,value in changes.items():setattr(args,key,value)
        return args

    def fails(self, code, function, *args, **kwargs):
        with self.assertRaises(BrainError) as caught:function(*args,**kwargs)
        self.assertEqual(code,caught.exception.code)
        return caught.exception

    def source(self):
        return self.brain.put_source(self.actor,self.sales,'catalogue','Catalogue','Fictional catalogue for quotation drafts')

    def mcp(self, result, messages):
        config=json.loads(Path(result['mcp_config']).read_text())['mcpServers']['atmet-brain']
        env={k:v for k,v in os.environ.items() if k not in {'ATMET_TOKEN','ATMET_TOKEN_FILE','ATMET_HOME'}}
        data='\n'.join(json.dumps(x) for x in messages)+'\n'
        child=subprocess.run([config['command'],*config['args']],input=data,capture_output=True,text=True,env=env,timeout=30)
        self.assertEqual(0,child.returncode,child.stderr)
        return [json.loads(line) for line in child.stdout.splitlines()]

    def test_new_mcp_bundle_has_scoped_service_no_secret_output_and_private_files(self):
        result=execute(self.args())
        token=Path(result['token_file']).read_text().strip()
        actor=self.brain.authenticate(token)
        identity=self.brain.whoami(actor)
        self.assertEqual('service',identity['kind'])
        self.assertNotEqual(self.actor.principal_id,actor.principal_id)
        self.assertEqual([self.sales],identity['credential_spaces'])
        self.assertEqual({'read','observe','contribute','history'},set(identity['credential_operations']))
        self.assertNotIn(token,json.dumps(result))
        directory=Path(result['directory'])
        self.assertEqual(0o700,directory.stat().st_mode & 0o777)
        for path in directory.iterdir():
            self.assertEqual(0o600,path.stat().st_mode & 0o777)
            if path.name!='agent.token':self.assertNotIn(token,path.read_text())
        self.assertEqual(['sales'],result['workspaces'])
        self.fails('forbidden',self.brain.get_context,actor,self.finance,'restricted')
        self.assertNotIn('publish',self.brain.check_access(actor,self.sales)['operations'])

    def test_generated_mcp_reports_and_drafts_with_separate_publisher(self):
        source=self.source();result=execute(self.args())
        arguments=dict(space_id=self.sales,report_key='wizard-completion',task_key='quotation',summary='Prepared draft',
                       outcome='succeeded',result='Safe draft ready',steps=['Read catalogue'],audience=['space'],
                       evidence=[{'source_id':source['id'],'revision':1}])
        replies=self.mcp(result,[{'jsonrpc':'2.0','id':1,'method':'initialize'},
                                {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'brain_complete_task','arguments':arguments}}])
        names={t['name'] for t in replies[1]['result']['tools']}
        self.assertIn('brain_propose_artifact',names);self.assertIn('brain_complete_task',names)
        self.assertFalse(any('review' in name or 'publish' in name for name in names))
        completion=json.loads(replies[2]['result']['content'][0]['text'])
        self.assertEqual('pending_review',completion['skill']['status'])
        actor=self.brain.authenticate(Path(result['token_file']).read_text().strip())
        self.fails('forbidden',self.brain.review_artifact,actor,completion['skill']['id'],1,True,'Denied')
        self.brain.review_artifact(self.actor,completion['skill']['id'],1,True,'Reviewed method and evidence')

    def test_read_mode_exposes_no_proposal_or_completion_tools(self):
        result=execute(self.args(access='read'))
        replies=self.mcp(result,[{'jsonrpc':'2.0','id':1,'method':'initialize'},{'jsonrpc':'2.0','id':2,'method':'tools/list'}])
        names={t['name'] for t in replies[1]['result']['tools']}
        self.assertNotIn('brain_complete_task',names);self.assertNotIn('brain_propose_artifact',names)
        actor=self.brain.authenticate(Path(result['token_file']).read_text().strip())
        self.assertEqual(['read'],self.brain.check_access(actor,self.sales)['operations'])

    def test_current_identity_child_is_narrowed_and_parent_revocation_applies(self):
        result=execute(self.args(identity='current',access='read'))
        child=self.brain.authenticate(Path(result['token_file']).read_text().strip())
        self.assertEqual(self.actor.principal_id,child.principal_id)
        self.assertEqual(['read'],self.brain.whoami(child)['credential_operations'])
        self.fails('forbidden',self.brain.create_space,child,'new-space')
        self.brain.revoke_credential(self.actor,self.actor.credential_id)
        self.fails('unauthenticated',self.brain.check_access,child,self.sales)

    def test_existing_reporter_can_create_only_a_narrower_current_identity(self):
        member=self.brain.add_team_member(self.actor,'Existing reporter',[self.sales],'reporter',kind='service')
        path=self.root/'existing.token';path.write_text(member['token'])
        result=execute(self.args(identity='current',token_file=path,access='read'))
        self.assertEqual(member['principal_id'],result['identity']['principal_id'])
        self.assertEqual(['read'],result['identity']['credential_operations'])
        self.fails('forbidden',execute,self.args('no-new-member',identity='new',token_file=path))

    def test_read_credential_cannot_enable_learning_and_no_child_is_issued(self):
        member=self.brain.add_team_member(self.actor,'Reader',[self.sales],'reader')
        path=self.root/'reader.token';path.write_text(member['token'])
        with self.brain.store.transaction() as conn:before=conn.execute('SELECT COUNT(*) FROM credentials').fetchone()[0]
        self.fails('forbidden',execute,self.args(identity='current',token_file=path))
        with self.brain.store.transaction() as conn:self.assertEqual(before,conn.execute('SELECT COUNT(*) FROM credentials').fetchone()[0])
        self.assertFalse((self.home/'agents/test-agent').exists())

    def test_invalid_or_missing_answers_leave_no_setup_or_credentials(self):
        with self.brain.store.transaction() as conn:before=conn.execute('SELECT COUNT(*) FROM credentials').fetchone()[0]
        for changes in [{'spaces':'unknown'},{'spaces':'sales,sales'},{'method':None},{'access':None},{'identity':None},{'name':'../../escape'}]:
            with self.assertRaises(BrainError):execute(self.args(**changes))
        with self.brain.store.transaction() as conn:self.assertEqual(before,conn.execute('SELECT COUNT(*) FROM credentials').fetchone()[0])
        self.assertFalse((self.home/'agents').exists())

    def test_existing_destination_and_symlink_are_never_overwritten(self):
        existing=self.root/'existing';existing.mkdir();marker=existing/'keep';marker.write_text('original')
        self.fails('already_exists',execute,self.args(output=existing))
        link=self.root/'link';link.symlink_to(self.root/'absent',target_is_directory=True)
        self.fails('already_exists',execute,self.args(output=link))
        self.assertEqual('original',marker.read_text())

    def test_interactive_names_review_and_human_ready_screen(self):
        args=parser().parse_args(['--home',str(self.home),'--plain','agent'])
        with patch('sys.stdin.isatty',return_value=True),patch('builtins.input',side_effect=['local','mcp','sales','learn','new','sales-helper','yes']),contextlib.redirect_stderr(io.StringIO()) as err:
            result=execute(args)
        self.assertIn('Review before creating access',err.getvalue())
        self.assertIn('#1',err.getvalue())
        screen=io.StringIO();Console(screen,plain=True).agent_ready(result)
        self.assertIn('Core access verified',screen.getvalue())
        self.assertIn('mcp.json',screen.getvalue())
        self.assertNotIn(Path(result['token_file']).read_text().strip(),screen.getvalue())

    def test_interactive_cancel_and_eof_issue_no_credential(self):
        for last,code in [('no','setup_cancelled'),(EOFError(),'setup_interrupted')]:
            args=parser().parse_args(['--home',str(self.home),'agent'])
            with patch('sys.stdin.isatty',return_value=True),patch('builtins.input',side_effect=['local','mcp','sales','read','new','cancel-agent',last]),contextlib.redirect_stderr(io.StringIO()):
                self.fails(code,execute,args)
        self.assertFalse((self.home/'agents').exists())

    def test_interactive_reader_is_offered_only_read_access(self):
        member=self.brain.add_team_member(self.actor,'Reader',[self.sales],'reader')
        token=self.root/'reader.token';token.write_text(member['token'])
        args=parser().parse_args(['--home',str(self.home),'--token-file',str(token),'agent'])
        with patch('sys.stdin.isatty',return_value=True),patch('builtins.input',side_effect=['local','mcp','sales','read','current','reader-helper','yes']),contextlib.redirect_stderr(io.StringIO()) as screen:
            result=execute(args)
        self.assertNotIn('Report results and draft skills',screen.getvalue())
        self.assertEqual('read',result['access'])

    def test_workspace_numbers_are_unambiguous_with_numeric_names(self):
        available=[{'id':'a','slug':'1'},{'id':'b','slug':'10'},{'id':'c','slug':'2'}]
        self.assertEqual('b',pick_spaces('#2',available)[0]['id'])
        self.assertEqual('c',pick_spaces('2',available)[0]['id'])
        self.fails('invalid_spaces',pick_spaces,'#2,10',available)

    def test_core_access_check_is_self_scoped_and_rechecks_live_grants(self):
        member=self.brain.add_team_member(self.actor,'Reader',[self.sales],'reader')
        actor=self.brain.authenticate(member['token'])
        result=dispatch(self.brain,actor,'access.check',{'space_id':self.sales})
        self.assertEqual(['read'],result['operations']);self.assertFalse(result['can_add_members'])
        self.fails('forbidden',self.brain.check_access,actor,self.finance)
        self.fails('invalid_params',dispatch,self.brain,actor,'access.check',{'space_id':self.sales,'principal_id':self.actor.principal_id})
        self.brain.revoke_credential(self.actor,member['credential_id'])
        self.fails('unauthenticated',self.brain.check_access,actor,self.sales)

    def test_explicit_token_file_wins_over_ambient_owner_token(self):
        member=self.brain.add_team_member(self.actor,'Reader',[self.sales],'reader')
        path=self.root/'reader.token';path.write_text(member['token'])
        args=parser().parse_args(['--home',str(self.home),'--token-file',str(path),'rpc','identity.me'])
        with patch.dict(os.environ,{'ATMET_TOKEN':self.owner['token']}):
            self.assertEqual(member['principal_id'],execute(args)['principal_id'])
        with patch.dict(os.environ,{'ATMET_TOKEN':self.owner['token']}):
            self.fails('forbidden',execute,self.args(token_file=path,identity='current'))

    def test_generated_mcp_keeps_its_scope_with_an_ambient_owner_token(self):
        result=execute(self.args(access='read'))
        config=result['mcp_entry']['mcpServers']['atmet-brain']
        messages='\n'.join(json.dumps(x) for x in [{'jsonrpc':'2.0','id':1,'method':'initialize'},
            {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'brain_list_spaces','arguments':{}}}])+'\n'
        env=dict(os.environ,ATMET_TOKEN=self.owner['token'])
        process=subprocess.run([config['command'],*config['args']],input=messages,text=True,capture_output=True,env=env,timeout=20)
        replies=[json.loads(line) for line in process.stdout.splitlines()]
        spaces=json.loads(replies[1]['result']['content'][0]['text'])
        self.assertEqual([self.sales],[space['id'] for space in spaces])

    def test_old_server_preflight_has_a_clear_upgrade_message_before_issuing_credentials(self):
        original=LocalClient.call
        def old_server(client,method,**params):
            if method=='access.check':raise BrainError('unknown_method','Unknown operation',404)
            return original(client,method,**params)
        with patch.object(LocalClient,'call',old_server):
            self.fails('server_upgrade_required',execute,self.args())
        self.assertFalse((self.home/'agents').exists())

    def test_local_rest_and_python_outputs_are_usable_without_starting_services(self):
        self.source()
        for method in ['rest','python','terminal']:
            result=execute(self.args(name=method,method=method,access='read'))
            self.assertFalse(result['external_agent_verified'])
            self.assertEqual('context.get',json.loads((Path(result['directory'])/'request.json').read_text())['method'])
            if method=='python':
                p=subprocess.run([sys.executable,str(Path(result['directory'])/'agent.py')],capture_output=True,text=True,timeout=15)
                self.assertEqual(0,p.returncode,p.stderr)
            if method=='rest':self.assertIn('Start the local API',result['next'][0])
            if method=='terminal':
                import shlex
                command=result['next'][0].split('Run this scoped context command: ',1)[1]
                process=subprocess.run(shlex.split(command),capture_output=True,text=True,timeout=15)
                self.assertEqual(0,process.returncode,process.stderr)
                self.assertEqual(self.sales,json.loads(process.stdout)['space_id'])

    def test_failed_bundle_write_revokes_new_credential_and_preserves_existing_data(self):
        from atmet_brain import agent_setup
        original=agent_setup.private_write
        def denied(path,*args,**kwargs):
            if Path(path).name=='mcp.json':raise OSError('fixture disk failure')
            return original(path,*args,**kwargs)
        with patch.object(agent_setup,'private_write',side_effect=denied):
            self.fails('agent_setup_incomplete',execute,self.args())
        with self.brain.store.transaction() as conn:
            row=conn.execute("SELECT c.revoked FROM credentials c JOIN principals p ON p.id=c.principal_id WHERE p.name='test-agent'").fetchone()
            self.assertEqual(1,row[0])
        self.assertFalse((self.home/'agents/test-agent/agent.token').exists())
        self.assertEqual(2,len(self.brain.list_spaces(self.actor)))

    def test_child_expiry_does_not_exceed_a_short_lived_issuer(self):
        import time
        expiry=time.time()+600
        with self.brain.store.transaction(write=True) as conn:conn.execute('UPDATE credentials SET expires_at=? WHERE id=?',(expiry,self.actor.credential_id))
        result=execute(self.args())
        self.assertLessEqual(result['identity']['expires_at'],expiry)

    def test_missing_local_brain_does_not_initialize_or_store_credentials(self):
        home=self.root/'empty';args=self.args(home=home)
        self.fails('brain_missing',execute,args)
        self.assertFalse(home.exists())

    def test_remote_profile_uses_derived_identity_and_never_opens_local_database(self):
        endpoint=self.server();local=self.root/'client';token=self.root/'remote-owner.token';token.write_text(self.owner['token'])
        connect(local,'company',endpoint,token)
        result=execute(self.args(home=local,connection='company'))
        self.assertEqual('agent-test-agent',result['connection'])
        self.assertNotEqual(self.actor.principal_id,result['identity']['principal_id'])
        self.assertFalse((local/'brain.sqlite3').exists())
        config=json.loads(Path(result['mcp_config']).read_text())['mcpServers']['atmet-brain']
        self.assertIn('agent-test-agent',config['args'])
        replies=self.mcp(result,[{'jsonrpc':'2.0','id':1,'method':'initialize'}])
        self.assertIn('instructions',replies[0]['result'])

    def test_remote_failure_never_falls_back_to_local_owner(self):
        endpoint=self.server();local=self.root/'client';token=self.root/'remote-owner.token';token.write_text(self.owner['token'])
        connect(local,'company',endpoint,token)
        self.brain.revoke_credential(self.actor,self.actor.credential_id)
        self.fails('unauthenticated',execute,self.args(home=local,connection='company'))
        self.assertFalse((local/'brain.sqlite3').exists())

    def test_ssh_route_is_preserved_and_direct_http_examples_are_not_offered(self):
        from atmet_brain.ssh import SSHClient
        local=self.root/'ssh-client';token=self.root/'ssh-owner.token';token.write_text(self.owner['token'])
        def core_call(client,method,**params):
            return dispatch(self.brain,self.brain.authenticate(client.token),method,params)
        # Exercise route/profile logic independently of the separately tested SSH tunnel.
        with patch.object(SSHClient,'call',core_call):
            connect(local,'company','ssh://forward@example.test',token,ssh={'destination':'forward@example.test','port':7310})
            self.fails('agent_answers_required',execute,self.args(home=local,connection='company',method='rest'))
            self.assertFalse((local/'agents').exists())
            result=execute(self.args(home=local,connection='company'))
        profile=json.loads((local/'connections'/f"{result['connection']}.json").read_text())
        self.assertEqual('forward@example.test',profile['ssh']['destination'])
        self.assertFalse((Path(result['directory'])/'agent.py').exists())

    def test_remote_rest_and_python_keep_trusted_ca(self):
        endpoint=self.server(tls=True);local=self.root/'https-client';token=self.root/'https-owner.token';token.write_text(self.owner['token'])
        connect(local,'company',endpoint,token,self.root/'ca.pem')
        for method in ['rest','python']:
            result=execute(self.args(name=method,home=local,connection='company',method=method,access='read'))
            if method=='python':
                process=subprocess.run([sys.executable,str(Path(result['directory'])/'agent.py')],capture_output=True,text=True,timeout=20)
                self.assertEqual(0,process.returncode,process.stderr)
                self.assertIn(str(self.root/'ca.pem'),(Path(result['directory'])/'agent.py').read_text())
            self.assertFalse((local/'brain.sqlite3').exists())

    def test_interactive_join_can_continue_into_agent_setup(self):
        from atmet_brain.sharing import create_share
        endpoint=self.server(tls=True);share=self.root/'join.atmet-join.json'
        create_share(self.brain,self.actor,'Joined reporter',['sales'],'reporter',share,endpoint=endpoint)
        local=self.root/'joined-client'
        args=parser().parse_args(['--home',str(local),'--ca-file',str(self.root/'ca.pem'),'agent'])
        answers=['join',str(share),'company','yes','mcp','sales','learn','current','joined-agent','yes']
        with patch('sys.stdin.isatty',return_value=True),patch('builtins.input',side_effect=answers),contextlib.redirect_stderr(io.StringIO()):
            result=execute(args)
        self.assertEqual('agent-joined-agent',result['connection'])
        self.assertFalse((local/'brain.sqlite3').exists())

    def test_cli_json_output_has_no_raw_token(self):
        p=self.cli(self.home,'--json','agent','--name','machine','--method','terminal','--spaces','sales','--access','read','--identity','new')
        self.assertEqual(0,p.returncode,p.stderr)
        result=json.loads(p.stdout)
        self.assertNotIn(Path(result['token_file']).read_text().strip(),p.stdout+p.stderr)
        self.assertEqual('terminal',result['method'])
