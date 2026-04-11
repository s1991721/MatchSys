import json
import logging
import os
from datetime import timedelta

from django.conf import settings as django_settings
from django.db import close_old_connections, connection, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from bpmatch import llmsTool
from bpmatch.gmailTool import GmailTool
from bpmatch.mailTool import resolve_sendmsg_sync_targets, sync_today_my_mails_from_imap
from bpmatch.models import SavedMailInfo, MailTechnicianInfo, MailProjectInfo, MyMail
from settings.activation_code import is_activation_code_valid
from settings.mails_arrival_notification import notify_project_ingested
from settings.models import SysSettings


# 按日期初始化日志logger
def _ensure_logger(logger: logging.Logger):
    date_tag = timezone.now().strftime("%Y-%m-%d")
    logs_dir = os.path.join(django_settings.BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, f"time_to_save_{date_tag}.log")

    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == log_path:
            return

    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


# 激活码验证
def _validate_activation(logger: logging.Logger, task_name: str) -> bool:
    # 校验激活码是否存在且在有效期内
    activation_record = SysSettings.objects.filter(
        name="activation", deleted_at__isnull=True
    ).first()
    activation_settings = (
        activation_record.settings
        if activation_record and isinstance(activation_record.settings, dict)
        else {}
    )
    activation_code = str(activation_settings.get("code") or "").strip()
    if not activation_code:
        logger.warning("%s skipped: missing activation code", task_name)
        return False
    valid, _payload, reason = is_activation_code_valid(
        activation_code, now=timezone.now()
    )
    if not valid:
        logger.warning("%s skipped: invalid activation code reason=%s", task_name, reason)
        return False
    return True


# -------------------------------------分析邮件
logger_save = logging.getLogger("bpmatch.time_to_save")

# 默认周期天数
DEFAULT_CYCLE_DAYS = 14


# 获取Match 配置周期天数
def _get_cycle_days():
    record = SysSettings.objects.filter(name="match", deleted_at__isnull=True).first()
    if not record or not isinstance(record.settings, dict):
        return DEFAULT_CYCLE_DAYS
    value = record.settings.get("cycle_days", DEFAULT_CYCLE_DAYS)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_CYCLE_DAYS
    return value if value > 0 else DEFAULT_CYCLE_DAYS


def _parse_datetime(value: str):
    if not value:
        return None
    parsed = parse_datetime(value)
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.utc)
    return parsed


def _parse_detail(value: str):
    try:
        detail = json.loads(value) if value else {}
    except Exception:
        detail = {}
    country = detail.get("country")
    skills = detail.get("skills") or []
    price = detail.get("price")

    if isinstance(skills, list):
        skills_text = ",".join(
            [str(skill).strip() for skill in skills if str(skill).strip()]
        )
    elif isinstance(skills, str):
        skills_text = skills
    else:
        skills_text = ""

    if price in (None, ""):
        price_value = None
    else:
        try:
            price_value = float(price)
        except Exception:
            price_value = None

    return ("" if country is None else str(country), skills_text, price_value)


# 夜间定时处理营业邮件
def run_time_to_save():
    _ensure_logger(logger_save)
    if not _validate_activation(logger_save, "time_to_save"):
        return
    close_old_connections()
    # 开始工作的时间
    started_at = timezone.now()
    logger_save.info("time_to_save started at %s", timezone.localtime(started_at).strftime("%Y-%m-%d %H:%M:%S"))

    # 当前日期
    end_date = timezone.now().date()
    # 需要处理邮件的起始日期
    start_date = end_date - timedelta(days=_get_cycle_days())
    gmail = GmailTool()

    page = 1
    page_size = 100
    mail_list = []

    # 获取邮件
    while True:
        messages, has_next, _ = gmail.fetch_new_messages(
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date,
        )
        mail_list.extend(messages)
        logger_save.info("time_to_save fetched page=%s count=%s", page, len(messages))
        if not has_next:
            break
        page += 1

    # 邮件分类
    project_list = []
    technician_list = []
    for mail in mail_list:
        title = mail.get("subject") or ""
        label = llmsTool.title_analysis(title)
        label_str = str(label).strip()
        if label_str == "0":
            project_list.append(mail)
        elif label_str == "1":
            technician_list.append(mail)

    logger_save.info("time_to_save classified total=%s projects=%s technicians=%s",
                     len(mail_list), len(project_list), len(technician_list), )

    # 案件邮件落库
    for mail in project_list:
        try:
            with transaction.atomic():
                detail_json = llmsTool.qiuren_detail_analysis(mail.get("body") or "")
                country, skills, price = _parse_detail(detail_json)
                MailProjectInfo.objects.create(
                    id=mail.get("id"),
                    title=mail.get("subject") or "",
                    address=mail.get("from") or "",
                    body=mail.get("body") or "",
                    files="",
                    date=_parse_datetime(mail.get("date") or ""),
                    remark="",
                    country=country,
                    skills=skills,
                    price=price,
                )
                SavedMailInfo.objects.create(
                    id=mail.get("id"),
                    date=mail.get("date"),
                )
                transaction.on_commit(
                    lambda _mail=mail, _country=country, _skills=skills, _price=price: notify_project_ingested(
                        _mail, _country, _skills, _price
                    )
                )
        except Exception:
            logger_save.exception("time_to_save project failed from:%s subject:%s",
                                  mail.get("from"), mail.get("subject"))

    # 技术者邮件落库
    for mail in technician_list:
        try:
            with transaction.atomic():
                detail_json = llmsTool.qiuanjian_detail_analysis(mail.get("body") or "")
                country, skills, price = _parse_detail(detail_json)
                MailTechnicianInfo.objects.create(
                    id=mail.get("id"),
                    title=mail.get("subject") or "",
                    address=mail.get("from") or "",
                    body=mail.get("body") or "",
                    files="",
                    date=_parse_datetime(mail.get("date") or ""),
                    remark="",
                    country=country,
                    skills=skills,
                    price=price,
                )
                SavedMailInfo.objects.create(
                    id=mail.get("id"),
                    date=mail.get("date"),
                )
        except Exception:
            logger_save.exception("time_to_save technician failed from:%s subject:%s",
                                  mail.get("from"), mail.get("subject"))

    logger_save.info("time_to_save finished total=%s projects=%s technicians=%s duration_s=%.2f",
                     len(mail_list), len(project_list), len(technician_list),
                     (timezone.now() - started_at).total_seconds(), )
    close_old_connections()


