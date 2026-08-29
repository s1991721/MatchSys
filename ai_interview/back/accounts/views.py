import json

from django.contrib.auth.hashers import check_password
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import UserAccount


def error_response(message: str, *, code: str, status: int) -> JsonResponse:
    return JsonResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status=status,
    )


@csrf_exempt
@require_POST
def login(request):
    """Authenticate a company account and start a Django session."""

    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return error_response(
            "请求内容不是有效的 JSON。",
            code="invalid_json",
            status=400,
        )

    if not isinstance(payload, dict):
        return error_response(
            "请求内容必须是 JSON 对象。",
            code="invalid_json",
            status=400,
        )

    # The login page submits `user_name`; accepting `username` as an alias also
    # keeps the API convenient for non-browser clients.
    username = payload.get("user_name", payload.get("username", ""))
    password = payload.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str):
        return error_response(
            "账号和密码必须是字符串。",
            code="invalid_parameters",
            status=400,
        )

    username = username.strip()
    if not username or not password:
        return error_response(
            "请输入账号和密码。",
            code="missing_credentials",
            status=400,
        )

    account = (
        UserAccount.objects.filter(username=username, deleted_at__isnull=True)
        .only(
            "id",
            "username",
            "password",
            "display_name",
            "company_name",
            "company_code",
        )
        .first()
    )

    # Keep the failure response identical so callers cannot enumerate accounts.
    if account is None or not check_password(password, account.password):
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
            "data": {
                "user": {
                    "id": account.id,
                    "user_name": account.username,
                    "display_name": account.display_name,
                    "company_name": account.company_name,
                    "company_code": account.company_code,
                }
            },
        }
    )
