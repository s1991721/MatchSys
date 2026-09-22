import logging
import threading
import uuid
from copy import deepcopy
from datetime import timezone as datetime_timezone

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from settings.LINE import get_line_notify_filter, send_project_notify_group_text


logger_save = logging.getLogger("bpmatch.time_to_save")

# LINE 单个文本消息上限为 5000 字符。预留空间给剩余数量提示。
LINE_REPLY_TEXT_SOFT_LIMIT = 4500
LINE_REPLY_MAX_MESSAGES = 5

_LATEST_PROJECT_BATCH_LOCK = threading.Lock()
_LATEST_PROJECT_BATCH = {
    "version": uuid.uuid4().hex,
    "task_name": "",
    "completed_at": "",
    "projects": [],
    "claim_id": "",
}


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


# 时间改为日本时区
def _format_mail_date_jst(value):
    raw = str(value or "").strip()
    if not raw:
        return "-"
    parsed = parse_datetime(raw)
    if not parsed:
        return raw
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    return timezone.localtime(parsed).strftime("%Y-%m-%d %H:%M:%S JST")


# 1:外国籍可  0：仅日籍
def _format_country_label(value):
    raw = str(value or "").strip()
    if raw == "1":
        return "外国籍可"
    if raw == "0":
        return "仅日籍"
    return raw or "-"


# LINE 送信前过滤
# 按国籍与技能判断案件是否进入最近批次
def _project_matches_filter(project: dict, line_filter: dict) -> bool:
    try:
        project_country = int(project.get("country"))
        nationality_filter = int(line_filter.get("nationality", -1))
    except (TypeError, ValueError):
        return False
    if project_country != nationality_filter:
        return False
    return _skills_match_line_filter(
        project.get("skills") or "",
        line_filter.get("skills", []),
    )


# 构建LINE送信内容
# 构建单个案件的 LINE 详情内容
def _build_project_detail(project: dict, index: int) -> str:
    # todo 做成案件描述通知、附上链接，单击链接进入系统案件详情页
    mail = project.get("mail") if isinstance(project.get("mail"), dict) else {}
    title = str(mail.get("subject") or "").strip() or "（无标题）"
    sender = str(mail.get("from") or "").strip() or "（未知发件人）"
    mail_date = _format_mail_date_jst(mail.get("date"))
    country = _format_country_label(project.get("country"))
    skills = str(project.get("skills") or "").strip() or "-"
    price = project.get("price")
    price_text = "-"
    if price is not None:
        try:
            price_text = f"{float(price):,.0f}"
        except Exception:
            price_text = str(price)

    return (
        f"【案件 {index}】\n"
        f"标题: {title}\n"
        f"发件人: {sender}\n"
        f"邮件时间: {mail_date}\n"
        f"国家: {country}\n"
        f"技能: {skills}\n"
        f"单价: {price_text}"
    )


# 在单次 Reply API 的 5 个消息对象限制内追加案件详情
def _try_append_project(messages: list[str], block: str) -> list[str] | None:
    candidate = list(messages)
    remaining = block
    while remaining:
        if not candidate:
            candidate.append("")
        separator = "\n\n──────────\n\n" if candidate[-1] else ""
        capacity = LINE_REPLY_TEXT_SOFT_LIMIT - len(candidate[-1]) - len(separator)
        if capacity <= 0:
            if len(candidate) >= LINE_REPLY_MAX_MESSAGES:
                return None
            candidate.append("")
            continue
        chunk = remaining[:capacity]
        candidate[-1] = f"{candidate[-1]}{separator}{chunk}"
        remaining = remaining[len(chunk):]
        if remaining:
            if len(candidate) >= LINE_REPLY_MAX_MESSAGES:
                return None
            candidate.append("")
    return candidate


