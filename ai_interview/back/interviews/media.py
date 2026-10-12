"""Idempotent browser recording chunks; private files contain candidate video + mixed audio."""
import asyncio
import hashlib
import os
import re
import tempfile
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, StreamingHttpResponse
from .api import APIError, body, only, integer, success, endpoint
from .candidate import public, lookup, payload
from .models import Interview, InterviewRuntime
from . import runtime

MAX_PART = 8 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_PARTS = 256
MIMES = {'video/webm':'webm', 'video/mp4':'mp4'}


def folder(item, session):
    return Path(settings.MEDIA_ROOT) / 'interviews' / str(item.pk) / session.page_id_hash[:24]


def validate_mime(value):
    if not isinstance(value,str) or len(value)>100 or value.split(';')[0] not in MIMES:
        raise APIError('录制格式不支持。','invalid_recording',400)
    return value.split(';')[0]


def atomic_write(path, chunks):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as handle:
            temporary=Path(handle.name)
            for chunk in chunks:handle.write(chunk)
        os.replace(temporary,path)
    finally:
        if temporary and temporary.exists():temporary.unlink()


@public
def upload(request):
    only(request.POST,{'code','page_id','index','mime'})
    if set(request.FILES)!={'chunk'}:raise APIError('请提交录制分片。','invalid_recording',400)
    try:index=int(request.POST.get('index',''))
    except (ValueError,TypeError):raise APIError('分片编号无效。','invalid_recording',400)
    integer(index,'index',0,MAX_PARTS-1)
    uploaded=request.FILES['chunk'];mime=validate_mime(request.POST.get('mime'))
    if not 0<uploaded.size<=MAX_PART:raise APIError('录制分片超过 8MB 或为空。','invalid_recording',400)
    content=uploaded.read();digest=hashlib.sha256(content).hexdigest()
    if index==0 and not (content.startswith(b'\x1aE\xdf\xa3') if mime=='video/webm' else len(content)>8 and content[4:8]==b'ftyp'):
        raise APIError('录制文件格式无效。','invalid_recording',400)
    with transaction.atomic():
        item=lookup({'code':request.POST.get('code')},lock=True)
        session=runtime.require(item,request.POST.get('page_id'),allow_abnormal=True)
        # 编号、摘要和大小共同保证重试幂等；同编号不同内容不能覆盖原始录制。
        existing=session.recording_chunks.get(str(index))
        if existing:
            if existing['sha256']!=digest or existing['size']!=len(content) or session.recording_mime!=mime:
                raise APIError('同一分片内容不一致。','recording_conflict',409)
            return success({'stored':True,'index':index})
        if session.recording_final_count is not None:
            raise APIError('录制已经封存。','recording_sealed',409)
        if session.recording_mime and session.recording_mime!=mime:
            raise APIError('录制格式发生变化。','invalid_recording',400)
        if sum(row['size'] for row in session.recording_chunks.values())+len(content)>MAX_TOTAL:
            raise APIError('录制文件超过大小限制。','invalid_recording',400)
        path=folder(item,session)/'parts'/f'{index:04d}.part'
        atomic_write(path,[content])
        session.recording_mime=mime
        session.recording_chunks={**session.recording_chunks,str(index):{'sha256':digest,'size':len(content)}}
        session.recording_state='partial' if item.status=='abnormal' else 'recording'
        session.save(update_fields=['recording_chunks','recording_mime','recording_state'])
    return success({'stored':True,'index':index})


def sealed_response(item, session, count, duration):
    if session.recording_final_count is None:
        return None
    if (session.recording_final_count, session.recording_duration_ms) != (count, duration):
        raise APIError('封存参数不一致。', 'recording_conflict', 409)
    return success(payload(item))


