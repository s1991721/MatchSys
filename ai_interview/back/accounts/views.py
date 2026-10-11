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
    """Authenticate a company account and start a Django session."""

    try:
        payload = json.loads(request.body)
        username = payload.get("user_name", "").strip()
        password = payload.get("password", "")
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
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
    """Return the account attached to the current Django session."""

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
    """Update only the signed-in account, with CSRF and current-password checks."""
    account_id = request.session.get("user_account_id")
    account = UserAccount.objects.filter(id=account_id, deleted_at__isnull=True).first() if account_id else None
    if account is None:
        return error_response("请重新登录。", code="authentication_required", status=401)
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
            return error_response("显示名需为1至100个字符。", code="invalid_display_name", status=400)
        account.display_name = name.strip()
        fields = ["display_name"]
    elif action == "password":
        current = payload.get("current_password")
        new = payload.get("new_password")
        confirm = payload.get("confirm_password")
        if not isinstance(current, str) or not password_matches(current, account.password):
            return error_response("当前密码错误。", code="incorrect_password", status=400)
        if not isinstance(new, str) or not 8 <= len(new) <= 128 or not new.strip():
            return error_response("新密码需为8至128个字符。", code="invalid_password", status=400)
        if new != confirm:
            return error_response("两次新密码不一致。", code="password_mismatch", status=400)
        if new == current:
            return error_response("新密码不能与当前密码相同。", code="password_unchanged", status=400)
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
