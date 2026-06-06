import csv
import json
import threading
from datetime import timedelta
from io import StringIO
from urllib.parse import quote

from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from project.api import api_error, api_paginated, api_success
from project.common_tools import paginate_queryset, parse_json_body, require_login
from project.error_codes import ErrorCode
from settings.models import SysSettings
from . import llmsTool
from .gmailTool import GmailTool
from .mailTool import (
    MailToolError,
    send_bulk_mail_by_login,
    send_mail_by_login,
    ensure_send_config_for_login,
    list_my_mails_from_db,
    mark_my_mail_as_read,
    query_my_mails,
    count_unread_mails_from_db,
    sync_my_mails,
    get_my_mail_detail_from_db,
)
from .models import SentEmailLog, MailProjectInfo, MailTechnicianInfo, WrongMailInfo, MyMail, SavedMailInfo


def _mark_my_mail_as_read_async(login_id, mail_id):
    try:
        if str(mail_id or "").startswith("system:"):
            MyMail.objects.filter(
                owner_id=login_id,
                id=mail_id,
                is_unread=True,
            ).update(is_unread=False)
            return
        try:
            send_config = ensure_send_config_for_login(login_id)
        except MailToolError:
            send_config = None
        if send_config:
            mark_my_mail_as_read(send_config, mail_id, owner_id=login_id)
        else:
            MyMail.objects.filter(owner_id=login_id, id=mail_id, is_unread=True).update(is_unread=False)
    except Exception:
        pass


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


def _normalize_country(value):
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    text = str(value).strip()
    if text in ("0", "1"):
        return text
    if text in ("日本籍", "日本", "日本国籍"):
        return "0"
    if text in ("外国籍", "外国", "非日本"):
        return "1"
    return text


def _get_mail_template(template_name):
    record = SysSettings.objects.filter(name="mail-template", deleted_at__isnull=True).first()
    settings_payload = record.settings if record and isinstance(record.settings, dict) else {}
    template = settings_payload.get(template_name)
    if template is None:
        return ""
    template_str = str(template).strip()
    return template_str


def _load_attachment_items(value):
    if not value:
        return []
    if isinstance(value, list):
        raw_list = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except Exception:
            return []
        raw_list = parsed if isinstance(parsed, list) else []
    else:
        return []

    normalized = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or "").strip()
        attachment_id = str(item.get("attachment_id") or "").strip()
        message_id = str(item.get("message_id") or "").strip()
        if not filename or not attachment_id or not message_id:
            continue
        normalized.append(
            {
                "filename": filename,
                "mime_type": str(item.get("mime_type") or "application/octet-stream").strip()
                             or "application/octet-stream",
                "size": int(item.get("size") or 0),
                "part_id": str(item.get("part_id") or "").strip(),
                "attachment_id": attachment_id,
                "message_id": message_id,
                "inline": bool(item.get("inline")),
            }
        )
    return normalized


class _TemplateSafeDict(dict):
    def __missing__(self, key):
        return ""


