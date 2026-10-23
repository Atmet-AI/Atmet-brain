"""Automatic completion hooks preserve source access, replay and review boundaries."""

import json
from unittest.mock import patch
import unittest

from atmet_brain import BrainError
from atmet_brain.auth import ROLES
from atmet_brain.client import Client
from atmet_brain.feedback import LocalClient
from atmet_brain.mcp import MCPServer
from atmet_brain.rpc import dispatch, input_schema
from atmet_brain.util import uid
from tests import test_task_reports as fixtures


class FeedbackCase(unittest.TestCase):
    setUp = fixtures.TaskReportCase.setUp
    source = fixtures.TaskReportCase.source
    proof = fixtures.TaskReportCase.proof
    fails = fixtures.TaskReportCase.fails
    user = fixtures.TaskReportCase.user

    def payload(self, **changes):
        args = dict(space_id=self.space, report_key=uid('completion'), task_key='prepare-quotation',
                    summary='Prepared quotation draft', outcome='corrected', result='Corrected draft ready',
                    evidence=self.proof(self.source()), steps=['Read catalogue', 'Prepare draft'],
                    corrections=['Check customer template'], checks=['Prices checked'])
        args.update(changes)
        return args

    def complete(self, actor=None, **changes):
        return self.brain.complete_task_report(actor or self.actor, **self.payload(**changes))

    def session(self, client=None, **changes):
        args=self.payload(**changes)
        for key in ('outcome','result','steps','corrections','checks'):
            args.pop(key)
        return (client or LocalClient(self.brain,self.owner['token'])).task_feedback(**args)

    def test_completion_is_private_pending_and_approval_remains_separate(self):
        result=self.complete()
        self.assertFalse(result['publication_authorized'])
        self.assertEqual('pending_review',result['skill']['status'])
        report=self.brain.get_task_report(self.actor,result['report']['id'])
        self.assertEqual(['principal:'+self.actor.principal_id],report['audience'])
        skill=self.brain.get_artifact(self.actor,result['skill']['id'],revision=1)
        self.assertEqual(report['audience'],skill['audience'])
        self.assertEqual([],self.brain.list_artifacts(self.actor,self.space,'skill'))
        self.brain.review_artifact(self.actor,result['skill']['id'],1,True,'Reviewed source, steps and checks')
        self.assertEqual(1,len(self.brain.list_artifacts(self.actor,self.space,'skill')))

    def test_reporter_role_can_draft_but_cannot_publish_or_erase(self):
        actor,_=self.user(ROLES['reporter'])
        result=self.complete(actor,audience=['space'])
        self.assertEqual('pending_review',result['skill']['status'])
        self.fails('forbidden',self.brain.review_artifact,actor,result['skill']['id'],1,True,'Self approval')
        self.fails('forbidden',self.brain.erase_task_report,actor,result['report']['id'])

    def test_exact_retries_reuse_report_and_skill_and_report_current_review_state(self):
        args=self.payload();one=self.brain.complete_task_report(self.actor,**args)
        two=self.brain.complete_task_report(self.actor,**args)
        self.assertEqual(one['report']['id'],two['report']['id'])
        self.assertEqual(one['skill']['id'],two['skill']['id'])
        self.brain.review_artifact(self.actor,one['skill']['id'],1,True,'Reviewed')
        replay=self.brain.complete_task_report(self.actor,**args)
        self.assertEqual('approved',replay['skill']['state'])
        self.assertEqual('existing',replay['skill']['status'])
        args['result']='Different result'
        self.fails('report_conflict',self.brain.complete_task_report,self.actor,**args)

    def test_failed_missing_steps_and_disabled_learning_preserve_report_only(self):
        for changes,status in [({'outcome':'failed'},'not_eligible'),({'steps':[]},'not_eligible'),({'learn':False},'not_requested')]:
            result=self.complete(**changes)
            self.assertEqual(status,result['skill']['status'])
            self.assertEqual('recorded',result['report']['status'])
        self.fails('invalid_report',self.complete,learn='true')

    def test_new_completion_does_not_revise_an_already_approved_method(self):
        first=self.complete()
        self.brain.review_artifact(self.actor,first['skill']['id'],1,True,'Reviewed')
        next_run=self.complete()
        self.assertNotEqual(first['skill']['id'],next_run['skill']['id'])
        self.assertEqual('pending_review',next_run['skill']['status'])
        self.assertEqual(1,self.brain.get_artifact(self.actor,first['skill']['id'])['revision'])

    def test_concurrent_completion_retries_create_one_report_and_one_candidate(self):
        from concurrent.futures import ThreadPoolExecutor
        args=self.payload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.brain.complete_task_report(self.actor,**args),range(2)))
        self.assertEqual(results[0]['report']['id'],results[1]['report']['id'])
        self.assertEqual(results[0]['skill']['id'],results[1]['skill']['id'])
        with self.brain.store.transaction() as conn:
            self.assertEqual(1,conn.execute('SELECT COUNT(*) FROM task_reports').fetchone()[0])
            self.assertEqual(1,conn.execute('SELECT COUNT(*) FROM artifact_versions').fetchone()[0])

    def test_draft_failure_can_resume_without_losing_report_or_repeating_task(self):
        session=self.session()
        with patch.object(self.brain,'learn_skill_from_reports',side_effect=BrainError('temporary_failure','Draft not created',503)):
            session.run(lambda task:(task.step('Read catalogue'),'Prepared draft')[1])
        report_id=session.receipt['report']['id']
        self.assertEqual('blocked',session.receipt['skill']['status'])
        session.retry()
        self.assertEqual(report_id,session.receipt['report']['id'])
        self.assertEqual('pending_review',session.receipt['skill']['status'])

    def test_missing_history_saves_report_and_exposes_blocked_drafting(self):
        actor,key=self.user(['read','observe','contribute'])
        args=self.payload(audience=['space'])
        result=self.brain.complete_task_report(actor,**args)
        self.assertEqual('blocked',result['skill']['status'])
        self.assertEqual('forbidden',result['skill']['error']['code'])
        self.brain.grant(self.actor,actor.principal_id,self.space,['read','observe','contribute','history'])
        # A new credential also needs history. Grants alone cannot widen a token.
        self.assertEqual('blocked',self.brain.complete_task_report(actor,**args)['skill']['status'])
        new=self.brain.create_credential(self.actor,actor.principal_id,ROLES['reporter'],[self.space])
        retried=self.brain.complete_task_report(self.brain.authenticate(new['token']),**args)
        self.assertEqual(result['report']['id'],retried['report']['id'])
        self.assertEqual('pending_review',retried['skill']['status'])

    def test_restricted_source_and_private_report_hide_automatic_candidates(self):
        result=self.complete(audience=['space'])
        other,_=self.user(ROLES['reporter'])
        report=self.brain.get_task_report(self.actor,result['report']['id'])
        self.brain.set_source_access(self.actor,report['evidence'][0]['source_id'],['principal:'+self.actor.principal_id])
        self.fails('not_found',self.brain.get_task_report,other,report['id'])
        self.fails('not_found',self.brain.get_artifact,other,result['skill']['id'],revision=1)

    def test_source_change_between_report_and_learning_returns_partial_receipt(self):
        source=self.source(external='changing');args=self.payload(evidence=self.proof(source))
        original=self.brain.learn_skill_from_reports
        def changed(*values,**options):
            self.brain.put_source(self.actor,self.space,'changing','Updated','Updated source',expected_revision=1)
            return original(*values,**options)
        with patch.object(self.brain,'learn_skill_from_reports',side_effect=changed):
            result=self.brain.complete_task_report(self.actor,**args)
        self.assertEqual('recorded',result['report']['status'])
        self.assertEqual('stale_evidence',result['skill']['error']['code'])
        self.assertEqual(1,len(self.brain.search_task_reports(self.actor,self.space)['results']))

    def test_report_erasure_cannot_be_undone_by_a_completion_retry(self):
        args=self.payload();result=self.brain.complete_task_report(self.actor,**args)
        self.brain.erase_task_report(self.actor,result['report']['id'])
        self.fails('not_found',self.brain.complete_task_report,self.actor,**args)
        with self.brain.store.transaction() as conn:
            self.assertEqual('retracted',conn.execute('SELECT state FROM artifact_versions WHERE artifact_id=?',(result['skill']['id'],)).fetchone()[0])

    def test_hook_wraps_host_function_and_automatically_reports_and_drafts(self):
        session=self.session()
        calls=[]
        def host(task):
            calls.append('business action')
            task.step('Read catalogue');task.correction('Use customer template');task.check('Prices checked')
            return 'Quotation draft ready'
        self.assertEqual('Quotation draft ready',session.run(host))
        self.assertEqual('pending_review',session.receipt['skill']['status'])
        session.retry()
        self.assertEqual(['business action'],calls)
        self.assertEqual(1,len(self.brain.search_task_reports(self.actor,self.space)['results']))
        self.fails('task_closed',session.step,'Mutate completion')
        self.fails('task_closed',session.run,host)

    def test_context_manager_records_deliberate_result_and_extra_provenance(self):
        session=self.session()
        source=self.source(external='extra')
        with session as task:
            task.cite(self.proof(source));task.cite(self.proof(source))
            task.step('Check both sources');task.result('Corrected draft',outcome='corrected')
            self.fails('task_active',task.submit)
        report=self.brain.get_task_report(self.actor,session.receipt['report']['id'])
        self.assertEqual(2,len(report['evidence']))
        self.assertEqual('corrected',report['body']['outcome'])

    def test_hook_failure_is_reported_without_raw_exception_or_success_claim(self):
        session=self.session()
        def host(task):
            task.step('Read catalogue')
            task.result('Premature success')
            raise RuntimeError('sensitive-exception-message')
        with self.assertRaisesRegex(RuntimeError,'sensitive-exception-message'):
            session.run(host)
        self.assertEqual('not_eligible',session.receipt['skill']['status'])
        report=self.brain.get_task_report(self.actor,session.receipt['report']['id'])
        self.assertEqual('failed',report['body']['outcome'])
        self.assertNotIn('sensitive-exception-message',json.dumps(report))

    def test_no_implicit_success_in_context_manager_or_io_during_interrupt(self):
        session=self.session()
        self.fails('incomplete_task',session.__exit__,None,None,None)
        interrupted=self.session()
        with self.assertRaises(KeyboardInterrupt):
            with interrupted:
                raise KeyboardInterrupt()
        self.assertIsNone(interrupted.receipt)
        self.assertEqual([],self.brain.search_task_reports(self.actor,self.space)['results'])

    def test_ambiguous_transport_failure_retries_frozen_payload_without_duplicate_or_task_rerun(self):
        client=LocalClient(self.brain,self.owner['token']);call=client.call;attempt=[]
        def lost(method,**params):
            result=call(method,**params)
            if not attempt:
                attempt.append(1)
                raise BrainError('connection_failed','Lost response',503)
            return result
        session=self.session(client=client);calls=[]
        def host(task):
            calls.append(1);task.step('Read catalogue');return 'Prepared safe draft'
        with patch.object(client,'call',side_effect=lost):
            self.fails('connection_failed',session.run,host)
            session.params['result']='Accidental mutation after completion'
            session.retry()
        self.assertEqual([1],calls)
        self.assertEqual('pending_review',session.receipt['skill']['status'])
        self.assertEqual(1,len(self.brain.search_task_reports(self.actor,self.space)['results']))

    def test_failed_reporting_preserves_original_host_exception_and_revocation_is_live(self):
        actor,key=self.user(ROLES['reporter'])
        client=LocalClient(self.brain,key['token']);session=self.session(client=client)
        self.brain.revoke_credential(self.actor,key['credential_id'])
        def host(task):
            raise ValueError('original host error')
        with self.assertRaisesRegex(ValueError,'original host error'):
            session.run(host)
        self.assertEqual('unauthenticated',session.error['code'])
        self.fails('unauthenticated',session.retry)
        self.assertEqual([],self.brain.search_task_reports(self.actor,self.space)['results'])

    def test_completion_rejects_identity_publication_and_cross_space_fields(self):
        args=self.payload();args['approve']=True
        self.fails('invalid_params',dispatch,self.brain,self.actor,'reports.complete',args)
        args.pop('approve');args['recorded_by']='another-user'
        self.fails('invalid_params',dispatch,self.brain,self.actor,'reports.complete',args)
        args.pop('recorded_by');args['space_id']=self.brain.create_space(self.actor,'other')['id']
        self.fails('evidence_unavailable',dispatch,self.brain,self.actor,'reports.complete',args)
        self.assertEqual('boolean',input_schema(self.brain,'reports.complete')['properties']['learn']['type'])


