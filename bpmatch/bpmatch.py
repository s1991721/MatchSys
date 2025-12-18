import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

from .gmailTool import GmailTool
from .llmsTool import (
    title_analysis,
    qiuren_detail_analysis,
    qiuanjian_detail_analysis,
)

# Reuse one Gmail client to avoid repeating OAuth flows.
gmail_tool = GmailTool()

qiuanjian_message = None
qiuanjian_jponly_message = None
qiuanjian_other_message = None
update_time = None


def fetch_recent_two_weeks_emails(
    query: str = "",
    mark_seen: bool = False,
    page_size: int = 100,
) -> List[Dict]:
    """
    Fetch all emails from the past two weeks (inclusive), using the current time as the end point.
    """
    global qiuanjian_message, qiuanjian_jponly_message, qiuanjian_other_message, update_time
    qiuanjian_message = None
    qiuanjian_jponly_message = None
    qiuanjian_other_message = None
    update_time = None
    end_date = datetime.now().date()
    # todo 正式生产环境改回14
    start_date = end_date - timedelta(days=30)

    page = 1
    all_messages: List[Dict] = []

    # todo 记得正式生产环境改回true
    while page < 2:
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
    return qiuanjian_jponly_message


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


def _normalize_skills(skills_raw) -> List[str]:
    """
    Normalize skills into lowercased unique list.
    """
    if not isinstance(skills_raw, (list, tuple, set)):
        return []
    dedup = []
    seen = set()
    for skill in skills_raw:
        skill_str = str(skill).strip().lower()
        if skill_str and skill_str not in seen:
            dedup.append(skill_str)
            seen.add(skill_str)
    return dedup


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
    global qiuanjian_jponly_message, qiuanjian_other_message
    classified: List[Dict] = []
    for email in emails:
        subject = email.get("subject") or ""
        label_raw = title_analysis(subject)
        try:
            label = int(str(label_raw).strip())
        except Exception:
            label = -1

        if label == 1:  # 仅保留「求案件」类型
            detail_text = _normalize_str(email.get("body") or email.get("detail") or "")
            analysis_json: Any
            try:
                analysis_raw = (
                    qiuanjian_detail_analysis(detail_text) if detail_text else ""
                )
                try:
                    analysis_json = json.loads(analysis_raw) if analysis_raw else {}
                except Exception:
                    analysis_json = {"raw": analysis_raw}
            except Exception as exc:
                print(f"[qiuanjian_email_filter] 解析求案件正文失败: {exc}")
                analysis_json = {"error": str(exc)}

            extra_fields: Dict[str, Any]
            if isinstance(analysis_json, dict):
                extra_fields = analysis_json
            else:
                extra_fields = {"analysis_raw": analysis_json}

            to_add = {**email, "type": label, **extra_fields}
            try:
                print(
                    "[qiuanjian_email_filter] 即将添加:",
                    json.dumps(to_add, ensure_ascii=False),
                )
            except Exception as exc:
                print(f"[qiuanjian_email_filter] 打印对象失败: {exc}")

            country_str = str(to_add.get("country_code", "1")).strip()
            if country_str == "0":
                if qiuanjian_jponly_message is None:
                    qiuanjian_jponly_message = []
                qiuanjian_jponly_message.append(to_add)
            if country_str == "1":
                if qiuanjian_other_message is None:
                    qiuanjian_other_message = []
                qiuanjian_other_message.append(to_add)

            classified.append(to_add)
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
    Analyze a 求人邮件正文，返回分析结果、国籍分支及匹配到的求案件列表。
    """
    detail = _normalize_str(job_payload.get("detail") or job_payload.get("body") or "")
    if not detail:
        print("[match] 求人正文为空，无法分析")
        return {"analysis": "", "error": "empty detail"}

    # 1) 调用 LLM 做正文分析
    try:
        analysis = qiuren_detail_analysis(detail)
        print(f"[match] 求人分析结果: {analysis}")
    except Exception as exc:
        print(f"[match] 求人分析异常: {exc}")
        return {"analysis": "", "error": str(exc)}

    # 2) 解析分析结果
    country = 1
    matches: List[Dict[str, Any]] = []
    skills_from_analysis: List[str] = []
    try:
        analysis_json = json.loads(analysis)
        if isinstance(analysis_json, dict):
            try:
                country = int(str(analysis_json.get("country", 1)).strip())
            except Exception:
                country = 1

            skills_from_analysis = _normalize_skills(analysis_json.get("skills", []))

            if country == 0:
                print("[match] 国籍=0，走日本籍分支")
            elif country == 1:
                print("[match] 国籍=1，走非日本籍分支")
    except Exception as exc:
        print(f"[match] 解析 analysis JSON 失败: {exc}")

    # 3) 国籍为日本籍时，按技能匹配求案件列表
    if skills_from_analysis:
        if country == 0:
            source_messages = qiuanjian_jponly_message or []
        if country == 1:
            source_messages = qiuanjian_other_message or []

        skills_set = set(skills_from_analysis)
        for message in source_messages:
            message_skills = set(_normalize_skills(message.get("skills", [])))
            overlap = skills_set & message_skills
            if overlap:
                matches.append({**message, "matched_skills": sorted(overlap)})

    print(f"analysis: {analysis}, country: {country}, matches: {matches}")
    return {
        "analysis": analysis,
        "country": country,
        "matches": matches,
        "job_skills": skills_from_analysis,
    }


if __name__ == "__main__":
    emails = fetch_recent_two_weeks_emails()
