"""Runtime metadata and final assessment only. No dialog/transcript persistence."""
import hashlib
import re
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from .api import APIError
from .models import Interview, InterviewRuntime, InterviewReport

ACTIVE = ('running', 'submitting')
ABNORMAL_REASONS = {'page_closed', 'page_reloaded', 'connection_lost', 'connection_timeout',
    'provider_failed', 'recording_failed', 'upload_failed', 'evaluation_failed', 'finish_timeout', 'server_shutdown'}


def page_hash(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', value):
        raise APIError('页面凭证无效。', 'invalid_page', 400)
    return hashlib.sha256(value.encode()).hexdigest()


def owns(runtime, page_id):
    try:
        return constant_time_compare(runtime.page_id_hash, page_hash(page_id))
    except APIError:
        return False


def abnormal(item, runtime, reason):
    # 调用方须持有行锁并处于事务中；终态不再修改，避免迟到消息覆盖结果。
    if item.status not in ACTIVE:
        return
    now = timezone.now()
    item.status = 'abnormal'; item.updated_at = now
    item.save(update_fields=['status', 'updated_at'])
    if runtime:
        runtime.abnormal_reason = reason if reason in ABNORMAL_REASONS else 'connection_lost'
        runtime.closed_at = now
        # 异常面试保留已上传录制，但丢弃尚未发布的评价草稿。
        runtime.evaluation = None
        runtime.recording_state = 'partial' if runtime.recording_chunks else 'missing'
        runtime.save(update_fields=['abnormal_reason', 'closed_at', 'evaluation', 'recording_state'])


def stale_reason(runtime, now=None):
    now = now or timezone.now()
    if runtime.connected_at is None:
        return 'connection_timeout' if now > runtime.started_at + timedelta(seconds=90) else None
    if runtime.heartbeat_at is None or now > runtime.heartbeat_at + timedelta(seconds=20):
        return 'connection_lost'
    if runtime.finishing_at and now > runtime.finishing_at + timedelta(seconds=120):
        return 'finish_timeout'
    return None


def inspect(item, page_id):
    runtime = InterviewRuntime.objects.select_for_update().filter(interview=item).first()
    if item.status in ACTIVE:
        if runtime is None or not owns(runtime, page_id):
            abnormal(item, runtime, 'page_reloaded')
        elif reason := stale_reason(runtime):
            abnormal(item, runtime, reason)
    return runtime


def require(item, page_id, *, allow_abnormal=False):
    runtime = InterviewRuntime.objects.select_for_update().filter(interview=item).first()
    if runtime is None or not owns(runtime, page_id):
        raise APIError('页面凭证无效。', 'invalid_page', 403)
    if item.status not in ACTIVE + (('abnormal',) if allow_abnormal else ()):
        raise APIError('当前面试阶段不允许此操作。', 'invalid_state', 409)
    if item.status in ACTIVE and (reason := stale_reason(runtime)):
        # Callers needing terminalization commit it before returning an error.
        raise APIError('面试连接已中断。', 'interview_abnormal', 409)
    return runtime


def expire_sessions():
    count = 0
    now = timezone.now()
    # 先筛选疑似超时记录，再逐条加锁复核；多个 ASGI worker 不争抢健康会话。
    suspect = (Q(runtime__isnull=True)
        | Q(runtime__connected_at__isnull=True, runtime__started_at__lt=now-timedelta(seconds=90))
        | (Q(runtime__connected_at__isnull=False) & (
            Q(runtime__heartbeat_at__isnull=True)
            | Q(runtime__heartbeat_at__lt=now-timedelta(seconds=20))
            | Q(runtime__finishing_at__lt=now-timedelta(seconds=120)))))
    ids = Interview.objects.filter(suspect, status__in=ACTIVE, deleted_at__isnull=True).values_list('pk', flat=True)
    for pk in ids.iterator(chunk_size=200):
        with transaction.atomic():
            item = Interview.objects.select_for_update().get(pk=pk)
            if item.status not in ACTIVE or item.deleted_at is not None:
                continue
            runtime = InterviewRuntime.objects.select_for_update().filter(interview=item).first()
            reason = stale_reason(runtime) if runtime else 'connection_lost'
            if reason:
                abnormal(item, runtime, reason); count += 1
    return count


def sweep():
    """HTTP deployments inspect abandoned sessions on candidate/company requests."""
    from django.core.cache import cache
    if cache.add('candidate-runtime-sweep', True, 5):
        return expire_sessions()
    return 0


def complete(item, runtime):
    """Publish only when the same live session's assessment AND recording are complete."""
    if item.status != 'submitting' or not runtime.evaluation or runtime.recording_state != 'complete':
        return False
    # 两个输出可能先后到达；在同一事务内发布报告并更新终态，防止重复发布。
    from .ai import validate_report
    report = validate_report(item, runtime.evaluation)
    now = timezone.now()
    existing = InterviewReport.objects.filter(interview=item).order_by('id').first()
    if existing is None:
        existing = InterviewReport(interview=item, created_at=now)
    existing.report_text = report['report_text']
    existing.assessment_scores = report['assessment_scores']
    existing.generated_at = existing.updated_at = now
    existing.deleted_at = existing.read_at = None
    existing.save()
    item.status = 'completed'; item.updated_at = now
    item.save(update_fields=['status', 'updated_at'])
    runtime.closed_at = now; runtime.evaluation = None
    runtime.save(update_fields=['closed_at', 'evaluation'])
    return True
