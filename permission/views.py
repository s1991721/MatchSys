import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from permission.models import Menu, Role
from project.api import api_error, api_success
from project.common_tools import parse_json_body, require_login
from project.error_codes import ErrorCode


ADMIN_ROLE_ID = 999


def _require_admin(request):
    if str(request.session.get("role_id") or "") != str(ADMIN_ROLE_ID):
        return api_error(ErrorCode.FORBIDDEN, status=403)
    return None


def _menu_list_to_htmls(value):
    raw = (value or "").strip()
    if not raw:
        return []
    if raw == "*":
        return ["*"]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    cleaned = raw.strip("[]")
    parts = [item.strip().strip("'\"") for item in cleaned.split(",") if item.strip()]
    return [item for item in parts if item]


def _menu_htmls_to_list(menu_htmls):
    if not menu_htmls:
        return "[]"
    return json.dumps(menu_htmls, ensure_ascii=False)


def _menu_list_to_payload(value):
    htmls = _menu_list_to_htmls(value)
    if htmls == ["*"]:
        return "*"
    return htmls


@csrf_exempt
@require_http_methods(["GET"])
def menus_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    queryset = Menu.objects.filter(deleted_at__isnull=True).order_by("sort_order", "id")
    items = [Menu.serialize(menu) for menu in queryset]
    return api_success(data={"items": items})


@csrf_exempt
@require_http_methods(["GET"])
def roles_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    queryset = Role.objects.filter(deleted_at__isnull=True).order_by("id")
    items = []
    for role in queryset:
        item = Role.serialize(role)
        item["menu_list"] = _menu_list_to_payload(role.menu_list)
        items.append(item)
    return api_success(data={"items": items})


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def role_detail_api(request, role_id):
    login_id, error = require_login(request)
    if error:
        return error

    try:
        role = Role.objects.get(pk=role_id, deleted_at__isnull=True)
    except Role.DoesNotExist:
        return api_error(ErrorCode.PERMISSION_ROLE_NOT_FOUND)

    if request.method == "GET":
        item = Role.serialize(role)
        item["menu_list"] = _menu_list_to_payload(role.menu_list)
        return api_success(data={"item": item})

    if request.method == "PUT":
        admin_error = _require_admin(request)
        if admin_error:
            return admin_error
        payload, error = parse_json_body(request)
        if error:
            return error
        menu_list = payload.get("menu_list")
        if menu_list == "*":
            role.menu_list = "*"
        elif isinstance(menu_list, list):
            normalized = [str(item).strip() for item in menu_list if str(item).strip()]
            allowed_htmls = set(
                Menu.objects.filter(deleted_at__isnull=True).values_list("menu_html", flat=True)
            )
            if any(item not in allowed_htmls for item in normalized):
                return api_error(ErrorCode.INVALID_REQUEST, message="Invalid menu_list")
            role.menu_list = _menu_htmls_to_list(list(dict.fromkeys(normalized)))
        else:
            return api_error(ErrorCode.INVALID_REQUEST, message="Invalid menu_list")
        role.updated_by = login_id
        role.save(update_fields=["menu_list", "updated_by", "updated_at"])
        item = Role.serialize(role)
        item["menu_list"] = _menu_list_to_payload(role.menu_list)
        return api_success(data={"item": item})

# Create your views here.
