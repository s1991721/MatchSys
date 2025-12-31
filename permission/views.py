import json

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from permission.models import Menu, Role
from project.api import api_error, api_success
from project.common_tools import parse_json_body


def _require_login(request):
    login_id = request.session.get("employee_id")
    if not login_id:
        return None, api_error(status=401, message="employee id is required")
    return login_id, None


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
@require_http_methods(["GET", "POST"])
def menus_api(request):
    login_id, error = _require_login(request)
    if error:
        return error

    if request.method == "GET":
        queryset = Menu.objects.filter(deleted_at__isnull=True).order_by("sort_order", "id")
        items = [Menu.serialize(menu) for menu in queryset]
        return api_success(data={"items": items})

    payload, error = parse_json_body(request)
    if error:
        return error
    if not (payload.get("menu_name") or "").strip():
        return api_error("Missing field: menu_name")
    if not (payload.get("menu_html") or "").strip():
        return api_error("Missing field: menu_html")
    menu = Menu()
    Menu.apply_payload(menu, payload)
    menu.created_by = login_id
    menu.save()
    return api_success(data={"item": Menu.serialize(menu)})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def menu_detail_api(request, menu_id):
    login_id, error = _require_login(request)
    if error:
        return error

    try:
        menu = Menu.objects.get(pk=menu_id, deleted_at__isnull=True)
    except Menu.DoesNotExist:
        return api_error("Menu not found", status=404)

    if request.method == "GET":
        return api_success(data={"item": Menu.serialize(menu)})

    if request.method == "PUT":
        payload, error = parse_json_body(request)
        if error:
            return error
        if not (payload.get("menu_name") or "").strip():
            return api_error("Missing field: menu_name")
        if not (payload.get("menu_html") or "").strip():
            return api_error("Missing field: menu_html")
        Menu.apply_payload(menu, payload)
        menu.updated_by = login_id
        menu.save()
        return api_success(data={"item": Menu.serialize(menu)})

    if request.method == "DELETE":
        menu.deleted_at = timezone.now()
        menu.updated_by = login_id
        menu.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        return api_success()

    return api_error("Method not allowed", status=405)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def roles_api(request):
    login_id, error = _require_login(request)
    if error:
        return error

    if request.method == "GET":
        queryset = Role.objects.filter(deleted_at__isnull=True).order_by("id")
        items = []
        for role in queryset:
            item = Role.serialize(role)
            item["menu_list"] = _menu_list_to_payload(role.menu_list)
            items.append(item)
        return api_success(data={"items": items})

    payload, error = parse_json_body(request)
    if error:
        return error
    if not (payload.get("role_name") or "").strip():
        return api_error("Missing field: role_name")
    role = Role()
    Role.apply_payload(role, payload)
    menu_list = payload.get("menu_list")
    if menu_list == "*":
        role.menu_list = "*"
    elif isinstance(menu_list, list):
        role.menu_list = _menu_htmls_to_list(menu_list)
    elif isinstance(menu_list, str):
        role.menu_list = menu_list
    role.created_by = login_id
    role.save()
    item = Role.serialize(role)
    item["menu_list"] = _menu_list_to_payload(role.menu_list)
    return api_success(data={"item": item})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def role_detail_api(request, role_id):
    login_id, error = _require_login(request)
    if error:
        return error

    try:
        role = Role.objects.get(pk=role_id, deleted_at__isnull=True)
    except Role.DoesNotExist:
        return api_error("Role not found", status=404)

    if request.method == "GET":
        item = Role.serialize(role)
        item["menu_list"] = _menu_list_to_payload(role.menu_list)
        return api_success(data={"item": item})

    if request.method == "PUT":
        payload, error = parse_json_body(request)
        if error:
            return error
        if not (payload.get("role_name") or "").strip():
            return api_error("Missing field: role_name")
        Role.apply_payload(role, payload)
        menu_list = payload.get("menu_list")
        if menu_list == "*":
            role.menu_list = "*"
        elif isinstance(menu_list, list):
            role.menu_list = _menu_htmls_to_list(menu_list)
        elif isinstance(menu_list, str):
            role.menu_list = menu_list
        role.updated_by = login_id
        role.save()
        item = Role.serialize(role)
        item["menu_list"] = _menu_list_to_payload(role.menu_list)
        return api_success(data={"item": item})

    if request.method == "DELETE":
        role.deleted_at = timezone.now()
        role.updated_by = login_id
        role.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        return api_success()

    return api_error("Method not allowed", status=405)

# Create your views here.
