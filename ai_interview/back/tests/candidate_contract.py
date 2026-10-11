"""隔离的 SQLite 契约测试：不连接业务数据库。运行 python tests/candidate_contract.py。"""
import hashlib
import json
import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from django.conf import settings
settings.configure(INSTALLED_APPS=['accounts', 'interviews'], DATABASES={'default': {'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}, USE_TZ=True, SECRET_KEY='test', CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache'}}, AI_INTERVIEW_INVITATION_BASE_URL='http://localhost/candidate.html')
import django
django.setup()
from django.db import connection
from django.core.cache import cache
from django.test import RequestFactory
from django.utils import timezone
from interviews.models import Interview
from interviews.candidate import verify, start, submit
from interviews.views import invitation_data, new_invitation

class CandidateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            editor.create_model(Interview)
    def setUp(self):
        Interview.objects.all().delete(); cache.clear()
        self.code = 'ABCD-1234-5678-EF90'
        now = timezone.now()
        self.item = Interview.objects.create(user_id=1,request_id='one',invitation_token_hash=hashlib.sha256(self.code.replace('-', '').lower().encode()).hexdigest(),position_name='Backend',work_description='Build services',skills=[{'name':'Python'}],assessment_targets=[],candidate_name='A',candidate_email='a@example.com',invite_expires_at=now+timedelta(days=1),created_at=now,updated_at=now)
    def call(self, view, data):
        response = view(RequestFactory().post('/',json.dumps(data),content_type='application/json'))
        return response.status_code, json.loads(response.content)
    def test_both_credentials_and_rotation(self):
        code=invitation_data(self.code)['invitation_code']
        for data in [{'code':self.code},{'code':code.replace('-', '').lower()}]:
            status,result=self.call(verify,data); self.assertEqual(status,200); self.assertEqual(result['data']['interview']['id'],self.item.id)
        self.item.invitation_token_hash=hashlib.sha256(('b'*43).encode()).hexdigest();self.item.save()
        self.assertEqual(self.call(verify,{'code':code})[0],404)
        self.assertEqual(self.call(verify,{'token':'a'*43})[0],400)
    def test_start_requires_readiness_and_is_monotonic(self):
        self.assertEqual(self.call(start,{'code':self.code})[0],409)
        data={'code':self.code,'devices_ready':True,'consent':True}
        self.assertEqual(self.call(start,data)[1]['data']['interview']['status'],'running')
        self.assertEqual(self.call(start,data)[1]['data']['interview']['status'],'running')
        self.assertEqual(self.call(submit,{'code':self.code})[1]['data']['interview']['status'],'submitting')
        self.assertEqual(self.call(start,data)[1]['data']['interview']['status'],'submitting')
        self.assertEqual(self.call(verify,{'code':self.code})[1]['data']['interview']['status'],'submitting')
    def test_expired_deleted_completed_invalid(self):
        self.item.invite_expires_at=timezone.now()-timedelta(seconds=1);self.item.save()
        self.assertEqual(self.call(verify,{'code':self.code})[0],410)
        self.item.status='completed';self.item.save()
        self.assertEqual(self.call(verify,{'code':self.code})[1]['data']['interview']['status'],'completed')
        self.item.deleted_at=timezone.now();self.item.save()
        self.assertEqual(self.call(verify,{'code':self.code})[0],404)
        self.assertEqual(self.call(verify,{'code':'bad'})[0],404)
    def test_submit_before_start_and_no_private_fields(self):
        self.assertEqual(self.call(submit,{'code':self.code})[0],409)
        payload=self.call(verify,{'code':self.code})[1]['data']['interview']
        self.assertNotIn('candidate_email',payload);self.assertNotIn('invitation_token_hash',payload)
    def test_invitations_are_isolated(self):
        original_id = self.item.id
        self.item.pk = None
        self.item.request_id = 'two'
        other = '1234567890abcdef'
        self.item.invitation_token_hash = hashlib.sha256(other.encode()).hexdigest()
        self.item.save()
        self.call(start, {'code': self.code, 'devices_ready': True, 'consent': True})
        self.assertEqual(self.call(verify, {'code': other})[1]['data']['interview']['status'], 'waiting')
        self.assertNotEqual(self.call(verify, {'code': other})[1]['data']['interview']['id'], original_id)

    def test_new_code_is_shared_by_link_and_manual_entry(self):
        from urllib.parse import urlparse, parse_qs
        code, digest = new_invitation()
        data = invitation_data(code)
        self.assertNotIn('invitation_token', data)
        self.assertEqual(parse_qs(urlparse(data['invitation_url']).query)['code'][0], code)
        self.assertEqual(digest, hashlib.sha256(code.replace('-', '').lower().encode()).hexdigest())
        self.item.invitation_token_hash = digest
        self.item.save()
        self.assertEqual(self.call(verify, {'code': code})[0], 200)

    def test_rate_limit(self):
        for _ in range(60):self.call(verify,{'code':'bad'})
        self.assertEqual(self.call(verify,{'code':'bad'})[0],429)

if __name__=='__main__':unittest.main()
