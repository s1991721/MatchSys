import json
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import fcntl
import threading
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings as django_settings
from django.db import transaction
from django.utils import timezone

from settings.models import ScheduledTask

_scheduler_lock = threading.Lock()
_scheduler_process_lock_file = None
_scheduler = None
_logger = None


def _get_logger():
    global _logger
    if _logger:
        return _logger
    logger = logging.getLogger("settings.task_scheduler")
    if not logger.handlers:
        logs_dir = os.path.join(django_settings.BASE_DIR, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_path = os.path.join(logs_dir, "scheduled_tasks.log")
        handler = TimedRotatingFileHandler(
            log_path,
            when="midnight",
            interval=1,
            backupCount=14,
            encoding="utf-8",
            utc=False,
        )
        handler.setLevel(logging.INFO)
        handler.suffix = "%Y-%m-%d"
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    _logger = logger
    return logger


# 抢一个跨进程文件锁
def _acquire_scheduler_process_lock(logger):
    global _scheduler_process_lock_file
    if _scheduler_process_lock_file:
        return True

    logs_dir = os.path.join(django_settings.BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    lock_path = os.path.join(logs_dir, "scheduler.lock")
    lock_file = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        logger.info("scheduler skipped because another process holds lock")
        return False
    except Exception:
        lock_file.close()
        logger.exception("scheduler skipped because process lock failed")
        return False

    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    _scheduler_process_lock_file = lock_file
    logger.info("scheduler process lock acquired pid=%s", os.getpid())
    return True


def _base_url():
    return (
        os.getenv("TASK_BASE_URL")
        or getattr(django_settings, "TASK_BASE_URL", None)
        or "http://127.0.0.1:8000"
    )


def _normalize_url(api):
    api = (api or "").strip()
    if not api:
        return ""
    if api.startswith("http://") or api.startswith("https://"):
        return api
    if api.startswith("/"):
        return f"{_base_url().rstrip('/')}{api}"
    return f"{_base_url().rstrip('/')}/{api}"


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _expand_part(part, min_value, max_value):
    part = part.strip()
    if not part:
        return set()
    if part == "*":
        return set(range(min_value, max_value + 1))
    if part.startswith("*/"):
        step = _parse_int(part[2:])
        if not step:
            return set()
        return set(range(min_value, max_value + 1, step))
    if "-" in part:
        if "/" in part:
            range_part, step_part = part.split("/", 1)
            step = _parse_int(step_part)
        else:
            range_part, step = part, 1
        if "-" not in range_part:
            return set()
        start_str, end_str = range_part.split("-", 1)
        start = _parse_int(start_str)
        end = _parse_int(end_str)
        if start is None or end is None or step is None or step <= 0:
            return set()
        start = max(min_value, start)
        end = min(max_value, end)
        if start > end:
            return set()
        return set(range(start, end + 1, step))
    value = _parse_int(part)
    if value is None:
        return set()
    if value < min_value or value > max_value:
        return set()
    return {value}


def _parse_field(field, min_value, max_value):
    values = set()
    for part in field.split(","):
        values.update(_expand_part(part, min_value, max_value))
    return values


def _cron_matches(dt: datetime, expr: str):
    parts = [p for p in (expr or "").split() if p]
    if len(parts) != 5:
        return False
    minute, hour, day, month, dow = parts
    minutes = _parse_field(minute, 0, 59)
    hours = _parse_field(hour, 0, 23)
    days = _parse_field(day, 1, 31)
    months = _parse_field(month, 1, 12)
    dows = _parse_field(dow, 0, 7)
    if 7 in dows:
        dows.add(0)
        dows.discard(7)

    cron_dow = (dt.weekday() + 1) % 7
    return (
        dt.minute in minutes
        and dt.hour in hours
        and dt.day in days
        and dt.month in months
        and cron_dow in dows
    )


def _same_minute(a: datetime, b: datetime):
    return a.replace(second=0, microsecond=0) == b.replace(second=0, microsecond=0)


def _resolve_cron_expr(task: ScheduledTask):
    expr = (task.cron_expr or "").strip()
    if expr:
        return expr
    if task.frequency == "每天" and task.time:
        return f"{task.time.minute} {task.time.hour} * * *"
    return ""


def _run_task(task: ScheduledTask, timeout=10):
    logger = _get_logger()
    url = _normalize_url(task.api)
    if not url:
        return False, "Missing API address"
    method = (task.method or "POST").strip().upper() or "POST"
    data = None
    if method not in ("GET", "HEAD"):
        body_text = (task.body or "").strip() or "{}"
        try:
            body_obj = json.loads(body_text)
            body_text = json.dumps(body_obj)
        except json.JSONDecodeError:
            pass
        data = body_text.encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            logger.info("task=%s method=%s url=%s status=ok", task.id, method, url)
            return True, ""
    except urllib.error.HTTPError as exc:
        logger.warning(
            "task=%s method=%s url=%s status=error code=%s",
            task.id,
            method,
            url,
            exc.code,
        )
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        logger.warning(
            "task=%s method=%s url=%s status=error reason=%s",
            task.id,
            method,
            url,
            exc.reason,
        )
        return False, str(exc.reason)
    except Exception as exc:
        logger.exception("task=%s method=%s url=%s status=exception", task.id, method, url)
        return False, str(exc)


# todo 将tasks进行缓存，新增和编辑定时任务时，缓存失效
def _scan_and_run():
    logger = _get_logger()
    now = timezone.localtime(timezone.now())
    tasks = ScheduledTask.objects.filter(deleted_at__isnull=True, enabled=True)
    logger.info("scan started tasks=%s", tasks.count())
    for task in tasks:
        cron_expr = _resolve_cron_expr(task)
        if not cron_expr:
            continue
        if not _cron_matches(now, cron_expr):
            continue
        if task.last_run_at and _same_minute(
            timezone.localtime(task.last_run_at), now
        ):
            continue
        ok, error = _run_task(task)
        with transaction.atomic():
            task.last_run_at = now
            if ok:
                task.last_status = "success"
                task.last_error = ""
            else:
                task.last_status = "error"
                task.last_error = error
            task.save(
                update_fields=["last_run_at", "last_status", "last_error", "updated_at"]
            )
    logger.info("scan finished")


# 每分钟扫一遍定时任务列表，符合条件即执行
def start_scheduler():
    global _scheduler
    logger = _get_logger()
    with _scheduler_lock:
        if _scheduler and _scheduler.running:
            return _scheduler
        if not _acquire_scheduler_process_lock(logger):
            return None
        tz_name = getattr(django_settings, "TIME_ZONE", "UTC")
        tz = ZoneInfo(tz_name)
        scheduler = BackgroundScheduler(timezone=tz)
        scheduler.add_job(
            _scan_and_run,
            CronTrigger(minute="*", second="0", timezone=tz),
            id="scheduled_task_runner",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        logger.info("scheduler started")
        _scheduler = scheduler
        return _scheduler
