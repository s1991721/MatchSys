import json
from datetime import date, datetime

from project.api import api_error


# 解析请求体
def parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, api_error("Invalid JSON body")


def require_login(request):
    login_id = request.session.get("employee_id")
    if not login_id:
        return None, api_error(status=401, message="employee id is required")
    return login_id, None


# 格式化日期
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
    return None, api_error("Invalid date")


# 格式化时间
def parse_time_value(value):
    value = (value or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return api_error("Invalid time")


# 获取星期
def weekday_label(value):
    labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return labels[value.weekday()]


# 是否工作日
def is_workday(value):
    return value.weekday() < 5


# 几年前
def years_ago(today, years):
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, month=2, day=28)


# 月份偏移 2023-12-15 偏移 +1 得到 2024-01-01；偏移 -2 得到 2023-10-01。
def shift_month(value, offset):
    year = value.year + (value.month - 1 + offset) // 12
    month = (value.month - 1 + offset) % 12 + 1
    return date(year, month, 1)


import calendar


# 计算当月工作日
def count_workdays(value):
    _, days_in_month = calendar.monthrange(value.year, value.month)
    return sum(
        1
        for day in range(1, days_in_month + 1)
        if is_workday(date(value.year, value.month, day))
    )


import os
from django.conf import settings


# ss存储路径
def ss_storage_dir():
    return os.path.join(settings.BASE_DIR, "ss")

def contract_storage_dir():
    return os.path.join(settings.BASE_DIR, "customer_contract")
