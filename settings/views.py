import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings as django_settings
from django.utils import timezone
from django.utils.dateparse import parse_time
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from bpmatch.authorize_gmail import test_connection
from bpmatch.mailTool import test_receive_connection, test_smtp_connection
from employee.models import UserLogin
from project.api import api_error, api_success
from project.common_tools import parse_json_body, require_login
from settings.LINE import (
    invalidate_line_notify_filter_cache,
    test_line_connection,
)
from settings.activation_code import is_activation_code_valid
from settings.llm_check import check_cloud_model, check_local_model
from settings.models import ScheduledTask, SysSettings
from settings.timer_task import (
    run_time_to_save,
    run_time_to_save_day,
    run_time_to_clean,
    run_time_to_hello,
    run_time_to_sync_my_mails,
)

# 失败默认返回值
SECTION_DEFAULTS = {
    "business-email": {
        "auth_filename": "",
        "auth_path": "",
        "token_filename": "",
        "token_path": "",
    },
    "match": {
        "cycle_days": 14,
    },
    "ocr": {
        "ocr_filename": "",
        "ocr_path": "",
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
    "bank-account": {
        "bank_name": "",
        "branch_code": "",
        "branch_name": "",
        "account_type": "",
        "account_number": "",
        "account_holder": "",
    },
    "sendmsg": [],
    "line-notify": {
        "channel_access_token": "",
        "channel_secret": "",
        "to_user_id": "",
        "nationality": -1,
        "skills": [],
    },
    "activation": {
        "code": "",
        "expires_at": "",
        "username": "",
        "email": "",
        "system_version": "",
    },
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
def _handle_business_email_upload(auth_file, token_file, login_id):
    if not auth_file and not token_file:
        return api_error("Missing Gmail auth or token file")

    record = _get_setting("business-email")
    settings_payload = record.settings if record else SECTION_DEFAULTS["business-email"].copy()

    base_dir = Path(django_settings.BASE_DIR)
    credentials_dir = base_dir / "credentials"
    credentials_dir.mkdir(parents=True, exist_ok=True)

    if auth_file:
        try:
            auth_bytes = auth_file.read()
            json.loads(auth_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return api_error("Invalid Gmail auth JSON file")
        auth_target = credentials_dir / "gmail_credentials.json"
        auth_target.write_bytes(auth_bytes)
        settings_payload.update({
            "auth_filename": "gmail_credentials.json",
            "auth_path": str(Path("credentials") / "gmail_credentials.json"),
        })

    if token_file:
        try:
            token_bytes = token_file.read()
            json.loads(token_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return api_error("Invalid Gmail token JSON file")
        token_target = credentials_dir / "gmail_token.json"
        token_target.write_bytes(token_bytes)
        settings_payload.update({
            "token_filename": "gmail_token.json",
            "token_path": str(Path("credentials") / "gmail_token.json"),
        })

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


def _handle_ocr_upload(ocr_auth_file, login_id):
    if not ocr_auth_file:
        return api_error("Missing OCR auth file")

    try:
        ocr_auth_bytes = ocr_auth_file.read()
        json.loads(ocr_auth_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return api_error("Invalid OCR auth JSON file")

    base_dir = Path(django_settings.BASE_DIR)
    credentials_dir = base_dir / "credentials"
    credentials_dir.mkdir(parents=True, exist_ok=True)

    ocr_target = credentials_dir / "ocr_credentials.json"
    ocr_target.write_bytes(ocr_auth_bytes)

    record = _get_setting("ocr")
    merged = SECTION_DEFAULTS["ocr"].copy()
    if record and isinstance(record.settings, dict):
        merged.update(record.settings)
    merged.update({
        "ocr_filename": "ocr_credentials.json",
        "ocr_path": str(Path("credentials") / "ocr_credentials.json"),
    })
    return _save_setting("ocr", merged, login_id)


def _handle_ocr(settings_payload, login_id):
    if settings_payload is None:
        settings_payload = {}
    if not isinstance(settings_payload, dict):
        return api_error("Invalid settings payload")
    record = _get_setting("ocr")
    merged = SECTION_DEFAULTS["ocr"].copy()
    if record and isinstance(record.settings, dict):
        merged.update(record.settings)
    if "ocr_filename" in settings_payload:
        merged["ocr_filename"] = str(settings_payload.get("ocr_filename") or "").strip()
    if "ocr_path" in settings_payload:
        merged["ocr_path"] = str(settings_payload.get("ocr_path") or "").strip()
    return _save_setting("ocr", merged, login_id)


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
    normalized = []
    for item in settings_payload:
        if not isinstance(item, dict):
            continue
        imap_use_smtp_auth_raw = item.get("imap_use_smtp_auth")
        if isinstance(imap_use_smtp_auth_raw, bool):
            imap_use_smtp_auth = imap_use_smtp_auth_raw
        elif isinstance(imap_use_smtp_auth_raw, str):
            imap_use_smtp_auth = imap_use_smtp_auth_raw.strip().lower() not in ("0", "false", "no", "off")
        elif isinstance(imap_use_smtp_auth_raw, (int, float)):
            imap_use_smtp_auth = bool(imap_use_smtp_auth_raw)
        else:
            imap_use_smtp_auth = True

        pop3_use_smtp_auth_raw = item.get("pop3_use_smtp_auth")
        if isinstance(pop3_use_smtp_auth_raw, bool):
            pop3_use_smtp_auth = pop3_use_smtp_auth_raw
        elif isinstance(pop3_use_smtp_auth_raw, str):
            pop3_use_smtp_auth = pop3_use_smtp_auth_raw.strip().lower() not in ("0", "false", "no", "off")
        elif isinstance(pop3_use_smtp_auth_raw, (int, float)):
            pop3_use_smtp_auth = bool(pop3_use_smtp_auth_raw)
        else:
            pop3_use_smtp_auth = True

        incoming_protocol = str(item.get("incoming_protocol") or "").strip().lower()
        if incoming_protocol not in ("imap", "pop3"):
            incoming_protocol = "pop3" if str(item.get("pop3_host") or "").strip() else "imap"

        normalized.append(
            {
                "email": str(item.get("email") or "").strip(),
                "password": str(item.get("password") or ""),
                "smtp": str(item.get("smtp") or "").strip(),
                "port": str(item.get("port") or "").strip(),
                "user": str(item.get("user") or "").strip(),
                "incoming_protocol": incoming_protocol,
                "imap_host": str(item.get("imap_host") or "").strip(),
                "imap_port": str(item.get("imap_port") or "").strip(),
                "imap_security": str(item.get("imap_security") or "").strip().lower(),
                "imap_folder": str(item.get("imap_folder") or "").strip(),
                "imap_use_smtp_auth": imap_use_smtp_auth,
                "imap_user": str(item.get("imap_user") or "").strip(),
                "imap_password": str(item.get("imap_password") or ""),
                "pop3_host": str(item.get("pop3_host") or "").strip(),
                "pop3_port": str(item.get("pop3_port") or "").strip(),
                "pop3_security": str(item.get("pop3_security") or "").strip().lower(),
                "pop3_use_smtp_auth": pop3_use_smtp_auth,
                "pop3_user": str(item.get("pop3_user") or "").strip(),
                "pop3_password": str(item.get("pop3_password") or ""),
            }
        )
    return _save_setting("sendmsg", normalized, login_id)


def _handle_line_notify(settings_payload, login_id):
    if not isinstance(settings_payload, dict):
        return api_error("Invalid settings payload")

    def _normalize_nationality(value):
        # -1: 未设置, 0: 仅日本籍, 1: 外国籍可
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return -1
        return parsed if parsed in (-1, 0, 1) else -1

    def _normalize_skills(value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raw = str(value).strip()
        if not raw:
            return []
        normalized = raw
        for sep in ("，", ",", "/", "|", ";", "；"):
            normalized = normalized.replace(sep, "、")
        return [item.strip() for item in normalized.split("、") if item.strip()]

    record = _get_setting("line-notify")
    normalized = SECTION_DEFAULTS["line-notify"].copy()
    if record and isinstance(record.settings, dict):
        normalized.update(record.settings)

    if "channel_access_token" in settings_payload:
        normalized["channel_access_token"] = str(settings_payload.get("channel_access_token") or "").strip()
    if "channel_secret" in settings_payload:
        normalized["channel_secret"] = str(settings_payload.get("channel_secret") or "").strip()
    if "to_user_id" in settings_payload:
        normalized["to_user_id"] = str(settings_payload.get("to_user_id") or "").strip()
    if "nationality" in settings_payload:
        normalized["nationality"] = _normalize_nationality(settings_payload.get("nationality"))
    else:
        normalized["nationality"] = -1
    if "skills" in settings_payload:
        skills_payload = settings_payload.get("skills")
        normalized["skills"] = _normalize_skills(skills_payload)

    response = _save_setting("line-notify", normalized, login_id)
    invalidate_line_notify_filter_cache()
    return response


def _handle_bank_account(settings_payload, login_id):
    if not isinstance(settings_payload, dict):
        return api_error("Invalid settings payload")
    normalized = {
        "bank_name": str(settings_payload.get("bank_name") or "").strip(),
        "branch_code": str(settings_payload.get("branch_code") or "").strip(),
        "branch_name": str(settings_payload.get("branch_name") or "").strip(),
        "account_type": str(settings_payload.get("account_type") or "").strip(),
        "account_number": str(settings_payload.get("account_number") or "").strip(),
        "account_holder": str(settings_payload.get("account_holder") or "").strip(),
    }
    return _save_setting("bank-account", normalized, login_id)


def _handle_activation(settings_payload, login_id):
    if not isinstance(settings_payload, dict):
        return api_error("Invalid settings payload")
    code = str(settings_payload.get("code") or "").strip()
    if not code:
        return api_error("Missing activation code")
    valid, payload, _reason = is_activation_code_valid(code, now=timezone.now())
    if not valid or not payload:
        return api_error("Invalid or expired activation code")
    expires_at = str(payload.get("expires_at") or "")
    normalized = {
        "code": code,
        "expires_at": expires_at,
        "username": str(payload.get("username") or ""),
        "email": str(payload.get("email") or ""),
        "system_version": str(payload.get("system_version") or ""),
    }
    return _save_setting("activation", normalized, login_id)


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


_TASK_LOG_LINE_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>[A-Z]+) (?P<message>.+)$"
)


def _parse_task_log_line(line):
    match = _TASK_LOG_LINE_RE.match(line)
    if not match:
        return None
    return {
        "time": match.group("time"),
        "level": match.group("level"),
        "message": match.group("message"),
    }


def _parse_log_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _collect_task_logs(task_id, limit, start_date=None, end_date=None, log_glob="scheduled_tasks.log*",
                       task_filter=None):
    logs_dir = Path(django_settings.BASE_DIR) / "logs"
    if not logs_dir.exists():
        return [], 0
    files = sorted(
        logs_dir.glob(log_glob),
        key=lambda path: path.stat().st_mtime,
    )
    task_pattern = re.compile(rf"\\btask={task_id}\\b") if task_id else None
    entries = []
    current = None
    for log_file in files:
        try:
            lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in lines:
            parsed = _parse_task_log_line(line)
            if parsed:
                current = parsed
                entries.append(current)
            elif current:
                current["message"] = f"{current['message']}\n{line}"
            else:
                continue
    filtered = []
    for entry in entries:
        message = entry.get("message") or ""
        if task_pattern and not task_pattern.search(message):
            continue
        if task_filter and not task_filter.search(message):
            continue
        log_date = _parse_log_date((entry.get("time") or "")[:10])
        if start_date and (not log_date or log_date < start_date):
            continue
        if end_date and (not log_date or log_date > end_date):
            continue
        filtered.append(entry)
    if not filtered:
        return [], len(files)
    return list(reversed(filtered[-limit:])), len(files)


def _list_tasks():
    tasks = ScheduledTask.objects.filter(deleted_at__isnull=True).order_by("id")
    return [_serialize_task(task) for task in tasks]


# 各个配置的处理方法
SECTION_HANDLERS = {
    "match": _handle_match,
    "ocr": _handle_ocr,
    "ai": _handle_ai,
    "backup": _handle_backup,
    "bank-account": _handle_bank_account,
    "sendmsg": _handle_sendmsg,
    "line-notify": _handle_line_notify,
    "activation": _handle_activation,
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
        if request.FILES.get("auth_file") or request.FILES.get("token_file"):
            if section != "business-email":
                return api_error("Unsupported action for this section", status=405)
            return _handle_business_email_upload(
                request.FILES.get("auth_file"),
                request.FILES.get("token_file"),
                login_id,
            )
        # gmail认证文件上传end
        if request.FILES.get("ocr_auth_file"):
            if section != "ocr":
                return api_error("Unsupported action for this section", status=405)
            return _handle_ocr_upload(
                request.FILES.get("ocr_auth_file"),
                login_id,
            )

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
@require_http_methods(["GET"])
def activation_status_api(request):
    record = _get_setting("activation")
    if not record:
        return api_success(data={"valid": False, "reason": "missing"})
    settings_payload = record.settings or {}
    code = str(settings_payload.get("code") or "").strip()
    if not code:
        return api_success(data={"valid": False, "reason": "missing"})
    valid, payload, reason = is_activation_code_valid(code, now=timezone.now())
    if not valid:
        return api_success(data={"valid": False, "reason": reason or "invalid"})
    return api_success(
        data={
            "valid": True,
            "expires_at": payload.get("expires_at") if payload else "",
            "username": payload.get("username") if payload else "",
            "email": payload.get("email") if payload else "",
            "system_version": payload.get("system_version") if payload else "",
        }
    )


@csrf_exempt
@require_POST
def activation_code_api(request):
    payload, error = parse_json_body(request)
    if error:
        return error
    code = str(payload.get("code") or "").strip()
    if not code:
        return api_error("Missing activation code")
    valid, parsed, _reason = is_activation_code_valid(code, now=timezone.now())
    if not valid or not parsed:
        return api_error("激活码无效或已过期")
    settings_payload = {
        "code": code,
        "expires_at": str(parsed.get("expires_at") or ""),
        "username": str(parsed.get("username") or ""),
        "email": str(parsed.get("email") or ""),
        "system_version": str(parsed.get("system_version") or ""),
    }
    return _save_setting("activation", settings_payload, login_id=None)


@csrf_exempt
@require_POST
def activation_validate_api(request):
    payload, error = parse_json_body(request)
    if error:
        return error
    code = str(payload.get("code") or "").strip()
    if not code:
        return api_error("Missing activation code")
    valid, parsed, _reason = is_activation_code_valid(code, now=timezone.now())
    if not valid or not parsed:
        return api_error("激活码无效或已过期")
    return api_success(
        data={
            "expires_at": str(parsed.get("expires_at") or ""),
            "username": str(parsed.get("username") or ""),
            "email": str(parsed.get("email") or ""),
            "system_version": str(parsed.get("system_version") or ""),
        }
    )


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


@csrf_exempt
@require_http_methods(["GET"])
def sys_task_logs_api(request):
    _login_id, error = require_login(request)
    if error:
        return error

    task_id_raw = request.GET.get("task_id")
    if not task_id_raw:
        return api_error("Missing task_id")
    try:
        task_id = int(task_id_raw)
    except (TypeError, ValueError):
        return api_error("Invalid task_id")

    limit_raw = request.GET.get("limit", 50)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 200))

    start_date = _parse_log_date(request.GET.get("start_date"))
    end_date = _parse_log_date(request.GET.get("end_date"))
    if request.GET.get("start_date") and not start_date:
        return api_error("Invalid start_date")
    if request.GET.get("end_date") and not end_date:
        return api_error("Invalid end_date")
    if start_date and end_date and start_date > end_date:
        return api_error("Invalid date range")

    task = ScheduledTask.objects.filter(id=task_id, deleted_at__isnull=True).first()
    log_glob = "scheduled_tasks.log*"
    task_filter = None
    if task and task.api:
        api = task.api.strip()
        if "time-to-save-day" in api:
            log_glob = "time_to_save_day_*.log"
        elif "time-to-save" in api:
            log_glob = "time_to_save_*.log"
        elif "time-to-clean" in api:
            log_glob = "time_to_clean_*.log"
        elif "time-to-backup" in api:
            log_glob = "time_to_backup_*.log"
        elif "time-to-hello" in api:
            log_glob = "time_to_hello_*.log"
        elif "time-to-sync-my-mails" in api:
            log_glob = "time_to_sync_my_mails_*.log"
        else:
            log_glob = "scheduled_tasks.log*"
            task_filter = re.compile(rf"\\btask={task_id}\\b")

    entries, file_count = _collect_task_logs(
        task_id if log_glob == "scheduled_tasks.log*" else None,
        limit,
        start_date,
        end_date,
        log_glob=log_glob,
        task_filter=task_filter,
    )
    return api_success(
        data={
            "task_id": task_id,
            "entries": entries,
            "limit": limit,
            "file_count": file_count,
        }
    )


# ---------------------------------------------账号密码重置---------------------------------------------

@csrf_exempt
@require_POST
def sys_password_reset_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    payload, payload_error = parse_json_body(request)
    if payload_error:
        return payload_error

    user_name = (payload.get("user_name") or "").strip()
    password = payload.get("password") or ""
    expires_in_days = payload.get("expires_in_days", 1)
    if not user_name or not password:
        return api_error("Missing user_name or password")
    try:
        expires_in_days = int(expires_in_days)
    except (TypeError, ValueError):
        return api_error("Invalid expires_in_days")
    if expires_in_days < 1:
        return api_error("expires_in_days must be at least 1")

    user_login = UserLogin.objects.filter(user_name=user_name, deleted_at__isnull=True).first()
    if not user_login:
        return api_error("User login not found", status=404)

    expires_at = timezone.now() + timedelta(days=expires_in_days)
    user_login.password = password
    user_login.password_expires_at = expires_at
    user_login.updated_by = login_id
    user_login.save(update_fields=["password", "password_expires_at", "updated_by", "updated_at"])

    return api_success(data={
        "user_name": user_name,
        "expires_at": expires_at.isoformat(),
    })


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
def sys_settings_sendmsg_test_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    payload, payload_error = parse_json_body(request)
    if payload_error:
        return payload_error

    email = str(payload.get("email") or "").strip()
    password = str(payload.get("password") or "")
    smtp_host = str(payload.get("smtp") or "").strip()
    smtp_port_raw = str(payload.get("port") or "").strip()

    if not email or not password or not smtp_host or not smtp_port_raw:
        return api_error("Missing SMTP config")

    try:
        smtp_port = int(smtp_port_raw)
    except (TypeError, ValueError):
        return api_error("Invalid SMTP port")

    try:
        result = test_smtp_connection(
            host=smtp_host,
            port=smtp_port,
            username=email,
            password=password,
        )
    except Exception as exc:
        return api_error(str(exc))

    return api_success(data=result)


@csrf_exempt
@require_POST
def sys_settings_sendmsg_receiver_test_api(request):
    _login_id, error = require_login(request)
    if error:
        return error

    payload, payload_error = parse_json_body(request)
    if payload_error:
        return payload_error

    try:
        result = test_receive_connection(payload or {})
    except Exception as exc:
        return api_error(str(exc))

    return api_success(data=result)


@csrf_exempt
@require_POST
def sys_settings_line_notify_test_api(request):
    _login_id, error = require_login(request)
    if error:
        return error

    payload, payload_error = parse_json_body(request)
    if payload_error:
        payload = {}

    channel_access_token = str(payload.get("channel_access_token") or "").strip() or None
    to_user_id = str(payload.get("to_user_id") or "").strip() or None

    try:
        result = test_line_connection(channel_access_token, to_user_id)
    except Exception as exc:
        return api_error(str(exc))

    return api_success(data=result)


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
# 夜间定时刷新数据库中的案件及技术者信息
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
# 日间定时刷新数据库中的案件及技术者信息，仅当天
def time_to_save_day(request):
    thread = threading.Thread(
        target=run_time_to_save_day,
        name="time_to_save",
        daemon=True,
    )
    thread.start()
    return api_success()


@csrf_exempt
@require_POST
# 定时清理过期的案件及技术者信息
def time_to_clean(request):
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
def time_to_backup(request):
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


@csrf_exempt
@require_POST
def time_to_sync_my_mails(request):
    thread = threading.Thread(
        target=run_time_to_sync_my_mails,
        name="time_to_sync_my_mails",
        daemon=True,
    )
    thread.start()
    return api_success()
