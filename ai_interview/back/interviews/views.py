import hashlib
import secrets
from datetime import datetime, time, timedelta
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .api import (
    APIError,
    SNAPSHOT_FIELDS,
    body,
    endpoint,
    integer,
    only,
    snapshot,
    string,
    success,
)
from .models import Interview, InterviewReport, InterviewRuntime, UserQuota

# 列表无需加载报告正文和评分 JSON，仅选取用于展示的列。
REPORT_LIST_FIELDS = (
    "id",
    "interview_id",
    "generated_at",
    "read_at",
    "interview__id",
    "interview__candidate_name",
    "interview__candidate_email",
    "interview__position_name",
)


def status_condition(status, now):
    """列表与统计共用有效状态条件，确保过期判断口径一致。"""
    if status == "attention":
        # 首页异常分类合并运行异常和邀请过期，分页仍由数据库完成。
        return Q(status="abnormal") | status_condition("expired", now)
    if status == "waiting":
        return Q(status="waiting", invite_expires_at__gt=now)
    if status == "expired":
        return Q(status="expired") | Q(status="waiting", invite_expires_at__lte=now)
    return Q(status=status)


def invitation_data(code):
    """链接与手动输入统一使用同一个面试码。"""
    base = settings.AI_INTERVIEW_INVITATION_BASE_URL.rstrip('/')
    return {
        'invitation_code': code,
        'invitation_url': f'{base}?code={quote(code)}' if base.endswith('.html') else f'{base}/{quote(code)}',
    }


def new_invitation():
    """只生成面试码；兼容旧数据库列名，存储完整 SHA-256。"""
    raw = secrets.token_hex(8).upper()
    code = '-'.join(raw[i:i+4] for i in range(0, 16, 4))
    return code, hashlib.sha256(raw.lower().encode()).hexdigest()


def owned(request, *, lock=False):
    """构造当前企业的有效面试查询；修改时可在事务内加行锁。"""
    query = Interview.objects.filter(
        user_id=request.account.id, deleted_at__isnull=True
    )
    return query.select_for_update() if lock else query


def get_item(query, pk):
    """从已限定权限的查询中取记录，不存在与无权限统一返回 404。"""
    item = query.filter(id=pk).first()
    if item is None:
        raise APIError("记录不存在。", "not_found", 404)
    return item


def effective_status(item, now=None):
    """仅待参加状态受有效期影响，查询时推导过期而不修改数据库。"""
    return (
        "expired"
        if item.status == "waiting"
        and item.invite_expires_at <= (now or timezone.now())
        else item.status
    )


def interview_data(item):
    """输出企业端面试快照，不暴露企业归属、凭证哈希或内部审计字段。"""
    return {
        **{
            key: getattr(item, key)
            for key in (
                "id",
                "position_name",
                "work_description",
                "position_requirements",
                "skills",
                "assessment_targets",
                "duration_minutes",
                "candidate_name",
                "candidate_email",
                "invite_expires_at",
                "created_at",
                "updated_at",
            )
        },
        "status": effective_status(item),
        "language": "ja",
    }


def page(request, query, serialize):
    """统一校验分页参数并仅加载当前页记录。"""
    try:
        number = int(request.GET.get("page", "1"))
        size = int(request.GET.get("page_size", "20"))
    except ValueError:
        raise APIError("分页参数错误。")
    integer(number, "page", 1, 1000000)
    integer(size, "page_size", 1, 100)
    total = query.count()
    rows = list(query[(number - 1) * size : number * size])
    return success(
        {
            "items": [serialize(item) for item in rows],
            "total": total,
            "page": number,
            "page_size": size,
        }
    )