@public
def seal(request):
    data = body(request)
    only(data, {'code', 'page_id', 'count', 'duration_ms'})
    count = integer(data.get('count'), 'count', 1, MAX_PARTS)
    duration = integer(data.get('duration_ms'), 'duration_ms', 1, 30 * 60 * 1000)
    with transaction.atomic():
        item = lookup({'code': data.get('code')}, lock=True)
        session = InterviewRuntime.objects.select_for_update().filter(interview=item).first()
        if item.status == 'completed' and session and runtime.owns(session, data.get('page_id')):
            return sealed_response(item, session, count, duration)
        session = runtime.require(item, data.get('page_id'), allow_abnormal=True)
        if item.status == 'running':
            raise APIError('请先结束面试。', 'invalid_state', 409)
        if response := sealed_response(item, session, count, duration):
            return response
        # 保存上传清单快照；耗时合并结束后，重新加锁核对状态和清单。
        manifest = session.recording_chunks
        if set(manifest) != set(map(str, range(count))):
            raise APIError('录制分片尚未全部上传。', 'recording_incomplete', 409)
        extension = MIMES.get(session.recording_mime)
        if not extension:
            raise APIError('录制格式无效。', 'invalid_recording', 400)
        destination = folder(item, session) / ('recording.' + extension)

    # Merging up to 256 MB must not block Live heartbeats or abnormal terminalization.
    # A private temporary file also isolates concurrent seal requests.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            for index in range(count):
                digest = hashlib.sha256()
                size = 0
                with (destination.parent / 'parts' / f'{index:04d}.part').open('rb') as source:
                    while block := source.read(65536):
                        digest.update(block)
                        size += len(block)
                        output.write(block)
                # 校验落盘内容，避免缺片或磁盘损坏被当作完整录制。
                expected = manifest[str(index)]
                if size != expected['size'] or digest.hexdigest() != expected['sha256']:
                    raise APIError('录制分片损坏，请联系邀请方。', 'invalid_recording', 409)
        with transaction.atomic():
            item = lookup({'code': data.get('code')}, lock=True)
            session = InterviewRuntime.objects.select_for_update().filter(interview=item).first()
            if item.status == 'completed' and session and runtime.owns(session, data.get('page_id')):
                return sealed_response(item, session, count, duration)
            session = runtime.require(item, data.get('page_id'), allow_abnormal=True)
            if response := sealed_response(item, session, count, duration):
                return response
            if session.recording_chunks != manifest:
                raise APIError('录制分片发生变化。', 'recording_conflict', 409)
            # 合并期间可能已断线：以最新状态封存，异常录制只保留为 partial。
            os.replace(temporary, destination)
            session.recording_final_count = count
            session.recording_duration_ms = duration
            session.recording_state = 'partial' if item.status == 'abnormal' else 'complete'
            session.save(update_fields=['recording_final_count', 'recording_duration_ms', 'recording_state'])
            key = destination.relative_to(Path(settings.MEDIA_ROOT)).as_posix()
            item.video_storage_key = item.recording_storage_key = key
            item.save(update_fields=['video_storage_key', 'recording_storage_key'])
            runtime.complete(item, session)
            return success(payload(item))
    except OSError:
        raise APIError('录制文件保存失败，请联系邀请方。', 'recording_failed', 503)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@endpoint(['GET','HEAD'])
def recording(request,pk):
    item=Interview.objects.filter(pk=pk,user_id=request.account.pk,deleted_at__isnull=True).first()
    if not item or not item.video_storage_key:raise APIError('录制文件不存在。','not_found',404)
    root=Path(settings.MEDIA_ROOT).resolve();path=(root/item.video_storage_key).resolve()
    if root not in path.parents or not path.is_file():raise APIError('录制文件不存在。','not_found',404)
    size=path.stat().st_size;start=0;end=size-1;status=200
    header=request.headers.get('Range')
    if header:
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
        if not match or not any(match.groups()):return HttpResponse(status=416,headers={'Content-Range':f'bytes */{size}'})
        left,right=match.groups()
        # 极长数字也属于无效范围，不能让 int 转换异常变成 500。
        try:
            if left:start=int(left);end=min(int(right) if right else end,end)
            else:start=max(0,size-int(right))
        except ValueError:
            return HttpResponse(status=416,headers={'Content-Range':f'bytes */{size}'})
        if start>=size or end<start:return HttpResponse(status=416,headers={'Content-Range':f'bytes */{size}'})
        status=206
    # 支持浏览器拖动播放；流式读取避免将整段录制载入内存。
    async def stream():
        with path.open('rb') as handle:
            handle.seek(start);remaining=end-start+1
            while remaining:
                block=await asyncio.to_thread(handle.read,min(65536,remaining))
                if not block:break
                remaining-=len(block);yield block
    def sync_stream():
        with path.open('rb') as handle:
            handle.seek(start); remaining=end-start+1
            while remaining:
                block=handle.read(min(65536,remaining))
                if not block: break
                remaining-=len(block); yield block
    mime='video/webm' if path.suffix=='.webm' else 'video/mp4'
    content = stream() if hasattr(request, 'scope') else sync_stream()
    response=HttpResponse(content_type=mime,status=status) if request.method=='HEAD' else StreamingHttpResponse(content,content_type=mime,status=status)
    response['Content-Length']=str(end-start+1);response['Accept-Ranges']='bytes'
    response['Cache-Control']='private, no-store';response['X-Content-Type-Options']='nosniff'
    if status==206:response['Content-Range']=f'bytes {start}-{end}/{size}'
    return response
