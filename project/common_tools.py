import json
from datetime import date, datetime
from pathlib import Path

from project.api import api_error
from project.error_codes import ErrorCode


# 解析请求体
def parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, api_error(ErrorCode.INVALID_JSON)

# todo 需要将json和file分开
def parse_request_body(request):
    content_type = (request.META.get("CONTENT_TYPE") or "").lower()
    if content_type.startswith("multipart/form-data"):
        return request.POST, None
    return parse_json_body(request)

# todo 需要将json和file分开
def payload_to_dict(payload):
    return payload.dict() if hasattr(payload, "dict") else dict(payload or {})


def require_fields(payload, fields):
    for field in fields:
        if str(payload.get(field) or "").strip() == "":
            return api_error(ErrorCode.INVALID_REQUEST, f"Missing field: {field}")
    return None


# 校验登录，返回 employee_id
def require_login(request):
    login_id = request.session.get("employee_id")
    if not login_id:
        return None, api_error(ErrorCode.LOGIN_REQUIRED, "employee id is required", status=401)
    return login_id, None


# 格式化日期
def parse_date(value, field=None):
    if value in (None, ""):
        return None, None
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date(), None
        except ValueError:
            return None, api_error(ErrorCode.INVALID_DATE, f"Invalid date: {field}" if field else "Invalid date")
    return None, api_error(ErrorCode.INVALID_DATE, f"Invalid date: {field}" if field else "Invalid date")


# 组装分页请求参数
def paginate_queryset(queryset, request, default_page_size=10, max_page_size=100):
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get("page_size", default_page_size))
    except (TypeError, ValueError):
        page_size = default_page_size
    page = max(page, 1)
    page_size = max(min(page_size, max_page_size), 1)
    total = queryset.count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * page_size
    return queryset[offset: offset + page_size], total, page, page_size, total_pages


def _has_upload_extension(uploaded_file, extension):
    return Path(uploaded_file.name or "").suffix.lower() == extension


def _has_magic_bytes(uploaded_file, expected):
    try:
        position = uploaded_file.tell()
        header = uploaded_file.read(len(expected))
        uploaded_file.seek(position)
    except (AttributeError, OSError, ValueError):
        return False
    return header == expected


# 判断上传文件为PNG
def is_png_upload(uploaded_file):
    return (
        bool(uploaded_file)
        and _has_upload_extension(uploaded_file, ".png")
        and _has_magic_bytes(uploaded_file, b"\x89PNG\r\n\x1a\n")
    )


# 判断上传文件为PDF
def is_pdf_upload(uploaded_file):
    return (
        bool(uploaded_file)
        and _has_upload_extension(uploaded_file, ".pdf")
        and _has_magic_bytes(uploaded_file, b"%PDF")
    )


# 格式化时间
def parse_time_value(value):
    value = (value or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return api_error(ErrorCode.INVALID_TIME)


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


from project import storage
from project.storage import StorageArea


# ss存储路径
def ss_storage_dir():
    return storage.path(StorageArea.SS)


def contract_storage_dir():
    return storage.path(StorageArea.CUSTOMER_CONTRACT)
