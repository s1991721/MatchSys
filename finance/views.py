from datetime import datetime
from decimal import Decimal
from io import BytesIO
from urllib.parse import quote

from django.db import transaction
from django.http import HttpResponse
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from openpyxl import Workbook

from attendance.models import get_monthly_attendance_models
from employee.models import Employee
from project.api import api_error, api_paginated, api_success
from project.common_tools import is_workday, paginate_queryset, parse_date, parse_json_body, require_login, shift_month
from project.error_codes import ErrorCode
from .models import (
    FinanceSettings,
    FinancePayable,
    FinancePayment,
    FinancePaymentDetail,
    FinanceReceivable,
    FinanceReceipt,
    PayrollBasicInfo,
    PayrollMonthlyCalculation,
)


FINANCE_ANNUITY_SETTING_NAME = "annuity_insurance"
FINANCE_EMPLOYMENT_SETTING_NAME = "employment_insurance"
FINANCE_INCOME_TAX_SETTING_NAME = "income_tax"
FINANCE_PAYROLL_BASIC_ITEMS_SETTING_NAME = "payroll_basic_items"
PAYROLL_BASIC_ITEM_CATEGORIES = (
    "increase_items",
    "non_taxable_increase_items",
    "decrease_items",
)

RECEIVABLE_DISPLAY_STATUS_LABELS = {
    0: "未收",
    1: "部分入金",
    2: "已收",
    3: "逾期",
    5: "异常",
    6: "核销",
}


def _finance_settings_payload_error(message="Invalid annuity insurance settings"):
    return api_error(ErrorCode.SETTINGS_PAYLOAD_INVALID, message, status=400)


def _unwrap_annuity_settings_payload(payload):
    if not isinstance(payload, dict):
        return None, _finance_settings_payload_error()
    if isinstance(payload.get("settings"), dict):
        return payload["settings"], None
    for setting_name in (
        FINANCE_ANNUITY_SETTING_NAME,
        FINANCE_EMPLOYMENT_SETTING_NAME,
        FINANCE_INCOME_TAX_SETTING_NAME,
    ):
        if isinstance(payload.get(setting_name), dict):
            return payload[setting_name], None
    return payload, None


def _parse_json_decimal(value, field_name, allow_negative=False):
    if value in (None, ""):
        return None, _finance_settings_payload_error(f"Missing field: {field_name}")
    try:
        parsed = Decimal(str(value).replace(",", "").strip())
    except Exception:
        return None, _finance_settings_payload_error(f"Invalid field: {field_name}")
    if not parsed.is_finite() or (not allow_negative and parsed < 0):
        return None, _finance_settings_payload_error(f"Invalid field: {field_name}")
    return parsed, None


def _decimal_to_json_number(value):
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _normalize_annuity_metadata(value):
    if not isinstance(value, dict):
        return None, _finance_settings_payload_error("Missing field: metadata")

    try:
        year = int(value.get("year"))
    except (TypeError, ValueError):
        return None, _finance_settings_payload_error("Invalid field: metadata.year")
    if year <= 0:
        return None, _finance_settings_payload_error("Invalid field: metadata.year")

    region = str(value.get("region") or "").strip()
    if not region:
        return None, _finance_settings_payload_error("Missing field: metadata.region")

    return {
        "year": year,
        "region": region,
        "region_name": str(value.get("region_name") or "").strip(),
        "currency": str(value.get("currency") or "JPY").strip() or "JPY",
    }, None


def _normalize_annuity_base_standards(value):
    if not isinstance(value, list):
        return None, _finance_settings_payload_error("Invalid field: base_standards")

    rows = []
    seen_grades = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            return None, _finance_settings_payload_error(f"Invalid field: base_standards[{index}]")

        try:
            grade = int(item.get("grade"))
        except (TypeError, ValueError):
            return None, _finance_settings_payload_error(f"Invalid field: base_standards[{index}].grade")
        if grade in seen_grades:
            return None, _finance_settings_payload_error(f"Duplicate grade: {grade}")
        seen_grades.add(grade)

        monthly_amount, error = _parse_json_decimal(
            item.get("monthly_amount", item.get("standard_salary")),
            f"base_standards[{index}].monthly_amount",
        )
        if error:
            return None, error
        daily_amount, error = _parse_json_decimal(
            item.get("daily_amount", item.get("daily_salary")),
            f"base_standards[{index}].daily_amount",
        )
        if error:
            return None, error
        salary_min, error = _parse_json_decimal(
            item.get("salary_min", item.get("min_salary")),
            f"base_standards[{index}].salary_min",
        )
        if error:
            return None, error
        salary_max, error = _parse_json_decimal(
            item.get("salary_max", item.get("max_salary")),
            f"base_standards[{index}].salary_max",
        )
        if error:
            return None, error

        rows.append({
            "grade": grade,
            "monthly_amount": _decimal_to_json_number(monthly_amount),
            "daily_amount": _decimal_to_json_number(daily_amount),
            "salary_min": _decimal_to_json_number(salary_min),
            "salary_max": _decimal_to_json_number(salary_max),
        })

    return rows, None


def _normalize_annuity_tax_items(value):
    if not isinstance(value, list):
        return None, _finance_settings_payload_error("Invalid field: tax_items")

    items = []
    seen_keys = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            return None, _finance_settings_payload_error(f"Invalid field: tax_items[{index}]")

        name = str(item.get("name") or "").strip()
        if not name:
            return None, _finance_settings_payload_error(f"Missing field: tax_items[{index}].name")

        key = str(item.get("key") or f"tax_item_{index + 1}").strip()
        if not key or key in seen_keys:
            return None, _finance_settings_payload_error(f"Invalid field: tax_items[{index}].key")
        seen_keys.add(key)

        rate, error = _parse_json_decimal(item.get("rate"), f"tax_items[{index}].rate")
        if error:
            return None, error
        if rate > Decimal("1"):
            return None, _finance_settings_payload_error(f"Invalid field: tax_items[{index}].rate")

        items.append({
            "key": key,
            "name": name,
            "rate": _decimal_to_json_number(rate),
        })

    return items, None


def _normalize_annuity_amount_overrides(value, grades, tax_item_keys):
    if value in (None, ""):
        return [], None
    if not isinstance(value, list):
        return None, _finance_settings_payload_error("Invalid field: amount_overrides")

    overrides = []
    seen = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            return None, _finance_settings_payload_error(f"Invalid field: amount_overrides[{index}]")

        try:
            grade = int(item.get("grade"))
        except (TypeError, ValueError):
            return None, _finance_settings_payload_error(f"Invalid field: amount_overrides[{index}].grade")
        if grade not in grades:
            return None, _finance_settings_payload_error(f"Unknown grade in amount_overrides[{index}]")

        tax_item_key = str(item.get("tax_item_key") or item.get("key") or "").strip()
        if not tax_item_key or tax_item_key not in tax_item_keys:
            return None, _finance_settings_payload_error(f"Unknown tax_item_key in amount_overrides[{index}]")

        pair = (grade, tax_item_key)
        if pair in seen:
            return None, _finance_settings_payload_error(f"Duplicate amount override: {grade}/{tax_item_key}")
        seen.add(pair)

        amount, error = _parse_json_decimal(item.get("amount"), f"amount_overrides[{index}].amount")
        if error:
            return None, error
        overrides.append({
            "grade": grade,
            "tax_item_key": tax_item_key,
            "amount": _decimal_to_json_number(amount),
        })

    return overrides, None


def _normalize_annuity_settings(payload):
    settings_payload, error = _unwrap_annuity_settings_payload(payload)
    if error:
        return None, error

    metadata, error = _normalize_annuity_metadata(settings_payload.get("metadata"))
    if error:
        return None, error
    base_standards, error = _normalize_annuity_base_standards(settings_payload.get("base_standards"))
    if error:
        return None, error
    tax_items, error = _normalize_annuity_tax_items(settings_payload.get("tax_items"))
    if error:
        return None, error

    grades = {item["grade"] for item in base_standards}
    tax_item_keys = {item["key"] for item in tax_items}
    amount_overrides, error = _normalize_annuity_amount_overrides(
        settings_payload.get("amount_overrides"),
        grades,
        tax_item_keys,
    )
    if error:
        return None, error

    return {
        "metadata": metadata,
        "base_standards": base_standards,
        "tax_items": tax_items,
        "amount_overrides": amount_overrides,
    }, None


def _quantize_amount(value):
    return Decimal(value or "0").quantize(Decimal("0.01"))