def filtered(request, query):
    """按有效状态、候选人及东京时区的创建日期筛选面试。"""
    status = request.GET.get("status", "all")
    now = timezone.now()
    if status not in ("all", "waiting", "expired", "completed", "abnormal", "running", "submitting", "attention"):
        raise APIError("状态筛选无效。")
    if status != "all":
        query = query.filter(status_condition(status, now))
    needle = request.GET.get("query", "").strip()
    if len(needle) > 255:
        raise APIError("搜索内容过长。")
    if needle:
        query = query.filter(
            Q(candidate_name__icontains=needle) | Q(candidate_email__icontains=needle)
        )
    dates = {}
    for param in ("from", "to"):
        value = request.GET.get(param)
        if value:
            try:
                if len(value) != 10:
                    raise ValueError
                parsed = datetime.strptime(value, "%Y-%m-%d").date()
                if parsed.isoformat() != value:
                    raise ValueError
                dates[param] = parsed
            except ValueError:
                raise APIError("日期必须为 YYYY-MM-DD。")
    if "from" in dates and "to" in dates and dates["from"] > dates["to"]:
        raise APIError("开始日期不能晚于结束日期。")
    if "from" in dates:
        query = query.filter(
            created_at__gte=timezone.make_aware(
                datetime.combine(dates["from"], time.min)
            )
        )
    # 截止日期按下一日零点的开区间过滤，包含所选日期的全部时间。
    if "to" in dates:
        try:
            end = dates["to"] + timedelta(days=1)
        except OverflowError:
            raise APIError("截止日期超出支持范围。")
        query = query.filter(
            created_at__lt=timezone.make_aware(datetime.combine(end, time.min))
        )
    # 时间相同时用 ID 排序，避免分页结果顺序不确定。
    return query.order_by("-created_at", "-id")


@endpoint(["GET", "POST"])
def interviews(request):
    """查询面试列表或创建面试邀请。

    接口：GET /api/interviews；POST /api/interviews（兼容末尾 /）。
    认证：企业 session；POST 还需 X-CSRFToken。
    GET 参数：page 默认 1，page_size 默认 20（1–100）；
        status 为 all/waiting/completed/abnormal/expired/attention，默认 all；
        attention 为异常与过期的合并筛选，仅用于查询，不存为面试状态；
        query 搜索候选人姓名或邮箱，from/to 为 YYYY-MM-DD 创建日期，包含两端。
    GET 返回：200，data 为 items、total、page、page_size。
    POST 请求：JSON，必填 request_id、position_name、work_description、skills、
        assessment_targets、candidate_name、candidate_email、validity_days（1–30）；
        可选 position_requirements、duration_minutes（默认且仅允许 15）。
        skills 项为 name、level（basic/proficient/advanced）；
        assessment_targets 项为 id（可省略）、name、detail、weight；
        两种列表各 1–20 项，评价 ID 唯一，权重为整数且合计 100。
    POST 返回：201，data 包含 interview、invitation_code、invitation_url、remaining_count。
    规则：创建与扣减一次额度同事务，原始凭证仅返回一次，数据库只存哈希。
    错误：400 参数错误；401 未登录；403 CSRF 失败；
        409 额度未配置、额度不足或 request_id 重复（包含已软删除的记录）。
    """
    from .runtime import sweep
    sweep()
    if request.method == "GET":
        return page(request, filtered(request, owned(request)), interview_data)
    data = body(request)
    values = snapshot(data)
    request_id = string(data, "request_id", 100)
    if not request_id.isascii():
        raise APIError("request_id 必须为 ASCII 字符。")
    days = integer(data.get("validity_days"), "validity_days", 1, 30)
    now = timezone.now()
    code, code_hash = new_invitation()
    # SQL 未设置 request_id 唯一约束，先锁定企业唯一的额度行，
    # 将同一企业的创建操作串行化；事务内插入失败时额度扣减也会回滚。
    with transaction.atomic():
        quota = (
            UserQuota.objects.select_for_update()
            .filter(user_id=request.account.id, deleted_at__isnull=True)
            .first()
        )
        if quota is None:
            raise APIError("账户未配置额度。", "quota_unavailable", 409)
        # 包含已软删除的记录，避免重试旧请求再次创建并扣费。
        if Interview.objects.filter(
            user_id=request.account.id, request_id=request_id
        ).exists():
            raise APIError(
                "此创建请求已处理，请查询面试列表。", "duplicate_request", 409
            )
        # 额外使用余额大于零的条件更新，并由数据库执行 F 表达式扣减。
        if not UserQuota.objects.filter(id=quota.id, remaining_count__gt=0).update(
            remaining_count=F("remaining_count") - 1,
            updated_at=now,
            updated_by=request.account.id,
        ):
            raise APIError("面试额度不足。", "quota_exhausted", 409)
        item = Interview.objects.create(
            **values,
            request_id=request_id,
            user_id=request.account.id,
            invitation_token_hash=code_hash,
            invite_expires_at=now + timedelta(days=days),
            created_at=now,
            updated_at=now,
            created_by=request.account.id,
            updated_by=request.account.id,
        )
    return success(
        {
            "interview": interview_data(item),
            **invitation_data(code),
            "remaining_count": quota.remaining_count - 1,
        },
        201,
    )


