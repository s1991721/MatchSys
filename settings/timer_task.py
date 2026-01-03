import json
import logging
import os
from datetime import timezone, timedelta

from django.conf import settings as django_settings
from django.db import close_old_connections, transaction
from django.utils.dateparse import parse_datetime

from bpmatch import llmsTool
from bpmatch.gmailTool import GmailTool
from bpmatch.models import SavedMailInfo, MailTechnicianInfo, MailProjectInfo


def _ensure_time_to_save_logger(date_tag: str, logger: logging.Logger):
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


# -------------------------------------分析邮件
logger_save = logging.getLogger("bpmatch.time_to_save")

TIME_SAVE_DAYS = 14


def run_time_to_save():
    date_tag = timezone.now().strftime("%Y-%m-%d")
    _ensure_time_to_save_logger(date_tag)
    close_old_connections()
    started_at = timezone.now()
    logger_save.info("time_to_save started at %s", started_at.isoformat())
    try:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=TIME_SAVE_DAYS)
        gmail = GmailTool()

        page = 1
        page_size = 100
        mail_list = []

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

        logger_save.info(
            "time_to_save classified total=%s projects=%s technicians=%s",
            len(mail_list),
            len(project_list),
            len(technician_list),
        )

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

        for mail in project_list:
            with transaction.atomic():
                detail_json = llmsTool.qiuren_detail_analysis(mail.get("body") or "")
                country, skills, price = _parse_detail(detail_json)
                MailProjectInfo.objects.create(
                    id=mail.get("message_id_header"),
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
                    id=mail.get("message_id_header"),
                    date=mail.get("date"),
                )

        for mail in technician_list:
            with transaction.atomic():
                detail_json = llmsTool.qiuanjian_detail_analysis(mail.get("body") or "")
                country, skills, price = _parse_detail(detail_json)
                MailTechnicianInfo.objects.create(
                    id=mail.get("message_id_header"),
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
                    id=mail.get("message_id_header"),
                    date=mail.get("date"),
                )

        logger_save.info(
            "time_to_save finished total=%s projects=%s technicians=%s duration_s=%.2f",
            len(mail_list),
            len(project_list),
            len(technician_list),
            (timezone.now() - started_at).total_seconds(),
        )
    except Exception:
        logger_save.exception("time_to_save failed")
    finally:
        close_old_connections()


# -------------------------------------清理过期邮件
logger_clean = logging.getLogger("bpmatch.time_to_clean")


def run_time_to_clean():
    return


# -------------------------------------备份数据
logger_backup = logging.getLogger("bpmatch.time_to_backup")