def _finance_tax_table_settings_api(request, setting_name):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "GET":
        record = (
            FinanceSettings.objects
            .filter(name=setting_name, deleted_at__isnull=True)
            .order_by("id")
            .first()
        )
        return api_success(data={
            "name": setting_name,
            "settings": record.settings if record else None,
        })

    payload, error = parse_json_body(request)
    if error:
        return error
    settings_payload, error = _normalize_annuity_settings(payload)
    if error:
        return error

    with transaction.atomic():
        record = (
            FinanceSettings.objects
            .select_for_update()
            .filter(name=setting_name, deleted_at__isnull=True)
            .order_by("id")
            .first()
        )
        if record:
            record.settings = settings_payload
            record.updated_by = login_id
            record.save(update_fields=["settings", "updated_by", "updated_at"])
        else:
            record = FinanceSettings.objects.create(
                name=setting_name,
                settings=settings_payload,
                created_by=login_id,
                updated_by=login_id,
            )

    return api_success(data={
        "name": record.name,
        "settings": record.settings,
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_annuity_insurance_settings_api(request):
    return _finance_tax_table_settings_api(request, FINANCE_ANNUITY_SETTING_NAME)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_employment_insurance_settings_api(request):
    return _finance_tax_table_settings_api(request, FINANCE_EMPLOYMENT_SETTING_NAME)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_income_tax_settings_api(request):
    return _finance_tax_table_settings_api(request, FINANCE_INCOME_TAX_SETTING_NAME)


def _normalize_payroll_basic_item_names(value, category):
    if not isinstance(value, list):
        return None, _finance_settings_payload_error(f"Invalid field: {category}")

    items = []
    seen = set()
    for index, value_item in enumerate(value):
        if not isinstance(value_item, str):
            return None, _finance_settings_payload_error(f"Invalid field: {category}[{index}]")
        item_name = value_item.strip()
        if not item_name or len(item_name) > 100:
            return None, _finance_settings_payload_error(f"Invalid field: {category}[{index}]")
        if item_name in seen:
            return None, _finance_settings_payload_error(f"Duplicate item: {item_name}")
        seen.add(item_name)
        items.append(item_name)
    return items, None


def _read_payroll_basic_item_settings(value):
    source = value if isinstance(value, dict) else {}
    settings = {}
    for category in PAYROLL_BASIC_ITEM_CATEGORIES:
        raw_items = source.get(category)
        settings[category] = raw_items if isinstance(raw_items, list) else []
    return settings


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_payroll_basic_item_settings_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "GET":
        record = (
            FinanceSettings.objects
            .filter(name=FINANCE_PAYROLL_BASIC_ITEMS_SETTING_NAME, deleted_at__isnull=True)
            .order_by("id")
            .first()
        )
        return api_success(data={
            "name": FINANCE_PAYROLL_BASIC_ITEMS_SETTING_NAME,
            "settings": _read_payroll_basic_item_settings(record.settings if record else None),
        })

    payload, error = parse_json_body(request)
    if error:
        return error
    if not isinstance(payload, dict):
        return _finance_settings_payload_error("Invalid payroll basic item settings")

    category = payload.get("category")
    if category not in PAYROLL_BASIC_ITEM_CATEGORIES:
        return _finance_settings_payload_error("Invalid field: category")
    items, error = _normalize_payroll_basic_item_names(payload.get("items"), category)
    if error:
        return error

    with transaction.atomic():
        record = (
            FinanceSettings.objects
            .select_for_update()
            .filter(name=FINANCE_PAYROLL_BASIC_ITEMS_SETTING_NAME, deleted_at__isnull=True)
            .order_by("id")
            .first()
        )
        settings = _read_payroll_basic_item_settings(record.settings if record else None)
        settings[category] = items
        if record:
            record.settings = settings
            record.updated_by = login_id
            record.save(update_fields=["settings", "updated_by", "updated_at"])
        else:
            record = FinanceSettings.objects.create(
                name=FINANCE_PAYROLL_BASIC_ITEMS_SETTING_NAME,
                settings=settings,
                created_by=login_id,
                updated_by=login_id,
            )

    return api_success(data={
        "name": record.name,
        "settings": record.settings,
        "saved_category": category,
    })


def _get_receivable_display_status(item, today=None):
    today = today or timezone.localdate()
    if item.finance_status == 1:
        return 5, RECEIVABLE_DISPLAY_STATUS_LABELS[5]
    if item.finance_status == 2:
        return 6, RECEIVABLE_DISPLAY_STATUS_LABELS[6]
    if item.outstanding_amount <= 0:
        return 2, RECEIVABLE_DISPLAY_STATUS_LABELS[2]
    if item.due_date and item.due_date < today:
        return 3, RECEIVABLE_DISPLAY_STATUS_LABELS[3]
    if item.received_amount > 0:
        return 1, RECEIVABLE_DISPLAY_STATUS_LABELS[1]
    return 0, RECEIVABLE_DISPLAY_STATUS_LABELS[0]


def _serialize_receivable(item):
    display_status, display_status_label = _get_receivable_display_status(item)
    return {
        "id": item.id,
        "pay_request_id": item.pay_request_id,
        "source_type": "request" if item.pay_request_id else "manual",
        "source_label": "请求书" if item.pay_request_id else "手动",
        "request_no": item.request_no or "",
        "customer_id": item.customer_id,
        "customer_name": item.customer_name,
        "receivable_amount": str(item.receivable_amount),
        "received_amount": str(item.received_amount),
        "outstanding_amount": str(item.outstanding_amount),
        "due_date": item.due_date.isoformat() if item.due_date else "",
        "finance_status": item.finance_status,
        "display_status": display_status,
        "display_status_label": display_status_label,
        "remark": item.remark or "",
    }


def _serialize_receipt(item):
    return {
        "id": item.id,
        "receivable_id": item.receivable_id,
        "customer_id": item.customer_id,
        "payer_name": item.payer_name or "",
        "bank_transaction_no": item.bank_transaction_no or "",
        "receipt_amount": str(item.receipt_amount),
        "receipt_date": item.receipt_date.isoformat() if item.receipt_date else "",
        "remark": item.remark or "",
    }


def _parse_receivable_month(value):
    value = (value or "").strip()
    if not value:
        return None, None
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1), None
    except ValueError:
        return None, api_error("Invalid field: month", status=400)


def _parse_receivable_display_status(value):
    if value in (None, "", "all"):
        return None, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: status", status=400)
    if parsed not in RECEIVABLE_DISPLAY_STATUS_LABELS:
        return None, api_error("Invalid field: status", status=400)
    return parsed, None


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


def _apply_receivable_display_status_filter(qs, status):
    today = timezone.localdate()
    if status == 5:
        return qs.filter(finance_status=1)
    if status == 6:
        return qs.filter(finance_status=2)
    base_qs = qs.filter(finance_status=0)
    if status == 2:
        return base_qs.filter(outstanding_amount__lte=0)
    if status == 3:
        return base_qs.filter(outstanding_amount__gt=0, due_date__lt=today)
    if status == 1:
        return base_qs.filter(
            received_amount__gt=0,
            outstanding_amount__gt=0,
        ).filter(Q(due_date__isnull=True) | Q(due_date__gte=today))
    if status == 0:
        return base_qs.filter(
            received_amount__lte=0,
            outstanding_amount__gt=0,
        ).filter(Q(due_date__isnull=True) | Q(due_date__gte=today))
    return qs


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


def _recalculate_receivable_amounts(receivable, updated_by=None):
    total = (
        FinanceReceipt.objects.filter(
            receivable_id=receivable.id,
            deleted_at__isnull=True,
        ).aggregate(total=Sum("receipt_amount"))["total"]
        or Decimal("0")
    )
    receivable.received_amount = _quantize_amount(total)
    receivable.outstanding_amount = _quantize_amount(receivable.receivable_amount - receivable.received_amount)
    if updated_by is not None:
        receivable.updated_by = updated_by
    receivable.save(update_fields=["received_amount", "outstanding_amount", "updated_by", "updated_at"])
    return receivable


def _get_active_receivable(receivable_id, for_update=False):
    qs = FinanceReceivable.objects.filter(id=receivable_id, deleted_at__isnull=True)
    if for_update:
        qs = qs.select_for_update()
    return qs.first()


def _build_receivable_values(payload, existing=None):
    values = {}

    if existing is None or "customer_id" in payload:
        customer_id, error = _parse_optional_int(payload.get("customer_id"), "customer_id")
        if error:
            return None, error
        values["customer_id"] = customer_id

    if existing is None or "customer_name" in payload:
        customer_name = (payload.get("customer_name") or "").strip()
        if not customer_name:
            return None, api_error("Missing field: customer_name")
        values["customer_name"] = customer_name

    if existing is None or "receivable_amount" in payload:
        receivable_amount, error = _parse_decimal_field(payload, "receivable_amount", allow_zero=False)
        if error:
            return None, error
        values["receivable_amount"] = receivable_amount

    if existing is None or "due_date" in payload:
        due_date, error = parse_date(payload.get("due_date"), "due_date")
        if error:
            return None, error
        values["due_date"] = due_date

    if existing is None or "finance_status" in payload:
        finance_status, error = _parse_receivable_finance_status(payload.get("finance_status", 0))
        if error:
            return None, error
        values["finance_status"] = finance_status

    if existing is None or "remark" in payload:
        values["remark"] = (payload.get("remark") or "").strip() or None

    return values, None


def _apply_receivable_values(item, values):
    for field_name, value in values.items():
        setattr(item, field_name, value)
    if "receivable_amount" in values:
        item.outstanding_amount = _quantize_amount(item.receivable_amount - item.received_amount)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_receivables_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "POST":
        payload, error = parse_json_body(request)
        if error:
            return error
        if payload.get("pay_request_id") not in (None, "") or payload.get("request_no") not in (None, ""):
            return api_error("Source fields cannot be created manually", status=400)
        values, error = _build_receivable_values(payload)
        if error:
            return error
        item = FinanceReceivable.objects.create(
            pay_request_id=None,
            request_no=None,
            received_amount=Decimal("0"),
            outstanding_amount=values["receivable_amount"],
            created_by=login_id,
            updated_by=login_id,
            **values,
        )
        return api_success(data={"item": _serialize_receivable(item)}, status=201)

    month, error = _parse_receivable_month(request.GET.get("month"))
    if error:
        return error

    display_status, error = _parse_receivable_display_status(request.GET.get("status"))
    if error:
        return error

    source = (request.GET.get("source") or "").strip()
    if source == "all":
        source = ""
    if source and source not in ("request", "manual"):
        return api_error("Invalid field: source", status=400)

    qs = FinanceReceivable.objects.filter(deleted_at__isnull=True)

    if month:
        qs = qs.filter(due_date__gte=month, due_date__lt=shift_month(month, 1))

    if source == "request":
        qs = qs.filter(pay_request_id__isnull=False)
    elif source == "manual":
        qs = qs.filter(pay_request_id__isnull=True)

    if display_status is not None:
        qs = _apply_receivable_display_status_filter(qs, display_status)

    paged, total, page, page_size, total_pages = paginate_queryset(
        qs.order_by("due_date", "id"),
        request,
    )
    return api_paginated(
        items=[_serialize_receivable(item) for item in paged],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@require_http_methods(["GET"])
def finance_receivables_overview_api(request):
    _login_id, error = require_login(request)
    if error:
        return error

    month, error = _parse_receivable_month(request.GET.get("month"))
    if error:
        return error
    month = month or timezone.localdate().replace(day=1)
    next_month = shift_month(month, 1)

    current_qs = FinanceReceivable.objects.filter(
        deleted_at__isnull=True,
        due_date__gte=month,
        due_date__lt=next_month,
    )
    current_summary = current_qs.aggregate(
        receivable_amount=Sum("receivable_amount"),
        received_amount=Sum("received_amount"),
        outstanding_amount=Sum("outstanding_amount"),
    )

    historical_rows = (
        FinanceReceivable.objects.filter(
            deleted_at__isnull=True,
            finance_status=0,
            due_date__lt=month,
            outstanding_amount__gt=0,
        )
        .annotate(month=TruncMonth("due_date"))
        .values("month")
        .annotate(
            count=Count("id"),
            receivable_amount=Sum("receivable_amount"),
            received_amount=Sum("received_amount"),
            outstanding_amount=Sum("outstanding_amount"),
        )
        .order_by("-month")
    )

    return api_success(
        data={
            "month": month.strftime("%Y-%m"),
            "summary": {
                "receivable_amount": str(_quantize_amount(current_summary["receivable_amount"])),
                "received_amount": str(_quantize_amount(current_summary["received_amount"])),
                "outstanding_amount": str(_quantize_amount(current_summary["outstanding_amount"])),
            },
            "unbalanced_months": [
                {
                    "month": row["month"].strftime("%Y-%m") if row["month"] else "",
                    "count": row["count"] or 0,
                    "receivable_amount": str(_quantize_amount(row["receivable_amount"])),
                    "received_amount": str(_quantize_amount(row["received_amount"])),
                    "outstanding_amount": str(_quantize_amount(row["outstanding_amount"])),
                }
                for row in historical_rows
            ],
        }
    )


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def finance_receivable_detail_api(request, receivable_id):
    item = _get_active_receivable(receivable_id)
    if not item:
        return api_error("Finance receivable not found", status=404)

    if request.method == "GET":
        return api_success(data={"item": _serialize_receivable(item)})

    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "DELETE":
        has_receipts = FinanceReceipt.objects.filter(receivable_id=item.id, deleted_at__isnull=True).exists()
        if has_receipts:
            return api_error("Receivable has receipts and cannot be deleted", status=409)
        item.deleted_at = timezone.now()
        item.updated_by = login_id
        item.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        return api_success(data={"deleted": True})

    payload, error = parse_json_body(request)
    if error:
        return error
    if "pay_request_id" in payload or "request_no" in payload:
        return api_error("Source fields cannot be changed", status=400)
    values, error = _build_receivable_values(payload, existing=item)
    if error:
        return error

    with transaction.atomic():
        item = FinanceReceivable.objects.select_for_update().get(id=item.id)
        _apply_receivable_values(item, values)
        item.updated_by = login_id
        item.save()
        if "receivable_amount" in values:
            _recalculate_receivable_amounts(item, login_id)
    return api_success(data={"item": _serialize_receivable(item)})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_receivable_receipts_api(request, receivable_id):
    login_id, error = require_login(request)
    if error:
        return error

    receivable = _get_active_receivable(receivable_id)
    if not receivable:
        return api_error("Finance receivable not found", status=404)

    if request.method == "GET":
        items = FinanceReceipt.objects.filter(
            receivable_id=receivable.id,
            deleted_at__isnull=True,
        ).order_by("receipt_date", "id")
        return api_success(data={"items": [_serialize_receipt(item) for item in items]})

    if receivable.finance_status == 2:
        return api_error("Written-off receivable cannot receive payments", status=409)

    payload, error = parse_json_body(request)
    if error:
        return error
    amount, error = _parse_decimal_field(payload, "receipt_amount", allow_zero=False)
    if error:
        return error
    receipt_date, error = parse_date(payload.get("receipt_date"), "receipt_date")
    if error:
        return error
    if not receipt_date:
        return api_error("Missing field: receipt_date")
    customer_id, error = _parse_optional_int(payload.get("customer_id"), "customer_id")
    if error:
        return error

    with transaction.atomic():
        receivable = _get_active_receivable(receivable_id, for_update=True)
        if not receivable:
            return api_error("Finance receivable not found", status=404)
        if receivable.finance_status == 2:
            return api_error("Written-off receivable cannot receive payments", status=409)
        item = FinanceReceipt.objects.create(
            receivable_id=receivable.id,
            customer_id=customer_id,
            payer_name=(payload.get("payer_name") or "").strip() or None,
            bank_transaction_no=(payload.get("bank_transaction_no") or "").strip() or None,
            receipt_amount=amount,
            receipt_date=receipt_date,
            remark=(payload.get("remark") or "").strip() or None,
            created_by=login_id,
            updated_by=login_id,
        )
        _recalculate_receivable_amounts(receivable, login_id)
    return api_success(
        data={"item": _serialize_receipt(item), "receivable": _serialize_receivable(receivable)},
        status=201,
    )


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def finance_receipt_detail_api(request, receipt_id):
    item = FinanceReceipt.objects.filter(id=receipt_id, deleted_at__isnull=True).first()
    if not item:
        return api_error("Finance receipt not found", status=404)

    receivable = _get_active_receivable(item.receivable_id)
    if not receivable:
        return api_error("Finance receivable not found", status=404)

    if request.method == "GET":
        return api_success(data={"item": _serialize_receipt(item)})

    login_id, error = require_login(request)
    if error:
        return error

    if receivable.finance_status == 2:
        return api_error("Written-off receivable receipt cannot be changed", status=409)

    with transaction.atomic():
        receivable = _get_active_receivable(item.receivable_id, for_update=True)
        if not receivable:
            return api_error("Finance receivable not found", status=404)
        if receivable.finance_status == 2:
            return api_error("Written-off receivable receipt cannot be changed", status=409)

        item = FinanceReceipt.objects.select_for_update().get(id=item.id)
        if request.method == "DELETE":
            item.deleted_at = timezone.now()
            item.updated_by = login_id
            item.save(update_fields=["deleted_at", "updated_by", "updated_at"])
            _recalculate_receivable_amounts(receivable, login_id)
            return api_success(data={"deleted": True, "receivable": _serialize_receivable(receivable)})

        payload, error = parse_json_body(request)
        if error:
            return error
        if "receipt_amount" in payload:
            amount, error = _parse_decimal_field(payload, "receipt_amount", allow_zero=False)
            if error:
                return error
            item.receipt_amount = amount
        if "receipt_date" in payload:
            receipt_date, error = parse_date(payload.get("receipt_date"), "receipt_date")
            if error:
                return error
            if not receipt_date:
                return api_error("Missing field: receipt_date")
            item.receipt_date = receipt_date
        if "customer_id" in payload:
            customer_id, error = _parse_optional_int(payload.get("customer_id"), "customer_id")
            if error:
                return error
            item.customer_id = customer_id
        if "payer_name" in payload:
            item.payer_name = (payload.get("payer_name") or "").strip() or None
        if "bank_transaction_no" in payload:
            item.bank_transaction_no = (payload.get("bank_transaction_no") or "").strip() or None
        if "remark" in payload:
            item.remark = (payload.get("remark") or "").strip() or None
        item.updated_by = login_id
        item.save()
        _recalculate_receivable_amounts(receivable, login_id)
    return api_success(data={"item": _serialize_receipt(item), "receivable": _serialize_receivable(receivable)})


PAYABLE_DISPLAY_STATUS_LABELS = {
    0: "未付",
    1: "部分支付",
    2: "已付",
    3: "逾期",
    5: "异常",
    6: "核销",
}


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


def _get_payable_display_status(item, today=None):
    today = today or timezone.localdate()
    if item.finance_status == 1:
        return 5, PAYABLE_DISPLAY_STATUS_LABELS[5]
    if item.finance_status == 2:
        return 6, PAYABLE_DISPLAY_STATUS_LABELS[6]
    if item.outstanding_amount <= 0:
        return 2, PAYABLE_DISPLAY_STATUS_LABELS[2]
    if item.due_date and item.due_date < today:
        return 3, PAYABLE_DISPLAY_STATUS_LABELS[3]
    if item.paid_amount > 0:
        return 1, PAYABLE_DISPLAY_STATUS_LABELS[1]
    return 0, PAYABLE_DISPLAY_STATUS_LABELS[0]


def _serialize_payable(item):
    display_status, display_status_label = _get_payable_display_status(item)
    return {
        "id": item.id,
        "year": item.payable_month.year if item.payable_month else None,
        "purchase_order_id": item.purchase_order_id,
        "source_type": "purchase_order" if item.purchase_order_id else "manual",
        "source_label": "发注" if item.purchase_order_id else "手动",
        "order_no": item.order_no or "",
        "payable_month": item.payable_month.strftime("%Y-%m") if item.payable_month else "",
        "customer_id": item.customer_id,
        "customer_name": item.customer_name,
        "payable_amount": str(item.payable_amount),
        "paid_amount": str(item.paid_amount),
        "outstanding_amount": str(item.outstanding_amount),
        "due_date": item.due_date.isoformat() if item.due_date else "",
        "finance_status": item.finance_status,
        "display_status": display_status,
        "display_status_label": display_status_label,
        "remark": item.remark or "",
    }


def _serialize_payment(item):
    return {
        "id": item.id,
        "year": item.payment_date.year if item.payment_date else None,
        "customer_id": item.customer_id,
        "payee_name": item.payee_name or "",
        "bank_transaction_no": item.bank_transaction_no or "",
        "payment_amount": str(item.payment_amount),
        "payment_date": item.payment_date.isoformat() if item.payment_date else "",
        "remark": item.remark or "",
    }


def _serialize_payment_detail(item):
    return {
        "id": item.id,
        "payment_id": item.payment_id,
        "payable_id": item.payable_id,
        "payment_amount": str(item.payment_amount),
        "remark": item.remark or "",
    }


def _truthy_request_value(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _serialize_payment_for_ledger(
    item,
    details=None,
    payables=None,
    details_loaded=True,
    details_count=None,
    details_amount=None,
):
    details = details or []
    payables = payables or {}
    serialized_details = []
    for detail in details:
        payable = payables.get(detail.payable_id)
        serialized_detail = _serialize_payment_detail(detail)
        serialized_detail.update({
            "source_type": "payable",
            "source_no": (payable.order_no if payable else "") or f"PAYABLE-{detail.payable_id}",
            "source_name": (
                f"{payable.customer_name} / {payable.payable_month.strftime('%Y-%m')}"
                if payable and payable.payable_month
                else ""
            ),
            "payable": _serialize_payable(payable) if payable else None,
        })
        serialized_details.append(serialized_detail)

    item_payload = _serialize_payment(item)
    item_payload.update({
        "type": "payable",
        "type_label": "应付",
        "method": "bank" if item.bank_transaction_no else "other",
        "method_label": "银行转账" if item.bank_transaction_no else "其他",
        "details": serialized_details,
        "details_loaded": details_loaded,
        "details_count": details_count if details_count is not None else len(serialized_details),
        "details_amount": str(_quantize_amount(
            details_amount
            if details_amount is not None
            else sum((detail.payment_amount for detail in details), Decimal("0"))
        )),
    })
    return item_payload


def _parse_payable_display_status(value):
    if value in (None, "", "all"):
        return None, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: status", status=400)
    if parsed not in PAYABLE_DISPLAY_STATUS_LABELS:
        return None, api_error("Invalid field: status", status=400)
    return parsed, None


def _apply_payable_display_status_filter(qs, status):
    today = timezone.localdate()
    if status == 5:
        return qs.filter(finance_status=1)
    if status == 6:
        return qs.filter(finance_status=2)
    base_qs = qs.filter(finance_status=0)
    if status == 2:
        return base_qs.filter(outstanding_amount__lte=0)
    if status == 3:
        return base_qs.filter(outstanding_amount__gt=0, due_date__lt=today)
    if status == 1:
        return base_qs.filter(
            paid_amount__gt=0,
            outstanding_amount__gt=0,
        ).filter(Q(due_date__isnull=True) | Q(due_date__gte=today))
    if status == 0:
        return base_qs.filter(
            paid_amount__lte=0,
            outstanding_amount__gt=0,
        ).filter(Q(due_date__isnull=True) | Q(due_date__gte=today))
    return qs


def _get_active_payable(payable_id, year, for_update=False):
    payable_model = FinancePayable.model_for_period(year)
    qs = payable_model.objects.filter(id=payable_id, deleted_at__isnull=True)
    if for_update:
        qs = qs.select_for_update()
    return qs.first()


def _recalculate_payable_amounts(payable, year, updated_by=None):
    detail_model = FinancePaymentDetail.model_for_period(year)
    total = (
        detail_model.objects.filter(
            payable_id=payable.id,
            deleted_at__isnull=True,
        ).aggregate(total=Sum("payment_amount"))["total"]
        or Decimal("0")
    )
    payable.paid_amount = _quantize_amount(total)
    payable.outstanding_amount = _quantize_amount(payable.payable_amount - payable.paid_amount)
    if updated_by is not None:
        payable.updated_by = updated_by
    payable.save(update_fields=["paid_amount", "outstanding_amount", "updated_by", "updated_at"])
    return payable


def _build_payable_values(payload, existing=None):
    values = {}

    if existing is None or "payable_month" in payload:
        month, error = _parse_finance_month(payload.get("payable_month") or payload.get("month"))
        if error:
            return None, error
        if not month:
            return None, api_error("Missing field: payable_month")
        values["payable_month"] = month

    if existing is None or "customer_id" in payload:
        customer_id, error = _parse_optional_int(payload.get("customer_id"), "customer_id")
        if error:
            return None, error
        values["customer_id"] = customer_id

    if existing is None or "customer_name" in payload:
        customer_name = (payload.get("customer_name") or "").strip()
        if not customer_name:
            return None, api_error("Missing field: customer_name")
        values["customer_name"] = customer_name

    if existing is None or "payable_amount" in payload:
        payable_amount, error = _parse_decimal_field(payload, "payable_amount", allow_zero=False)
        if error:
            return None, error
        values["payable_amount"] = payable_amount

    if existing is None or "due_date" in payload:
        due_date, error = parse_date(payload.get("due_date"), "due_date")
        if error:
            return None, error
        values["due_date"] = due_date

    if existing is None or "finance_status" in payload:
        finance_status, error = _parse_receivable_finance_status(payload.get("finance_status", 0))
        if error:
            return None, error
        values["finance_status"] = finance_status

    if existing is None or "remark" in payload:
        values["remark"] = (payload.get("remark") or "").strip() or None

    return values, None


def _apply_payable_values(item, values):
    for field_name, value in values.items():
        setattr(item, field_name, value)
    if "payable_amount" in values:
        item.outstanding_amount = _quantize_amount(item.payable_amount - item.paid_amount)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_payables_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "POST":
        payload, error = parse_json_body(request)
        if error:
            return error
        if payload.get("purchase_order_id") not in (None, "") or payload.get("order_no") not in (None, ""):
            return api_error("Source fields cannot be created manually", status=400)
        values, error = _build_payable_values(payload)
        if error:
            return error
        payable_model = FinancePayable.model_for_period(values["payable_month"])
        item = payable_model.objects.create(
            purchase_order_id=None,
            order_no=None,
            paid_amount=Decimal("0"),
            outstanding_amount=values["payable_amount"],
            created_by=login_id,
            updated_by=login_id,
            **values,
        )
        return api_success(data={"item": _serialize_payable(item)}, status=201)

    month, error = _parse_finance_month(request.GET.get("month"))
    if error:
        return error
    year, error = _year_from_request(request)
    if error:
        return error

    display_status, error = _parse_payable_display_status(request.GET.get("status"))
    if error:
        return error

    source = (request.GET.get("source") or "").strip()
    if source == "all":
        source = ""
    if source and source not in ("purchase_order", "manual"):
        return api_error("Invalid field: source", status=400)

    qs = FinancePayable.objects_for_period(year).filter(deleted_at__isnull=True)

    if month:
        qs = qs.filter(payable_month=month)

    if source == "purchase_order":
        qs = qs.filter(purchase_order_id__isnull=False)
    elif source == "manual":
        qs = qs.filter(purchase_order_id__isnull=True)

    keyword = (request.GET.get("keyword") or "").strip()
    if keyword:
        qs = qs.filter(Q(customer_name__icontains=keyword) | Q(order_no__icontains=keyword))

    if display_status is not None:
        qs = _apply_payable_display_status_filter(qs, display_status)

    paged, total, page, page_size, total_pages = paginate_queryset(
        qs.order_by("payable_month", "due_date", "id"),
        request,
    )
    return api_paginated(
        items=[_serialize_payable(item) for item in paged],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@require_http_methods(["GET"])
def finance_payables_overview_api(request):
    _login_id, error = require_login(request)
    if error:
        return error

    month, error = _parse_finance_month(request.GET.get("month"), default_current=True)
    if error:
        return error
    payable_model = FinancePayable.model_for_period(month)

    current_qs = payable_model.objects.filter(
        deleted_at__isnull=True,
        payable_month=month,
    )
    current_summary = current_qs.aggregate(
        payable_amount=Sum("payable_amount"),
        paid_amount=Sum("paid_amount"),
        outstanding_amount=Sum("outstanding_amount"),
    )

    historical_rows = (
        payable_model.objects.filter(
            deleted_at__isnull=True,
            finance_status=0,
            payable_month__lt=month,
            outstanding_amount__gt=0,
        )
        .values("payable_month")
        .annotate(
            count=Count("id"),
            payable_amount=Sum("payable_amount"),
            paid_amount=Sum("paid_amount"),
            outstanding_amount=Sum("outstanding_amount"),
        )
        .order_by("-payable_month")
    )

    return api_success(
        data={
            "month": month.strftime("%Y-%m"),
            "summary": {
                "payable_amount": str(_quantize_amount(current_summary["payable_amount"])),
                "paid_amount": str(_quantize_amount(current_summary["paid_amount"])),
                "outstanding_amount": str(_quantize_amount(current_summary["outstanding_amount"])),
            },
            "unbalanced_months": [
                {
                    "month": row["payable_month"].strftime("%Y-%m") if row["payable_month"] else "",
                    "count": row["count"] or 0,
                    "payable_amount": str(_quantize_amount(row["payable_amount"])),
                    "paid_amount": str(_quantize_amount(row["paid_amount"])),
                    "outstanding_amount": str(_quantize_amount(row["outstanding_amount"])),
                }
                for row in historical_rows
            ],
        }
    )


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def finance_payable_detail_api(request, payable_id):
    year, error = _year_from_request(request)
    if error:
        return error
    item = _get_active_payable(payable_id, year)
    if not item:
        return api_error("Finance payable not found", status=404)

    if request.method == "GET":
        return api_success(data={"item": _serialize_payable(item)})

    login_id, error = require_login(request)
    if error:
        return error

    detail_model = FinancePaymentDetail.model_for_period(year)
    if request.method == "DELETE":
        has_payments = detail_model.objects.filter(payable_id=item.id, deleted_at__isnull=True).exists()
        if has_payments:
            return api_error("Payable has payments and cannot be deleted", status=409)
        item.deleted_at = timezone.now()
        item.updated_by = login_id
        item.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        return api_success(data={"deleted": True})

    if item.purchase_order_id:
        return api_error("Purchase order payable cannot be changed manually", status=409)

    payload, error = parse_json_body(request)
    if error:
        return error
    if "purchase_order_id" in payload or "order_no" in payload:
        return api_error("Source fields cannot be changed", status=400)
    values, error = _build_payable_values(payload, existing=item)
    if error:
        return error
    if "payable_month" in values and values["payable_month"].year != year:
        return api_error("Payable month year cannot be changed through this endpoint", status=400)
    if "payable_amount" in values and values["payable_amount"] < item.paid_amount:
        return api_error("Payable amount cannot be less than paid amount", status=409)

    with transaction.atomic():
        item = FinancePayable.model_for_period(year).objects.select_for_update().get(id=item.id)
        _apply_payable_values(item, values)
        item.updated_by = login_id
        item.save()
        if "payable_amount" in values:
            _recalculate_payable_amounts(item, year, login_id)
    return api_success(data={"item": _serialize_payable(item)})


@require_http_methods(["GET"])
def finance_payable_payments_api(request, payable_id):
    _login_id, error = require_login(request)
    if error:
        return error
    year, error = _year_from_request(request)
    if error:
        return error
    payable = _get_active_payable(payable_id, year)
    if not payable:
        return api_error("Finance payable not found", status=404)
    detail_model = FinancePaymentDetail.model_for_period(year)
    details = detail_model.objects.filter(
        payable_id=payable.id,
        deleted_at__isnull=True,
    ).order_by("id")
    payment_model = FinancePayment.model_for_period(year)
    payment_ids = [item.payment_id for item in details]
    payments = {
        item.id: item
        for item in payment_model.objects.filter(id__in=payment_ids, deleted_at__isnull=True)
    }
    return api_success(
        data={
            "items": [
                {
                    **_serialize_payment_detail(detail),
                    "payment": _serialize_payment(payments[detail.payment_id]) if detail.payment_id in payments else None,
                }
                for detail in details
            ]
        }
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_payments_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "GET":
        month, error = _parse_finance_month(request.GET.get("month"))
        if error:
            return error
        year, error = _year_from_request(request)
        if error:
            return error
        qs = FinancePayment.objects_for_period(year).filter(deleted_at__isnull=True)
        if month:
            qs = qs.filter(payment_date__gte=month, payment_date__lt=shift_month(month, 1))
        customer_id, error = _parse_optional_int(request.GET.get("customer_id"), "customer_id")
        if error:
            return error
        if customer_id is not None:
            qs = qs.filter(customer_id=customer_id)
        keyword = (request.GET.get("keyword") or "").strip()
        if keyword:
            qs = qs.filter(Q(payee_name__icontains=keyword) | Q(bank_transaction_no__icontains=keyword))

        summary_total = qs.aggregate(total=Sum("payment_amount"))["total"] or Decimal("0")

        payment_type = (request.GET.get("type") or "").strip()
        if payment_type == "all":
            payment_type = ""
        if payment_type and payment_type != "payable":
            qs = qs.none()

        paged, total, page, page_size, total_pages = paginate_queryset(
            qs.order_by("-payment_date", "-id"),
            request,
        )
        paged = list(paged)
        details_by_payment = {}
        detail_stats_by_payment = {}
        payables_by_id = {}
        include_details = _truthy_request_value(request.GET.get("include_details"))
        if paged:
            detail_model = FinancePaymentDetail.model_for_period(year)
            detail_qs = detail_model.objects.filter(
                payment_id__in=[item.id for item in paged],
                deleted_at__isnull=True,
            )
            detail_stats_by_payment = {
                row["payment_id"]: row
                for row in detail_qs.values("payment_id").annotate(
                    count=Count("id"),
                    amount=Sum("payment_amount"),
                )
            }
            if include_details:
                details = list(detail_qs.order_by("id"))
                for detail in details:
                    details_by_payment.setdefault(detail.payment_id, []).append(detail)
                payable_ids = {detail.payable_id for detail in details}
                if payable_ids:
                    payable_model = FinancePayable.model_for_period(year)
                    payables_by_id = {
                        item.id: item
                        for item in payable_model.objects.filter(id__in=payable_ids, deleted_at__isnull=True)
                    }
        return api_success(
            data={
                "items": [
                    _serialize_payment_for_ledger(
                        item,
                        details_by_payment.get(item.id, []),
                        payables_by_id,
                        details_loaded=include_details,
                        details_count=(detail_stats_by_payment.get(item.id) or {}).get("count", 0),
                        details_amount=(detail_stats_by_payment.get(item.id) or {}).get("amount", Decimal("0")),
                    )
                    for item in paged
                ],
                "summary": {
                    "total_amount": str(_quantize_amount(summary_total)),
                    "salary_amount": "0.00",
                    "payable_amount": str(_quantize_amount(summary_total)),
                    "reimbursement_amount": "0.00",
                    "other_amount": "0.00",
                },
            },
            meta={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        )

    payload, error = parse_json_body(request)
    if error:
        return error
    payment_date, error = parse_date(payload.get("payment_date"), "payment_date")
    if error:
        return error
    if not payment_date:
        return api_error("Missing field: payment_date")
    payment_amount, error = _parse_decimal_field(payload, "payment_amount", allow_zero=False)
    if error:
        return error
    customer_id, error = _parse_optional_int(payload.get("customer_id"), "customer_id")
    if error:
        return error
    allocations = payload.get("allocations")
    if not isinstance(allocations, list) or not allocations:
        return api_error("Missing field: allocations")

    payment_year = payment_date.year
    payable_model = FinancePayable.model_for_period(payment_year)
    payment_model = FinancePayment.model_for_period(payment_year)
    detail_model = FinancePaymentDetail.model_for_period(payment_year)

    parsed_allocations = []
    total_allocated = Decimal("0")
    for index, allocation in enumerate(allocations, start=1):
        if not isinstance(allocation, dict):
            return api_error(f"Invalid field: allocations[{index}]", status=400)
        payable_id, error = _parse_optional_int(allocation.get("payable_id"), f"allocations[{index}].payable_id")
        if error:
            return error
        if not payable_id:
            return api_error(f"Missing field: allocations[{index}].payable_id")
        amount, error = _parse_decimal_field(allocation, "payment_amount", allow_zero=False)
        if error:
            return error
        total_allocated += amount
        parsed_allocations.append((payable_id, amount, (allocation.get("remark") or "").strip() or None))

    payable_ids = [item[0] for item in parsed_allocations]
    if len(payable_ids) != len(set(payable_ids)):
        return api_error("Duplicate payable allocation", status=400)

    total_allocated = _quantize_amount(total_allocated)
    payment_amount = _quantize_amount(payment_amount)
    if total_allocated != payment_amount:
        return api_error("Payment amount must equal allocation total", status=400)

    with transaction.atomic():
        payables = {
            item.id: item
            for item in payable_model.objects.select_for_update().filter(
                id__in=payable_ids,
                deleted_at__isnull=True,
            )
        }
        if len(payables) != len(set(payable_ids)):
            return api_error("Finance payable not found", status=404)
        if any(item.finance_status == 2 for item in payables.values()):
            return api_error("Written-off payable cannot be paid", status=409)
        customer_ids = {item.customer_id for item in payables.values()}
        if len(customer_ids) > 1:
            return api_error("Payment allocations must belong to one customer", status=400)
        if customer_id is not None and customer_ids and customer_id not in customer_ids:
            return api_error("Payment customer does not match payable customer", status=400)
        resolved_customer_id = customer_id if customer_id is not None else next(iter(customer_ids), None)
        for payable_id, amount, _remark in parsed_allocations:
            payable = payables[payable_id]
            if amount > payable.outstanding_amount:
                return api_error("Payment amount exceeds payable outstanding amount", status=409)

        payment = payment_model.objects.create(
            customer_id=resolved_customer_id,
            payee_name=(payload.get("payee_name") or "").strip() or None,
            bank_transaction_no=(payload.get("bank_transaction_no") or "").strip() or None,
            payment_amount=payment_amount,
            payment_date=payment_date,
            remark=(payload.get("remark") or "").strip() or None,
            created_by=login_id,
            updated_by=login_id,
        )
        details = []
        for payable_id, amount, remark in parsed_allocations:
            details.append(
                detail_model.objects.create(
                    payment_id=payment.id,
                    payable_id=payable_id,
                    payment_amount=amount,
                    remark=remark,
                    created_by=login_id,
                    updated_by=login_id,
                )
            )
        updated_payables = [
            _recalculate_payable_amounts(payable, payment_year, login_id)
            for payable in payables.values()
        ]

    return api_success(
        data={
            "item": _serialize_payment(payment),
            "details": [_serialize_payment_detail(item) for item in details],
            "payables": [_serialize_payable(item) for item in updated_payables],
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def finance_payment_detail_api(request, payment_id):
    year, error = _year_from_request(request)
    if error:
        return error
    payment_model = FinancePayment.model_for_period(year)
    detail_model = FinancePaymentDetail.model_for_period(year)
    payment = payment_model.objects.filter(id=payment_id, deleted_at__isnull=True).first()
    if not payment:
        return api_error("Finance payment not found", status=404)

    if request.method == "GET":
        details = list(detail_model.objects.filter(
            payment_id=payment.id,
            deleted_at__isnull=True,
        ).order_by("id"))
        payable_model = FinancePayable.model_for_period(year)
        payables = {
            item.id: item
            for item in payable_model.objects.filter(
                id__in=[detail.payable_id for detail in details],
                deleted_at__isnull=True,
            )
        }
        return api_success(
            data={
                "item": _serialize_payment_for_ledger(payment, details, payables),
                "details": [
                    _serialize_payment_for_ledger(payment, [detail], payables)["details"][0]
                    for detail in details
                ],
            }
        )

    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "PUT":
        payload, error = parse_json_body(request)
        if error:
            return error
        detail_id, error = _parse_optional_int(payload.get("detail_id"), "detail_id")
        if error:
            return error
        remark = (payload.get("remark") or "").strip() or None
        with transaction.atomic():
            payment = payment_model.objects.select_for_update().get(id=payment.id)
            if detail_id:
                detail = detail_model.objects.select_for_update().filter(
                    id=detail_id,
                    payment_id=payment.id,
                    deleted_at__isnull=True,
                ).first()
                if not detail:
                    return api_error("Finance payment detail not found", status=404)
                detail.remark = remark
                detail.updated_by = login_id
                detail.save(update_fields=["remark", "updated_by", "updated_at"])
            else:
                payment.remark = remark
                payment.updated_by = login_id
                payment.save(update_fields=["remark", "updated_by", "updated_at"])
        details = list(detail_model.objects.filter(
            payment_id=payment.id,
            deleted_at__isnull=True,
        ).order_by("id"))
        payable_model = FinancePayable.model_for_period(year)
        payables = {
            item.id: item
            for item in payable_model.objects.filter(
                id__in=[detail.payable_id for detail in details],
                deleted_at__isnull=True,
            )
        }
        return api_success(
            data={
                "item": _serialize_payment_for_ledger(payment, details, payables),
                "details": [
                    _serialize_payment_for_ledger(payment, [detail], payables)["details"][0]
                    for detail in details
                ],
            }
        )

    with transaction.atomic():
        payment = payment_model.objects.select_for_update().get(id=payment.id)
        details = list(
            detail_model.objects.select_for_update().filter(
                payment_id=payment.id,
                deleted_at__isnull=True,
            )
        )
        payment.deleted_at = timezone.now()
        payment.updated_by = login_id
        payment.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        now = timezone.now()
        for detail in details:
            detail.deleted_at = now
            detail.updated_by = login_id
            detail.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        payable_model = FinancePayable.model_for_period(year)
        payables = payable_model.objects.select_for_update().filter(
            id__in=[item.payable_id for item in details],
            deleted_at__isnull=True,
        )
        updated_payables = [
            _recalculate_payable_amounts(payable, year, login_id)
            for payable in payables
        ]
    return api_success(
        data={
            "deleted": True,
            "payables": [_serialize_payable(item) for item in updated_payables],
        }
    )


def _parse_payroll_month(value):
    value = (value or "").strip()
    if not value:
        return None, api_error("Missing field: month")
    try:
        parsed = datetime.strptime(value, "%Y-%m").date()
    except ValueError:
        return None, api_error("Invalid field: month", status=400)
    return parsed.replace(day=1), None


def _parse_monthly_status(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: status", status=400)
    if parsed not in (0, 1, 2):
        return None, api_error("Invalid field: status", status=400)
    return parsed, None


def _parse_bank_info(value):
    if value in (None, ""):
        return None, None
    if isinstance(value, dict):
        return value, None
    return None, api_error("Invalid field: bank_info", status=400)


def _serialize_monthly_items(items):
    return [PayrollMonthlyCalculation.serialize(item) for item in items]


def _get_attendance_days_map(target_month, employee_ids):
    if not employee_ids:
        return {}
    record_model = get_monthly_attendance_models(target_month)[1]
    records = record_model.objects.filter(
        employee_id__in=employee_ids,
        deleted_at__isnull=True,
    ).order_by("employee_id", "punch_date")
    result = {employee_id: Decimal("0") for employee_id in employee_ids}
    seen = set()
    for record in records:
        if not is_workday(record.punch_date):
            continue
        if record.start_time is None and record.end_time is None:
            continue
        key = (record.employee_id, record.punch_date)
        if key in seen:
            continue
        seen.add(key)
        result[record.employee_id] = result.get(record.employee_id, Decimal("0")) + Decimal("1")
    return result


def _parse_payroll_contract_type(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: contract_type", status=400)
    if parsed not in (0, 1, 2):
        return None, api_error("Invalid field: contract_type", status=400)
    return parsed, None


def _parse_payroll_status(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: status", status=400)
    if parsed not in (0, 1):
        return None, api_error("Invalid field: status", status=400)
    return parsed, None


def _parse_payroll_items(value, field_name):
    if value in (None, ""):
        return [], None
    if not isinstance(value, list):
        return None, api_error(f"Invalid field: {field_name}", status=400)

    result = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            return None, api_error(f"Invalid field: {field_name}", status=400)
        name = (item.get("name") or "").strip()
        raw_amount = item.get("amount")
        if not name and raw_amount in (None, "", 0, "0"):
            continue
        if not name:
            return None, api_error(f"Missing field: {field_name}[{index}].name", status=400)
        try:
            amount = Decimal(str(raw_amount or "0"))
        except Exception:
            return None, api_error(f"Invalid field: {field_name}[{index}].amount", status=400)
        if amount < 0:
            return None, api_error(f"Invalid field: {field_name}[{index}].amount", status=400)
        result.append({"name": name, "amount": str(amount)})
    return result, None


def _sum_payroll_items(items):
    total = Decimal("0")
    for item in items or []:
        try:
            total += Decimal(str(item.get("amount") or "0"))
        except Exception:
            continue
    return total


def _serialize_payroll_basic_items(items):
    employee_ids = [item.employee_id for item in items]
    employees = {
        employee.id: employee
        for employee in Employee.objects.filter(id__in=employee_ids, deleted_at__isnull=True)
    }
    return [
        PayrollBasicInfo.serialize(item, employees.get(item.employee_id))
        for item in items
    ]


@csrf_exempt
@require_http_methods(["GET", "POST"])
def payroll_basic_info_api(request):
    if request.method == "GET":
        employee_id = request.GET.get("employee_id")
        keyword = (request.GET.get("keyword") or "").strip()
        contract_type = request.GET.get("contract_type")
        status = request.GET.get("status")

        qs = PayrollBasicInfo.objects.filter(deleted_at__isnull=True)

        if employee_id not in (None, ""):
            try:
                qs = qs.filter(employee_id=int(employee_id))
            except (TypeError, ValueError):
                return api_error("Invalid employee_id", status=400)

        if contract_type not in (None, ""):
            parsed_contract_type, error = _parse_payroll_contract_type(contract_type)
            if error:
                return error
            qs = qs.filter(contract_type=parsed_contract_type)

        if status not in (None, ""):
            parsed_status, error = _parse_payroll_status(status)
            if error:
                return error
            qs = qs.filter(status=parsed_status)

        if keyword:
            qs = qs.filter(employee_name__icontains=keyword)

        paged, total, page, page_size, total_pages = paginate_queryset(
            qs.order_by("employee_id", "id"),
            request,
        )
        items = _serialize_payroll_basic_items(list(paged))
        return api_paginated(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    login_id, error = require_login(request)
    if error:
        return error

    payload, error = parse_json_body(request)
    if error:
        return error

    employee_id = payload.get("employee_id")
    try:
        employee_id = int(employee_id)
    except (TypeError, ValueError):
        return api_error("Missing field: employee_id")

    employee = Employee.objects.filter(id=employee_id, deleted_at__isnull=True).first()
    if not employee:
        return api_error("Employee not found", status=404)

    if PayrollBasicInfo.objects.filter(employee_id=employee_id, deleted_at__isnull=True).exists():
        return api_error("Payroll basic info already exists", status=409)

    contract_type, error = _parse_payroll_contract_type(payload.get("contract_type", 0))
    if error:
        return error
    status_value, error = _parse_payroll_status(payload.get("status", 1))
    if error:
        return error
    addition_items, error = _parse_payroll_items(payload.get("addition_items"), "addition_items")
    if error:
        return error
    non_taxable_addition_items, error = _parse_payroll_items(
        payload.get("non_taxable_addition_items"),
        "non_taxable_addition_items",
    )
    if error:
        return error
    deduction_items, error = _parse_payroll_items(payload.get("deduction_items"), "deduction_items")
    if error:
        return error
    base_salary, error = _parse_decimal_field(payload, "base_salary")
    if error:
        return error

    item = PayrollBasicInfo.objects.create(
        employee_id=employee_id,
        employee_name=employee.name,
        contract_type=contract_type,
        base_salary=base_salary,
        addition_items=addition_items,
        non_taxable_addition_items=non_taxable_addition_items,
        deduction_items=deduction_items,
        status=status_value,
        remark=(payload.get("remark") or "").strip() or None,
        created_by=login_id,
        updated_by=login_id,
    )
    return api_success(data={"item": PayrollBasicInfo.serialize(item, employee)})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def payroll_basic_info_detail_api(request, payroll_basic_id):
    item = PayrollBasicInfo.objects.filter(id=payroll_basic_id, deleted_at__isnull=True).first()
    if not item:
        return api_error("Payroll basic info not found", status=404)

    if request.method == "GET":
        employee = Employee.objects.filter(id=item.employee_id, deleted_at__isnull=True).first()
        return api_success(data={"item": PayrollBasicInfo.serialize(item, employee)})

    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "DELETE":
        if item.status != 0:
            return api_error(ErrorCode.PAYROLL_BASIC_DELETE_STATUS_INVALID)
        item.deleted_at = timezone.now()
        item.updated_by = login_id
        item.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        return api_success(data={"id": payroll_basic_id})

    payload, error = parse_json_body(request)
    if error:
        return error

    if "contract_type" in payload:
        contract_type, error = _parse_payroll_contract_type(payload.get("contract_type"))
        if error:
            return error
        item.contract_type = contract_type

    if "status" in payload:
        status_value, error = _parse_payroll_status(payload.get("status"))
        if error:
            return error
        item.status = status_value

    if "base_salary" in payload:
        value, error = _parse_decimal_field(payload, "base_salary")
        if error:
            return error
        item.base_salary = value

    if "addition_items" in payload:
        addition_items, error = _parse_payroll_items(payload.get("addition_items"), "addition_items")
        if error:
            return error
        item.addition_items = addition_items

    if "non_taxable_addition_items" in payload:
        non_taxable_addition_items, error = _parse_payroll_items(
            payload.get("non_taxable_addition_items"),
            "non_taxable_addition_items",
        )
        if error:
            return error
        item.non_taxable_addition_items = non_taxable_addition_items

    if "deduction_items" in payload:
        deduction_items, error = _parse_payroll_items(payload.get("deduction_items"), "deduction_items")
        if error:
            return error
        item.deduction_items = deduction_items

    if "remark" in payload:
        item.remark = (payload.get("remark") or "").strip() or None

    item.updated_by = login_id
    item.save()
    employee = Employee.objects.filter(id=item.employee_id, deleted_at__isnull=True).first()
    return api_success(data={"item": PayrollBasicInfo.serialize(item, employee)})


def _apply_monthly_filters(qs, request):
    contract_type = request.GET.get("contract_type")
    keyword = (request.GET.get("keyword") or "").strip()
    if contract_type not in (None, ""):
        parsed_contract_type, error = _parse_payroll_contract_type(contract_type)
        if error:
            return None, error
        qs = qs.filter(contract_type=parsed_contract_type)
    if keyword:
        qs = qs.filter(employee_name__icontains=keyword)
    return qs, None


def _build_monthly_payload(payload, target_month=None):
    values = {}
    if target_month is None:
        target_month, error = _parse_payroll_month(payload.get("month"))
        if error:
            return None, error
    values["payroll_month"] = target_month

    raw_employee_id = payload.get("employee_id")
    if raw_employee_id in (None, ""):
        employee_id = 0
    else:
        try:
            employee_id = int(raw_employee_id)
        except (TypeError, ValueError):
            return None, api_error("Invalid field: employee_id", status=400)
        if employee_id < 0:
            return None, api_error("Invalid field: employee_id", status=400)
    employee_name = (payload.get("employee_name") or "").strip()
    if not employee_name:
        return None, api_error("Missing field: employee_name")
    contract_type, error = _parse_payroll_contract_type(payload.get("contract_type", 0))
    if error:
        return None, error
    status_value, error = _parse_monthly_status(payload.get("status", 0))
    if error:
        return None, error
    bank_info, error = _parse_bank_info(payload.get("bank_info"))
    if error:
        return None, error
    addition_items, error = _parse_payroll_items(payload.get("addition_items"), "addition_items")
    if error:
        return None, error
    non_taxable_addition_items, error = _parse_payroll_items(
        payload.get("non_taxable_addition_items"),
        "non_taxable_addition_items",
    )
    if error:
        return None, error
    deduction_items, error = _parse_payroll_items(payload.get("deduction_items"), "deduction_items")
    if error:
        return None, error

    amount_values = {}
    for field_name in (
        "attendance_days",
        "base_salary",
        "allowance_amount",
        "deduction_amount",
        "social_insurance_amount",
        "net_salary",
    ):
        value, error = _parse_decimal_field(payload, field_name)
        if error:
            return None, error
        amount_values[field_name] = value

    values.update(
        {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "contract_type": contract_type,
            "status": status_value,
            "bank_info": bank_info,
            "addition_items": addition_items,
            "non_taxable_addition_items": non_taxable_addition_items,
            "deduction_items": deduction_items,
            "remark": (payload.get("remark") or "").strip() or None,
            **amount_values,
        }
    )
    return values, None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def payroll_monthly_api(request):
    if request.method == "GET":
        target_month, error = _parse_payroll_month(request.GET.get("month"))
        if error:
            return error
        monthly_objects = PayrollMonthlyCalculation.objects_for_period(target_month)
        base_qs = monthly_objects.filter(
            payroll_month=target_month,
            deleted_at__isnull=True,
        )
        qs, error = _apply_monthly_filters(base_qs, request)
        if error:
            return error
        paged, total, page, page_size, total_pages = paginate_queryset(
            qs.order_by("employee_id", "id"),
            request,
        )
        return api_success(
            data={
                "calculated": base_qs.exists(),
                "items": _serialize_monthly_items(list(paged)),
            },
            meta={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        )

    login_id, error = require_login(request)
    if error:
        return error
    payload, error = parse_json_body(request)
    if error:
        return error
    values, error = _build_monthly_payload(payload)
    if error:
        return error
    monthly_objects = PayrollMonthlyCalculation.objects_for_period(values["payroll_month"])
    if values["employee_id"] and monthly_objects.filter(
            payroll_month=values["payroll_month"],
            employee_id=values["employee_id"],
            deleted_at__isnull=True,
    ).exists():
        return api_error("Payroll monthly calculation already exists", status=409)
    item = PayrollMonthlyCalculation.create_for_period(
        values["payroll_month"],
        created_by=login_id,
        updated_by=login_id,
        **values,
    )
    return api_success(data={"item": PayrollMonthlyCalculation.serialize(item)})


@csrf_exempt
@require_http_methods(["POST"])
def payroll_monthly_calculate_api(request):
    login_id, error = require_login(request)
    if error:
        return error
    payload, error = parse_json_body(request)
    if error:
        return error
    target_month, error = _parse_payroll_month(payload.get("month"))
    if error:
        return error
    monthly_objects = PayrollMonthlyCalculation.objects_for_period(target_month)
    if monthly_objects.filter(
        payroll_month=target_month,
        deleted_at__isnull=True,
    ).exists():
        return api_error("此月份已计算，不能重复计算", status=409)

    basic_items = list(
        PayrollBasicInfo.objects.filter(
            status=1,
            deleted_at__isnull=True,
        ).order_by("employee_id", "id")
    )
    attendance_map = _get_attendance_days_map(target_month, [item.employee_id for item in basic_items])
    created_items = []
    for basic in basic_items:
        addition_items = basic.addition_items or []
        non_taxable_addition_items = basic.non_taxable_addition_items or []
        deduction_items = basic.deduction_items or []
        allowance_amount = _sum_payroll_items(addition_items) + _sum_payroll_items(non_taxable_addition_items)
        deduction_amount = _sum_payroll_items(deduction_items)
        social_insurance_amount = Decimal("0")
        net_salary = basic.base_salary + allowance_amount - deduction_amount - social_insurance_amount
        created_items.append(
            PayrollMonthlyCalculation.build_for_period(
                target_month,
                payroll_month=target_month,
                employee_id=basic.employee_id,
                employee_name=basic.employee_name,
                contract_type=basic.contract_type,
                attendance_days=attendance_map.get(basic.employee_id, Decimal("0")),
                base_salary=basic.base_salary,
                allowance_amount=allowance_amount,
                deduction_amount=deduction_amount,
                addition_items=addition_items,
                non_taxable_addition_items=non_taxable_addition_items,
                deduction_items=deduction_items,
                social_insurance_amount=social_insurance_amount,
                net_salary=net_salary,
                bank_info=None,
                status=0,
                remark=None,
                created_by=login_id,
                updated_by=login_id,
            )
        )
    if created_items:
        PayrollMonthlyCalculation.bulk_create_for_period(target_month, created_items)
    items = list(
        monthly_objects.filter(
            payroll_month=target_month,
            deleted_at__isnull=True,
        ).order_by("employee_id", "id")
    )
    return api_success(
        data={
            "created": len(created_items),
            "items": _serialize_monthly_items(items),
        }
    )


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def payroll_monthly_detail_api(request, calculation_id):
    if request.method == "PUT":
        login_id, error = require_login(request)
        if error:
            return error

        payload, error = parse_json_body(request)
        if error:
            return error
        target_month, error = _parse_payroll_month(payload.get("month"))
        if error:
            return error
    else:
        target_month, error = _parse_payroll_month(request.GET.get("month"))
        if error:
            return error
        payload = None
        login_id = None

    item = PayrollMonthlyCalculation.objects_for_period(target_month).filter(
        id=calculation_id,
        deleted_at__isnull=True,
    ).first()
    if not item:
        return api_error("Payroll monthly calculation not found", status=404)

    if request.method == "GET":
        return api_success(data={"item": PayrollMonthlyCalculation.serialize(item)})

    if request.method == "DELETE":
        login_id, error = require_login(request)
        if error:
            return error
        item.deleted_at = timezone.now()
        item.updated_by = login_id
        item.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        return api_success(data={"id": calculation_id})

    if "contract_type" in payload:
        contract_type, error = _parse_payroll_contract_type(payload.get("contract_type"))
        if error:
            return error
        item.contract_type = contract_type
    if "status" in payload:
        status_value, error = _parse_monthly_status(payload.get("status"))
        if error:
            return error
        item.status = status_value
    if "employee_name" in payload:
        employee_name = (payload.get("employee_name") or "").strip()
        if not employee_name:
            return api_error("Missing field: employee_name")
        item.employee_name = employee_name
    if "bank_info" in payload:
        bank_info, error = _parse_bank_info(payload.get("bank_info"))
        if error:
            return error
        item.bank_info = bank_info
    if "addition_items" in payload:
        addition_items, error = _parse_payroll_items(payload.get("addition_items"), "addition_items")
        if error:
            return error
        item.addition_items = addition_items
    if "non_taxable_addition_items" in payload:
        non_taxable_addition_items, error = _parse_payroll_items(
            payload.get("non_taxable_addition_items"),
            "non_taxable_addition_items",
        )
        if error:
            return error
        item.non_taxable_addition_items = non_taxable_addition_items
    if "deduction_items" in payload:
        deduction_items, error = _parse_payroll_items(payload.get("deduction_items"), "deduction_items")
        if error:
            return error
        item.deduction_items = deduction_items
    if "remark" in payload:
        item.remark = (payload.get("remark") or "").strip() or None

    for field_name in (
        "attendance_days",
        "base_salary",
        "allowance_amount",
        "deduction_amount",
        "social_insurance_amount",
        "net_salary",
    ):
        if field_name in payload:
            value, error = _parse_decimal_field(payload, field_name)
            if error:
                return error
            setattr(item, field_name, value)

    item.updated_by = login_id
    item.save()
    return api_success(data={"item": PayrollMonthlyCalculation.serialize(item)})


@require_GET
def payroll_monthly_export_api(request):
    _login_id, error = require_login(request)
    if error:
        return error
    target_month, error = _parse_payroll_month(request.GET.get("month"))
    if error:
        return error
    qs = PayrollMonthlyCalculation.objects_for_period(target_month).filter(
        payroll_month=target_month,
        deleted_at__isnull=True,
    )
    qs, error = _apply_monthly_filters(qs, request)
    if error:
        return error
    items = list(qs.order_by("employee_id", "id"))

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "月度工资"
    headers = [
        "月份",
        "员工",
        "出勤日数",
        "基本工资",
        "补贴",
        "扣款",
        "社保/年金/保险",
        "实发金额",
        "状态",
    ]
    worksheet.append(headers)
    for item in items:
        serialized = PayrollMonthlyCalculation.serialize(item)
        worksheet.append(
            [
                serialized["month"],
                serialized["employee_name"],
                float(item.attendance_days),
                float(item.base_salary),
                float(item.allowance_amount),
                float(item.deduction_amount),
                float(item.social_insurance_amount),
                float(item.net_salary),
                serialized["status_label"],
            ]
        )
    for column in worksheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        worksheet.column_dimensions[column[0].column_letter].width = min(max(max_length + 2, 10), 24)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    month_label = target_month.strftime("%Y-%m")
    safe_filename = f"payroll_monthly_{month_label}.xlsx"
    display_filename = f"月度工资_{month_label}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f"attachment; filename=\"{safe_filename}\"; filename*=UTF-8''{quote(display_filename)}"
    )
    return response
