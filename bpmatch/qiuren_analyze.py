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
    try:
        llm_result = json.loads(llm_result)
    except Exception:
        llm_result = {"country": 1, "skills": [], "price": 0}
    country = _judge_country_by_rule(_extract_country_context(email_text))
    # 如果明文判定为仅日籍则0
    if country == 0:
        llm_result["country"] = country

    llm_result["skills"] = _normalize_skills(
        llm_result.get("skills"),
        email_text
    )

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
