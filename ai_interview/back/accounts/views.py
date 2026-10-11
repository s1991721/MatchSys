import json

from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import UserAccount


def error_response(message: str, *, code: str, status: int) -> JsonResponse:
    return JsonResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status=status,
    )


def password_matches(raw_password, stored_password):
    # Keep existing accounts usable while new passwords use Django hashes.
    try:
        identify_hasher(stored_password)
    except ValueError:
        return constant_time_compare(raw_password, stored_password)
    return check_password(raw_password, stored_password)


def user_payload(account: UserAccount) -> dict:
    return {
        "id": account.id,
        "user_name": account.username,
        "display_name": account.display_name,
        "company_name": account.company_name,
        "company_code": account.company_code,
    }


@csrf_exempt
@require_POST
def login(request):
    """企业账户登录。

    接口：POST /api/login（兼容末尾 /）。
    认证：无需登录；当前为兼容已有前端豁免 CSRF。
    请求：JSON 对象，user_name 为账号，password 为密码，均为必填字符串。
    返回：200，data.user 为账户信息，同时建立 Django session cookie。
    错误：400 参数错误或缺少凭据；401 账号或密码错误。
    """

    try:
        payload = json.loads(request.body)
        # 先检查 JSON 对象及字段类型，避免非法请求导致字符串处理异常。
        if not isinstance(payload, dict):
            raise ValueError
        username = payload.get("user_name", "")
        password = payload.get("password", "")
        if not isinstance(username, str) or not isinstance(password, str):
            raise ValueError
        username = username.strip()
    except (ValueError, UnicodeDecodeError, AttributeError):
        return error_response(
            "请求参数错误。",
            code="invalid_request",
            status=400,
        )

    if not username or not password:
        return error_response(
            "请输入账号和密码。",
            code="missing_credentials",
            status=400,
        )

    account = (
        UserAccount.objects.filter(
            username=username,
            deleted_at__isnull=True,
        )
        .only(
            "id",
            "password",
            "username",
            "display_name",
            "company_name",
            "company_code",
        )
        .first()
    )

    if account is None or not password_matches(password, account.password):
        return error_response(
            "账号或密码错误。",
            code="invalid_credentials",
            status=401,
        )

    request.session.cycle_key()
    request.session["user_account_id"] = account.id
    request.session["username"] = account.username
    request.session["display_name"] = account.display_name
    request.session["company_name"] = account.company_name

    return JsonResponse(
        {
            "success": True,
            "data": {"user": user_payload(account)},
        }
    )


@require_GET
def current_user(request):
    """读取当前登录账户。

    接口：GET /api/me（兼容末尾 /）。
    认证：企业 session；无请求参数。
    返回：200，data.user 为账户信息，data.csrf_token 用于后续修改请求。
    错误：401 未登录或账户已删除；失效账户的会话会被清除。
    """

    account_id = request.session.get("user_account_id")
    if not account_id:
        return error_response(
            "登录状态已失效，请重新登录。",
            code="authentication_required",
            status=401,
        )

    account = (
        UserAccount.objects.filter(
            id=account_id,
            deleted_at__isnull=True,
        )
        .only(
            "id",
            "username",
            "display_name",
            "company_name",
            "company_code",
        )
        .first()
    )
    if account is None:
        request.session.flush()
        return error_response(
            "登录状态已失效，请重新登录。",
            code="authentication_required",
            status=401,
        )

    return JsonResponse(
        {
            "success": True,
            "data": {"user": user_payload(account), "csrf_token": get_token(request)},
        }
    )


@require_POST
def update_account(request):
    """修改当前账户显示名或密码。

    接口：POST /api/account（兼容末尾 /）。
    认证：企业 session，并通过 X-CSRFToken 校验。
    请求：JSON 对象，action 指定操作：
        display_name：display_name 为 1–100 字符的显示名。
        password：current_password、new_password、confirm_password；
            新密码为 8–128 字符，须与确认值一致且不同于当前密码。
    返回：200，data.user 为更新后的账户信息；修改密码时轮换 session key。
    错误：400 参数错误或密码校验失败；401 未登录；403 CSRF 校验失败。
    """
    account_id = request.session.get("user_account_id")
    account = (
        UserAccount.objects.filter(id=account_id, deleted_at__isnull=True).first()
        if account_id
        else None
    )
    if account is None:
        return error_response(
            "请重新登录。", code="authentication_required", status=401
        )
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return error_response("请求参数错误。", code="invalid_request", status=400)
    if not isinstance(payload, dict):
        return error_response("请求参数错误。", code="invalid_request", status=400)
    action = payload.get("action")
    if action == "display_name":
        name = payload.get("display_name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            return error_response(
                "显示名需为1至100个字符。", code="invalid_display_name", status=400
            )
        account.display_name = name.strip()
        fields = ["display_name"]
    elif action == "password":
        current = payload.get("current_password")
        new = payload.get("new_password")
        confirm = payload.get("confirm_password")
        if not isinstance(current, str) or not password_matches(
            current, account.password
        ):
            return error_response(
                "当前密码错误。", code="incorrect_password", status=400
            )
        if not isinstance(new, str) or not 8 <= len(new) <= 128 or not new.strip():
            return error_response(
                "新密码需为8至128个字符。", code="invalid_password", status=400
            )
        if new != confirm:
            return error_response(
                "两次新密码不一致。", code="password_mismatch", status=400
            )
        if new == current:
            return error_response(
                "新密码不能与当前密码相同。", code="password_unchanged", status=400
            )
        account.password = make_password(new)
        fields = ["password"]
    else:
        return error_response("请求参数错误。", code="invalid_request", status=400)
    account.updated_at = timezone.now()
    account.updated_by = account.id
    account.save(update_fields=fields + ["updated_at", "updated_by"])
    request.session["display_name"] = account.display_name
    if action == "password":
        request.session.cycle_key()
    return JsonResponse({"success": True, "data": {"user": user_payload(account)}})


@require_GET
def csrf_token(request):
    """获取 CSRF token。

    接口：GET /api/csrf（兼容末尾 /）。
    认证：无需登录；无请求参数。
    返回：200，data.csrf_token；中间件同时设置 CSRF cookie。
    调用方需保留 cookie，并在修改请求的 X-CSRFToken 中传入 token。
    """
    return JsonResponse({"success": True, "data": {"csrf_token": get_token(request)}})


@require_POST
def logout(request):
    """退出当前登录会话。

    接口：POST /api/logout（兼容末尾 /）。
    认证：通过 X-CSRFToken 校验；无需请求体，可重复调用。
    返回：200，data.logged_out 为 true，当前 session 被清除。
    错误：403 CSRF 校验失败。
    """
    request.session.flush()
    return JsonResponse({"success": True, "data": {"logged_out": True}})
