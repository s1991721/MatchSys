import json

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
            password=password,
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
