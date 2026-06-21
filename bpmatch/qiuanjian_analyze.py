import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from bpmatch.qiuren_analyze import _normalize_skills

KEYWORDS = [
    "国籍", "日本国籍", "日本人", "日本籍",
]

# 价格标签保持严格，避免把年龄、日期、精算时间和电话号码当作价格。
_PRICE_LABEL_RE = re.compile(
    r"(?:希\s*望\s*)?(?:単\s*価|単\s*金)|希\s*望\s*額|月\s*額",
    re.IGNORECASE,
)
_AMOUNT = r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
_UNIT = r"(?:万\s*円?|円)"
_RANGE_SEPARATOR = r"(?:~|-|ー|–|—|から)"
_PRICE_RE = re.compile(
    rf"(?P<prefix>{_RANGE_SEPARATOR})?\s*"
    rf"(?P<first>{_AMOUNT})\s*(?P<first_unit>{_UNIT})?\s*"
    rf"(?:"
    rf"(?P<separator>{_RANGE_SEPARATOR})\s*"
    rf"(?P<second>{_AMOUNT})?\s*(?P<second_unit>{_UNIT})?"
    rf"|(?P<suffix>以上|以下|前後|程度|くらい|位)"
    rf")?",
    re.IGNORECASE,
)
_UNKNOWN_PRICE_RE = re.compile(
    r"応\s*相\s*談|未\s*定|相\s*談\s*可|ス\s*キ\s*ル\s*見\s*合(?:い)?",
    re.IGNORECASE,
)


def _to_yen(raw_amount, unit):
    try:
        amount = Decimal(raw_amount.replace(",", ""))
    except (AttributeError, InvalidOperation):
        return None

    if re.sub(r"\s+", "", unit or "").startswith("万"):
        amount *= Decimal("10000")

    if amount == amount.to_integral_value():
        return int(amount)
    return float(amount)


def _extract_price(email_text):
    """提取技术者月单价并统一转换为日元数字；范围价格取最低值。"""
    text = unicodedata.normalize("NFKC", str(email_text or ""))
    text = text.replace("〜", "~").replace("～", "~")

    for label_match in _PRICE_LABEL_RE.finditer(text):
        # 允许价格位于标签同行或紧邻的下一行。
        line_end = text.find("\n", label_match.end())
        if line_end == -1:
            context_end = min(len(text), label_match.end() + 100)
        else:
            next_line_end = text.find("\n", line_end + 1)
            context_end = next_line_end if next_line_end != -1 else min(len(text), line_end + 101)
        context = text[label_match.end():context_end]

        if _UNKNOWN_PRICE_RE.search(context):
            continue

        for match in _PRICE_RE.finditer(context):
            first_unit = match.group("first_unit") or match.group("second_unit")
            if not first_unit:
                continue

            first = _to_yen(match.group("first"), first_unit)
            if first is None:
                continue

            second_raw = match.group("second")
            if not second_raw:
                return first

            second_unit = match.group("second_unit") or first_unit
            second = _to_yen(second_raw, second_unit)
            if second is None:
                return first
            return min(first, second)

    return None


# 截取关键词前后的句子
def _extract_country_context(text, window=80):
    contexts = []

    for kw in KEYWORDS:
        for m in re.finditer(re.escape(kw), text):
            start = max(0, m.start() - window)
            end = min(len(text), m.end() + window)
            contexts.append(text[start:end])

    if not contexts:
        return ""

    # 去重
    seen = set()
    result = []
    for c in contexts:
        c = c.strip()
        if c not in seen:
            seen.add(c)
            result.append(c)

    return "\n".join(result)


# 根据技术者内容判断国籍
def _judge_technician_country_by_rule(text):
    if not text.strip():
        return 1

    normalized = text.replace(" ", "").replace("　", "").lower()

    jp_patterns = [
        r"国籍[:：]?(日本|日本国籍)",
        r"(日本籍|日本国籍|日本人)",
    ]

    for pattern in jp_patterns:
        if re.search(pattern, normalized):
            return 0

    return 1


# 抽取全部内容
def extract_all_fields(email_text, llm_func):
    llm_result = llm_func(email_text)
    try:
        llm_result = json.loads(llm_result)
    except Exception:
        llm_result = {"country": 1, "skills": [], "price": None}
    country = _judge_technician_country_by_rule(_extract_country_context(email_text))
    if country != llm_result["country"] and country == 0:
        llm_result["country"] = country

    llm_result["skills"] = _normalize_skills(
        llm_result.get("skills"),
        email_text
    )

    llm_result["price"] = _extract_price(email_text)

    return json.dumps(llm_result)
