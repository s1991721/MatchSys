import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

from . import bpmatch, llmsTool
from .gmailTool import GmailTool


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
                "name": match.get("subject")
                or match.get("title")
                or "(无标题)",
                "belong": match.get("from") or "",
                "detail": match.get("body") or match.get("detail") or "",
                "date": match.get("date") or "",
                "matched_skills": matched_skills if isinstance(matched_skills, list) else [],
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
        parsed = None

    return JsonResponse(
        {
            "status": "ok",
            "data": parsed,
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
        )
    except FileNotFoundError as exc:
        return JsonResponse({"error": f"OAuth credentials missing: {exc}"}, status=500)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse({"status": "ok", "message_id": message_id})
