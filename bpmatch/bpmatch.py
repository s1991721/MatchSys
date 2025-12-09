from datetime import datetime, timedelta
from typing import List, Dict

from gmailTool import GmailTool
from llmsTool import title_analysis

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
    qiuanjian_message = None

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=14)

    page = 1
    all_messages: List[Dict] = []

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
    update_time = end_date
    return all_messages


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


if __name__ == "__main__":
    emails = fetch_recent_two_weeks_emails()
