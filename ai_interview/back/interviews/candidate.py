"""Candidate credentials; page ownership is ephemeral and a live run is never resumed."""
import hashlib
import re
import json
import logging
import ssl
import certifi
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from django.conf import settings
from datetime import timedelta
from functools import wraps
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .api import APIError, body, only, success, error_response
from .models import Interview, InterviewRuntime
from . import runtime, ai

logger = logging.getLogger(__name__)


def provider_tls_context():
    # Preserve OS/custom trust roots and add Mozilla roots for Python installs
    # (notably macOS) whose default CA store is missing or incomplete.
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


def public(view):
    @csrf_exempt
    @wraps(view)
    def wrapped(request):
        try:
            if request.method != 'POST':
                raise APIError('请求方法不支持。','method_not_allowed',405)
            key = 'candidate-rate:' + hashlib.sha256(request.META.get('REMOTE_ADDR','').encode()).hexdigest()
            cache.add(key,0,60)
            if cache.incr(key) > 60:
                raise APIError('尝试过于频繁，请稍后重试。','rate_limited',429)
            # HTTP 部署没有 ASGI lifespan，访问入口同样触发超时巡检。
            runtime.sweep()
            response = view(request)
        except APIError as error:
            response = JsonResponse({'success':False,'error':{'code':error.code,'message':error.message}},status=error.status)
        response['Cache-Control'] = 'no-store'
        return response
    return wrapped


def lookup(data, lock=False):
    only(data, {'code','page_id','devices_ready','consent','reason'})
    code = data.get('code')
    if not isinstance(code,str):
        raise APIError('面试码无效。','invalid_invitation',404)
    code = re.sub(r'[\s-]','',code).lower()
    if not re.fullmatch(r'[a-f0-9]{16}',code):
        raise APIError('面试码无效。','invalid_invitation',404)
    from django.db.models import Q
    query = Interview.objects.filter(deleted_at__isnull=True)
    if lock:query=query.select_for_update()
    items=list(query.filter(Q(invitation_token_hash=hashlib.sha256(code.encode()).hexdigest()) | Q(invitation_token_hash__startswith=code))[:2])
    if len(items)!=1:raise APIError('面试码无效。','invalid_invitation',404)
    item=items[0]
    if item.status=='expired' or (item.status=='waiting' and item.invite_expires_at<=timezone.now()):
        raise APIError('邀请已过期，请联系邀请方。','invitation_expired',410)
    if item.status not in ('waiting','running','submitting','completed','abnormal'):
        raise APIError('面试状态无效。','invalid_state',409)
    return item


def payload(item):
    session=InterviewRuntime.objects.filter(interview=item).first() if item.status!='waiting' else None
    return {'interview':{'id':item.id,'position_name':item.position_name,'work_description':item.work_description,
        'language':'ja','duration_minutes':item.duration_minutes,'skills':item.skills,'status':item.status,
        'invite_expires_at':item.invite_expires_at,'server_time':timezone.now().isoformat(),
        'deadline_at':session.deadline_at.isoformat() if session else None,
        'abnormal_reason':session.abnormal_reason if session and item.status=='abnormal' else None}}


@public
def verify(request):
    data=body(request);only(data,{'code','page_id'})
    with transaction.atomic():
        item=lookup(data,lock=True)
        runtime.inspect(item,data.get('page_id'))
        return success(payload(item))


@public
def start(request):
    data=body(request);only(data,{'code','page_id','devices_ready','consent'})
    with transaction.atomic():
        item=lookup(data,lock=True)
        if item.status=='waiting':
            ai.configured()
            owner=runtime.page_hash(data.get('page_id'))
            if data.get('devices_ready') is not True or data.get('consent') is not True:
                raise APIError('请完成设备检查并确认准备就绪。','preparation_required',409)
            now=timezone.now()
            InterviewRuntime.objects.create(interview=item,page_id_hash=owner,started_at=now,
                deadline_at=now+timedelta(minutes=item.duration_minutes),recording_chunks={})
            item.status='running';item.updated_at=now;item.save(update_fields=['status','updated_at'])
        else:runtime.inspect(item,data.get('page_id'))
        return success(payload(item))


@public
def abort(request):
    data=body(request);only(data,{'code','page_id','reason'})
    with transaction.atomic():
        item=lookup(data,lock=True)
        session=InterviewRuntime.objects.select_for_update().filter(interview=item).first()
        if item.status in runtime.ACTIVE:
            if not session or not runtime.owns(session,data.get('page_id')):
                runtime.abnormal(item,session,'page_reloaded')
            else:
                runtime.abnormal(item,session,data.get('reason','connection_lost'))
        return success(payload(item))


def health(request):
    if request.method not in ('GET','HEAD'):return JsonResponse({'success':False},status=405)
    return success({'available':True})