# 日间定时处理营业邮件
def run_time_to_save_day():
    _ensure_logger(logger_save)
    if not _validate_activation(logger_save, "time_to_save_day"):
        return
    close_old_connections()
    # 开始工作的时间
    started_at = timezone.now()
    logger_save.info("time_to_save_day started at %s", timezone.localtime(started_at).strftime("%Y-%m-%d %H:%M:%S"))

    # 日间同步只处理当天邮件，避免白天定时任务重复回扫历史周期
    start_date = timezone.now().date()
    end_date = start_date
    gmail = GmailTool()

    page = 1
    page_size = 100
    mail_list = []

    # 获取邮件
    while True:
        messages, has_next, _ = gmail.fetch_new_messages(
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date,
        )
        mail_list.extend(messages)
        logger_save.info("time_to_save_day fetched page=%s count=%s", page, len(messages))
        if not has_next:
            break
        page += 1

    # 邮件分类
    project_list = []
    technician_list = []
    for mail in mail_list:
        title = mail.get("subject") or ""
        label = llmsTool.title_analysis(title)
        label_str = str(label).strip()
        if label_str == "0":
            project_list.append(mail)
        elif label_str == "1":
            technician_list.append(mail)

    logger_save.info("time_to_save_day classified total=%s projects=%s technicians=%s",
                     len(mail_list), len(project_list), len(technician_list), )

    # 案件邮件落库
    for mail in project_list:
        try:
            with transaction.atomic():
                detail_json = llmsTool.qiuren_detail_analysis(mail.get("body") or "")
                country, skills, price = _parse_detail(detail_json)
                MailProjectInfo.objects.create(
                    id=mail.get("id"),
                    title=mail.get("subject") or "",
                    address=mail.get("from") or "",
                    body=mail.get("body") or "",
                    files="",
                    date=_parse_datetime(mail.get("date") or ""),
                    remark="",
                    country=country,
                    skills=skills,
                    price=price,
                )
                SavedMailInfo.objects.create(
                    id=mail.get("id"),
                    date=mail.get("date"),
                )
                transaction.on_commit(
                    lambda _mail=mail, _country=country, _skills=skills, _price=price: notify_project_ingested(
                        _mail, _country, _skills, _price
                    )
                )
        except Exception:
            logger_save.exception("time_to_save_day project failed from:%s subject:%s",
                                  mail.get("from"), mail.get("subject"))

    # 技术者邮件落库
    for mail in technician_list:
        try:
            with transaction.atomic():
                detail_json = llmsTool.qiuanjian_detail_analysis(mail.get("body") or "")
                country, skills, price = _parse_detail(detail_json)
                MailTechnicianInfo.objects.create(
                    id=mail.get("id"),
                    title=mail.get("subject") or "",
                    address=mail.get("from") or "",
                    body=mail.get("body") or "",
                    files="",
                    date=_parse_datetime(mail.get("date") or ""),
                    remark="",
                    country=country,
                    skills=skills,
                    price=price,
                )
                SavedMailInfo.objects.create(
                    id=mail.get("id"),
                    date=mail.get("date"),
                )
        except Exception:
            logger_save.exception("time_to_save_day technician failed from:%s subject:%s",
                                  mail.get("from"), mail.get("subject"))

    logger_save.info("time_to_save_day finished total=%s projects=%s technicians=%s duration_s=%.2f",
                     len(mail_list), len(project_list), len(technician_list),
                     (timezone.now() - started_at).total_seconds(), )
    close_old_connections()

# -------------------------------------清理过期邮件
logger_clean = logging.getLogger("bpmatch.time_to_clean")