@endpoint(["GET", "PATCH", "DELETE"])
def interview_detail(request, pk):
    """读取、修改或软删除面试。

    接口：GET/PATCH/DELETE /api/interviews/{pk}（兼容末尾 /）。
    认证：企业 session；PATCH/DELETE 还需 X-CSRFToken。
    路径参数：pk 为面试 ID，只允许访问当前企业未删除的记录。
    PATCH 请求：JSON，至少提供一个岗位、技能、评价目标、时长或候选人快照字段；
        字段结构与创建接口一致，不允许修改 request_id、validity_days 或运行状态。
    返回：GET/PATCH 为 200，data.interview 为面试快照；
        DELETE 为 200，data.deleted 为 true。
    规则：仅未过期的 waiting 面试可修改；删除时同事务软删除报告，不返还额度。
    错误：400 参数错误；401 未登录；403 CSRF 失败；
        404 不存在或不属于当前企业；409 面试不可编辑。
    """
    from .runtime import sweep
    sweep()
    if request.method == "GET":
        item = get_item(owned(request), pk)
        detail = interview_data(item)
        run = InterviewRuntime.objects.filter(interview=item).first()
        if run:
            detail.update(started_at=run.started_at, ended_at=run.closed_at,
                abnormal_reason=run.abnormal_reason or None, recording_state=run.recording_state)
        return success({"interview": detail})
    with transaction.atomic():
        item = get_item(owned(request, lock=True), pk)
        now = timezone.now()
        if request.method == "DELETE":
            # 删除面试时同事务隐藏报告；已消耗额度不返还。
            item.deleted_at = now
            InterviewReport.objects.filter(
                interview_id=item.id, deleted_at__isnull=True
            ).update(deleted_at=now, updated_at=now)
            fields = ["deleted_at"]
        else:
            if effective_status(item, now) != "waiting":
                raise APIError(
                    "仅待参加的面试可以修改。", "interview_not_editable", 409
                )
            data = body(request)
            only(data, SNAPSHOT_FIELDS)
            if not data:
                raise APIError("请提供修改字段。")
            # PATCH 与当前字段合并后校验完整快照，避免局部修改破坏权重合计。
            values = snapshot(
                {key: data.get(key, getattr(item, key)) for key in SNAPSHOT_FIELDS}
            )
            for key, value in values.items():
                setattr(item, key, value)
            fields = list(values)
        item.updated_at, item.updated_by = now, request.account.id
        item.save(update_fields=fields + ["updated_at", "updated_by"])
    return success(
        {"deleted": True}
        if request.method == "DELETE"
        else {"interview": interview_data(item)}
    )


def report_query(request):
    """通过有效面试限定企业归属，避免访问其他企业或已删除面试的报告。"""
    return InterviewReport.objects.filter(
        interview__user_id=request.account.id,
        interview__deleted_at__isnull=True,
        deleted_at__isnull=True,
    )


def report_data(report, interview=None, *, detail=False):
    """列表返回阅读状态与摘要，详情额外返回正文、评分和媒体存储 key。"""
    interview = interview if interview is not None else report.interview
    result = {
        "id": report.id,
        "interview_id": report.interview_id,
        "candidate_name": interview.candidate_name,
        "candidate_email": interview.candidate_email,
        "position_name": interview.position_name,
        "generated_at": report.generated_at,
        "read_at": report.read_at,
        "is_read": report.read_at is not None,
    }
    if detail:
        result.update(
            report_text=report.report_text,
            assessment_scores=report.assessment_scores,
            assessment_targets=interview.assessment_targets,
            recording_storage_key=interview.recording_storage_key,
            video_storage_key=interview.video_storage_key,
        )
    return result


