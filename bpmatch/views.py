import json
from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from project.api import api_error, api_paginated, api_success
from project.common_tools import parse_json_body, require_login
from employee.models import UserLogin
from settings.models import SysSettings
from . import llmsTool
from .smtp_sender import SmtpMailSender
from .models import SentEmailLog, MailProjectInfo, MailTechnicianInfo


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
# 送信
def send_mail(request):
    login_id, error = require_login(request)
    if error:
        return error

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

    user_login = UserLogin.objects.filter(
        employee_id=login_id,
        deleted_at__isnull=True,
    ).first()
    if not user_login:
        return api_error("User login not found", status=404)

    send_settings = SysSettings.objects.filter(
        name="sendmsg",
        deleted_at__isnull=True,
    ).first()
    send_configs = send_settings.settings if send_settings else []
    if not isinstance(send_configs, list):
        send_configs = []
    target_users = {
        str(user_login.user_name or "").strip(),
        str(user_login.employee_name or "").strip(),
        str(login_id),
    }
    send_config = None
    for item in send_configs:
        if not isinstance(item, dict):
            continue
        item_user = str(item.get("user") or "").strip()
        if item_user and item_user in target_users:
            send_config = item
            break

    if not send_config:
        return api_error("No send config for current user")

    smtp_host = str(send_config.get("smtp") or "").strip()
    smtp_port_raw = str(send_config.get("port") or "").strip()
    smtp_user = str(send_config.get("email") or "").strip()
    smtp_password = str(send_config.get("password") or "")

    if not smtp_host or not smtp_port_raw or not smtp_user or not smtp_password:
        return api_error("Send config is incomplete")
    try:
        smtp_port = int(smtp_port_raw)
    except (TypeError, ValueError):
        return api_error("Invalid SMTP port")

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
        sender = SmtpMailSender(
            host=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_password,
        )
        message_id = sender.send_message(
            to=to_addr,
            cc=cc_addr or None,
            subject=subject,
            body=body,
            sender=smtp_user,
            attachments=normalized_atts,
            in_reply_to=payload.get("in_reply_to"),
            references=payload.get("references"),
            mail_type=mail_type,
            created_by=login_id,
        )
    except Exception as exc:
        return api_error(str(exc), status=500)

    payload = {"message_id": message_id}
    return api_success(data=payload)


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