@csrf_exempt
@require_GET
# 获取案件列表
def mail_projects_api(request):
    project_id = request.GET.get("id", "").strip()
    sender = request.GET.get("sender", "").strip()
    date_str = request.GET.get("date", "").strip()

    queryset = MailProjectInfo.objects.all()

    if project_id:
        queryset = queryset.filter(id=project_id)

    if sender:
        queryset = queryset.filter(address__icontains=sender)

    if date_str:
        target_date = parse_date(date_str)
        if target_date:
            queryset = queryset.filter(date__date=target_date)

    queryset = queryset.order_by("-date", "-id")

    paged, total, page, page_size, total_pages = paginate_queryset(
        queryset,
        request,
        default_page_size=50,
    )

    items = []
    for row in paged:
        items.append(
            {
                "id": row.id,
                "title": row.title or "(无标题)",
                "address": row.address or "",
                "cc": row.cc or "",
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
        return api_error(ErrorCode.MATCH_ID_REQUIRED)

    try:
        project = MailProjectInfo.objects.get(id=project_id)
    except MailProjectInfo.DoesNotExist:
        return api_error(ErrorCode.MATCH_PROJECT_INFO_NOT_FOUND)

    project_skills = _normalize_skills(project.skills)
    project_skill_set = {skill.lower() for skill in project_skills}
    tech_queryset = MailTechnicianInfo.objects.filter(country=project.country)

    scored_items = []
    for tech in tech_queryset:
        tech_skills = _normalize_skills(tech.skills)
        tech_files = _load_attachment_items(tech.files)
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
                    "address": tech.address or "",
                    "cc": tech.cc or "",
                    "body": tech.body or "",
                    "files": tech_files,
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


def _get_wrong_mail_source(mail_id, wrong_label):
    if wrong_label == 1:
        return MailTechnicianInfo.objects.filter(id=mail_id).first(), None
    if wrong_label == 0:
        return MailProjectInfo.objects.filter(id=mail_id).first(), None
    return None, api_error(ErrorCode.MATCH_WRONG_LABEL_INVALID)


def _build_wrong_mail_defaults(source_obj, wrong_label, wrong_type, correct_label=None):
    return {
        "title": source_obj.title,
        "address": source_obj.address,
        "body": source_obj.body,
        "files": source_obj.files,
        "date": source_obj.date,
        "remark": source_obj.remark,
        "country": source_obj.country,
        "skills": source_obj.skills,
        "price": source_obj.price,
        "wrong_type": wrong_type,
        "wrong_label": wrong_label,
        "correct_label": correct_label,
    }


# 提交被错误分类的邮件
@csrf_exempt
@require_POST
def wrong_mail_info_api(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    mail_id = str(payload.get("id") or "").strip()
    if not mail_id:
        return api_error(ErrorCode.MATCH_ID_REQUIRED)

    wrong_label = payload.get("wrong_label")
    if wrong_label is None:
        return api_error(ErrorCode.MATCH_WRONG_LABEL_REQUIRED)

    correct_label = payload.get("correct_label")

    source_obj, label_error = _get_wrong_mail_source(mail_id, wrong_label)
    if label_error:
        return label_error

    if source_obj is None:
        return api_error(ErrorCode.MATCH_MAIL_NOT_FOUND)

    defaults = _build_wrong_mail_defaults(
        source_obj,
        wrong_label=wrong_label,
        wrong_type=1,
        correct_label=correct_label,
    )

    with transaction.atomic():
        WrongMailInfo.objects.update_or_create(
            id=mail_id,
            defaults=defaults,
        )
        source_obj.delete()

    return api_success()


# 提交详情识别错误的邮件
@csrf_exempt
@require_POST
def wrong_mail_detail_api(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    mail_id = str(payload.get("id") or "").strip()
    if not mail_id:
        return api_error(ErrorCode.MATCH_ID_REQUIRED)

    wrong_label = payload.get("wrong_label")
    if wrong_label is None:
        return api_error(ErrorCode.MATCH_WRONG_LABEL_REQUIRED)

    wrong_type = payload.get("wrong_type")
    if wrong_type is None:
        return api_error(ErrorCode.MATCH_WRONG_TYPE_REQUIRED)
    if wrong_type not in (2, 3):
        return api_error(ErrorCode.MATCH_WRONG_TYPE_INVALID)

    source_obj, label_error = _get_wrong_mail_source(mail_id, wrong_label)
    if label_error:
        return label_error

    if source_obj is None:
        return api_error(ErrorCode.MATCH_MAIL_NOT_FOUND)

    defaults = _build_wrong_mail_defaults(
        source_obj,
        wrong_label=wrong_label,
        wrong_type=wrong_type,
        correct_label=None,
    )

    WrongMailInfo.objects.update_or_create(
        id=mail_id,
        defaults=defaults,
    )

    return api_success()


WRONG_MAIL_TYPE_LABELS = {
    1: "邮件分类错误",
    2: "国籍识别错误",
    3: "关键词识别错误",
}


@csrf_exempt
@require_GET
def wrong_mail_stats_api(request):
    queryset = WrongMailInfo.objects.filter(deleted_at__isnull=True)
    total = queryset.count()
    counts = {
        item["wrong_type"]: item["count"]
        for item in queryset.values("wrong_type").annotate(count=Count("id"))
    }
    by_wrong_type = [
        {
            "wrong_type": wrong_type,
            "label": label,
            "count": counts.get(wrong_type, 0),
        }
        for wrong_type, label in WRONG_MAIL_TYPE_LABELS.items()
    ]

    return api_success(
        {
            "total": total,
            "by_wrong_type": by_wrong_type,
        }
    )


@csrf_exempt
@require_GET
def wrong_mail_export_api(request):
    fields = [
        "id",
        "title",
        "address",
        "body",
        "files",
        "date",
        "remark",
        "country",
        "skills",
        "price",
        "wrong_type",
        "wrong_label",
        "correct_label",
    ]

    with transaction.atomic():
        rows = list(
            WrongMailInfo.objects.filter(deleted_at__isnull=True)
            .order_by("-date", "-id")
            .values(*fields)
        )
        row_ids = [row["id"] for row in rows]
        if row_ids:
            WrongMailInfo.objects.filter(id__in=row_ids, deleted_at__isnull=True).update(
                deleted_at=timezone.now()
            )

    buffer = StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(fields)
    for row in rows:
        writer.writerow(
            [
                row["id"] or "",
                row["title"] or "",
                row["address"] or "",
                row["body"] or "",
                row["files"] or "",
                row["date"].isoformat() if row["date"] else "",
                row["remark"] or "",
                row["country"] or "",
                row["skills"] or "",
                row["price"] if row["price"] is not None else "",
                row["wrong_type"] if row["wrong_type"] is not None else "",
                row["wrong_label"] if row["wrong_label"] is not None else "",
                row["correct_label"] if row["correct_label"] is not None else "",
            ]
        )

    timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    filename = f"wrong_mails_{timestamp}.csv"
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
    )
    return response


@csrf_exempt
@require_POST
# 根据技术者信息匹配案件
def mail_project_search_api(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    country = _normalize_country(payload.get("country"))
    sender = (payload.get("sender") or "").strip()
    date_range = (payload.get("date_range") or "all").strip().lower()
    intro = payload.get("intro") or ""

    parsed = {}
    if intro.strip():
        try:
            llm_result = llmsTool.qiuanjian_detail_analysis(intro)
        except Exception as exc:
            return api_error(ErrorCode.EXTERNAL_LLM, str(exc), status=500)
        try:
            parsed = json.loads(llm_result)
        except Exception as exc:
            print(f"[mail_project_search_api] 解析 LLM JSON 失败: {exc}")
            parsed = {}

    input_skills = _normalize_skills(parsed.get("skills") if isinstance(parsed, dict) else None)

    queryset = MailProjectInfo.objects.all()

    if country:
        queryset = queryset.filter(country=country)

    if sender:
        queryset = queryset.filter(address__icontains=sender)

    if date_range in ("today", "yesterday"):
        target_date = timezone.localdate()
        if date_range == "yesterday":
            target_date = target_date - timedelta(days=1)
        queryset = queryset.filter(date__date=target_date)

    queryset = queryset.order_by("-date", "-id")

    items = []
    scored_items = []
    for row in queryset:
        project_skills = _normalize_skills(row.skills)
        matched = []
        score = 0
        if input_skills:
            project_skill_set = {skill.lower() for skill in project_skills}
            seen = set()
            for skill in input_skills:
                key = skill.lower()
                if key in project_skill_set and key not in seen:
                    matched.append(skill)
                    seen.add(key)
            score = len(matched)
            if score == 0:
                continue

        item = {
            "id": row.id,
            "title": row.title or "(无标题)",
            "address": row.address or "",
            "cc": row.cc or "",
            "detail": row.body or "",
            "date": row.date.isoformat() if row.date else "",
            "country": row.country or "",
            "skills": project_skills,
            "matched_skills": matched,
            "match_score": score,
        }

        if input_skills:
            scored_items.append((score, item))
        else:
            items.append(item)

    if input_skills:
        scored_items.sort(key=lambda item: item[0], reverse=True)
        items = [item for _, item in scored_items]

    payload = {
        "items": items,
        "filters": {
            "country": country,
            "sender": sender,
            "date_range": date_range,
            "skills": input_skills,
        },
    }
    return api_success(data=payload)


@csrf_exempt
@require_POST
# 根据案件信息匹配技术者
def mail_technician_search_api(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    sender = (payload.get("sender") or "").strip()
    date_range = (payload.get("date_range") or "all").strip().lower()
    intro = payload.get("intro") or ""

    parsed = {}
    if intro.strip():
        try:
            llm_result = llmsTool.qiuren_detail_analysis(intro)
        except Exception as exc:
            return api_error(ErrorCode.EXTERNAL_LLM, str(exc), status=500)
        try:
            parsed = json.loads(llm_result)
        except Exception as exc:
            print(f"[mail_technician_search_api] 解析 LLM JSON 失败: {exc}")
            parsed = {}

    parsed_country = None
    if isinstance(parsed, dict):
        parsed_country = _normalize_country(parsed.get("country"))
    input_skills = _normalize_skills(parsed.get("skills") if isinstance(parsed, dict) else None)

    queryset = MailTechnicianInfo.objects.all()

    if parsed_country:
        queryset = queryset.filter(country=parsed_country)

    if sender:
        queryset = queryset.filter(address__icontains=sender)

    if date_range in ("today", "yesterday"):
        target_date = timezone.localdate()
        if date_range == "yesterday":
            target_date = target_date - timedelta(days=1)
        queryset = queryset.filter(date__date=target_date)

    queryset = queryset.order_by("-date", "-id")

    items = []
    scored_items = []
    for row in queryset:
        tech_skills = _normalize_skills(row.skills)
        matched = []
        score = 0
        if input_skills:
            tech_skill_set = {skill.lower() for skill in tech_skills}
            seen = set()
            for skill in input_skills:
                key = skill.lower()
                if key in tech_skill_set and key not in seen:
                    matched.append(skill)
                    seen.add(key)
            score = len(matched)
            if score == 0:
                continue

        item = {
            "id": row.id,
            "title": row.title or "(无标题)",
            "address": row.address or "",
            "cc": row.cc or "",
            "detail": row.body or "",
            "files": _load_attachment_items(row.files),
            "date": row.date.isoformat() if row.date else "",
            "country": row.country or "",
            "skills": tech_skills,
            "matched_skills": matched,
            "match_score": score,
        }

        if input_skills:
            scored_items.append((score, item))
        else:
            items.append(item)

    if input_skills:
        scored_items.sort(key=lambda item: item[0], reverse=True)
        items = [item for _, item in scored_items]

    payload = {
        "items": items,
        "filters": {
            "sender": sender,
            "date_range": date_range,
            "country": parsed_country or "",
            "skills": input_skills,
        },
    }
    return api_success(data=payload)


@csrf_exempt
@require_POST
# 抽取案件信息，生成送信模板
def extract_project_detail(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    fields = {
        "project_block": "",
        "detail_block": "",
        "requirement_block": "",
        "skills_must_block": "",
        "skills_can_block": "",
        "remark_block": "",
    }

    template = _get_mail_template("anjian")
    formatted_message = template.format_map(_TemplateSafeDict(fields))

    response_payload = {"body": formatted_message}
    return api_success(data=response_payload)


@csrf_exempt
@require_POST
# 抽取技术者信息，生成送信模板
def extract_technician_detail(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    body = payload.get("body") if isinstance(payload, dict) else {}

    fields = {
        "person_intro": body,
    }

    template = _get_mail_template("technician")
    formatted_message = template.format_map(_TemplateSafeDict(fields))
    response_payload = {"body": formatted_message}
    return api_success(data=response_payload)


@csrf_exempt
@require_POST
# 送信（接口入口在 views，SMTP 细节在 mailTool）
def send_mail(request):
    login_id, error = require_login(request)
    if error:
        return error
    payload, error = parse_json_body(request)
    if error:
        return error
    try:
        data = send_mail_by_login(login_id, payload)
        return api_success(data=data)
    except MailToolError as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, exc.message, status=exc.status)
    except Exception as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, str(exc), status=500)


@csrf_exempt
@require_POST
def send_bulk_mail(request):
    login_id, error = require_login(request)
    if error:
        return error
    payload, error = parse_json_body(request)
    if error:
        return error
    try:
        data = send_bulk_mail_by_login(login_id, payload)
        return api_success(data=data)
    except MailToolError as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, exc.message, status=exc.status)
    except Exception as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, str(exc), status=500)


@csrf_exempt
@require_GET
# 我的邮件列表
def my_mails_api(request):
    # 1. 检查是否登录
    login_id, error = require_login(request)
    if error:
        return error

    # 2. 检查当前登录用户是否配置了邮箱信息
    mailbox = ''
    try:
        send_config = ensure_send_config_for_login(login_id)
        mailbox = str(send_config.get("email") or "").strip()
    except MailToolError :
        print("没有邮箱配置")

    page = request.GET.get("page", 1)
    page_size = request.GET.get("page_size", 20)
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = 20
    page = max(1, page)
    page_size = max(1, min(page_size, 50))

    try:
        # 3. 默认从 DB 读取邮件列表
        data, meta = list_my_mails_from_db(
            login_id,
            page=page,
            page_size=page_size,
            mailbox_email=mailbox,
        )
        return api_success(data=data, meta=meta)
    except MailToolError as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, exc.message, status=exc.status)
    except Exception as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, str(exc), status=500)


@csrf_exempt
@require_GET
# 我的邮件查询（关键字、送信日期）
# 注意：
# 查询直接走 IMAP 服务器，不落本地 DB。
# pop3情况下，查询本地
def my_mails_query_api(request):
    login_id, error = require_login(request)
    if error:
        return error
    try:
        send_config = ensure_send_config_for_login(login_id)
    except MailToolError as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, exc.message, status=exc.status)

    page = request.GET.get("page", 1)
    page_size = request.GET.get("page_size", 20)
    keyword = request.GET.get("keyword", "")
    send_date = request.GET.get("send_date", "")
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = 20
    page = max(1, page)
    page_size = max(1, min(page_size, 50))

    try:
        data, meta = query_my_mails(
            send_config,
            owner_id=login_id,
            page=page,
            page_size=page_size,
            keyword=keyword,
            send_date=send_date,
        )
        return api_success(data=data, meta=meta)
    except MailToolError as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, exc.message, status=exc.status)
    except Exception as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, str(exc), status=500)