# 过期邮件清理
def _clean_expired_mails():
    # 清理过期邮件（含日期为空的记录）
    cutoff = timezone.now() - timedelta(days=_get_cycle_days())
    with transaction.atomic():
        saved_deleted, _ = SavedMailInfo.objects.filter(
            Q(date__lt=cutoff) | Q(date__isnull=True)
        ).delete()
        project_deleted, _ = MailProjectInfo.objects.filter(
            Q(date__lt=cutoff) | Q(date__isnull=True)
        ).delete()
        technician_deleted, _ = MailTechnicianInfo.objects.filter(
            Q(date__lt=cutoff) | Q(date__isnull=True)
        ).delete()
        my_mail_deleted, _ = MyMail.objects.filter(
            Q(received_at__lt=cutoff) | Q(received_at__isnull=True)
        ).delete()

    logger_clean.info(
        "time_to_clean mails deleted saved=%s projects=%s technicians=%s my_mail=%s cutoff=%s",
        saved_deleted,
        project_deleted,
        technician_deleted,
        my_mail_deleted,
        timezone.localtime(cutoff).strftime("%Y-%m-%d %H:%M:%S"),
    )


# 删除上个月及之前的考勤分表
def _drop_expired_attendance_tables():
    today = timezone.localdate()
    first_of_month = today.replace(day=1)
    last_month_date = first_of_month - timedelta(days=1)
    last_month_suffix = int(last_month_date.strftime("%Y%m"))

    table_prefix = "attendance_punch_"
    to_drop = []
    existing_tables = set(connection.introspection.table_names())
    for table_name in existing_tables:
        if not table_name.startswith(table_prefix):
            continue
        suffix = table_name[len(table_prefix):]
        if len(suffix) != 6 or not suffix.isdigit():
            continue
        if int(suffix) <= last_month_suffix:
            to_drop.append(table_name)

    dropped_tables = 0
    if to_drop:
        with connection.cursor() as cursor:
            for table_name in sorted(to_drop):
                quoted = connection.ops.quote_name(table_name)
                cursor.execute(f"DROP TABLE IF EXISTS {quoted}")
                dropped_tables += 1

    logger_clean.info(
        "time_to_clean attendance tables dropped=%s through_suffix=%s tables=%s",
        dropped_tables,
        last_month_suffix,
        ",".join(sorted(to_drop)) if to_drop else "",
    )


# 定时清理无用数据
def run_time_to_clean():
    _ensure_logger(logger_clean)
    if not _validate_activation(logger_clean, "time_to_clean"):
        return
    close_old_connections()
    started_at = timezone.now()
    logger_clean.info(
        "time_to_clean started at %s",
        timezone.localtime(started_at).strftime("%Y-%m-%d %H:%M:%S"),
    )
    try:
        _clean_expired_mails()
        _drop_expired_attendance_tables()
        logger_clean.info(
            "time_to_clean finished duration_s=%.2f",
            (timezone.now() - started_at).total_seconds(),
        )
    except Exception:
        logger_clean.exception("time_to_clean failed")
    finally:
        close_old_connections()


def run_time_to_hello():
    print("hello", flush=True)


# -------------------------------------同步我的邮件
logger_sync_my_mails = logging.getLogger("bpmatch.time_to_sync_my_mails")


# 我的邮件（而非营业邮件）
def run_time_to_sync_my_mails():
    _ensure_logger(logger_sync_my_mails)
    close_old_connections()
    started_at = timezone.now()
    logger_sync_my_mails.info(
        "time_to_sync_my_mails started at %s",
        timezone.localtime(started_at).strftime("%Y-%m-%d %H:%M:%S"),
    )
    try:
        if not _validate_activation(logger_sync_my_mails, "time_to_sync_my_mails"):
            return

        targets, skipped = resolve_sendmsg_sync_targets()
        inserted_total = 0
        for item in targets:
            owner_id = item.get("owner_id")
            send_config = item.get("send_config") or {}
            mailbox = str(send_config.get("email") or "").strip()
            if not owner_id:
                continue
            try:
                inserted = sync_today_my_mails_from_imap(
                    owner_id=owner_id,
                    send_config=send_config,
                    sync_limit=500,
                    only_new=True,
                )
                inserted_total += int(inserted or 0)
                logger_sync_my_mails.info(
                    "time_to_sync_my_mails owner_id=%s mailbox=%s inserted=%s",
                    owner_id,
                    mailbox,
                    inserted,
                )
            except Exception as exc:
                logger_sync_my_mails.warning(
                    "time_to_sync_my_mails owner_id=%s mailbox=%s error=%s",
                    owner_id,
                    mailbox,
                    exc,
                )

        logger_sync_my_mails.info(
            "time_to_sync_my_mails finished targets=%s skipped=%s inserted_total=%s duration_s=%.2f",
            len(targets),
            len(skipped),
            inserted_total,
            (timezone.now() - started_at).total_seconds(),
        )
    except Exception:
        logger_sync_my_mails.exception("time_to_sync_my_mails failed")
    finally:
        close_old_connections()


# -------------------------------------备份数据
logger_backup = logging.getLogger("bpmatch.time_to_backup")
