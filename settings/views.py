import json
import threading
from pathlib import Path

from django.conf import settings as django_settings
from django.utils import timezone
from django.utils.dateparse import parse_time
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from bpmatch.authorize_gmail import test_connection
from project.api import api_error, api_success
from project.common_tools import parse_json_body, require_login
from settings.llm_check import check_cloud_model, check_local_model
from settings.models import ScheduledTask, SysSettings
from settings.timer_task import run_time_to_save, run_time_to_clean, run_time_to_hello

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
        "model_type": "local",
        "model_name": "",
        "api_key": "",
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

    base_dir = Path(django_settings.BASE_DIR)
    credentials_dir = base_dir / "credentials"
    credentials_dir.mkdir(parents=True, exist_ok=True)
    target_path = credentials_dir / "gmail_credentials.json"
    target_path.write_bytes(file_bytes)

    settings_payload = {
        "auth_filename": "gmail_credentials.json",
        "auth_path": str(Path("credentials") / "gmail_credentials.json"),
    }
    return _save_setting("business-email", settings_payload, login_id)


# 保存AI配置
def _handle_ai(settings_payload, login_id):
    if not isinstance(settings_payload, dict):
        return api_error("Invalid settings payload")

    model_type = settings_payload.get("model_type")
    if model_type not in ("local", "cloud"):
        return api_error("Invalid mode")

    model_name = settings_payload.get("model_name")
    if model_name is None:
        return api_error("Invalid model name")

    api_key = settings_payload.get("api_key")
    if api_key is None:
        return api_error("Invalid API key")

    settings_payload = {
        "model_type": model_type,
        "model_name": str(model_name or "").strip(),
        "api_key": settings_payload.get("api_key")
    }
    return _save_setting("ai", settings_payload, login_id)


# 保存Match 配置
def _handle_match(settings_payload, login_id):
    if not isinstance(settings_payload, dict):
        return api_error("Invalid settings payload")

    cycle_days = int(settings_payload.get("cycle_days", 0))

    if cycle_days < 1:
        return api_error("Invalid cycle_days")

    return _save_setting("match", {"cycle_days": cycle_days}, login_id)


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
    existing_tasks = {
        task.id: task
        for task in ScheduledTask.objects.filter(deleted_at__isnull=True)
    }
    seen_task_ids = set()
    saved_tasks = []

    for item in settings_payload:
        if not isinstance(item, dict):
            return api_error("Invalid task payload")
        raw_id = item.get("id")
        task_id = None
        if raw_id not in (None, ""):
            try:
                task_id = int(raw_id)
            except (TypeError, ValueError):
                return api_error("Invalid task id")

        task = existing_tasks.get(task_id) if task_id else ScheduledTask()
        task.name = str(item.get("name") or "").strip()

        time_raw = str(item.get("time") or "").strip()
        task_time = parse_time(time_raw) if time_raw else None
        task.time = task_time

        task.frequency = str(item.get("frequency") or "").strip()
        task.cron_expr = str(item.get("cron_expr") or "").strip()

        method = str(item.get("method") or "POST").strip().upper()
        task.method = method

        task.api = str(item.get("api") or "").strip()
        task.body = str(item.get("body") or "")

        enabled = item.get("enabled")
        if enabled is None and task.id:
            pass
        else:
            task.enabled = bool(enabled) if enabled is not None else True

        if task.id:
            task.updated_by = login_id
        else:
            task.created_by = login_id
            task.updated_by = login_id

        task.save()
        saved_tasks.append(task)
        seen_task_ids.add(task.id)

    for task in existing_tasks.values():
        if task.id not in seen_task_ids:
            task.deleted_at = timezone.now()
            task.save(update_fields=["deleted_at"])

    return api_success(
        data={"name": "tasks", "settings": [_serialize_task(task) for task in saved_tasks]}
    )


def _serialize_task(task: ScheduledTask):
    return {
        "id": task.id,
        "name": task.name,
        "time": task.time.strftime("%H:%M") if task.time else "",
        "frequency": task.frequency,
        "cron_expr": task.cron_expr,
        "method": task.method,
        "api": task.api,
        "body": task.body,
        "enabled": task.enabled,
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
        "last_status": task.last_status,
        "last_error": task.last_error,
    }


def _list_tasks():
    tasks = ScheduledTask.objects.filter(deleted_at__isnull=True).order_by("id")
    return [_serialize_task(task) for task in tasks]


# 各个配置的处理方法
SECTION_HANDLERS = {
    "match": _handle_match,
    "ai": _handle_ai,
    "backup": _handle_backup,
    "sendmsg": _handle_sendmsg,
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
@require_http_methods(["GET", "POST"])
def sys_tasks_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "GET":
        return api_success(data={"tasks": _list_tasks()})

    payload, error = parse_json_body(request)
    if error:
        return error
    if "tasks" not in payload:
        return api_error("Missing field: tasks")
    return _handle_tasks(payload.get("tasks"), login_id)


# ---------------------------------------------配置的执行项---------------------------------------------

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


@csrf_exempt
@require_POST
# 测试AI连接
def sys_settings_ai_test_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    payload, payload_error = parse_json_body(request)
    if payload_error:
        payload = {}

    model_type = payload.get("model_type")
    model_name = payload.get("model_name")
    api_key = payload.get("api_key")

    if model_type not in ("local", "cloud"):
        return api_error("Invalid mode")
    if not model_name:
        return api_error("Missing model name")
    if model_type == "cloud" and not api_key:
        return api_error("Missing API key")

    if model_type == "local":
        return check_local_model(model_name)

    if model_type == "cloud":
        return check_cloud_model(model_name, api_key)

    return api_success(
        data={
            "message": "配置有效，已可以使用。",
            "model_name": model_name,
            "model_type": model_type,
        }
    )


# -------------------------------------定时任务

@csrf_exempt
@require_POST
# 定时刷新数据库中的案件及技术者信息
def time_to_save(request):
    thread = threading.Thread(
        target=run_time_to_save,
        name="time_to_save",
        daemon=True,
    )
    thread.start()
    return api_success()


@csrf_exempt
@require_POST
# 定时清理过期的案件及技术者信息
def time_to_clean():
    thread = threading.Thread(
        target=run_time_to_clean,
        name="time_to_clean",
        daemon=True,
    )
    thread.start()
    return api_success()


@csrf_exempt
@require_POST
# 定时备份数据
def time_to_backup():
    thread = threading.Thread(
        target=run_time_to_clean,
        name="time_to_clean",
        daemon=True,
    )
    thread.start()
    return api_success()


@csrf_exempt
@require_POST
def time_to_hello(request):
    thread = threading.Thread(
        target=run_time_to_hello,
        name="time_to_hello",
        daemon=True,
    )
    thread.start()
    return api_success()
