"""Isolated SQLite contracts; no business DB or OpenAI calls."""
import hashlib
import json
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from django.conf import settings
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
settings.configure(INSTALLED_APPS=['accounts','interviews'],DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}},
    USE_TZ=True,SECRET_KEY='test',CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache'}},
    AI_INTERVIEW_INVITATION_BASE_URL='http://localhost/candidate.html',OPENAI_API_KEY='test-key',ROOT_URLCONF='config.urls',ALLOWED_HOSTS=['testserver'],DEBUG=True)
import django
django.setup()
from django.db import connection
from django.core.cache import cache
from django.test import RequestFactory,override_settings
from django.utils import timezone
from django.urls import resolve,Resolver404
from accounts.models import UserAccount
from interviews.models import Interview,InterviewRuntime,InterviewReport
from interviews import candidate,runtime


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            existing=set(connection.introspection.table_names())
            for model in (UserAccount,Interview,InterviewRuntime,InterviewReport):
                if model._meta.db_table not in existing:editor.create_model(model)
    def setUp(self):
        InterviewReport.objects.all().delete();InterviewRuntime.objects.all().delete();Interview.objects.all().delete();UserAccount.objects.all().delete();cache.clear()
        self.code='ABCD-1234-5678-EF90';self.page='a'*32;now=timezone.now()
        self.account=UserAccount.objects.create(username='owner',password='test',display_name='Owner',company_name='Company',created_at=now,updated_at=now)
        self.item=Interview.objects.create(user_id=self.account.pk,request_id='one',invitation_token_hash=hashlib.sha256(self.code.replace('-','').lower().encode()).hexdigest(),
            position_name='Backend',work_description='Build',skills=[{'name':'Python','level':'advanced'}],assessment_targets=[{'id':'coding','name':'Coding','detail':'Design','weight':100}],
            candidate_name='A',candidate_email='a@example.com',invite_expires_at=now+timedelta(days=1),created_at=now,updated_at=now)
    def call(self,view,data):
        response=view(RequestFactory().post('/',json.dumps(data),content_type='application/json'))
        return response.status_code,json.loads(response.content)
    def start(self):return self.call(candidate.start,{'code':self.code,'page_id':self.page,'devices_ready':True,'consent':True})
    def connect(self):
        self.start();session=InterviewRuntime.objects.get(interview=self.item);session.connected_at=session.heartbeat_at=timezone.now();session.save();return session


class CandidateContract(Fixture):
    def test_readiness_and_missing_key_do_not_start(self):
        self.assertEqual(self.call(candidate.start,{'code':self.code,'page_id':self.page})[0],409)
        with override_settings(OPENAI_API_KEY=''):self.assertEqual(self.start()[0],503)
        self.item.refresh_from_db();self.assertEqual(self.item.status,'waiting');self.assertFalse(InterviewRuntime.objects.exists())
    def test_owner_is_ephemeral_and_refresh_is_abnormal(self):
        self.assertEqual(self.start()[0],200)
        self.assertEqual(self.call(candidate.verify,{'code':self.code,'page_id':self.page})[1]['data']['interview']['status'],'running')
        self.assertEqual(self.call(candidate.verify,{'code':self.code,'page_id':'b'*32})[1]['data']['interview']['status'],'abnormal')
        self.assertEqual(self.start()[1]['data']['interview']['status'],'abnormal')
        self.assertFalse(InterviewReport.objects.exists())
        session=InterviewRuntime.objects.get();self.assertEqual(session.abnormal_reason,'page_reloaded');self.assertIsNotNone(session.closed_at)
    def test_closed_page_cannot_be_resumed(self):
        self.connect()
        self.call(candidate.abort,{'code':self.code,'page_id':self.page,'reason':'page_closed'})
        result=self.call(candidate.verify,{'code':self.code,'page_id':self.page})[1]
        self.assertEqual(result['data']['interview']['status'],'abnormal')
    def test_watchdog_terminalizes_crashed_server(self):
        session=self.connect();session.heartbeat_at=timezone.now()-timedelta(seconds=21);session.save()
        self.assertEqual(runtime.expire_sessions(),1)
        self.item.refresh_from_db();self.assertEqual(self.item.status,'abnormal')
        session.refresh_from_db();self.assertEqual(session.abnormal_reason,'connection_lost')
    def test_waiting_for_connection_has_bounded_timeout(self):
        self.start();session=InterviewRuntime.objects.get();session.started_at=timezone.now()-timedelta(seconds=91);session.save()
        self.assertEqual(runtime.expire_sessions(),1)
    def test_no_dialog_fields_or_secondary_evaluation_routes(self):
        fields={field.name for field in InterviewRuntime._meta.fields}
        self.assertTrue(fields.isdisjoint({'messages','transcript','covered_targets'}))
        for path in ('/api/candidate/room','/api/candidate/turn','/api/candidate/evaluate','/api/candidate/submit'):
            with self.assertRaises(Resolver404):resolve(path)
    def test_invalid_expired_completed_and_private_fields(self):
        self.assertEqual(self.call(candidate.verify,{'code':'bad'})[0],404)
        self.assertEqual(self.call(candidate.verify,{'token':'old'})[0],400)
        self.item.invite_expires_at=timezone.now()-timedelta(seconds=1);self.item.save()
        self.assertEqual(self.call(candidate.verify,{'code':self.code})[0],410)
        self.item.status='completed';self.item.save()
        payload=self.call(candidate.verify,{'code':self.code})[1]['data']['interview']
        self.assertEqual(payload['status'],'completed');self.assertNotIn('candidate_email',payload);self.assertNotIn('page_id_hash',payload)


if __name__=='__main__':unittest.main()