@csrf_exempt
@require_POST
# 我的邮件本地DB刷新，与邮件服务器一致
def my_mails_sync_api(request):
    login_id, error = require_login(request)
    if error:
        return error
    try:
        send_config = ensure_send_config_for_login(login_id)
        updated = sync_my_mails(login_id, send_config)
        return api_success(data={"updated": int(updated or 0)})
    except MailToolError as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, exc.message, status=exc.status)
    except Exception as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, str(exc), status=500)


@csrf_exempt
@require_GET
# 我的邮件详情（接口入口在 views，IMAP 细节在 mailTool）
def my_mail_detail_api(request, mail_id):
    login_id, error = require_login(request)
    if error:
        return error
    try:
        data = get_my_mail_detail_from_db(login_id, mail_id)
        if data and data.get("unread"):
            data["unread"] = False
            thread = threading.Thread(
                target=_mark_my_mail_as_read_async,
                args=(login_id, mail_id),
                name="mark_my_mail_as_read",
                daemon=True,
            )
            thread.start()
        return api_success(data=data)
    except MailToolError as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, exc.message, status=exc.status)
    except Exception as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, str(exc), status=500)


@csrf_exempt
@require_GET
def gmail_attachment_open_api(request, message_id, attachment_id):
    login_id, error = require_login(request)
    if error:
        return error

    message_id = str(message_id or "").strip()
    attachment_id = str(attachment_id or "").strip()
    if not message_id or not attachment_id:
        return api_error(ErrorCode.MATCH_ATTACHMENT_IDS_REQUIRED)

    exists = (
            SavedMailInfo.objects.filter(id=message_id).exists()
            or MailProjectInfo.objects.filter(id=message_id).exists()
            or MailTechnicianInfo.objects.filter(id=message_id).exists()
            or WrongMailInfo.objects.filter(id=message_id).exists()
            or MyMail.objects.filter(id=message_id, owner_id=login_id).exists()
    )
    if not exists:
        return api_error(ErrorCode.MATCH_ATTACHMENT_NOT_FOUND, status=404)

    attachment_meta = None
    for source in (
            MailProjectInfo.objects.filter(id=message_id).values_list("files", flat=True).first(),
            MailTechnicianInfo.objects.filter(id=message_id).values_list("files", flat=True).first(),
            WrongMailInfo.objects.filter(id=message_id).values_list("files", flat=True).first(),
            MyMail.objects.filter(id=message_id, owner_id=login_id).values_list("files", flat=True).first(),
    ):
        for item in _load_attachment_items(source):
            if item.get("attachment_id") == attachment_id:
                attachment_meta = item
                break
        if attachment_meta:
            break
    if not attachment_meta:
        return api_error(ErrorCode.MATCH_ATTACHMENT_NOT_FOUND, status=404)

    disposition = str(request.GET.get("disposition") or "attachment").strip().lower()
    if disposition not in ("attachment", "inline"):
        disposition = "attachment"
    try:
        content = GmailTool().fetch_attachment(message_id, attachment_id)
    except Exception as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, str(exc), status=502)

    filename = str(attachment_meta.get("filename") or "attachment").replace('"', "")
    content_type = str(
        attachment_meta.get("mime_type") or "application/octet-stream").strip() or "application/octet-stream"
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = (
        f"{disposition}; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
    )
    response["Content-Length"] = str(len(content))
    return response


