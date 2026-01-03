import json
import logging
import os
import threading
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from project.api import api_error, api_paginated, api_success
from project.common_tools import parse_json_body
from . import llmsTool
from .gmailTool import GmailTool
from .models import SentEmailLog, MailProjectInfo, MailTechnicianInfo, SavedMailInfo

TIME_SAVE_DAYS = 14


def _normalize_skills(value):
    if not value:
        return []
    if isinstance(value, list):
        raw_list = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                raw_list = parsed if isinstance(parsed, list) else [text]
            except Exception:
                raw_list = text.split(",")
        else:
            raw_list = text.split(",")
    else:
        raw_list = [value]

    cleaned = []
    for item in raw_list:
        if item is None:
            continue
        item_str = str(item).strip()
        if item_str:
            cleaned.append(item_str)
    return cleaned


@csrf_exempt
@require_GET
# 获取案件列表
def mail_projects_api(request):
    sender = request.GET.get("sender", "").strip()
    date_str = request.GET.get("date", "").strip()
    page_str = request.GET.get("page", "1").strip()
    page_size_str = request.GET.get("page_size", "50").strip()

    page = int(page_str)
    page_size = int(page_size_str)

    queryset = MailProjectInfo.objects.all()

    if sender:
        queryset = queryset.filter(address__icontains=sender)

    if date_str:
        target_date = parse_date(date_str)
        if target_date:
            queryset = queryset.filter(date__date=target_date)

    queryset = queryset.order_by("-date", "-id")

    total = queryset.count()
    total_pages = (total + page_size - 1) // page_size if total else 1
    start = (page - 1) * page_size
    end = start + page_size

    items = []
    for row in queryset[start:end]:
        items.append(
            {
                "id": row.id,
                "title": row.title or "(无标题)",
                "desc": row.address or "",
                "detail": row.body or "",
                "date": row.date.isoformat() if row.date else "",
            }
        )

    return api_paginated(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@csrf_exempt
@require_GET
# 获取案件匹配的技术者
def mail_project_match_api(request):
    project_id = (request.GET.get("id") or "").strip()

    if not project_id:
        return api_error("Missing field: id")

    try:
        project = MailProjectInfo.objects.get(id=project_id)
    except MailProjectInfo.DoesNotExist:
        return api_error("MailProjectInfo not found", status=404)

    project_skills = _normalize_skills(project.skills)
    project_skill_set = {skill.lower() for skill in project_skills}
    tech_queryset = MailTechnicianInfo.objects.filter(country=project.country)

    scored_items = []
    for tech in tech_queryset:
        tech_skills = _normalize_skills(tech.skills)
        matched = []
        seen = set()
        for skill in tech_skills:
            key = skill.lower()
            if key in project_skill_set and key not in seen:
                matched.append(skill)
                seen.add(key)
        score = len(matched)
        if score == 0:
            continue
        scored_items.append(
            (
                score,
                {
                    "id": tech.id,
                    "subject": tech.title or "",
                    "title": tech.title or "",
                    "name": tech.title or "",
                    "belong": tech.address or "",
                    "from": tech.address or "",
                    "detail": tech.body or "",
                    "body": tech.body or "",
                    "date": tech.date.isoformat() if tech.date else "",
                    "country": tech.country or "",
                    "skills": tech_skills,
                    "price": float(tech.price) if tech.price is not None else None,
                    "matched_skills": matched,
                    "match_score": score,
                },
            )
        )

    scored_items.sort(key=lambda item: item[0], reverse=True)
    matches = [item for _, item in scored_items]
    payload = {
        "project": {
            "id": project.id,
            "country": project.country or "",
            "skills": project_skills,
            "price": float(project.price) if project.price is not None else None,
        },
        "matches": matches
    }
    return api_success(data=payload)


@csrf_exempt
@require_POST
# 抽取案件信息，生成送信模板
def extract_project_detail(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    text = payload.get("body") or ""
    if not text.strip():
        return api_error("Missing field: body")

    try:
        llm_result = llmsTool.extract_qiuren_detail(text)
    except Exception as exc:
        return api_error(str(exc), status=500)

    try:
        parsed = json.loads(llm_result)
    except Exception as exc:
        print(f"[extract_qiuren_detail] 解析 LLM JSON 失败: {exc}")
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    def make_block(title: str, value) -> str:
        """
        生成一个「标题 + 内容 + 空行」的区块
        - value 为空 / None / 空列表 / 空字符串 → 返回空字符串
        - value 为 list → 自动换行拼接
        """
        if not value:
            return ""

        if isinstance(value, list):
            value = "\n".join(v for v in value if v)

        value = str(value).strip()
        if not value:
            return ""

        return f"{title}\n{value}\n\n"

    project_name = parsed.get("project_name")
    project_detail = parsed.get("project_detail")
    requirement = parsed.get("requirement", [])
    skills_must = parsed.get("skills_must", [])
    skills_can = parsed.get("skills_can", [])
    remark = parsed.get("remark")

    fields = {
        "project_block": make_block("【案件名】", project_name),
        "detail_block": make_block("【業務概要】", project_detail),
        "requirement_block": make_block("【条件】", requirement),
        "skills_must_block": make_block("【必須スキル】", skills_must),
        "skills_can_block": make_block("【尚可スキル】", skills_can),
        "remark_block": make_block("【備考】", remark),
    }

    # todo 根据需求更改模板
    template = (
        "いつもお世話になっております。\n"
        "株式会社の林でございます。\n"
        "\n"
        "技術者をご紹介いただきありがとうございます。\n"
        "弊社にて対応可能な案件をご紹介させて頂きます。\n"
        "ご検討頂けますと幸いです。\n"
        "\n"
        "**************************************\n"
        "{project_block}"
        "{detail_block}"
        "{requirement_block}"
        "{skills_must_block}"
        "{skills_can_block}"
        "{remark_block}"
        "**************************************\n"
        "\n"
        "今後とも何卒よろしくお願い申し上げます。\n"
        "＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝\n"
        "\n"
        "株式会社\n"
        "IT サポート\n"
        "〒141-2222\n"
        "東京都品川区東五反田\n"
        "五反田F\n"
        "営業共通:sales@.co.jp\n"
        "TEL: 03-6666-8888　FAX: 03-6666-8888\n"
        "Web: http://.co.jp\n"
        "労働者派遣事業許可番号：　派 13-311111\n"
        "有料職業紹介事業許可番号：　13-ユ-311111\n"
    )

    formatted_message = template.format(**fields)

    response_payload = {"data": formatted_message, "raw": llm_result}
    return api_success(data=response_payload)


@csrf_exempt
@require_POST
# 送信
def send_mail(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    to_addr = (payload.get("to") or "").strip()
    cc_addr = (payload.get("cc") or "").strip()
    subject = (payload.get("subject") or "送信页邮件").strip() or "送信页邮件"
    body = payload.get("body") or ""
    attachments = payload.get("attachments") or []
    raw_mail_type = payload.get("mail_type")
    mail_type = None
    if raw_mail_type not in (None, ""):
        try:
            mail_type = int(raw_mail_type)
        except (TypeError, ValueError):
            return api_error("Invalid field: mail_type")

    if not to_addr:
        return api_error("Missing field: to")
    if not body.strip():
        return api_error("Missing field: body")

    # 标准化附件结构
    normalized_atts = []
    for att in attachments:
        if not isinstance(att, dict):
            continue
        normalized_atts.append(
            {
                "filename": att.get("filename") or "attachment",
                "content_type": att.get("content_type") or "application/octet-stream",
                "content": att.get("content") or "",
            }
        )

    try:
        gmail = GmailTool()
        message_id = gmail.send_message(
            to=to_addr,
            cc=cc_addr or None,
            subject=subject,
            body=body,
            attachments=normalized_atts,
            mail_type=mail_type,
        )
    except FileNotFoundError as exc:
        message = f"OAuth credentials missing: {exc}"
        return api_error(message, status=500)
    except Exception as exc:
        return api_error(str(exc), status=500)

    payload = {"message_id": message_id}
    return api_success(data=payload)


@csrf_exempt
@require_GET
def send_history(request):
    login_id = request.session.get("employee_id")
    if not login_id:
        return api_error("employee id is required", status=401)

    mail_type = (request.GET.get("mail_type") or "").strip()
    keyword = (request.GET.get("keyword") or "").strip()
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        page_size = 10
    page = max(page, 1)
    page_size = max(min(page_size, 100), 1)

    queryset = SentEmailLog.objects.filter(created_by=login_id)
    if mail_type != "":
        try:
            mail_type_value = int(mail_type)
        except (TypeError, ValueError):
            return api_error("Invalid mail_type")
        queryset = queryset.filter(mail_type=mail_type_value)
    if keyword:
        queryset = queryset.filter(to__icontains=keyword)
    queryset = queryset.order_by("-sent_at")
    total = queryset.count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * page_size
    logs = queryset[offset: offset + page_size]
    items = []
    current_tz = timezone.get_current_timezone()

    for log in logs:
        try:
            attachments = json.loads(log.attachments or "[]")
        except Exception:
            attachments = []
        items.append(
            {
                "id": log.id,
                "message_id": log.message_id,
                "title": log.subject or "(无标题)",
                "to": log.to or "",
                "cc": log.cc or "",
                "mail_type": log.mail_type,
                "sent_at": timezone.localtime(log.sent_at, current_tz).isoformat(),
                "time": timezone.localtime(log.sent_at, current_tz).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "content": log.body or "",
                "attachments": attachments if isinstance(attachments, list) else [],
            }
        )

    return api_paginated(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


# -------------------------------------定时任务

@csrf_exempt
@require_POST
# 定时刷新数据库中的案件及技术者信息
def time_to_save(request):
    thread = threading.Thread(
        target=_run_time_to_save,
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
        target=_run_time_to_clean,
        name="time_to_clean",
        daemon=True,
    )
    thread.start()
    return api_success()


logger = logging.getLogger("bpmatch.time_to_save")


def _ensure_time_to_save_logger(date_tag: str):
    logs_dir = os.path.join(settings.BASE_DIR, "logs")
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


def _run_time_to_save():
    date_tag = timezone.now().strftime("%Y-%m-%d")
    _ensure_time_to_save_logger(date_tag)
    close_old_connections()
    started_at = timezone.now()
    logger.info("time_to_save started at %s", started_at.isoformat())
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
            logger.info("time_to_save fetched page=%s count=%s", page, len(messages))
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

        logger.info(
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

        logger.info(
            "time_to_save finished total=%s projects=%s technicians=%s duration_s=%.2f",
            len(mail_list),
            len(project_list),
            len(technician_list),
            (timezone.now() - started_at).total_seconds(),
        )
    except Exception:
        logger.exception("time_to_save failed")
    finally:
        close_old_connections()

def _run_time_to_clean():
    return