def mint_secret(item):
    """Only a short-lived client credential is returned; never log provider bodies."""
    ai.configured()
    request = Request('https://api.openai.com/v1/realtime/client_secrets',
        data=json.dumps({'expires_after': {'anchor': 'created_at', 'seconds': 60},
                         'session': ai.configuration(item)}).encode(),
        headers={'Authorization': 'Bearer ' + settings.OPENAI_API_KEY,
                 'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(request, timeout=10, context=provider_tls_context()) as response:
            result = json.loads(response.read(65536))
        if not isinstance(result.get('value'), str) or not result['value']:
            raise ValueError()
        return {'value': result['value'], 'expires_at': result['expires_at']}
    except HTTPError as error:
        # Do not log bodies: they can contain credentials or interview prompts.
        logger.warning('Realtime credential request rejected: status=%s', error.code)
        raise APIError('无法连接 AI 服务，请联系邀请方检查密钥和服务配置。', 'provider_failed', 503) from None
    except URLError as error:
        certificate_error = isinstance(error.reason, ssl.SSLCertVerificationError)
        logger.warning('Realtime credential connection failed: reason=%s',
                       'certificate_verify_failed' if certificate_error else type(error.reason).__name__)
        message = ('AI 服务证书校验失败，请联系邀请方检查服务器证书配置。' if certificate_error
                   else '无法连接 AI 服务，请联系邀请方检查服务器网络配置。')
        raise APIError(message, 'provider_failed', 503) from None
    except (TimeoutError, ValueError, KeyError, TypeError) as error:
        logger.warning('Realtime credential request failed: reason=%s', type(error).__name__)
        raise APIError('无法连接 AI 服务，请联系邀请方检查密钥和服务配置。', 'provider_failed', 503)


@public
def client_secret(request):
    data = body(request); only(data, {'code', 'page_id'})
    rejection = None
    with transaction.atomic():
        item = lookup(data, lock=True)
        session = runtime.inspect(item, data.get('page_id'))
        if item.status != 'running' or session is None or session.connected_at is not None:
            if item.status == 'running':
                runtime.abnormal(item, session, 'connection_lost')
            rejection = APIError('当前面试不能建立新的连接。', 'invalid_state', 409)
        else:
            session.connected_at = session.heartbeat_at = timezone.now()
            session.save(update_fields=['connected_at', 'heartbeat_at'])
    # 检查产生的异常终态必须先提交，不能随错误响应一起回滚。
    if rejection is not None:
        raise rejection
    # 外部请求不持有数据库锁。
    try:
        secret = mint_secret(item)
    except APIError:
        with transaction.atomic():
            item = lookup(data, lock=True)
            session = InterviewRuntime.objects.select_for_update().get(interview=item)
            runtime.abnormal(item, session, 'provider_failed')
        raise
    with transaction.atomic():
        item = lookup(data, lock=True)
        session = runtime.require(item, data.get('page_id'))
        if item.status != 'running':
            raise APIError('面试已结束。', 'invalid_state', 409)
        return success({**payload(item), 'client_secret': secret,
                        'evaluation_response': ai.evaluation_response(item)})


def browser_state(request, action):
    data = body(request)
    only(data, {'code', 'page_id', 'evaluation'} if action == 'evaluation' else {'code', 'page_id'})
    with transaction.atomic():
        item = lookup({'code': data.get('code')}, lock=True)
        session = runtime.inspect(item, data.get('page_id'))
        if not session or not runtime.owns(session, data.get('page_id')):
            # 返回响应而非抛异常，保留 inspect 写入的页面刷新异常状态。
            return error_response('页面凭证无效。', code='invalid_page', status=403)
        if item.status in ('completed', 'abnormal'):
            return success(payload(item))
        if not session.connected_at:
            raise APIError('请先连接面试。', 'invalid_state', 409)
        now = timezone.now()
        fields = ['heartbeat_at']; session.heartbeat_at = now
        if action == 'finish' or now >= session.deadline_at:
            if item.status == 'running':
                item.status = 'submitting'; item.updated_at = now
                item.save(update_fields=['status', 'updated_at'])
                session.finishing_at = now; fields.append('finishing_at')
        if action == 'evaluation':
            if item.status != 'submitting':
                raise APIError('请先结束面试。', 'invalid_state', 409)
            evaluation = data.get('evaluation'); ai.validate_report(item, evaluation)
            if session.evaluation is not None and session.evaluation != evaluation:
                raise APIError('评价已提交，不能修改。', 'evaluation_conflict', 409)
            # 客户端提交的评价经过格式校验，不视为服务端验证的 AI 输出。
            session.evaluation = evaluation; fields.append('evaluation')
        session.save(update_fields=fields)
        runtime.complete(item, session)
        return success(payload(item))


@public
def heartbeat(request):
    return browser_state(request, 'heartbeat')


@public
def finish(request):
    return browser_state(request, 'finish')


@public
def evaluation(request):
    return browser_state(request, 'evaluation')