@csrf_exempt
@require_GET
# 我的邮件未读数（首页铃铛使用 DB 缓存统计）
def my_mails_unread_count_api(request):
    login_id, error = require_login(request)
    if error:
        return error
    try:
        # 首页仅显示红点计数，若未配置邮箱则按 0 处理，避免顶部报错。
        ensure_send_config_for_login(login_id)
    except MailToolError:
        return api_success(data={"unread_count": 0, "has_mailbox": False})

    try:
        unread_count = count_unread_mails_from_db(login_id)
        return api_success(data={"unread_count": int(unread_count), "has_mailbox": True})
    except Exception as exc:
        return api_error(ErrorCode.EXTERNAL_GMAIL, str(exc), status=500)


@csrf_exempt
@require_GET
# 送信历史
def send_history(request):
    login_id, error = require_login(request)
    if error:
        return error

    mail_type = (request.GET.get("mail_type") or "").strip()
    keyword = (request.GET.get("keyword") or "").strip()

    queryset = SentEmailLog.objects.filter(created_by=login_id)
    if mail_type and mail_type.lower() != "all":
        try:
            if "," in mail_type:
                mail_type_values = [int(v.strip()) for v in mail_type.split(",") if v.strip() != ""]
                queryset = queryset.filter(mail_type__in=mail_type_values)
            else:
                mail_type_value = int(mail_type)
                queryset = queryset.filter(mail_type=mail_type_value)
        except (TypeError, ValueError):
            return api_error(ErrorCode.MATCH_MAIL_TYPE_INVALID)
    if keyword:
        queryset = queryset.filter(to__icontains=keyword)
    queryset = queryset.order_by("-sent_at")
    logs, total, page, page_size, total_pages = paginate_queryset(queryset, request)
    items = []
    current_tz = timezone.get_current_timezone()

    for log in logs:
        try:
            attachments = json.loads(log.attachments or "[]")
        except Exception:
            attachments = []
        items.append(
            {
                "id": log.message_id,
                "title": log.subject or "(无标题)",
                "to": log.to or "",
                "cc": log.cc or "",
                "mail_type": log.mail_type,
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
