"""Task reporting, history, learning, migration and erasure invariants."""

import contextlib
import json
from pathlib import Path
import sqlite3
import threading
from unittest.mock import patch
import unittest

from atmet_brain import Brain, BrainError
from atmet_brain.auth import ROLES
from atmet_brain.backups import generate_backup_key
from atmet_brain.cli import execute, parser
from atmet_brain.db import SCHEMA_VERSION, Store
from atmet_brain.mcp import MCPServer
from atmet_brain.rpc import dispatch, input_schema
from atmet_brain.server import make_server
from atmet_brain.util import dumps, uid
from tests import test_core as core_fixtures
from tests import test_terminal_team as transport_fixtures


class TaskReportCase(unittest.TestCase):
    setUp = core_fixtures.CoreCase.setUp
    source = core_fixtures.CoreCase.source
    proof = core_fixtures.CoreCase.proof
    fails = core_fixtures.CoreCase.fails

    def user(self, operations, name="User"):
        principal = self.brain.create_principal(self.actor, name, "service")
        self.brain.grant(self.actor, principal['id'], self.space, operations)
        key = self.brain.create_credential(self.actor, principal['id'], operations, [self.space])
        return self.brain.authenticate(key['token']), key

    def report(self, source=None, actor=None, **changes):
        source = source or self.source()
        args = dict(space_id=self.space, report_key=uid('request'), task_key='prepare-quotation',
                    summary='Prepared a customer quotation', outcome='corrected', result='Accepted revised template: unique-history-marker',
                    evidence=self.proof(source), steps=['Check the current catalogue', 'Prepare the quotation draft'],
                    corrections=['Use the customer-specific template'], checks=['Prices match current evidence'], audience=['space'])
        args.update(changes)
        return self.brain.record_task_report(actor or self.actor, **args)

    def learn(self, reports, actor=None, **changes):
        args=dict(space_id=self.space, report_ids=[r['id'] for r in reports], name='prepare-quotation', idempotency_key=uid('learn'))
        args.update(changes)
        return self.brain.learn_skill_from_reports(actor or self.actor, **args)

    def test_report_records_actual_caller_and_stays_out_of_ordinary_retrieval(self):
        source=self.source(); report=self.report(source)
        row=self.brain.get_task_report(self.actor,report['id'])
        self.assertEqual(self.actor.principal_id,row['recorded_by'])
        self.assertEqual(self.actor.credential_id,row['recorded_credential'])
        self.assertFalse(row['outcome_verified']);self.assertFalse(row['instruction_authority'])
        self.assertEqual([source['id']],[s['id'] for s in self.brain.list_sources(self.actor,self.space)])
        self.assertEqual([],self.brain.search(self.actor,self.space,'unique-history-marker')['results'])
        self.assertEqual([],self.brain.get_context(self.actor,self.space,'unique-history-marker')['reference_evidence'])
        self.assertEqual([source['id']],[s['id'] for s in self.brain.export_space(self.actor,self.space)['sources']])
        with self.brain.store.transaction() as conn:
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM jobs WHERE source_id=?',(report['source_id'],)).fetchone()[0])
            self.assertEqual('observation',conn.execute('SELECT authority FROM sources WHERE id=?',(report['source_id'],)).fetchone()[0])

    def test_reporting_requires_observe_read_and_contribute(self):
        source=self.source()
        for operations in [['read'],['read','contribute'],['read','observe'],['contribute','observe']]:
            actor,_=self.user(operations)
            self.fails('forbidden',self.report,source,actor=actor)
        actor,_=self.user(['read','contribute','observe'])
        report=self.report(source,actor=actor)
        self.assertEqual('recorded',report['status'])
        self.fails('forbidden',self.brain.get_task_report,actor,report['id'])
        self.fails('forbidden',self.brain.search_task_reports,actor,self.space)
        self.fails('forbidden',self.brain.get_source,actor,report['source_id'])
        self.fails('forbidden',self.learn,[report],actor=actor)

    def test_default_private_and_source_audience_intersection(self):
        source=self.source(); other,_=self.user(['read','history'])
        private=self.report(source,audience=None)
        self.assertEqual([],self.brain.search_task_reports(other,self.space)['results'])
        self.fails('not_found',self.brain.get_task_report,other,private['id'])
        sensitive=self.source(audience=['principal:'+self.actor.principal_id])
        shared=self.report(sensitive,audience=['space'])
        self.assertEqual([],self.brain.search_task_reports(other,self.space)['results'])
        draft=self.learn([shared]);self.brain.review_artifact(self.actor,draft['id'],1,True,'Reviewed')
        self.fails('not_found',self.brain.get_artifact,other,draft['id'])

    def test_search_filters_before_matching_and_respects_task_limit(self):
        source=self.source(); actor,_=self.user(['read','history'])
        first=self.report(source)
        self.report(source,task_key='another-task',summary='Other work')
        self.report(source,audience=['principal:'+self.actor.principal_id],summary='Hidden needle')
        found=self.brain.search_task_reports(actor,self.space,'unique-history-marker',task_key='prepare-quotation',limit=1)
        self.assertEqual([first['id']],[r['id'] for r in found['results']])
        self.assertEqual([],self.brain.search_task_reports(actor,self.space,'Hidden needle')['results'])
        self.fails('invalid_limit',self.brain.search_task_reports,actor,self.space,limit=True)
        self.fails('invalid_limit',self.brain.search_task_reports,actor,self.space,limit=51)

    def test_idempotency_is_per_reporter_and_conflicts_do_not_overwrite(self):
        source=self.source(); params=dict(report_key='stable-retry')
        first=self.report(source,**params); again=self.report(source,**params)
        self.assertEqual(first['id'],again['id']);self.assertEqual('unchanged',again['status'])
        self.fails('report_conflict',self.report,source,report_key='stable-retry',result='Different')
        other,_=self.user(['read','observe','contribute'])
        second=self.report(source,actor=other,**params)
        self.assertNotEqual(first['id'],second['id'])

    def test_learning_is_pending_and_publication_is_a_separate_permission(self):
        source=self.source(); report=self.report(source)
        learner,_=self.user(['read','history','contribute'])
        draft=self.learn([report],actor=learner)
        self.assertEqual('pending_review',draft['status']);self.assertEqual(0,draft['model_calls'])
        self.assertTrue(draft['review_required']);self.assertFalse(draft['publication_authorized'])
        self.assertEqual([],self.brain.list_artifacts(learner,self.space,'skill'))
        self.fails('forbidden',self.brain.review_artifact,learner,draft['id'],1,True,'Self approve')
        pending=self.brain.get_artifact(self.actor,draft['id'],revision=1)
        self.assertIn('customer-specific template',pending['body']['instructions'])
        self.assertIn({'source_id':report['source_id'],'revision':1},pending['evidence'])
        publisher,_=self.user(ROLES['publisher'])
        self.brain.review_artifact(publisher,draft['id'],1,True,'Checked sources, applicability and procedure')
        self.assertEqual(1,len(self.brain.list_artifacts(learner,self.space,'skill')))
        resource=self.brain.skill_resource(learner,draft['id'],'references/task-evidence.json')
        self.assertFalse(resource['executable'])
        envelope=self.brain.get_context(learner,self.space,'quotation',artifact_ids=[draft['id']])
        self.assertEqual(draft['id'],envelope['approved_context'][0]['id'])

    def test_learning_replay_revision_update_and_stale_review(self):
        report=self.report();draft=self.learn([report],idempotency_key='same')
        replay=self.learn([report],idempotency_key='same');self.assertEqual(draft['id'],replay['id'])
        self.brain.review_artifact(self.actor,draft['id'],1,True,'Checked')
        revised=self.learn([report],artifact_id=draft['id'],expected_revision=1)
        self.assertEqual(2,revised['revision'])
        self.fails('revision_conflict',self.brain.review_artifact,self.actor,draft['id'],1,True,'Old review')
        self.fails('revision_conflict',self.learn,[report],artifact_id=draft['id'],expected_revision=1)
        self.assertEqual(1,self.brain.get_artifact(self.actor,draft['id'])['revision'])

    def test_failed_only_mixed_tasks_and_missing_steps_do_not_teach_a_method(self):
        failed=self.report(outcome='failed')
        self.fails('insufficient_evidence',self.learn,[failed])
        blank=self.report(steps=[])
        self.fails('insufficient_evidence',self.learn,[blank])
        normal=self.report(); other=self.report(task_key='other')
        self.fails('mixed_tasks',self.learn,[normal,other])
        self.fails('invalid_reports',self.learn,[normal,normal])
        draft=self.learn([normal,failed]);self.assertEqual('pending_review',draft['status'])

    def test_source_changes_preserve_history_but_block_learning_and_old_approval(self):
        source=self.source(external='changing');report=self.report(source);draft=self.learn([report])
        self.brain.put_source(self.actor,self.space,'changing',
                              'Updated','New source',authority='authoritative',expected_revision=1)
        self.assertIn('unique-history-marker',self.brain.get_task_report(self.actor,report['id'])['body']['result'])
        self.fails('stale_evidence',self.learn,[report],name='new-skill')
        self.fails('stale_evidence',self.brain.review_artifact,self.actor,draft['id'],1,True,'Stale source')

    def test_source_narrowing_and_revocation_hide_reports_skills_and_audit(self):
        source=self.source(); report=self.report(source);draft=self.learn([report])
        self.brain.review_artifact(self.actor,draft['id'],1,True,'Checked')
        other,_=self.user(['read','history'])
        self.assertEqual(1,len(self.brain.search_task_reports(other,self.space)['results']))
        self.brain.set_source_access(self.actor,source['id'],['principal:'+self.actor.principal_id])
        self.assertEqual([],self.brain.search_task_reports(other,self.space)['results'])
        self.fails('not_found',self.brain.get_task_report,other,report['id'])
        self.fails('not_found',self.brain.get_artifact,other,draft['id'])
        self.assertNotIn(report['id'],[r['target'] for r in self.brain.list_audit(other,self.space)])
        self.brain.set_source_access(self.actor,source['id'],['space'],active=False)
        self.assertEqual([],self.brain.search_task_reports(self.actor,self.space)['results'])

    def test_report_evidence_cannot_launder_a_stale_original_source(self):
        source=self.source(external='original');report=self.report(source)
        self.brain.put_source(self.actor,self.space,'original','Updated','New evidence',authority='authoritative',expected_revision=1)
        self.fails('stale_evidence',self.brain.propose_artifact,self.actor,self.space,'skill','manual-report-method',
                   {'description':'A method','instructions':'Reported procedure'},evidence=[{'source_id':report['source_id'],'revision':1}],idempotency_key='manual-1')

    def test_report_erasure_clears_payload_task_key_and_retracts_learned_skill(self):
        report=self.report(task_key='sensitive-customer-label');draft=self.learn([report])
        self.brain.review_artifact(self.actor,draft['id'],1,True,'Checked')
        self.brain.erase_task_report(self.actor,report['id'])
        self.fails('not_found',self.brain.get_task_report,self.actor,report['id'])
        with self.brain.store.transaction() as conn:
            self.assertEqual(b'',conn.execute('SELECT body FROM source_revisions WHERE source_id=?',(report['source_id'],)).fetchone()[0])
            self.assertEqual('',conn.execute('SELECT task_key FROM task_reports WHERE id=?',(report['id'],)).fetchone()[0])
            self.assertEqual(('{}','retracted'),tuple(conn.execute('SELECT body,state FROM artifact_versions WHERE artifact_id=?',(draft['id'],)).fetchone()))

    def test_original_source_erasure_also_clears_report_payload(self):
        source=self.source(); report=self.report(source)
        self.brain.erase_source(self.actor,source['id'])
        with self.brain.store.transaction() as conn:
            self.assertEqual(b'',conn.execute('SELECT body FROM source_revisions WHERE source_id=?',(report['source_id'],)).fetchone()[0])
        self.assertEqual([],self.brain.search_task_reports(self.actor,self.space)['results'])

    def test_reports_cannot_be_rewritten_through_sources_or_cite_each_other(self):
        report=self.report()
        self.fails('reserved_source',self.brain.put_source,self.actor,self.space,'atmet-report:'+report['id'],'Edited','data')
        self.fails('invalid_report',self.report,evidence=[{'source_id':report['source_id'],'revision':1}])
        self.fails('invalid_report',self.report,outcome='human_verified')
        self.fails('invalid_report',self.report,steps=['x']*31)
        self.fails('invalid_input',self.report,result='x'*10001)
        self.fails('invalid_params',dispatch,self.brain,self.actor,'reports.get',{'report_id':report['id'],'actor':'someone'})

    def test_cross_space_org_and_revoked_caller_fail_closed(self):
        report=self.report(); other_space=self.brain.create_space(self.actor,'finance')['id']
        self.fails('not_found',self.brain.learn_skill_from_reports,self.actor,other_space,[report['id']],'other','key')
        org=self.brain.provision_organization('other-company');other=self.brain.authenticate(org['token'])
        self.fails('not_found',self.brain.get_task_report,other,report['id'])
        actor,key=self.user(['read','history'])
        self.brain.revoke_credential(self.actor,key['credential_id'])
        self.fails('unauthenticated',self.brain.search_task_reports,actor,self.space)

    def test_backup_replay_erases_reports_and_retracts_drafts(self):
        source=self.source();report=self.report(source);draft=self.learn([report])
        key=self.home.parent/'backup.key';generate_backup_key(key)
        backup=self.home.parent/'before.atmet';self.brain.create_backup(backup,key)
        self.brain.erase_source(self.actor,source['id'])
        journal=self.home.parent/'latest.json';self.brain.flush_recovery_journal(journal)
        restored=self.home.parent/'restored';Brain.restore_backup(backup,restored,key)
        brain=Brain(restored);result=brain.finish_recovery(journal,'Recovery owner',True)
        with brain.store.transaction() as conn:
            self.assertEqual(b'',conn.execute('SELECT body FROM source_revisions WHERE source_id=?',(report['source_id'],)).fetchone()[0])
            self.assertEqual('retracted',conn.execute('SELECT state FROM artifact_versions WHERE artifact_id=?',(draft['id'],)).fetchone()[0])
        new=brain.authenticate(result['owners'][0]['token'])
        self.assertEqual([],brain.search_task_reports(new,self.space)['results'])

    def test_mcp_reporting_and_learning_are_opt_in_and_never_publish(self):
        readonly=MCPServer(self.brain,self.owner['token'])
        self.assertIn('brain_search_task_history',readonly.tools)
        self.assertNotIn('brain_report_task',readonly.tools);self.assertNotIn('brain_learn_skill',readonly.tools)
        enabled=MCPServer(self.brain,self.owner['token'],allow_writes=True,allow_task_reports=True)
        self.assertIn('brain_report_task',enabled.tools);self.assertIn('brain_learn_skill',enabled.tools)
        self.assertFalse(any('publish' in name or 'review' in name for name in enabled.tools))
        schema=input_schema(self.brain,'skills.learn');self.assertEqual('array',schema['properties']['report_ids']['type'])
        schema=input_schema(self.brain,'reports.record');self.assertEqual('array',schema['properties']['steps']['type'])

    def test_schema_one_migrates_existing_data_and_unknown_schema_is_rejected(self):
        source=self.source(); token=self.owner['token'];home=self.home.parent/'old-schema'
        home.mkdir();conn=sqlite3.connect(home/'brain.sqlite3')
        live=self.brain.store.connect();live.backup(conn);live.close()
        conn.execute('DROP TRIGGER report_state_insert');conn.execute('DROP TRIGGER report_state_update')
        conn.execute('DROP TABLE task_reports');conn.execute('ALTER TABLE sources DROP COLUMN category')
        conn.execute("UPDATE meta SET value='1' WHERE key='schema_version'");conn.commit();conn.close()
        upgraded=Brain(home)
        same_actor=upgraded.authenticate(token)
        self.assertEqual(source['id'],upgraded.get_source(same_actor,source['id'])['id'])
        with upgraded.store.transaction() as conn:
            self.assertEqual(str(SCHEMA_VERSION),conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
            self.assertIn('category',[r['name'] for r in conn.execute('PRAGMA table_info(sources)')])
            conn.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
        self.fails('schema_version',Store,home)

    def test_schema_one_backup_restores_and_migrates_before_recovery(self):
        import io,zipfile
        from cryptography.fernet import Fernet
        from atmet_brain.backups import MAGIC
        from atmet_brain.util import sha
        self.source(external='retained-source')
        snapshot=self.home.parent/'legacy.sqlite3';conn=sqlite3.connect(snapshot)
        live=self.brain.store.connect();live.backup(conn);live.close()
        conn.execute('DROP TRIGGER report_state_insert');conn.execute('DROP TRIGGER report_state_update')
        conn.execute('DROP TABLE task_reports');conn.execute('ALTER TABLE sources DROP COLUMN category')
        conn.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
        instance=conn.execute("SELECT value FROM meta WHERE key='instance_id'").fetchone()[0]
        conn.commit();conn.close();data=snapshot.read_bytes()
        manifest={'format':'atmet-brain-backup-v1','schema_version':1,'instance_id':instance,'recovery_sequence':0,
                  'database_sha256':sha(data),'database_bytes':len(data)}
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            archive.writestr('brain.sqlite3',data);archive.writestr('manifest.json',dumps(manifest))
        key=self.home.parent/'legacy.key';key.write_bytes(Fernet.generate_key())
        backup=self.home.parent/'legacy.atmet';backup.write_bytes(MAGIC+Fernet(key.read_bytes()).encrypt(buffer.getvalue()))
        destination=self.home.parent/'legacy-restored';restored=Brain.restore_backup(backup,destination,key)
        self.assertEqual('quarantined',restored['status'])
        with Brain(destination).store.transaction() as conn:
            self.assertEqual(str(SCHEMA_VERSION),conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM task_reports').fetchone()[0])
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM credentials WHERE revoked=0').fetchone()[0])

    def test_proposal_rechecks_report_access_after_draft_assembly(self):
        report=self.report()
        original=self.brain.propose_artifact
        def changed(*args,**kwargs):
            self.brain.erase_task_report(self.actor,report['id'])
            return original(*args,**kwargs)
        with patch.object(self.brain,'propose_artifact',side_effect=changed):
            self.fails('evidence_unavailable',self.learn,[report])

    def test_credential_expiry_blocks_saved_task_history(self):
        import time
        report=self.report();actor,_=self.user(['read','history'])
        with self.brain.store.transaction(write=True) as conn:
            conn.execute('UPDATE credentials SET expires_at=? WHERE id=?',(time.time()-1,actor.credential_id))
        self.fails('unauthenticated',self.brain.get_task_report,actor,report['id'])


    def test_legacy_active_source_queries_cannot_expose_operational_reports(self):
        report=self.report()
        with self.brain.store.transaction() as conn:
            self.assertNotIn(report['source_id'],[r['id'] for r in conn.execute("SELECT id FROM sources WHERE status='active'")])
            self.assertEqual('reported',conn.execute('SELECT status FROM sources WHERE id=?',(report['source_id'],)).fetchone()[0])
        with self.assertRaises(sqlite3.IntegrityError),self.brain.store.transaction(write=True) as conn:
            conn.execute("UPDATE sources SET status='active' WHERE id=?",(report['source_id'],))
        self.brain.set_source_access(self.actor,report['source_id'],['space'],active=False)
        self.brain.set_source_access(self.actor,report['source_id'],['space'],active=True)
        self.assertEqual(report['id'],self.brain.get_task_report(self.actor,report['id'])['id'])


class TaskReportTransportCase(unittest.TestCase):
    setUp=transport_fixtures.TerminalTeamCase.setUp
    server=transport_fixtures.TerminalTeamCase.server
    cli=transport_fixtures.TerminalTeamCase.cli

    def test_cli_local_and_remote_reports_history_and_learning(self):
        source=self.brain.put_source(self.actor,self.sales,'catalogue','Catalogue','Fictional product catalogue')
        report_file=self.root/'report.json'
        report_file.write_text(json.dumps({'report_key':'quotation-1','task_key':'quotation','summary':'Prepared quotation',
            'outcome':'succeeded','result':'Draft ready','steps':['Read catalogue','Prepare draft'],
            'checks':['Check prices'],'audience':['space'],'evidence':[{'source_id':source['id'],'revision':1}]}))
        created=self.cli(self.home,'task-report',str(report_file),'--space',self.sales)
        self.assertEqual(0,created.returncode,created.stderr)
        ident=json.loads(created.stdout)['id'];endpoint=self.server()
        remote=['--endpoint',endpoint,'--token-file',str(self.home/'owner.token')]
        history=self.cli(self.root/'remote',*remote,'task-history','quotation','--space',self.sales)
        self.assertEqual([ident],[r['id'] for r in json.loads(history.stdout)['results']])
        draft=self.cli(self.root/'remote',*remote,'task-learn','--space',self.sales,'--report',ident,'--name','quotation','--idempotency-key','learn-1')
        self.assertEqual(0,draft.returncode,draft.stderr)
        self.assertEqual('pending_review',json.loads(draft.stdout)['status'])
        self.assertFalse((self.root/'remote/brain.sqlite3').exists())
        read=self.cli(self.root/'remote',*remote,'task-get',ident);self.assertEqual(0,read.returncode,read.stderr)
        erased=self.cli(self.root/'remote',*remote,'task-erase',ident);self.assertEqual(0,erased.returncode,erased.stderr)
        self.assertEqual(1,self.cli(self.root/'remote',*remote,'task-get',ident).returncode)

    def test_remote_mcp_can_report_and_propose_but_never_publish(self):
        from atmet_brain.client import Client
        source=self.brain.put_source(self.actor,self.sales,'catalogue','Catalogue','Fictional catalogue')
        client=Client(self.server(),self.owner['token'])
        bridge=MCPServer(None,None,allow_writes=True,allow_task_reports=True,client=client)
        def call(name,args):
            reply=bridge.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':name,'arguments':args}})
            self.assertFalse(reply['result']['isError'],reply)
            return json.loads(reply['result']['content'][0]['text'])
        bridge.handle({'jsonrpc':'2.0','id':1,'method':'initialize'})
        report=call('brain_report_task',{'space_id':self.sales,'report_key':'mcp-task-1','task_key':'quotation','summary':'Prepared draft',
             'outcome':'succeeded','result':'Ready','steps':['Check source'],'audience':['space'],
             'evidence':[{'source_id':source['id'],'revision':1}]})
        history=call('brain_search_task_history',{'space_id':self.sales,'query':'draft'})
        self.assertEqual(report['id'],history['results'][0]['id'])
        draft=call('brain_learn_skill',{'space_id':self.sales,'report_ids':[report['id']],'name':'quotation','idempotency_key':'mcp-learn-1'})
        self.assertEqual('pending_review',draft['status'])
        self.assertEqual([],self.brain.list_artifacts(self.actor,self.sales,'skill'))
        result=self.cli(self.home,'--token-file',str(self.home/'owner.token'),'mcp-config','--allow-task-reports','--allow-proposals')
        self.assertEqual(0,result.returncode,result.stderr)
        arguments=json.loads(result.stdout)['mcpServers']['atmet-brain']['args']
        self.assertIn('--allow-task-reports',arguments);self.assertIn('--allow-proposals',arguments)

    def test_failed_schema_upgrade_rolls_back_new_tables_and_version(self):
        home=self.root/'migration-rollback';home.mkdir()
        conn=sqlite3.connect(home/'brain.sqlite3')
        sql=Path(__file__).parents[1]/'src/atmet_brain/schema.sql'
        old=sql.read_text().split('CREATE TABLE IF NOT EXISTS task_reports')[0].replace(", category TEXT NOT NULL DEFAULT 'document'",'')
        conn.executescript(old);conn.execute("INSERT INTO meta VALUES('schema_version','1')");conn.commit();conn.close()
        def denied(store):
            value=sqlite3.connect(store.path,isolation_level=None);value.row_factory=sqlite3.Row
            value.set_authorizer(lambda action,*args: sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_ALTER_TABLE else sqlite3.SQLITE_OK)
            return value
        with patch.object(Store,'connect',denied):
            with self.assertRaises(sqlite3.DatabaseError):
                Store(home)
        with sqlite3.connect(home/'brain.sqlite3') as check:
            self.assertEqual('1',check.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
            self.assertIsNone(check.execute("SELECT 1 FROM sqlite_master WHERE name='task_reports'").fetchone())

    def test_mcp_tool_flags_do_not_grant_reporting_or_history_permissions(self):
        from atmet_brain.client import Client
        member=self.brain.add_team_member(self.actor,'Read-only member',[self.sales],'reader')
        bridge=MCPServer(None,None,allow_writes=True,allow_task_reports=True,client=Client(self.server(),member['token']))
        bridge.handle({'jsonrpc':'2.0','id':1,'method':'initialize'})
        source=self.brain.put_source(self.actor,self.sales,'catalogue','Catalogue','Fictional catalogue')
        for tool,args in [('brain_search_task_history',{'space_id':self.sales}),
                          ('brain_report_task',{'space_id':self.sales,'report_key':'denied','task_key':'quotation','summary':'Draft',
                            'outcome':'succeeded','result':'Ready','evidence':[{'source_id':source['id'],'revision':1}]})]:
            response=bridge.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':tool,'arguments':args}})
            self.assertTrue(response['result']['isError'])
            self.assertEqual('forbidden',json.loads(response['result']['content'][0]['text'])['error']['code'])
