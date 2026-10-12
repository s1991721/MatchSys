"""Browser-owned Realtime session contracts, isolated DB and mocked credential minting."""
import json
import unittest
import ssl
from urllib.error import URLError
from unittest.mock import patch
from datetime import timedelta
import finalization_contract
EVALUATION = finalization_contract.EVALUATION
from django.utils import timezone
from django.test import override_settings
from interviews import candidate
from interviews.models import InterviewReport


class BrowserContract(finalization_contract.RecordingFixture):
    def test_provider_tls_keeps_certificate_and_hostname_verification(self):
        context=candidate.provider_tls_context()
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(context.cert_store_stats()['x509_ca'],0)

    def test_certificate_failure_is_diagnosed_without_leaking_secrets(self):
        with patch.object(candidate,'urlopen',side_effect=URLError(ssl.SSLCertVerificationError('private-detail'))), override_settings(
            AI_INTERVIEW_REALTIME_MODEL='gpt-realtime',AI_INTERVIEW_REALTIME_VOICE='marin'), self.assertLogs(candidate.logger,level='WARNING') as logs:
            with self.assertRaises(candidate.APIError) as caught:
                candidate.mint_secret(self.item)
        self.assertIn('证书校验失败',caught.exception.message)
        self.assertIn('certificate_verify_failed',' '.join(logs.output))
        self.assertNotIn('private-detail',' '.join(logs.output))

    def token(self):
        return self.call(candidate.client_secret, {'code':self.code, 'page_id':self.page})
    def event(self, view, **extra):
        return self.call(view, {'code':self.code, 'page_id':self.page, **extra})
    def test_short_credential_is_issued_only_once_and_never_returns_main_key(self):
        self.session.connected_at=None;self.session.save()
        with patch.object(candidate, 'mint_secret', return_value={'value':'ek_test','expires_at':123}), override_settings(
            AI_INTERVIEW_REALTIME_MODEL='gpt-realtime',AI_INTERVIEW_REALTIME_VOICE='marin'):
            status,data=self.token()
            self.assertEqual(status,200)
            self.assertEqual(data['data']['client_secret']['value'],'ek_test')
            self.assertNotIn('test-key',json.dumps(data))
            self.assertEqual(data['data']['evaluation_response']['tools'][0]['name'],'submit_interview_report')
            evaluation=data['data']['evaluation_response']
            self.assertEqual(evaluation['tool_choice'],'required')
            self.assertIn('coding',evaluation['instructions'])
            self.assertIn('提前结束',evaluation['instructions'])
            self.assertEqual(self.token()[0],409)
            self.item.refresh_from_db()
            self.assertEqual(self.item.status,'abnormal')
    def test_wrong_page_credential_request_commits_abnormal_state(self):
        self.session.connected_at=None;self.session.save()
        # 禁用入口巡检，确保异常终态确实由连接入口提交。
        with patch.object(candidate.runtime,'sweep'), patch.object(candidate,'mint_secret') as mint:
            status,_=self.call(candidate.client_secret,{'code':self.code,'page_id':'b'*32})
        self.assertEqual(status,409);mint.assert_not_called()
        self.item.refresh_from_db();self.session.refresh_from_db()
        self.assertEqual(self.item.status,'abnormal')
        self.assertEqual(self.session.abnormal_reason,'page_reloaded')
    def test_stale_credential_request_commits_abnormal_state(self):
        self.session.heartbeat_at=timezone.now()-timedelta(seconds=21);self.session.save()
        with patch.object(candidate.runtime,'sweep'), patch.object(candidate,'mint_secret') as mint:
            self.assertEqual(self.token()[0],409)
        mint.assert_not_called()
        self.item.refresh_from_db();self.assertEqual(self.item.status,'abnormal')
    def test_provider_failure_ends_attempt_without_leaking_provider_response(self):
        self.session.connected_at=None;self.session.save()
        with patch.object(candidate,'mint_secret',side_effect=candidate.APIError('AI unavailable','provider_failed',503)):
            self.assertEqual(self.token()[0],503)
        self.item.refresh_from_db();self.assertEqual(self.item.status,'abnormal')
    def test_provider_mint_uses_webrtc_configuration_and_returns_only_short_secret(self):
        with patch.object(candidate, 'urlopen') as upstream, override_settings(
            AI_INTERVIEW_REALTIME_MODEL='gpt-realtime',AI_INTERVIEW_REALTIME_VOICE='marin'):
            upstream.return_value.__enter__.return_value.read.return_value=json.dumps(
                {'value':'ek_short','expires_at':123,'session':{'private':'ignored'}}).encode()
            result=candidate.mint_secret(self.item)
            request=upstream.call_args.args[0];data=json.loads(request.data)
            self.assertEqual(data['expires_after']['seconds'],60)
            self.assertEqual(data['session']['model'],'gpt-realtime')
            self.assertNotIn('format',data['session']['audio']['input'])
            self.assertNotIn('format',data['session']['audio']['output'])
            self.assertIn('Coding',data['session']['instructions'])
            self.assertEqual(result,{'value':'ek_short','expires_at':123})
    def test_frontend_evaluation_and_recording_can_arrive_in_either_order(self):
        self.part(0);self.finish()
        self.assertEqual(self.event(candidate.evaluation,evaluation=EVALUATION)[0],200)
        self.assertEqual(InterviewReport.objects.count(),0)
        self.assertEqual(self.event(candidate.evaluation,evaluation=EVALUATION)[0],200)
        changed={**EVALUATION,'summary':'changed'}
        self.assertEqual(self.event(candidate.evaluation,evaluation=changed)[0],409)
        self.assertEqual(self.seal(1)[1]['data']['interview']['status'],'completed')
        self.assertEqual(self.event(candidate.evaluation,evaluation=EVALUATION)[0],200)
        self.assertEqual(InterviewReport.objects.count(),1)
    def test_evaluation_requires_finish_and_valid_targets(self):
        self.assertEqual(self.event(candidate.evaluation,evaluation=EVALUATION)[0],409)
        self.finish()
        bad={**EVALUATION,'scores':[dict(EVALUATION['scores'][0],score=101)]}
        self.assertEqual(self.event(candidate.evaluation,evaluation=bad)[0],400)
        self.assertFalse(InterviewReport.objects.exists())
    def test_heartbeat_enforces_deadline_and_stale_sessions(self):
        self.session.deadline_at=timezone.now()-timedelta(seconds=1);self.session.save()
        self.assertEqual(self.event(candidate.heartbeat)[1]['data']['interview']['status'],'submitting')
        self.session.refresh_from_db();self.assertIsNotNone(self.session.finishing_at)
        self.session.heartbeat_at=timezone.now()-timedelta(seconds=21);self.session.save()
        self.assertEqual(self.event(candidate.heartbeat)[1]['data']['interview']['status'],'abnormal')
        self.assertEqual(self.event(candidate.evaluation,evaluation=EVALUATION)[1]['data']['interview']['status'],'abnormal')
        self.assertFalse(InterviewReport.objects.exists())
    def test_browser_cannot_submit_from_another_page(self):
        response=self.call(candidate.evaluation,{'code':self.code,'page_id':'b'*32,'evaluation':EVALUATION})
        self.assertEqual(response[0],403);self.assertFalse(InterviewReport.objects.exists())
        self.item.refresh_from_db();self.session.refresh_from_db()
        self.assertEqual(self.item.status,'abnormal')
        self.assertEqual(self.session.abnormal_reason,'page_reloaded')


if __name__=='__main__':unittest.main()
