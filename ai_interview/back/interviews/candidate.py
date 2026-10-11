"""候选人凭证接口，不使用企业登录身份。"""
import hashlib
import re
from functools import wraps

from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .api import APIError, body, only, success
from .models import Interview


def public(view):
    @csrf_exempt
    @wraps(view)
    def wrapped(request):
        try:
            if request.method != 'POST':
                raise APIError('method_not_allowed', 'method_not_allowed', 405)
            # 共享缓存部署时使用 Redis；IP 来自应用的可信代理配置。
            key = 'candidate-rate:' + hashlib.sha256(request.META.get('REMOTE_ADDR', '').encode()).hexdigest()
            cache.add(key, 0, 60)
            if cache.incr(key) > 60:
                raise APIError('rate_limited', 'rate_limited', 429)
            response = view(request)
            response['Cache-Control'] = 'no-store'
            return response
        except APIError as error:
            return JsonResponse({'success': False, 'error': {'code': error.code}}, status=error.status)
    return wrapped


def lookup(data, lock=False):
    only(data, {'code', 'devices_ready', 'consent'})
    code = data.get('code')
    if not isinstance(code, str):
        raise APIError('invalid_invitation', 'invalid_invitation', 404)
    code = re.sub(r'[\s-]', '', code).lower()
    if not re.fullmatch(r'[a-f0-9]{16}', code):
        raise APIError('invalid_invitation', 'invalid_invitation', 404)
    from django.db.models import Q
    query = Interview.objects.filter(deleted_at__isnull=True)
    if lock:
        query = query.select_for_update()
    # 旧版面试码是历史凭证哈希的前缀，保留其可用性；新码只存完整哈希。
    query = query.filter(Q(invitation_token_hash=hashlib.sha256(code.encode()).hexdigest()) | Q(invitation_token_hash__startswith=code))
    items = list(query[:2])
    if len(items) != 1:
        raise APIError('invalid_invitation', 'invalid_invitation', 404)
    item = items[0]
    if item.status == 'expired' or (item.status == 'waiting' and item.invite_expires_at <= timezone.now()):
        raise APIError('invitation_expired', 'invitation_expired', 410)
    if item.status == 'abnormal':
        raise APIError('interview_abnormal', 'interview_abnormal', 409)
    if item.status not in ('waiting', 'running', 'submitting', 'completed'):
        raise APIError('invalid_state', 'invalid_state', 409)
    return item


def payload(item):
    return {'interview': {
        'id': item.id, 'position_name': item.position_name,
        'work_description': item.work_description,
        'language': 'ja', 'duration_minutes': item.duration_minutes,
        'skills': item.skills, 'status': item.status,
        'invite_expires_at': item.invite_expires_at,
    }}


@public
def verify(request):
    return success(payload(lookup(body(request))))


@public
def start(request):
    data = body(request)
    with transaction.atomic():
        item = lookup(data, lock=True)
        if item.status == 'waiting':
            if data.get('devices_ready') is not True or data.get('consent') is not True:
                raise APIError('preparation_required', 'preparation_required', 409)
            item.status = 'running'
            item.updated_at = timezone.now()
            item.save(update_fields=['status', 'updated_at'])
        # 并发或重试只返回当前阶段，不重置已经推进的状态。
        return success(payload(item))


@public
def submit(request):
    with transaction.atomic():
        item = lookup(body(request), lock=True)
        if item.status == 'waiting':
            raise APIError('interview_not_started', 'interview_not_started', 409)
        if item.status == 'running':
            item.status = 'submitting'
            item.updated_at = timezone.now()
            item.save(update_fields=['status', 'updated_at'])
        return success(payload(item))


def health(request):
    if request.method not in ('GET', 'HEAD'):
        return JsonResponse({'success': False}, status=405)
    return success({'available': True})
