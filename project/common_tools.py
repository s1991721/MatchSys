import json
from datetime import datetime

from project.api import api_error


# 解析请求体
def parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, api_error("Invalid JSON body")


# 格式化时间
def parse_date(value):
    if value in (None, ""):
        return None, None
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date(), None
        except ValueError:
            return None, api_error(
                "Invalid date"
            )
    return None, api_error(
        "Invalid date"
    )


# 几年前
def years_ago(today, years):
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, month=2, day=28)


import os
from django.conf import settings


# ss存储路径
def ss_storage_dir():
    return os.path.join(settings.BASE_DIR, "ss")
