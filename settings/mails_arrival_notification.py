import logging

from settings.LINE import get_line_notify_filter, send_line_text


# 同意skills格式
def _normalize_line_notify_skill_list(value):
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


# LINE 送信过滤技能关键词
def _skills_match_line_filter(project_skills: str, configured_skills: list[str]) -> bool:
    if not configured_skills:
        return True
    project_skill_items = _normalize_line_notify_skill_list(project_skills)
    if not project_skill_items:
        return False
    project_text = " ".join(project_skill_items).lower()
    for keyword in configured_skills:
        normalized = str(keyword).strip().lower()
        if normalized and normalized in project_text:
            return True
    return False


# 构建LINE送信内容
def _build_project_ingest_line_message(mail: dict, country: str, skills: str, price):
    # todo 做成案件描述通知、附上链接，单击链接进入系统案件详情页
    title = str(mail.get("subject") or "").strip()
    sender = str(mail.get("from") or "").strip()
    mail_date = str(mail.get("date") or "").strip()

    title = title if title else "（无标题）"
    sender = sender if sender else "（未知发件人）"
    country = country if str(country or "").strip() else "-"
    skills = skills if str(skills or "").strip() else "-"
    price_text = "-"
    if price is not None:
        try:
            price_text = f"{float(price):,.0f}"
        except Exception:
            price_text = str(price)

    return (
        "【Project邮件入库通知】\n"
        f"标题: {title}\n"
        f"发件人: {sender}\n"
        f"邮件时间: {mail_date or '-'}\n"
        f"国家: {country}\n"
        f"技能: {skills}\n"
        f"单价: {price_text}"
    )

logger_save = logging.getLogger("bpmatch.time_to_save")

# LINE 送信前过滤
def notify_project_ingested(mail: dict, country: str, skills: str, price):
    line_filter = get_line_notify_filter()
    nationality_filter = int(line_filter.get("nationality", -1))
    skill_filters = line_filter.get("skills", [])

    if int(country) != nationality_filter:
        return
    if not _skills_match_line_filter(skills, skill_filters):
        return

    message = _build_project_ingest_line_message(mail, country, skills, price)
    try:
        send_line_text(message)
        logger_save.info(
            "time_to_save line notify matched by filter message_id=%s filter=%s",
            mail.get("message_id_header"),
            nationality_filter,
        )
    except Exception as exc:
        logger_save.warning(
            "time_to_save line notify failed message_id=%s error=%s",
            mail.get("message_id_header"),
            str(exc),
        )