@endpoint(["GET"])
def reports(request):
    """分页查询当前企业的面试报告。

    接口：GET /api/reports（兼容末尾 /）。
    认证：企业 session。
    查询参数：page 默认 1，page_size 默认 20（1–100）；
        reading 为 all/unread/read，默认 all；interview_id 可按指定面试筛选。
    返回：200，data 为 items、total、page、page_size；
        items 包含报告 ID、面试 ID、候选人、岗位、generated_at、read_at、is_read。
    规则：按生成时间和 ID 降序排列，不加载正文及评分，不包含已删除面试的报告。
    错误：400 筛选或分页参数错误；401 未登录。
    """
    reading = request.GET.get("reading", "all")
    if reading not in ("all", "unread", "read"):
        raise APIError("阅读状态无效。")
    query = report_query(request)
    interview_id = request.GET.get("interview_id")
    if interview_id is not None:
        try:
            interview_id = int(interview_id)
        except ValueError:
            raise APIError("interview_id 必须为正整数。")
        integer(interview_id, "interview_id", 1, 2**63 - 1)
        # 保留企业归属限定，供面试列表直接跳转到对应面试的报告。
        query = query.filter(interview_id=interview_id)
    if reading != "all":
        query = query.filter(read_at__isnull=reading == "unread")
    # ORM JOIN 同时取得候选人信息，避免两次查询之间面试被软删除导致映射缺失。
    query = query.select_related("interview").only(*REPORT_LIST_FIELDS)
    return page(request, query.order_by("-generated_at", "-id"), report_data)


@endpoint(["GET", "DELETE"])
def report_detail(request, pk):
    """读取报告详情或软删除报告。

    接口：GET/DELETE /api/reports/{pk}（兼容末尾 /）。
    认证：企业 session；DELETE 还需 X-CSRFToken。
    路径参数：pk 为报告 ID，只访问当前企业有效面试下的未删除报告。
    返回：GET 为 200，data.report 包含列表字段、report_text、assessment_scores、
        recording_storage_key、video_storage_key；DELETE 为 200，data.deleted 为 true。
    规则：GET 不标记已读；媒体字段为存储 key，尚不是可直接播放的签名 URL。
    错误：401 未登录；403 CSRF 失败；404 不存在或不属于当前企业。
    """
    query = report_query(request)
    if request.method == "GET":
        report = get_item(query.select_related("interview"), pk)
        # GET 只返回详情，已读状态由独立 POST 更新。
        detail = report_data(report, detail=True)
        recording_session = InterviewRuntime.objects.filter(interview=report.interview).first()
        if report.interview.video_storage_key and recording_session:
            # Public production proxy prepends /ai_interview to Django's /api routes.
            prefix = "" if settings.DEBUG else "/ai_interview"
            url = request.build_absolute_uri(f"{prefix}/api/interviews/{report.interview_id}/recording")
            detail.update(video_url=url, recording_url=url,
                          recording_duration_ms=recording_session.recording_duration_ms)
        return success({"report": detail})
    report = get_item(query.only("id", "interview_id"), pk)
    with transaction.atomic():
        # 与后台报告写入使用相同的父面试锁，协调删除和更新操作。
        get_item(owned(request, lock=True).only("id"), report.interview_id)
        get_item(query.only("id"), pk)
        now = timezone.now()
        query.filter(id=pk).update(deleted_at=now, updated_at=now)
    return success({"deleted": True})


@endpoint(["POST"])
def report_read(request, pk):
    """标记报告首次阅读。

    接口：POST /api/reports/{pk}/read（兼容末尾 /）。
    认证：企业 session，并通过 X-CSRFToken 校验。
    路径参数：pk 为报告 ID；无需请求体。
    返回：200，data 为 id、read_at；重复调用保留首次阅读时间。
    规则：与报告写入、删除共用父面试行锁，协调 read_at 的并发更新。
    错误：401 未登录；403 CSRF 失败；404 不存在或不属于当前企业。
    """
    query = report_query(request)
    report = get_item(query.only("id", "interview_id"), pk)
    with transaction.atomic():
        # 与报告生成、删除统一锁定父面试，避免 read_at 的更新交错覆盖。
        get_item(owned(request, lock=True).only("id"), report.interview_id)
        report = get_item(query.only("id", "read_at"), pk)
        if report.read_at is None:
            now = timezone.now()
            query.filter(id=pk, read_at__isnull=True).update(
                read_at=now, updated_at=now
            )
            # SQL 使用 DATETIME，回读实际存储精度，确保重复阅读返回相同时间。
            report.refresh_from_db(fields=["read_at"])
    return success({"id": report.id, "read_at": report.read_at})


