import json
import re
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from project.api import api_error, api_paginated, api_success
from project.common_tools import parse_json_body, require_login
from . import llmsTool
from .mailTool import (
    MailToolError,
    send_mail_by_login,
    ensure_send_config_for_login,
    list_my_mails_from_db,
    query_my_mails_from_imap,
    count_unread_mails_from_db,
    sync_my_mails_from_imap,
    get_my_mail_detail_from_imap,
)
from .models import SentEmailLog, MailProjectInfo, MailTechnicianInfo, WrongMailInfo


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


def _read_payload_text(payload):
    if not isinstance(payload, dict):
        return ""
    text = payload.get("body")
    if not text:
        text = payload.get("text")
    return str(text or "")


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
                    "from": tech.address or "",
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


# 提交被错误分类的邮件
@csrf_exempt
@require_POST
def wrong_mail_info_api(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    mail_id = str(payload.get("id") or "").strip()
    if not mail_id:
        return api_error("Missing field: id")

    wrong_label = payload.get("wrong_label")
    if wrong_label is None:
        return api_error("Missing field: wrong_label")

    correct_label = payload.get("correct_label")

    if wrong_label == 1:
        source_obj = MailTechnicianInfo.objects.filter(id=mail_id).first()
    elif wrong_label == 0:
        source_obj = MailProjectInfo.objects.filter(id=mail_id).first()
    else:
        return api_error("Invalid field: wrong_label")

    if source_obj is None:
        return api_error("Mail not found", status=404)

    defaults = {
        "title": source_obj.title,
        "address": source_obj.address,
        "body": source_obj.body,
        "files": source_obj.files,
        "date": source_obj.date,
        "remark": source_obj.remark,
        "country": source_obj.country,
        "skills": source_obj.skills,
        "price": source_obj.price,
        "wrong_label": wrong_label,
        "correct_label": correct_label,
    }

    with transaction.atomic():
        WrongMailInfo.objects.update_or_create(
            id=mail_id,
            defaults=defaults,
        )
        source_obj.delete()

    return api_success()


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
            return api_error(str(exc), status=500)
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
            "desc": row.address or "",
            "detail": row.body or "",
            "date": row.date.isoformat() if row.date else "",
            "sender": row.address or "",
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
            return api_error(str(exc), status=500)
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
            "desc": row.address or "",
            "detail": row.body or "",
            "date": row.date.isoformat() if row.date else "",
            "sender": row.address or "",
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

    text = _read_payload_text(payload)
    if not text.strip():
        return api_error("Missing field: body")

    try:
        llm_result = llmsTool.extract_qiuren_detail(text)
    except Exception as exc:
        return api_error(str(exc), status=500)

    def _safe_parse_llm_json(raw_text: str) -> dict:
        """
        尝试解析 LLM 返回的 JSON。
        兜底策略：
        1) 直接 json.loads
        2) 提取首个 { ... } 片段再解析
        3) 失败则返回 {}
        """
        if not raw_text:
            return {}
        text = str(raw_text).strip()
        if not text:
            return {}
        try:
            parsed_obj = json.loads(text)
            return parsed_obj if isinstance(parsed_obj, dict) else {}
        except Exception:
            pass

        # 尝试从文本中提取第一个 JSON 对象
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            try:
                parsed_obj = json.loads(match.group(0))
                return parsed_obj if isinstance(parsed_obj, dict) else {}
            except Exception:
                return {}
        return {}

    parsed = _safe_parse_llm_json(llm_result)
    if not parsed:
        print("[extract_qiuren_detail] 解析 LLM JSON 失败或为空")

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
# 抽取技术者信息，生成送信模板
def extract_technician_detail(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    text = _read_payload_text(payload)
    if not text.strip():
        return api_error("Missing field: body")

    try:
        llm_result = llmsTool.qiuanjian_detail_analysis(text)
    except Exception as exc:
        return api_error(str(exc), status=500)

    try:
        parsed = json.loads(llm_result)
    except Exception as exc:
        print(f"[extract_technician_detail] 解析 LLM JSON 失败: {exc}")
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    def make_block(title: str, value) -> str:
        if value in (None, "", [], 0):
            return ""
        if isinstance(value, list):
            value = "\n".join(v for v in value if v)
        value = str(value).strip()
        if not value:
            return ""
        return f"{title}\n{value}\n\n"

    country_value = parsed.get("country")
    country_label = ""
    if country_value == 0 or str(country_value) == "0":
        country_label = "日本籍"
    elif country_value == 1 or str(country_value) == "1":
        country_label = "外国籍"

    skills = parsed.get("skills", [])
    price = parsed.get("price", 0)

    fields = {
        "country_block": make_block("【国籍】", country_label),
        "skills_block": make_block("【スキル】", skills),
        "price_block": make_block("【希望単価】", price),
    }

    # todo 根据需求更改模板
    template = (
        "いつもお世話になっております。\n"
        "株式会社の林でございます。\n"
        "\n"
        "技術者をご紹介させて頂きます。\n"
        "ご検討頂けますと幸いです。\n"
        "\n"
        "**************************************\n"
        "{country_block}"
        "{skills_block}"
        "{price_block}"
        "**************************************\n"
        "\n"
        "今後とも何卒よろしくお願い申し上げます。\n"
    )

    formatted_message = template.format(**fields)
    response_payload = {"data": formatted_message, "raw": llm_result}
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
        return api_error(exc.message, status=exc.status)
    except Exception as exc:
        return api_error(str(exc), status=500)


@csrf_exempt
@require_GET
# 我的邮件列表（接口入口在 views，邮件协议细节在 mailTool）
def my_mails_api(request):
    # 1. 检查是否登录
    login_id, error = require_login(request)
    if error:
        return error

    # 2. 检查当前登录用户是否配置了邮箱信息
    try:
        send_config = ensure_send_config_for_login(login_id)
    except MailToolError as exc:
        return api_error(exc.message, status=exc.status)

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
            mailbox_email=str(send_config.get("email") or "").strip(),
        )
        return api_success(data=data, meta=meta)
    except MailToolError as exc:
        return api_error(exc.message, status=exc.status)
    except Exception as exc:
        return api_error(str(exc), status=500)


@csrf_exempt
@require_GET
# 我的邮件查询（关键字、送信日期）
# 注意：查询直接走 IMAP 服务器，不落本地 DB。
def my_mails_query_api(request):
    login_id, error = require_login(request)
    if error:
        return error
    try:
        send_config = ensure_send_config_for_login(login_id)
    except MailToolError as exc:
        return api_error(exc.message, status=exc.status)

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
        data, meta = query_my_mails_from_imap(
            send_config,
            page=page,
            page_size=page_size,
            keyword=keyword,
            send_date=send_date,
        )
        return api_success(data=data, meta=meta)
    except MailToolError as exc:
        return api_error(exc.message, status=exc.status)
    except Exception as exc:
        return api_error(str(exc), status=500)


@csrf_exempt
@require_POST
# 我的邮件刷新同步（单独接口）
def my_mails_sync_api(request):
    login_id, error = require_login(request)
    if error:
        return error
    try:
        send_config = ensure_send_config_for_login(login_id)
        updated = sync_my_mails_from_imap(login_id, send_config)
        return api_success(data={"updated": int(updated or 0)})
    except MailToolError as exc:
        return api_error(exc.message, status=exc.status)
    except Exception as exc:
        return api_error(str(exc), status=500)


@csrf_exempt
@require_GET
# 我的邮件详情（接口入口在 views，IMAP 细节在 mailTool）
def my_mail_detail_api(request, mail_id):
    login_id, error = require_login(request)
    if error:
        return error
    try:
        # 5. 用户点击邮件列表时，按外部唯一标识从 IMAP 获取详情
        send_config = ensure_send_config_for_login(login_id)
        data = get_my_mail_detail_from_imap(send_config, mail_id)
        return api_success(data=data)
    except MailToolError as exc:
        return api_error(exc.message, status=exc.status)
    except Exception as exc:
        return api_error(str(exc), status=500)


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
        return api_error(str(exc), status=500)


@csrf_exempt
@require_GET
# 送信历史
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
    if mail_type and mail_type.lower() != "all":
        try:
            if "," in mail_type:
                mail_type_values = [int(v.strip()) for v in mail_type.split(",") if v.strip() != ""]
                queryset = queryset.filter(mail_type__in=mail_type_values)
            else:
                mail_type_value = int(mail_type)
                queryset = queryset.filter(mail_type=mail_type_value)
        except (TypeError, ValueError):
            return api_error("Invalid mail_type")
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