# 将最近批次组装为 LINE Reply API 的消息对象
def _build_reply_messages(projects: list[dict]) -> tuple[list[dict], int]:
    texts = [f"最近一次邮件任务共入库 {len(projects)} 个待查看案件。"]
    included = 0
    for index, project in enumerate(projects, start=1):
        candidate = _try_append_project(texts, _build_project_detail(project, index))
        if candidate is None:
            break
        texts = candidate
        included += 1

    remaining = len(projects) - included
    if remaining:
        texts[-1] += f"\n\n尚余 {remaining} 个案件，请再次 @Bot 并发送“查看案件”。"
    return ([{"type": "text", "text": text} for text in texts], included)


# 邮件任务完成后覆盖最近批次，并发送一条群组提醒
def replace_latest_project_batch(task_name: str, projects: list[dict]) -> int:
    """以最近一次邮件任务的结果覆盖内存批次，并只发送一条群组提醒。"""
    line_filter = get_line_notify_filter()
    matched_projects = [
        deepcopy(project)
        for project in projects
        if isinstance(project, dict) and _project_matches_filter(project, line_filter)
    ]

    with _LATEST_PROJECT_BATCH_LOCK:
        _LATEST_PROJECT_BATCH.update(
            {
                "version": uuid.uuid4().hex,
                "task_name": str(task_name or ""),
                "completed_at": timezone.now().isoformat(),
                "projects": matched_projects,
                "claim_id": "",
            }
        )

    if not matched_projects:
        return 0

    try:
        send_project_notify_group_text(
            f"有案件入库，共 {len(matched_projects)} 件。\n"
            "请 @Bot 并发送“查看案件”获取详情。"
        )
        logger_save.info(
            "%s line project batch announced projects=%s",
            task_name,
            len(matched_projects),
        )
    except Exception as exc:
        # 提醒失败不丢弃批次，群成员仍可主动查询。
        logger_save.warning(
            "%s line project batch announce failed projects=%s error=%s",
            task_name,
            len(matched_projects),
            str(exc),
        )
    return len(matched_projects)


# 查询时占用当前批次，防止并发重复发送
def claim_latest_project_batch() -> dict:
    """占用可回复的数据，防止并发查询重复发送。"""
    with _LATEST_PROJECT_BATCH_LOCK:
        if _LATEST_PROJECT_BATCH.get("claim_id"):
            return {"status": "busy", "messages": [], "project_count": 0}
        projects = _LATEST_PROJECT_BATCH.get("projects") or []
        if not projects:
            return {"status": "empty", "messages": [], "project_count": 0}
        messages, project_count = _build_reply_messages(projects)
        if not project_count:
            return {"status": "empty", "messages": [], "project_count": 0}
        claim_id = uuid.uuid4().hex
        _LATEST_PROJECT_BATCH["claim_id"] = claim_id
        return {
            "status": "ready",
            "claim_id": claim_id,
            "version": _LATEST_PROJECT_BATCH["version"],
            "messages": messages,
            "project_count": project_count,
            "remaining_count": len(projects) - project_count,
        }


# 回复成功后移除已经发送的案件
def complete_latest_project_batch_claim(claim: dict) -> None:
    """回复成功后，仅移除本次确实回复的案件。"""
    with _LATEST_PROJECT_BATCH_LOCK:
        if (
            _LATEST_PROJECT_BATCH.get("version") != claim.get("version")
            or _LATEST_PROJECT_BATCH.get("claim_id") != claim.get("claim_id")
        ):
            return
        count = max(int(claim.get("project_count") or 0), 0)
        _LATEST_PROJECT_BATCH["projects"] = (
            _LATEST_PROJECT_BATCH.get("projects") or []
        )[count:]
        _LATEST_PROJECT_BATCH["claim_id"] = ""


# 回复失败时解除占用并保留案件
def release_latest_project_batch_claim(claim: dict) -> None:
    """回复失败时解除占用，保留全部待查看案件。"""
    with _LATEST_PROJECT_BATCH_LOCK:
        if (
            _LATEST_PROJECT_BATCH.get("version") == claim.get("version")
            and _LATEST_PROJECT_BATCH.get("claim_id") == claim.get("claim_id")
        ):
            _LATEST_PROJECT_BATCH["claim_id"] = ""
