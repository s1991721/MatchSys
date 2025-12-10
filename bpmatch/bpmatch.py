from datetime import datetime, timedelta
from typing import List, Dict, Any

from .gmailTool import GmailTool
from .llmsTool import title_analysis, qiuren_detail_analysis

# Reuse one Gmail client to avoid repeating OAuth flows.
gmail_tool = GmailTool()

qiuanjian_message = None
update_time = None


def fetch_recent_two_weeks_emails(
    query: str = "",
    mark_seen: bool = False,
    page_size: int = 20,
) -> List[Dict]:
    """
    Fetch all emails from the past two weeks (inclusive), using the current time as the end point.
    """
    global qiuanjian_message, update_time
    qiuanjian_message = None
    update_time = None
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=14)

    page = 1
    all_messages: List[Dict] = []

    # todo 记得正式生产环境改回true
    while page < 5:
        messages, has_next = gmail_tool.fetch_messages(
            query=query,
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date,
            mark_seen=mark_seen,
        )
        all_messages.extend(qiuanjian_email_filter(messages))

        if not has_next:
            break
        page += 1

    qiuanjian_message = all_messages
    update_time = datetime.now()
    return all_messages


def _parse_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


def _normalize_str(value, default: str = "") -> str:
    """
    Ensure incoming values (possibly None/int) are converted to stripped strings.
    """
    if value is None:
        return default
    try:
        return str(value).strip()
    except Exception:
        return default


def fetch_page_emails(
    keyword: str = "",
    date_str: str = "",
    start_date_str: str = "",
    end_date_str: str = "",
    page_str: str = "1",
    page_size_str: str = "",
    limit_str: str = "",
) -> Dict:
    """
    Fetch a single page of emails with optional keyword/date filters.
    """

    keyword = _normalize_str(keyword)
    date_str = _normalize_str(date_str)
    start_date_str = _normalize_str(start_date_str)
    end_date_str = _normalize_str(end_date_str)
    page_str = _normalize_str(page_str, "1")
    page_size_str = _normalize_str(page_size_str)
    limit_str = _normalize_str(limit_str)

    try:
        parsed_page = int(page_str)
        page = parsed_page if parsed_page > 0 else 1
    except ValueError:
        page = 1

    try:
        parsed_size = int(page_size_str or limit_str or 20)
        page_size = min(max(parsed_size, 1), 100)
    except ValueError:
        page_size = 20

    # 单日优先（保持原有 date 参数兼容）；否则使用 start/end 区间。
    if date_str:
        start_date = end_date = _parse_date(date_str)
    else:
        start_date = _parse_date(start_date_str)
        end_date = _parse_date(end_date_str)

    query = keyword or ""

    messages, has_next = gmail_tool.fetch_messages(
        query=query,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
    )

    items = []
    for m in messages:
        if qiuren_email_filter(m.get("subject")):
            items.append(
                {
                    "id": m.get("id") or "",
                    "title": m.get("subject") or "(无标题)",
                    "desc": m.get("from") or "",
                    "detail": m.get("body") or "",
                    "date": m.get("date") or "",
                    "type": "0",
                }
            )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
    }


def qiuanjian_email_filter(emails: List[Dict]) -> List[Dict]:
    """
    Classify emails by title using llmsTool.title_analysis and return enriched copies.
    """
    classified: List[Dict] = []
    for email in emails:
        subject = email.get("subject") or ""
        label_raw = title_analysis(subject)
        try:
            label = int(str(label_raw).strip())
        except Exception:
            label = -1

        if label == 1:  # 仅保留「求案件」类型
            classified.append({**email, "type": label})
    return classified


def qiuren_email_filter(title: str) -> bool:
    label_raw = title_analysis(title)
    try:
        label = int(str(label_raw).strip())
    except Exception:
        label = -1

    if label == 0:  # 仅保留「求人」类型
        return True
    return False


def match(job_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a 求人邮件正文并打印结果。
    """
    detail = _normalize_str(
        job_payload.get("detail") or job_payload.get("body") or ""
    )
    if not detail:
        print("[match] 求人正文为空，无法分析")
        return {"analysis": "", "error": "empty detail"}

    try:
        analysis = qiuren_detail_analysis(detail)
        print(f"[match] 求人分析结果: {analysis}")
        return {"analysis": analysis}
    except Exception as exc:
        print(f"[match] 求人分析异常: {exc}")
        return {"analysis": "", "error": str(exc)}


if __name__ == "__main__":
    emails = fetch_recent_two_weeks_emails()
