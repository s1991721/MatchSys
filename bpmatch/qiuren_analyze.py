import json
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation

KEYWORDS = [
    "外国籍", "国籍", "日本国籍", "日本人", "日本籍",
    "永住者",
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
    """提取案件月单价并统一转换为日元数字；范围价格取最低值。"""
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
    try:
        llm_result = json.loads(llm_result)
    except Exception:
        llm_result = {"country": 1, "skills": [], "price": None}
    country = _judge_country_by_rule(_extract_country_context(email_text))
    # 如果明文判定为仅日籍则0
    if country == 0:
        llm_result["country"] = country

    llm_result["skills"] = _normalize_skills(
        llm_result.get("skills"),
        email_text
    )

    llm_result["price"] = _extract_price(email_text)

    return json.dumps(llm_result)


def _normalize_skills(llm_skills, text):
    if not isinstance(llm_skills, list):
        llm_skills = []

    # 小写 + 去空
    llm_skills = [s.strip().lower() for s in llm_skills if s]

    # 从原文补充
    rule_skills = _extract_skills_from_text(text)

    # 合并
    all_skills = set(llm_skills) | set(rule_skills)

    return list(all_skills)


SKILLS = [
    ".net", "access", "adobe", "alpine.js", "android", "angular", "apex", "api", "as400", "asp.net", "aurora", "aws",
    "azure",
    "bash", "batch", "bi", "bigquery",
    "c#", "c++", "chatwork", "ci/cd", "cobol", "css", "cursor",
    "dart", "db", "dba", "devops", "django", "docker", "dreamweaver",
    "ec2", "eclipse", "ecs", "erp", "excel", "express",
    "fastapi", "figma", "flask",
    "gcp", "git", "go", "gradle", "graphql",
    "hadoop", "hinemos", "hive", "html",
    "iis", "illustrator", "idea", "intra-mart", "ios", "iot",
    "java", "javascript", "jboss", "jdk", "jenkins", "jira", "jp1", "jquery", "jsp", "junit",
    "kintone", "kubernetes",
    "lambda", "lamp", "langchain", "laravel", "linux", "llm",
    "mac", "mariadb", "maven", "mcafee", "mongodb", "mvc", "mybatis", "mysql",
    "next.js", "nginx", "node.js", "nuxt.js",
    "objective-c", "opencv", "oracle",
    "perl", "photoshop", "php", "pl/sql", "pm", "pmo", "postgresql", "powerpoint", "powershell", "ppt", "python",
    "react", "redhat", "rpa", "ruby",
    "saas", "salesforce", "sap", "scala", "selenium", "seo", "servicenow", "shell", "slack", "snowflake", "spark",
    "spring", "springboot", "sql", "sqlite", "sre", "sso", "struts", "subversion", "svn", "sybase",
    "teams", "terraform", "thymeleaf", "typescript",
    "ubuntu", "uml", "unity",
    "vb", "vba", "vbs", "vmware", "vscode", "vue",
    "web", "webapi", "webform", "weblogic", "websphere", "windows", "word", "wordpress",
    "zabbix", "アセンブラ", "バッチ", "英語"
]


def _contains_skill(text, skill):
    text = text.lower()
    skill = skill.lower()

    # 日文技能直接包含匹配
    if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", skill):
        return skill in text

    # 含特殊符号的技能，比如 .net, c#, c++, node.js, pl/sql, ci/cd
    if re.search(r"[^a-z0-9]", skill):
        return skill in text

    # 普通英文/数字技能：用边界匹配，避免 java 命中 javascript
    pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


# 从候选列表抽取关键词
def _extract_skills_from_text(text):
    found = set()

    for skill in SKILLS:
        skill = skill.lower()
        if _contains_skill(text, skill):
            found.add(skill)

    return found
