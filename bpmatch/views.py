import json
import re

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from . import bpmatch, llmsTool
from .gmailTool import GmailTool
from .models import SentEmailLog


@csrf_exempt
@require_GET
def messages(request):
    try:
        payload = bpmatch.fetch_page_emails(
            keyword=request.GET.get("keyword", ""),
            date_str=request.GET.get("date", ""),
            start_date_str=request.GET.get("start_date", ""),
            end_date_str=request.GET.get("end_date", ""),
            page_str=request.GET.get("page", "1"),
            page_size_str=request.GET.get("page_size", ""),
            limit_str=request.GET.get("limit", ""),
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(payload)


@csrf_exempt
@require_GET
def persons(request):
    refresh = request.GET.get("refresh", "").strip() == "1"
    try:
        if refresh:
            msgs = bpmatch.fetch_recent_two_weeks_emails()
        else:
            msgs = bpmatch.qiuanjian_message or []
        refreshed_at = bpmatch.update_time
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    items = []
    for m in msgs or []:
        items.append(
            {
                "id": m.get("id") or "",
                "name": m.get("subject") or "(无标题)",
                "belong": m.get("from") or "",
                "detail": m.get("body") or "",
                "date": m.get("date") or "",
                "thread_id": m.get("thread_id") or "",
                "message_id_header": m.get("message_id_header") or "",
                "references_header": m.get("references_header") or "",
            }
        )

    return JsonResponse(
        {
            "items": items,
            "update_time": refreshed_at.isoformat() if refreshed_at else "",
        }
    )


@csrf_exempt
def log_job_click(request):
    """
    Receive a job click event from the frontend and log the payload for debugging.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is allowed"}, status=405)

    try:
        raw_body = request.body.decode("utf-8") if request.body else "{}"
        payload = json.loads(raw_body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    print(f"[job_click] 收到求人点击: {json.dumps(payload, ensure_ascii=False)}")
    try:
        match_result = bpmatch.match(payload)
    except Exception as exc:
        print(f"[job_click] 调用 match 失败: {exc}")
        return JsonResponse({"error": str(exc)}, status=500)

    # 标准化匹配结果，方便前端直接渲染人员列表
    matches_raw = match_result.get("matches") if isinstance(match_result, dict) else []

    def _match_len(item):
        if isinstance(item, dict):
            skills = item.get("matched_skills")
            if isinstance(skills, list):
                return len(skills)
        return 0

    sorted_matches = sorted(matches_raw or [], key=_match_len, reverse=True)
    items = []
    for idx, match in enumerate(sorted_matches):
        matched_skills = match.get("matched_skills") if isinstance(match, dict) else []
        items.append(
            {
                "id": match.get("id") or f"match-{idx}",
                "name": match.get("subject") or match.get("title") or "(无标题)",
                "belong": match.get("from") or "",
                "detail": match.get("body") or match.get("detail") or "",
                "date": match.get("date") or "",
                "matched_skills": (
                    matched_skills if isinstance(matched_skills, list) else []
                ),
            }
        )

    return JsonResponse(
        {
            "status": "ok",
            "match": match_result,
            "matches": items,
        }
    )


@csrf_exempt
def extract_qiuren_detail(request):
    """
    对外暴露 extract_qiuren_detail，输入邮件正文文本，返回结构化信息。
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is allowed"}, status=405)

    try:
        raw_body = request.body.decode("utf-8") if request.body else "{}"
        payload = json.loads(raw_body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    text = payload.get("text") or payload.get("body") or ""
    if not text.strip():
        return JsonResponse({"error": "Missing field: text"}, status=400)

    try:
        llm_result = llmsTool.extract_qiuren_detail(text)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    # extract_qiuren_detail 返回的是 JSON 字符串，这里尝试解析以便前端直接使用
    try:
        parsed = json.loads(llm_result)
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    def _format_multiline_section(text_value: str) -> str:
        """
        Improve readability by inserting a line break after every Japanese comma 「、」.
        """
        if not isinstance(text_value, str):
            return ""
        normalized = text_value.replace("\r\n", "\n").strip()
        if not normalized:
            return ""

        normalized = re.sub(r"([：:])\s*\n+\s*", r"\1", normalized)
        normalized = normalized.replace("，", "、").replace(",", "、")
        normalized = re.sub(r"、\s*", "、\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    fields = {
        "project_name": parsed.get("project_name") or "",
        "project_detail": parsed.get("project_detail") or "",
        "requirement": parsed.get("requirement") or "",
        "skills_must": parsed.get("skills_must") or "",
        "skills_can": parsed.get("skills_can") or "",
        "remark": parsed.get("remark") or "",
    }

    for section_key in ("requirement", "remark"):
        fields[section_key] = _format_multiline_section(fields[section_key])

    # todo 根据需求更改模板
    template = (
        "いつもお世話になっております。\n"
        "株式会社の林でございます。\n"
        "\n"
        "\n"
        "技術者をご紹介いただきありがとうございます。\n"
        "弊社にて対応可能な案件をご紹介させて頂きます。\n"
        "ご検討頂けますと幸いです。\n"
        "\n"
        "\n"
        "**************************************\n"
        "【案件名】\n"
        "{project_name}\n"
        "\n"
        "【業務概要】\n"
        "{project_detail}\n"
        "\n"
        "【条件】\n"
        "{requirement}\n"
        "\n"
        "【必須スキル】\n"
        "{skills_must}\n"
        "\n"
        "【尚可スキル】\n"
        "{skills_can}\n"
        "\n"
        "【備考】\n"
        "{remark}\n"
        "\n"
        "**************************************\n"
        "\n"
        "\n"
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

    return JsonResponse(
        {
            "status": "ok",
            "data": formatted_message,
            "raw": llm_result,
        }
    )


@csrf_exempt
def send_mail(request):
    """
    发送邮件到指定收件人，支持抄送和附件（base64）。
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is allowed"}, status=405)

    try:
        raw_body = request.body.decode("utf-8") if request.body else "{}"
        payload = json.loads(raw_body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    to_addr = (payload.get("to") or "").strip()
    cc_addr = (payload.get("cc") or "").strip()
    subject = (payload.get("subject") or "送信页邮件").strip() or "送信页邮件"
    body = payload.get("body") or ""
    attachments = payload.get("attachments") or []
    thread_id = (payload.get("thread_id") or "").strip()
    in_reply_to = (payload.get("in_reply_to") or "").strip()
    references = (
        payload.get("references")
        or payload.get("references_header")
        or ""
    ).strip()

    if not to_addr:
        return JsonResponse({"error": "Missing field: to"}, status=400)
    if not body.strip():
        return JsonResponse({"error": "Missing field: body"}, status=400)

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
            thread_id=thread_id or None,
            in_reply_to=in_reply_to or None,
            references=references or None,
        )
    except FileNotFoundError as exc:
        return JsonResponse({"error": f"OAuth credentials missing: {exc}"}, status=500)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse({"status": "ok", "message_id": message_id})


@csrf_exempt
@require_GET
def send_history(request):
    """
    返回发送历史记录，数据来源 sent_email_logs。
    """
    logs = SentEmailLog.objects.order_by("-sent_at")[:300]
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
                "status": log.status or "sent",
                "sent_at": timezone.localtime(log.sent_at, current_tz).isoformat(),
                "time": timezone.localtime(log.sent_at, current_tz).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "content": log.body or "",
                "attachments": attachments if isinstance(attachments, list) else [],
            }
        )

    return JsonResponse({"items": items, "count": len(items)})
