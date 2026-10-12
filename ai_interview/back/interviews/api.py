import json
from functools import wraps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.utils.crypto import constant_time_compare

from accounts.models import UserAccount
from accounts.views import error_response

# 快照字段共用于创建校验与 PATCH 白名单，避免两处定义不同步。
SNAPSHOT_FIELDS = (
    "position_name",
    "work_description",
    "position_requirements",
    "skills",
    "assessment_targets",
    "duration_minutes",
    "candidate_name",
    "candidate_email",
)
CREATE_FIELDS = frozenset(SNAPSHOT_FIELDS) | {"request_id", "validity_days"}


class APIError(Exception):
    """可预期的参数或业务异常，由接口装饰器转换为统一 JSON 错误响应。"""

    def __init__(self, message, code="invalid_request", status=400):
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def endpoint(methods, *, internal=False):
    """统一检查请求方法及身份；企业接口注入 request.account，内部接口验证服务密钥。"""
    methods = tuple(methods)

    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            try:
                if request.method not in methods:
                    response = error_response(
                        "请求方法不支持。", code="method_not_allowed", status=405
                    )
                    response["Allow"] = ", ".join(methods)
                    return response
                # 服务密钥为空时关闭内部入口；内部调用不依赖企业登录会话。
                if internal:
                    secret = settings.AI_INTERVIEW_SERVICE_KEY
                    if not secret or not constant_time_compare(
                        request.headers.get("X-Service-Key", ""), secret
                    ):
                        raise APIError(
                            "服务认证失败。", "service_authentication_required", 401
                        )
                else:
                    # 每次验证账户仍有效，不仅依赖 session 中保存的历史账户 ID。
                    account_id = request.session.get("user_account_id")
                    request.account = (
                        UserAccount.objects.only("id")
                        .filter(id=account_id, deleted_at__isnull=True)
                        .first()
                        if account_id
                        else None
                    )
                    if request.account is None:
                        raise APIError("请重新登录。", "authentication_required", 401)
                return view(request, *args, **kwargs)
            # 只处理明确的业务异常，数据库和程序错误仍交由 Django 记录。
            except APIError as error:
                return error_response(
                    error.message, code=error.code, status=error.status
                )

        return wrapped

    return decorate


def body(request):
    """只接受 JSON 对象，避免列表、空值等请求体进入后续字段处理。"""
    try:
        value = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise APIError("请求体必须为 JSON 对象。")
    if not isinstance(value, dict):
        raise APIError("请求体必须为 JSON 对象。")
    return value


def only(data, allowed):
    """拒绝白名单以外的字段，防止客户端写入归属、余额或审计信息。"""
    if data.keys() - set(allowed):
        raise APIError("包含不支持的字段。")


def string(data, key, limit, *, optional=False):
    """校验字符串类型与长度并去除首尾空白；可选字段允许空字符串。"""
    value = data.get(key, "" if optional else None)
    if not isinstance(value, str):
        raise APIError(f"{key} 长度或类型错误。")
    value = value.strip()
    if len(value) > limit or (not optional and not value):
        raise APIError(f"{key} 长度或类型错误。")
    return value


def integer(value, name, minimum, maximum):
    """校验整数范围，明确拒绝 Python 中属于 int 子类的布尔值。"""
    if type(value) is not int or not minimum <= value <= maximum:
        raise APIError(f"{name} 必须为 {minimum} 至 {maximum} 的整数。")
    return value


def snapshot(data):
    """创建和修改共用的快照校验，规范技能、评价项目及权重结构。"""
    only(data, CREATE_FIELDS)
    result = {
        key: string(data, key, limit)
        for key, limit in [
            ("position_name", 200),
            ("work_description", 10000),
            ("candidate_name", 100),
            ("candidate_email", 255),
        ]
    }
    result["position_requirements"] = string(
        data, "position_requirements", 10000, optional=True
    )
    try:
        validate_email(result["candidate_email"])
    except ValidationError:
        raise APIError("候选人邮箱无效。")
    # 首版按既有前端约定固定为 15 分钟。
    result["duration_minutes"] = integer(
        data.get("duration_minutes", 15), "duration_minutes", 15, 15
    )
    for key in ("skills", "assessment_targets"):
        rows = data.get(key)
        if not isinstance(rows, list) or not 1 <= len(rows) <= 20:
            raise APIError(f"{key} 必须包含 1 至 20 项。")
        normalized = []
        ids = set()
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise APIError(f"{key} 项目必须为对象。")
            item = {"name": string(row, "name", 100)}
            if key == "skills":
                only(row, {"name", "level"})
                if row.get("level") not in ("basic", "proficient", "advanced"):
                    raise APIError("技能等级无效。")
                item["level"] = row["level"]
            else:
                only(row, {"id", "name", "detail", "weight"})
                # 未提供 ID 时生成快照内的项目 ID，报告评分必须使用这些 ID。
                item.update(
                    id=string({"id": row.get("id", f"target-{index + 1}")}, "id", 100),
                    detail=string(row, "detail", 1000),
                    weight=integer(row.get("weight"), "weight", 1, 100),
                )
                if item["id"] in ids:
                    raise APIError("评价项目 ID 不能重复。")
                ids.add(item["id"])
            normalized.append(item)
        result[key] = normalized
    if sum(row["weight"] for row in result["assessment_targets"]) != 100:
        raise APIError("评价目标权重合计必须为 100%。")
    return result


def success(data, status=200):
    """封装统一成功响应，创建资源时由调用方传入 201 状态码。"""
    return JsonResponse({"success": True, "data": data}, status=status)


def csrf_failure(request, reason=""):
    """将 Django 的 CSRF 拒绝响应转换为前端可解析的 JSON。"""
    return error_response(
        "CSRF 校验失败，请刷新登录状态后重试。", code="csrf_failed", status=403
    )