@endpoint(["GET"])
def quota(request):
    """读取企业剩余面试额度。

    接口：GET /api/quota（兼容末尾 /）。
    认证：企业 session；无请求参数。
    返回：200，data.remaining_count 为余额，data.configured 表示是否有有效额度记录。
    规则：缺少额度记录时返回 0 和 false；额度由其他模块初始化和发放。
    错误：401 未登录。
    """
    item = UserQuota.objects.filter(
        user_id=request.account.id, deleted_at__isnull=True
    ).first()
    return success(
        {
            "remaining_count": item.remaining_count if item else 0,
            "configured": item is not None,
        }
    )


@endpoint(["GET"])
def dashboard(request):
    """读取企业首页统计。

    接口：GET /api/dashboard（兼容末尾 /）。
    认证：企业 session；无请求参数。
    返回：200，data 包含 total_interviews、today_created、waiting、completed、
        abnormal、expired、unread_reports。
    规则：只统计当前企业有效数据；今日按 Asia/Tokyo 创建日期计算；
        waiting 超过有效期计入 expired，completed/abnormal 不受有效期影响。
    错误：401 未登录。
    """
    from .runtime import sweep
    sweep()
    query = owned(request)
    now = timezone.now()
    today = timezone.localdate(now)
    start = timezone.make_aware(datetime.combine(today, time.min))
    end = start + timedelta(days=1)
    # 使用一次条件聚合取得全部面试计数，减少独立 COUNT 查询及统计时点差异。
    counts = query.aggregate(
        total_interviews=Count("id"),
        today_created=Count("id", filter=Q(created_at__gte=start, created_at__lt=end)),
        **{
            status: Count("id", filter=status_condition(status, now))
            for status in ("waiting", "completed", "abnormal", "expired")
        },
    )
    counts["unread_reports"] = (
        report_query(request).filter(read_at__isnull=True).count()
    )
    return success(counts)


# 后台服务使用独立密钥认证，没有浏览器 cookie 身份，因此不使用 CSRF 校验。
@csrf_exempt
@endpoint(["PATCH"], internal=True)
def runtime_update(request, pk):
    """供可信后台服务更新面试终态与媒体存储 key。

    接口：PATCH /api/internal/interviews/{pk}（兼容末尾 /）。
    认证：X-Service-Key 与 AI_INTERVIEW_SERVICE_KEY 匹配；不使用企业 session 或 CSRF。
    路径参数：pk 为有效面试 ID。
    请求：JSON，至少提供 status、recording_storage_key、video_storage_key 中的一项；
        status 仅支持 completed/abnormal，媒体 key 为最多 1000 字符的非空字符串。
    返回：200，data.interview 为更新后的面试快照。
    规则：已进入终态后只能保持相同状态；省略 status 时沿用原状态并校验其为终态。
    错误：400 参数错误；401 密钥无效或未配置；404 面试不存在；409 终态切换。
    """
    data = body(request)
    only(data, {"status", "recording_storage_key", "video_storage_key"})
    if not data:
        raise APIError("请提供修改字段。")
    with transaction.atomic():
        item = get_item(
            Interview.objects.select_for_update().filter(deleted_at__isnull=True), pk
        )
        status = data.get("status", item.status)
        if status not in ("completed", "abnormal"):
            raise APIError("运行状态仅允许 completed 或 abnormal。")
        if item.status in ("completed", "abnormal") and status != item.status:
            raise APIError("终态不能变更。", "invalid_transition", 409)
        for key in ("recording_storage_key", "video_storage_key"):
            if key in data:
                setattr(item, key, string(data, key, 1000))
        item.status, item.updated_at = status, timezone.now()
        item.save(
            update_fields=[
                "status",
                "recording_storage_key",
                "video_storage_key",
                "updated_at",
            ]
        )
    return success({"interview": interview_data(item)})


