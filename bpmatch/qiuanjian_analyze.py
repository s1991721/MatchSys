import json
import re

from bpmatch.qiuren_analyze import _normalize_skills

KEYWORDS = [
    "国籍", "日本国籍", "日本人", "日本籍",
]


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
    llm_result = json.loads(llm_result)
    country = _judge_technician_country_by_rule(_extract_country_context(email_text))
    if country != llm_result["country"] and country == 0:
        llm_result["country"] = country

    llm_result["skills"] = _normalize_skills(
        llm_result.get("skills"),
        email_text
    )

    return json.dumps(llm_result)
