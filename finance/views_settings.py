"""财务设置 API 视图模块。"""

from decimal import Decimal

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from project.api import api_error, api_success
from project.common_tools import parse_json_body, require_login
from project.error_codes import ErrorCode
from .models import FinanceSettings

FINANCE_ANNUITY_SETTING_NAME = "annuity_insurance"
FINANCE_EMPLOYMENT_SETTING_NAME = "employment_insurance"
FINANCE_INCOME_TAX_SETTING_NAME = "income_tax"
FINANCE_PAYROLL_EMPLOYMENT_SETTING_NAME = "payroll_employment_insurance"
INCOME_TAX_MONTHLY_COLUMNS = (
    "salary_min",
    "salary_max",
    "kou_0",
    "kou_1",
    "kou_2",
    "kou_3",
    "kou_4",
    "kou_5",
    "kou_6",
    "kou_7",
    "otsu",
)
FINANCE_PAYROLL_BASIC_ITEMS_SETTING_NAME = "payroll_basic_items"
PAYROLL_BASIC_ITEM_CATEGORIES = (
    "increase_items",
    "non_taxable_increase_items",
    "decrease_items",
)

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


def _parse_json_integer(value, field_name, allow_zero=True):
    if value in (None, ""):
        return None, _finance_settings_payload_error(f"Missing field: {field_name}")
    try:
        parsed = Decimal(str(value).replace(",", "").strip())
    except Exception:
        return None, _finance_settings_payload_error(f"Invalid field: {field_name}")
    if not parsed.is_finite() or parsed != parsed.to_integral_value():
        return None, _finance_settings_payload_error(f"Invalid field: {field_name}")
    parsed = int(parsed)
    if parsed < 0 or (not allow_zero and parsed == 0):
        return None, _finance_settings_payload_error(f"Invalid field: {field_name}")
    return parsed, None


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

        remark = str(item.get("remark") or item.get("note") or "").strip()
        items.append({
            "key": key,
            "name": name,
            "remark": remark,
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


def _unwrap_income_tax_settings_payload(payload):
    if not isinstance(payload, dict):
        return None, _finance_settings_payload_error("Invalid income tax settings")
    if isinstance(payload.get("settings"), dict):
        return payload["settings"], None
    if isinstance(payload.get(FINANCE_INCOME_TAX_SETTING_NAME), dict):
        return payload[FINANCE_INCOME_TAX_SETTING_NAME], None
    return payload, None


def _normalize_income_tax_metadata(value):
    if not isinstance(value, dict):
        return None, _finance_settings_payload_error("Missing field: metadata")

    year, error = _parse_json_integer(value.get("year"), "metadata.year", allow_zero=False)
    if error:
        return None, error

    table_type = str(value.get("table_type") or "").strip()
    if table_type != "monthly":
        return None, _finance_settings_payload_error("Invalid field: metadata.table_type")

    columns = value.get("columns")
    if not isinstance(columns, list) or tuple(columns) != INCOME_TAX_MONTHLY_COLUMNS:
        return None, _finance_settings_payload_error("Invalid field: metadata.columns")

    row_count, error = _parse_json_integer(value.get("row_count"), "metadata.row_count")
    if error:
        return None, error

    return {
        "year": year,
        "table_type": table_type,
        "columns": list(INCOME_TAX_MONTHLY_COLUMNS),
        "row_count": row_count,
    }, None


def _normalize_income_tax_monthly_rows(value):
    if not isinstance(value, list):
        return None, _finance_settings_payload_error("Invalid field: monthly_rows")

    rows = []
    seen_orders = set()
    previous_max = None
    tax_columns = INCOME_TAX_MONTHLY_COLUMNS[2:]
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            return None, _finance_settings_payload_error(f"Invalid field: monthly_rows[{index}]")

        row_order, error = _parse_json_integer(item.get("row_order"), f"monthly_rows[{index}].row_order", allow_zero=False)
        if error:
            return None, error
        if row_order in seen_orders:
            return None, _finance_settings_payload_error(f"Duplicate row_order: {row_order}")
        seen_orders.add(row_order)

        salary_min, error = _parse_json_integer(item.get("salary_min"), f"monthly_rows[{index}].salary_min")
        if error:
            return None, error
        salary_max, error = _parse_json_integer(item.get("salary_max"), f"monthly_rows[{index}].salary_max")
        if error:
            return None, error
        if salary_max <= salary_min:
            return None, _finance_settings_payload_error(f"Invalid salary range in monthly_rows[{index}]")
        if previous_max is not None and salary_min < previous_max:
            return None, _finance_settings_payload_error(f"Overlapping salary range in monthly_rows[{index}]")
        previous_max = salary_max

        row = {
            "row_order": row_order,
            "salary_min": salary_min,
            "salary_max": salary_max,
        }
        for column in tax_columns:
            amount, error = _parse_json_integer(item.get(column), f"monthly_rows[{index}].{column}")
            if error:
                return None, error
            row[column] = amount
        rows.append(row)

    return rows, None


def _normalize_income_tax_settings(payload):
    settings_payload, error = _unwrap_income_tax_settings_payload(payload)
    if error:
        return None, error

    metadata, error = _normalize_income_tax_metadata(settings_payload.get("metadata"))
    if error:
        return None, error
    monthly_rows, error = _normalize_income_tax_monthly_rows(settings_payload.get("monthly_rows"))
    if error:
        return None, error

    return {
        "metadata": metadata,
        "monthly_rows": monthly_rows,
    }, None


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
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "GET":
        record = (
            FinanceSettings.objects
            .filter(name=FINANCE_INCOME_TAX_SETTING_NAME, deleted_at__isnull=True)
            .order_by("id")
            .first()
        )
        return api_success(data={
            "name": FINANCE_INCOME_TAX_SETTING_NAME,
            "settings": record.settings if record else None,
        })

    payload, error = parse_json_body(request)
    if error:
        return error
    settings_payload, error = _normalize_income_tax_settings(payload)
    if error:
        return error

    with transaction.atomic():
        record = (
            FinanceSettings.objects
            .select_for_update()
            .filter(name=FINANCE_INCOME_TAX_SETTING_NAME, deleted_at__isnull=True)
            .order_by("id")
            .first()
        )
        if record:
            record.settings = settings_payload
            record.updated_by = login_id
            record.save(update_fields=["settings", "updated_by", "updated_at"])
        else:
            record = FinanceSettings.objects.create(
                name=FINANCE_INCOME_TAX_SETTING_NAME,
                settings=settings_payload,
                created_by=login_id,
                updated_by=login_id,
            )

    return api_success(data={
        "name": record.name,
        "settings": record.settings,
    })


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


def _normalize_payroll_employment_rate_settings(payload):
    if not isinstance(payload, dict):
        return None, _finance_settings_payload_error("Invalid employment insurance settings")
    source = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload

    employee_rate, error = _parse_json_decimal(
        source.get("employee_rate"),
        "employee_rate",
    )
    if error:
        return None, error
    company_rate, error = _parse_json_decimal(
        source.get("company_rate"),
        "company_rate",
    )
    if error:
        return None, error
    if employee_rate > 1:
        return None, _finance_settings_payload_error("Invalid field: employee_rate")
    if company_rate > 1:
        return None, _finance_settings_payload_error("Invalid field: company_rate")

    return {
        "employee_rate": _decimal_to_json_number(employee_rate),
        "company_rate": _decimal_to_json_number(company_rate),
    }, None


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


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_payroll_employment_insurance_settings_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "GET":
        record = (
            FinanceSettings.objects
            .filter(name=FINANCE_PAYROLL_EMPLOYMENT_SETTING_NAME, deleted_at__isnull=True)
            .order_by("id")
            .first()
        )
        settings = None
        if record:
            settings, _ = _normalize_payroll_employment_rate_settings(record.settings)
        return api_success(data={
            "name": FINANCE_PAYROLL_EMPLOYMENT_SETTING_NAME,
            "settings": settings,
        })

    payload, error = parse_json_body(request)
    if error:
        return error
    settings, error = _normalize_payroll_employment_rate_settings(payload)
    if error:
        return error

    with transaction.atomic():
        record = (
            FinanceSettings.objects
            .select_for_update()
            .filter(name=FINANCE_PAYROLL_EMPLOYMENT_SETTING_NAME, deleted_at__isnull=True)
            .order_by("id")
            .first()
        )
        if record:
            record.settings = settings
            record.updated_by = login_id
            record.save(update_fields=["settings", "updated_by", "updated_at"])
        else:
            record = FinanceSettings.objects.create(
                name=FINANCE_PAYROLL_EMPLOYMENT_SETTING_NAME,
                settings=settings,
                created_by=login_id,
                updated_by=login_id,
            )

    return api_success(data={
        "name": record.name,
        "settings": record.settings,
    })
