import json
import re

KEYWORDS = [
    "外国籍", "国籍", "日本国籍", "日本人", "日本籍",
    "永住者",
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


# 根据内容判断国籍
def _judge_country_by_rule(context):
    if not context.strip():
        return 1

    text = context.replace(" ", "").replace("　", "").lower()

    # 0: 外国籍不可
    ng_patterns = [
        r"外国籍[:：]?(不可|ng|ＮＧ)",
        r"外国籍.*?(不可|ng|ＮＧ)",
        r"日本国籍(のみ|限定|必須)",
        r"日本人(のみ|限定)",
        r"日本籍(のみ|限定|必須)",
        r"国籍[:：]?日本",
    ]

    # 1: 外国籍可
    ok_patterns = [
        r"外国籍[:：]?(可|ok|ＯＫ|可能)",
        r"外国籍.*?(可|ok|ＯＫ|可能)",
        r"国籍不問",
        r"非日本籍.*?可",
    ]

    for p in ng_patterns:
        if re.search(p, text):
            return 0

    for p in ok_patterns:
        if re.search(p, text):
            return 1

    return 1


# 抽取全部内容
def extract_all_fields(email_text, llm_func):
    llm_result = llm_func(email_text)
    llm_result = json.loads(llm_result)
    country = _judge_country_by_rule(_extract_country_context(email_text))
    # 如果明文判定为仅日籍则0
    if country == 0:
        llm_result["country"] = country

    return json.dumps(llm_result)