class FeedbackTransportCase(unittest.TestCase):
    setUp = fixtures.TaskReportTransportCase.setUp
    server = fixtures.TaskReportTransportCase.server
    cli = fixtures.TaskReportTransportCase.cli

    def payload(self):
        source=self.brain.put_source(self.actor,self.sales,'catalogue','Catalogue','Fictional catalogue')
        return dict(report_key=uid('completion'),task_key='quotation',summary='Prepared draft',outcome='succeeded',
                    result='Quotation draft ready',steps=['Read catalogue','Prepare draft'],audience=['space'],
                    evidence=[{'source_id':source['id'],'revision':1}])

    def test_real_remote_python_hook_rechecks_identity_and_keeps_review_separate(self):
        payload=self.payload()
        member=self.brain.add_team_member(self.actor,'Agent',[self.sales],'reporter',kind='service')
        client=Client(self.server(),member['token'])
        args={k:v for k,v in payload.items() if k not in {'steps','result','outcome'}}
        session=client.task_feedback(space_id=self.sales,**args)
        def host(task):
            task.step('Read catalogue');return 'Quotation ready'
        session.run(host)
        self.assertEqual('pending_review',session.receipt['skill']['status'])
        self.assertEqual(member['principal_id'],client.call('reports.get',report_id=session.receipt['report']['id'])['recorded_by'])
        self.brain.revoke_credential(self.actor,member['credential_id'])
        with self.assertRaises(BrainError):
            session.retry()

    def test_cli_completion_hook_supports_stdin_local_and_remote(self):
        import os,subprocess,sys
        payload=self.payload()
        command=[sys.executable,'-m','atmet_brain','--json','--home',str(self.home),'task-complete','-','--space',self.sales]
        local=subprocess.run(command,input=json.dumps(payload),text=True,capture_output=True,env=os.environ)
        self.assertEqual(0,local.returncode,local.stderr)
        one=json.loads(local.stdout);self.assertEqual('pending_review',one['skill']['status'])
        file=self.root/'completed.json';file.write_text(json.dumps(payload))
        remote=self.cli(self.root/'remote','--endpoint',self.server(),'--token-file',str(self.home/'owner.token'),
                        'task-complete',str(file),'--space',self.sales)
        self.assertEqual(0,remote.returncode,remote.stderr)
        self.assertEqual(one['skill']['id'],json.loads(remote.stdout)['skill']['id'])
        self.assertFalse((self.root/'remote/brain.sqlite3').exists())
        too_big=subprocess.run(command,input=' '*200001,text=True,capture_output=True,env=os.environ)
        self.assertEqual(1,too_big.returncode)

    def test_mcp_opt_in_instructions_completion_remote_grants_and_no_approval_tool(self):
        payload=self.payload()
        readonly=MCPServer(self.brain,self.owner['token'])
        self.assertNotIn('brain_complete_task',readonly.tools)
        reporter=self.brain.add_team_member(self.actor,'Reporter',[self.sales],'reporter',kind='service')
        client=Client(self.server(),reporter['token'])
        bridge=MCPServer(None,None,client=client,task_feedback=True)
        init=bridge.handle({'jsonrpc':'2.0','id':1,'method':'initialize'})
        self.assertIn('call brain_complete_task',init['result']['instructions'])
        self.assertFalse(any('review' in name or 'publish' in name for name in bridge.tools))
        reply=bridge.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'brain_complete_task','arguments':dict(space_id=self.sales,**payload)}})
        self.assertFalse(reply['result']['isError'])
        result=json.loads(reply['result']['content'][0]['text']);self.assertEqual('pending_review',result['skill']['status'])
        self.assertEqual([],client.call('artifacts.list',space_id=self.sales,kind='skill'))
        reader=self.brain.add_team_member(self.actor,'Reader',[self.sales],'reader')
        denied=MCPServer(self.brain,reader['token'],task_feedback=True)
        denied.handle({'jsonrpc':'2.0','id':1,'method':'initialize'})
        reply=denied.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'brain_complete_task','arguments':dict(space_id=self.sales,**payload)}})
        self.assertTrue(reply['result']['isError'])
        config=self.cli(self.home,'--token-file',str(self.home/'owner.token'),'mcp-config','--task-feedback')
        self.assertIn('--task-feedback',json.loads(config.stdout)['mcpServers']['atmet-brain']['args'])
