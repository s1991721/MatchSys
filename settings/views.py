import json
from pathlib import Path

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from bpmatch.authorize_gmail import test_connection
from project.api import api_error, api_success
from project.common_tools import parse_json_body, require_login
from settings.models import SysSettings

# 失败默认返回值
SECTION_DEFAULTS = {
    "business-email": {
        "auth_filename": "",
        "auth_path": "",
    },
    "match": {
        "cycle_days": 14,
    },
    "ai": {
        "mode": "local",
        "local_model": "",
        "cloud_model": "",
        "cloud_api_key": "",
    },
    "backup": {
        "host": "",
        "port": "",
        "database": "",
        "user": "",
        "password": "",
        "ssl_mode": "require",
        "note": "",
    },
    "sendmsg": [],
    "tasks": [],
}


# 根据section获取配置
def _get_setting(section):
    return SysSettings.objects.filter(name=section, deleted_at__isnull=True).first()


# 根据section保存配置
def _save_setting(section, settings_payload, login_id):
    record = _get_setting(section)
    if record:
        record.settings = settings_payload
        record.updated_by = login_id
    else:
        record = SysSettings(
            name=section,
            settings=settings_payload,
            created_by=login_id,
        )
    record.save()
    return api_success(data={"name": section, "settings": record.settings})


# 营业邮箱配置
def _handle_business_email_upload(auth_file, login_id):
    if not auth_file:
        return api_error("Missing Gmail auth file")
    try:
        file_bytes = auth_file.read()
        json.loads(file_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return api_error("Invalid Gmail auth JSON file")

    base_dir = Path(__file__).resolve().parent.parent
    credentials_dir = base_dir / "credentials"
    credentials_dir.mkdir(parents=True, exist_ok=True)
    target_path = credentials_dir / "gmail_credentials.json"
    target_path.write_bytes(file_bytes)

    settings_payload = {
        "auth_filename": "gmail_credentials.json",
        "auth_path": str(Path("credentials") / "gmail_credentials.json"),
    }
    return _save_setting("business-email", settings_payload, login_id)


def _handle_match(settings_payload, login_id):
    if not isinstance(settings_payload, dict):
        return api_error("Invalid settings payload")
    try:
        cycle_days = int(settings_payload.get("cycle_days", 0))
    except (TypeError, ValueError):
        cycle_days = 0
    if cycle_days < 1:
        return api_error("Invalid cycle_days")
    return _save_setting("match", {"cycle_days": cycle_days}, login_id)


def _handle_ai(settings_payload, login_id):
    if not isinstance(settings_payload, dict):
        return api_error("Invalid settings payload")
    mode = settings_payload.get("mode") or "local"
    if mode not in ("local", "cloud"):
        return api_error("Invalid mode")
    settings_payload = {
        "mode": mode,
        "local_model": (settings_payload.get("local_model") or "").strip(),
        "cloud_model": (settings_payload.get("cloud_model") or "").strip(),
        "cloud_api_key": settings_payload.get("cloud_api_key") or "",
    }
    return _save_setting("ai", settings_payload, login_id)


def _handle_backup(settings_payload, login_id):
    if not isinstance(settings_payload, dict):
        return api_error("Invalid settings payload")
    settings_payload = {
        "host": (settings_payload.get("host") or "").strip(),
        "port": str(settings_payload.get("port") or "").strip(),
        "database": (settings_payload.get("database") or "").strip(),
        "user": (settings_payload.get("user") or "").strip(),
        "password": settings_payload.get("password") or "",
        "ssl_mode": (settings_payload.get("ssl_mode") or "require").strip(),
        "note": (settings_payload.get("note") or "").strip(),
    }
    return _save_setting("backup", settings_payload, login_id)


def _handle_sendmsg(settings_payload, login_id):
    if settings_payload is None:
        settings_payload = []
    if not isinstance(settings_payload, list):
        return api_error("Invalid settings payload")
    return _save_setting("sendmsg", settings_payload, login_id)


def _handle_tasks(settings_payload, login_id):
    if settings_payload is None:
        settings_payload = []
    if not isinstance(settings_payload, list):
        return api_error("Invalid settings payload")
    return _save_setting("tasks", settings_payload, login_id)


# 各个配置的处理方法
SECTION_HANDLERS = {
    "match": _handle_match,
    "ai": _handle_ai,
    "backup": _handle_backup,
    "sendmsg": _handle_sendmsg,
    "tasks": _handle_tasks,
}


@csrf_exempt
@require_http_methods(["GET", "POST"])
# 获取配置&保存配置
def sys_settings_section_api(request, section):
    login_id, error = require_login(request)
    if error:
        return error

    if section not in SECTION_DEFAULTS:
        return api_error("Unknown settings section", status=404)

    if request.method == "GET":
        record = _get_setting(section)
        settings_payload = record.settings if record else SECTION_DEFAULTS[section]
        return api_success(data={"name": section, "settings": settings_payload})

    if request.method == "POST":
        # gmail认证文件上传start
        if request.FILES.get("auth_file"):
            if section != "business-email":
                return api_error("Unsupported action for this section", status=405)
            return _handle_business_email_upload(request.FILES.get("auth_file"), login_id)
        # gmail认证文件上传end

        payload, error = parse_json_body(request)
        if error:
            return error

        # 保存配置
        if "settings" not in payload:
            return api_error("Missing field: settings")
        settings_payload = payload.get("settings")
        handler = SECTION_HANDLERS.get(section)
        if not handler:
            return api_error("Unknown settings section", status=404)
        return handler(settings_payload, login_id)

    return api_error("Unknown settings section", status=404)


@csrf_exempt
@require_http_methods(["POST"])
# 测试gmail连接（也可当作获取token的方式）
def sys_settings_gmail_test_api(request):
    login_id, error = require_login(request)
    if error:
        return error
    try:
        result = test_connection()
    except FileNotFoundError as exc:
        return api_error(str(exc))
    except Exception as exc:
        return api_error(str(exc))
    return api_success(
        data={
            "message": "连接成功",
            "email_address": result.get("email_address"),
            "profile": result,
        }
    )
