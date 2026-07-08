"""财务视图模块共用工具函数。"""

from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from project.api import api_error
from project.common_tools import shift_month


def _quantize_amount(value):
    return Decimal(value or "0").quantize(Decimal("0.01"))

def _parse_receivable_month(value):
    value = (value or "").strip()
    if not value:
        return None, None
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1), None
    except ValueError:
        return None, api_error("Invalid field: month", status=400)

def _parse_receivable_finance_status(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: finance_status", status=400)
    if parsed not in (0, 1, 2):
        return None, api_error("Invalid field: finance_status", status=400)
    return parsed, None


def _parse_optional_int(value, field_name):
    if value in (None, ""):
        return None, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error(f"Invalid field: {field_name}", status=400)
    if parsed < 0:
        return None, api_error(f"Invalid field: {field_name}", status=400)
    return parsed, None


def _parse_decimal_field(payload, field_name, allow_zero=True):
    value = payload.get(field_name)
    if value in (None, ""):
        return Decimal("0"), None
    try:
        parsed = Decimal(str(value))
    except Exception:
        return None, api_error(f"Invalid field: {field_name}", status=400)
    if parsed < 0 or (not allow_zero and parsed <= 0):
        return None, api_error(f"Invalid field: {field_name}", status=400)
    return parsed, None



def _parse_finance_month(value, default_current=False):
    month, error = _parse_receivable_month(value)
    if error:
        return None, error
    if month is None and default_current:
        month = timezone.localdate().replace(day=1)
    return month, None


def _parse_finance_year(value, default_current=True):
    if value in (None, ""):
        if default_current:
            return timezone.localdate().year, None
        return None, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: year", status=400)
    if parsed < 1900 or parsed > 9999:
        return None, api_error("Invalid field: year", status=400)
    return parsed, None


def _year_from_request(request, default_current=True):
    month, error = _parse_finance_month(request.GET.get("month"))
    if error:
        return None, error
    if month:
        return month.year, None
    return _parse_finance_year(request.GET.get("year"), default_current=default_current)
