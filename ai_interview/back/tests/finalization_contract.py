"""Final Live assessment + recording contracts; no transcript-driven evaluation."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from candidate_contract import Fixture
from django.test import RequestFactory,override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from interviews import candidate,media,ai
from interviews.models import InterviewReport

EVALUATION={'summary':'実装能力の概要。','conclusion':'技術面を採用担当者が確認してください。',
    'scores':[{'id':'coding','score':80,'evaluation':'設計判断の説明が具体的。','sufficient_evidence':True}]}


class RecordingFixture(Fixture):
    def setUp(self):
        super().setUp();self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.override=override_settings(MEDIA_ROOT=Path(self.temporary.name));self.override.enable();self.addCleanup(self.override.disable)
        self.session=self.connect()
    def part(self,index,data=b'\x1aE\xdf\xa3webm-header',page=None):
        request=RequestFactory().post('/',{'code':self.code,'page_id':page or self.page,'index':str(index),'mime':'video/webm',
            'chunk':SimpleUploadedFile('part',data,content_type='video/webm')})
        response=media.upload(request);return response.status_code,json.loads(response.content)
    def seal(self,count=2):return self.call(media.seal,{'code':self.code,'page_id':self.page,'count':count,'duration_ms':10000})
    def finish(self):return self.call(candidate.finish,{'code':self.code,'page_id':self.page})
    def evaluate(self):
        return self.call(candidate.evaluation,{'code':self.code,'page_id':self.page,'evaluation':EVALUATION})[1]['data']['interview']['status']


class FinalizationContract(RecordingFixture):
    def test_chunks_are_ordered_and_idempotent(self):
        self.assertEqual(self.part(1,b'tail')[0],200);self.assertEqual(self.part(0)[0],200)
        self.assertEqual(self.part(1,b'tail')[0],200);self.assertEqual(self.part(1,b'different')[0],409)
        self.finish();self.assertEqual(self.seal()[0],200)
        self.item.refresh_from_db();data=(Path(self.temporary.name)/self.item.video_storage_key).read_bytes()
        self.assertEqual(data,b'\x1aE\xdf\xa3webm-headertail')
        self.assertEqual(self.item.recording_storage_key,self.item.video_storage_key)
    def test_no_completed_status_until_both_outputs_exist(self):
        self.part(0);self.part(1,b'tail');self.finish()
        self.assertEqual(self.evaluate(),'submitting')
        self.assertFalse(InterviewReport.objects.exists())
        result=self.seal();self.assertEqual(result[1]['data']['interview']['status'],'completed')
        self.assertEqual(InterviewReport.objects.count(),1)
        self.assertEqual(self.seal()[0],200);self.assertEqual(InterviewReport.objects.count(),1)
    def test_media_can_complete_before_evaluation(self):
        self.part(0);self.part(1,b'tail');self.finish();self.seal()
        self.assertEqual(self.evaluate(),'completed')
        self.assertEqual(InterviewReport.objects.count(),1)
    def test_incomplete_and_early_seals_are_rejected(self):
        self.part(0);self.assertEqual(self.seal()[0],409)
        self.finish();self.assertEqual(self.seal()[0],409)
        self.assertFalse(InterviewReport.objects.exists())
    def test_abnormal_preserves_parts_and_discards_unpublished_assessment(self):
        self.part(0);self.finish();self.evaluate()
        self.call(candidate.abort,{'code':self.code,'page_id':self.page,'reason':'connection_lost'})
        self.session.refresh_from_db();self.assertIsNone(self.session.evaluation);self.assertEqual(self.session.recording_state,'partial')
        self.assertTrue((media.folder(self.item,self.session)/'parts/0000.part').exists())
        self.assertFalse(InterviewReport.objects.exists())
        self.assertEqual(self.call(candidate.verify,{'code':self.code,'page_id':self.page})[1]['data']['interview']['status'],'abnormal')
    def test_wrong_owner_and_corrupt_header_rejected(self):
        self.assertEqual(self.part(0,page='b'*32)[0],403)
        self.assertEqual(self.part(0,b'not-video')[0],400)
        self.assertFalse(self.session.recording_chunks)
    def test_corrupt_or_missing_part_cannot_publish_report(self):
        self.part(0);self.finish()
        self.evaluate()
        part=media.folder(self.item,self.session)/'parts/0000.part'
        part.write_bytes(b'corrupt')
        self.assertEqual(self.seal(1)[0],409)
        part.unlink()
        self.assertEqual(self.seal(1)[0],503)
        self.assertFalse(InterviewReport.objects.exists())
        self.session.refresh_from_db()
        self.assertIsNone(self.session.recording_final_count)

    def test_merge_releases_locks_and_rechecks_abnormal_status(self):
        from django.db import connection
        self.part(0);self.finish()
        self.evaluate()
        original=Path.open
        def open_part(path,*args,**kwargs):
            if path.suffix=='.part':
                self.assertFalse(connection.in_atomic_block,'file merge must not hold DB locks')
                self.call(candidate.abort,{'code':self.code,'page_id':self.page,'reason':'connection_lost'})
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',open_part):
            result=self.seal(1)
        self.assertEqual(result[0],200)
        self.assertEqual(result[1]['data']['interview']['status'],'abnormal')
        self.assertFalse(InterviewReport.objects.exists())
        self.session.refresh_from_db()
        self.assertEqual(self.session.recording_state,'partial')

    def test_seal_retries_must_match_duration(self):
        self.part(0);self.finish();self.seal(1)
        response=self.call(media.seal,{'code':self.code,'page_id':self.page,'count':1,'duration_ms':20000})
        self.assertEqual(response[0],409)

    def test_final_score_validation_and_missing_evidence(self):
        bad={**EVALUATION,'scores':[dict(EVALUATION['scores'][0],id='other')]}
        with self.assertRaises(ai.APIError):ai.validate_report(self.item,bad)
        result=ai.validate_report(self.item,{**EVALUATION,'scores':[dict(EVALUATION['scores'][0],sufficient_evidence=False)]})
        self.assertIn('評価保留',result['report_text']);self.assertEqual(result['assessment_scores'][0]['score'],0)
    def test_private_recording_supports_ranges_and_company_isolation(self):
        self.part(0);self.part(1,b'tail');self.finish();self.seal()
        request=RequestFactory().get('/',HTTP_RANGE='bytes=0-3');request.session={'user_account_id':self.account.pk}
        request.scope={}
        response=media.recording(request,self.item.pk);self.assertEqual(response.status_code,206)
        async def read():
            return b''.join([block async for block in response])
        self.assertEqual(asyncio.run(read()),b'\x1aE\xdf\xa3')
        request.session={};self.assertEqual(media.recording(request,self.item.pk).status_code,401)
    def test_invalid_recording_ranges_return_416(self):
        self.part(0);self.finish();self.seal(1)
        for value in ('bytes=-0','bytes=8-3','bytes=999-','bytes=0-1,3-4','bytes='+'9'*5000+'-'):
            with self.subTest(value=value[:40]):
                request=RequestFactory().get('/',HTTP_RANGE=value)
                request.session={'user_account_id':self.account.pk}
                response=media.recording(request,self.item.pk)
                self.assertEqual(response.status_code,416)
                self.assertTrue(response['Content-Range'].startswith('bytes */'))


if __name__=='__main__':unittest.main()