@csrf_exempt
@endpoint(["PUT"], internal=True)
def report_write(request, pk):
    """供可信后台服务创建或更新成功生成的报告。

    接口：PUT /api/internal/interviews/{pk}/report（兼容末尾 /）。
    认证：X-Service-Key 与 AI_INTERVIEW_SERVICE_KEY 匹配；不使用企业 session 或 CSRF。
    路径参数：pk 为有效且已完成的面试 ID。
    请求：JSON，report_text 必填且最多 1000000 字符；assessment_scores 为列表，
        每项包含 id、score（0–100 整数）、evaluation（必填，最多 10000 字符）；
        评分 ID 必须完整覆盖面试评价目标，不得重复或包含未知 ID。
    返回：首次创建 201、更新或恢复 200，data.report 为完整报告详情。
    规则：锁定父面试保证最多一份报告；相同内容重试保留生成及阅读时间；
        内容变化或恢复软删除报告时刷新 generated_at，并重置为未读。
    错误：400 参数或评分错误；401 密钥无效或未配置；404 面试不存在；
        409 面试尚未完成。
    """
    data = body(request)
    only(data, {"report_text", "assessment_scores"})
    text = string(data, "report_text", 1000000)
    scores = data.get("assessment_scores")
    with transaction.atomic():
        item = get_item(
            Interview.objects.select_for_update().filter(deleted_at__isnull=True), pk
        )
        if item.status != "completed":
            raise APIError("面试完成后才能生成报告。", "interview_not_completed", 409)
        target_ids = {row["id"] for row in item.assessment_targets}
        if not isinstance(scores, list) or len(scores) != len(target_ids):
            raise APIError("评分必须覆盖所有评价项目。")
        seen = set()
        normalized = []
        for row in scores:
            if not isinstance(row, dict):
                raise APIError("评分格式错误。")
            only(row, {"id", "score", "evaluation"})
            target_id = string(row, "id", 100)
            if target_id not in target_ids or target_id in seen:
                raise APIError("评分项目 ID 无效或重复。")
            seen.add(target_id)
            normalized.append(
                {
                    "id": target_id,
                    "score": integer(row.get("score"), "score", 0, 100),
                    "evaluation": string(row, "evaluation", 10000),
                }
            )
        now = timezone.now()
        # SQL 未设置 interview_id 唯一约束，父面试行锁保证写入串行执行。
        # 查找时包含软删除报告，重新生成时恢复原记录，避免新增第二份报告。
        report = InterviewReport.objects.filter(interview_id=pk).order_by("id").first()
        created = report is None
        # 相同内容的后台重试保持生成时间和阅读状态，避免重复出现未读通知。
        if (
            report is not None
            and report.deleted_at is None
            and report.report_text == text
            and report.assessment_scores == normalized
        ):
            return success({"report": report_data(report, item, detail=True)})
        if created:
            report = InterviewReport(interview_id=pk, created_at=now)
        report.report_text, report.assessment_scores = text, normalized
        report.generated_at, report.updated_at = now, now
        # 内容变化或恢复已删除报告时重新计为未读。
        report.read_at, report.deleted_at = None, None
        report.save()
    return success(
        {"report": report_data(report, item, detail=True)}, 201 if created else 200
    )


@endpoint(["POST"])
def invitation_rotate(request, pk):
    """重新生成面试邀请凭证。

    接口：POST /api/interviews/{pk}/invitation（兼容末尾 /）。
    认证：企业 session，并通过 X-CSRFToken 校验。
    路径参数：pk 为当前企业的面试 ID；无需请求体。
    返回：200，data 包含 invitation_code、invitation_url、invite_expires_at。
    规则：仅未过期的 waiting 面试可轮换；旧凭证失效，不扣额度，不延长有效期；
        原始凭证只在响应中返回，数据库保存 SHA-256 哈希。
    错误：401 未登录；403 CSRF 失败；404 不存在或不属于当前企业；409 面试不可编辑。
    """
    with transaction.atomic():
        item = get_item(owned(request, lock=True), pk)
        if effective_status(item) != "waiting":
            raise APIError(
                "仅待参加的面试可以重新生成邀请。", "interview_not_editable", 409
            )
        code, item.invitation_token_hash = new_invitation()
        item.updated_at, item.updated_by = timezone.now(), request.account.id
        item.save(update_fields=["invitation_token_hash", "updated_at", "updated_by"])
    return success(
        {**invitation_data(code), "invite_expires_at": item.invite_expires_at}
    )
