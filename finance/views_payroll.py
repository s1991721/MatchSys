"""工资计算 API 视图模块。"""

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from attendance.models import get_monthly_attendance_models
from employee.models import Employee
from project.api import api_error, api_paginated, api_success
from project.common_tools import is_workday, paginate_queryset, parse_json_body, require_login, shift_month
from project.error_codes import ErrorCode
from .models import FinanceSettings, PayrollBasicInfo, PayrollMonthlyCalculation
from .views_common import _parse_decimal_field
from .views_settings import (
    FINANCE_ANNUITY_SETTING_NAME,
    FINANCE_INCOME_TAX_SETTING_NAME,
    FINANCE_PAYROLL_EMPLOYMENT_SETTING_NAME,
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


def _parse_payroll_withholding_tax_type(value):
    if value in (None, ""):
        return None, api_error("Missing field: withholding_tax_type", status=400)
    parsed = str(value).strip()
    if parsed not in ("kou", "otsu"):
        return None, api_error("Invalid field: withholding_tax_type", status=400)
    return parsed, None


def _parse_payroll_dependent_count(value):
    if value in (None, ""):
        return None, api_error("Missing field: dependent_count", status=400)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: dependent_count", status=400)
    if parsed < 0 or parsed > 7:
        return None, api_error("Invalid field: dependent_count", status=400)
    return parsed, None


def _parse_payroll_items(value, field_name, omit_zero=False):
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
        if omit_zero and amount == 0:
            continue
        parsed_item = {"name": name, "amount": str(amount)}
        if item.get("payroll_calculated") is True:
            parsed_item["payroll_calculated"] = True
        if item.get("calculation_group") in ("fixed", "variable"):
            parsed_item["calculation_group"] = item.get("calculation_group")
        calculation_key = str(item.get("calculation_key") or "").strip()
        if calculation_key:
            parsed_item["calculation_key"] = calculation_key
        if item.get("calculation_rate") not in (None, ""):
            rate = _decimal_from_setting(item.get("calculation_rate"))
            parsed_item["calculation_rate"] = str(rate)
        calculation_base_label = str(item.get("calculation_base_label") or "").strip()
        if calculation_base_label:
            parsed_item["calculation_base_label"] = calculation_base_label
        result.append(parsed_item)
    return result, None


def _sum_payroll_items(items):
    total = Decimal("0")
    for item in items or []:
        try:
            total += Decimal(str(item.get("amount") or "0"))
        except Exception:
            continue
    return total


PAYROLL_EMPLOYMENT_INSURANCE_NAME = "雇佣保险料"
PAYROLL_EMPLOYMENT_INSURANCE_KEY = "employmentInsurance"
PAYROLL_VARIABLE_DEDUCTION_NAMES = {PAYROLL_EMPLOYMENT_INSURANCE_NAME, "所得税"}
PAYROLL_FIXED_DEDUCTION_EMPLOYEE_SHARE = Decimal("0.5")
PAYROLL_CARE_INSURANCE_MIN_AGE = 40
PAYROLL_INCOME_TAX_NAME = "所得税"
PAYROLL_INCOME_TAX_KEY = "incomeTax"


def _round_payroll_amount(value):
    return Decimal(value or "0").quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _decimal_from_setting(value, default="0"):
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except Exception:
        return Decimal(default)


def _annuity_tax_item_names(settings):
    if not settings:
        return set()
    return {
        str(item.get("name") or "").strip()
        for item in settings.get("tax_items") or []
        if str(item.get("name") or "").strip()
    }


def _strip_calculated_payroll_items(items, annuity_settings=None):
    annuity_names = _annuity_tax_item_names(annuity_settings)
    return [
        item for item in (items or [])
        if item.get("payroll_calculated") is not True
        and item.get("calculation_group") not in ("fixed", "variable")
        and (item.get("name") or "").strip() not in PAYROLL_VARIABLE_DEDUCTION_NAMES
        and (item.get("name") or "").strip() not in annuity_names
    ]


def _get_annuity_settings():
    record = (
        FinanceSettings.objects
        .filter(name=FINANCE_ANNUITY_SETTING_NAME, deleted_at__isnull=True)
        .order_by("id")
        .first()
    )
    return record.settings if record and isinstance(record.settings, dict) else None


def _get_income_tax_settings():
    record = (
        FinanceSettings.objects
        .filter(name=FINANCE_INCOME_TAX_SETTING_NAME, deleted_at__isnull=True)
        .order_by("id")
        .first()
    )
    return record.settings if record and isinstance(record.settings, dict) else None


def _get_payroll_employment_insurance_settings():
    record = (
        FinanceSettings.objects
        .filter(name=FINANCE_PAYROLL_EMPLOYMENT_SETTING_NAME, deleted_at__isnull=True)
        .order_by("id")
        .first()
    )
    return record.settings if record and isinstance(record.settings, dict) else None


def _get_payroll_employment_insurance_employee_rate():
    settings = _get_payroll_employment_insurance_settings() or {}
    rate = _decimal_from_setting(settings.get("employee_rate"))
    if rate < 0 or rate > 1:
        return Decimal("0")
    return rate


def _find_annuity_standard(settings, remuneration_base):
    if not settings:
        return None
    rows = settings.get("base_standards")
    if not isinstance(rows, list):
        return None
    valid_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        valid_rows.append(row)
        salary_min = _decimal_from_setting(row.get("salary_min", row.get("min_salary")))
        salary_max = _decimal_from_setting(row.get("salary_max", row.get("max_salary")))
        upper_matches = salary_max <= 0 or remuneration_base < salary_max
        if remuneration_base >= salary_min and upper_matches:
            return row
    if not valid_rows:
        return None
    valid_rows.sort(key=lambda item: _decimal_from_setting(item.get("salary_min", item.get("min_salary"))))
    first = valid_rows[0]
    if remuneration_base < _decimal_from_setting(first.get("salary_min", first.get("min_salary"))):
        return first
    return valid_rows[-1]


def _find_annuity_amount_override(settings, grade, tax_item_key):
    if not settings or grade in (None, "") or not tax_item_key:
        return None
    for item in settings.get("amount_overrides") or []:
        if str(item.get("grade")) == str(grade) and str(item.get("tax_item_key") or item.get("key") or "") == str(tax_item_key):
            return _decimal_from_setting(item.get("amount"))
    return None


def _age_at(birthday, target_date):
    if not birthday or not target_date:
        return None
    return target_date.year - birthday.year - (
        (target_date.month, target_date.day) < (birthday.month, birthday.day)
    )


def _get_employee_birthday(source, overrides=None):
    employee_id = (overrides or {}).get("employee_id", getattr(source, "employee_id", None))
    if not employee_id:
        return None
    return (
        Employee.objects
        .filter(id=employee_id, deleted_at__isnull=True)
        .values_list("birthday", flat=True)
        .first()
    )


def _is_care_insurance_tax_item(tax_item):
    key = str(tax_item.get("key") or "").strip().lower()
    name = str(tax_item.get("name") or "").strip()
    return "care" in key or "介護" in name or "介护" in name


def _should_apply_care_insurance(tax_item, birthday, target_month):
    if not _is_care_insurance_tax_item(tax_item):
        return True
    if not birthday or not target_month:
        return False
    month_end = shift_month(target_month, 1) - timedelta(days=1)
    age = _age_at(birthday, month_end)
    return age is not None and age >= PAYROLL_CARE_INSURANCE_MIN_AGE


def _calculate_annuity_tax_item_total_amount(settings, standard_row, tax_item):
    if not standard_row:
        return Decimal("0")
    standard_salary = _decimal_from_setting(standard_row.get("monthly_amount", standard_row.get("standard_salary")))
    override = _find_annuity_amount_override(
        settings,
        standard_row.get("grade"),
        tax_item.get("key"),
    )
    if override is not None:
        return _round_payroll_amount(override)
    return _round_payroll_amount(standard_salary * _decimal_from_setting(tax_item.get("rate")))


def _calculate_annuity_tax_item_employee_amount(settings, standard_row, tax_item, birthday=None, target_month=None):
    if not _should_apply_care_insurance(tax_item, birthday, target_month):
        return Decimal("0")
    total_amount = _calculate_annuity_tax_item_total_amount(settings, standard_row, tax_item)
    return _round_payroll_amount(total_amount * PAYROLL_FIXED_DEDUCTION_EMPLOYEE_SHARE)


def _calculate_annuity_tax_item_employee_rate(tax_item):
    return _decimal_from_setting(tax_item.get("rate")) * PAYROLL_FIXED_DEDUCTION_EMPLOYEE_SHARE


def _get_payroll_withholding_info(source, overrides=None):
    overrides = overrides or {}
    withholding_tax_type = overrides.get("withholding_tax_type", getattr(source, "withholding_tax_type", None))
    dependent_count = overrides.get("dependent_count", getattr(source, "dependent_count", None))

    if withholding_tax_type in (None, "") or dependent_count in (None, ""):
        employee_id = overrides.get("employee_id", getattr(source, "employee_id", None))
        basic = None
        if employee_id:
            basic = (
                PayrollBasicInfo.objects
                .filter(employee_id=employee_id, deleted_at__isnull=True)
                .order_by("id")
                .first()
            )
        if basic:
            withholding_tax_type = basic.withholding_tax_type
            dependent_count = basic.dependent_count

    withholding_tax_type = "otsu" if withholding_tax_type == "otsu" else "kou"
    try:
        dependent_count = int(dependent_count)
    except (TypeError, ValueError):
        dependent_count = 0
    dependent_count = max(0, min(7, dependent_count))
    if withholding_tax_type == "otsu":
        dependent_count = 0
    return withholding_tax_type, dependent_count


def _find_income_tax_monthly_row(settings, taxable_salary_after_deductions):
    if not settings:
        return None
    rows = settings.get("monthly_rows")
    if not isinstance(rows, list):
        return None
    valid_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        valid_rows.append(row)
        salary_min = _decimal_from_setting(row.get("salary_min"))
        salary_max = _decimal_from_setting(row.get("salary_max"))
        if taxable_salary_after_deductions >= salary_min and taxable_salary_after_deductions < salary_max:
            return row
    if not valid_rows:
        return None
    valid_rows.sort(key=lambda item: _decimal_from_setting(item.get("salary_min")))
    first = valid_rows[0]
    if taxable_salary_after_deductions < _decimal_from_setting(first.get("salary_min")):
        return first
    return valid_rows[-1]


def _calculate_income_tax_amount(settings, taxable_salary_after_deductions, withholding_tax_type, dependent_count):
    row = _find_income_tax_monthly_row(settings, taxable_salary_after_deductions)
    if not row:
        return Decimal("0")
    column = "otsu" if withholding_tax_type == "otsu" else f"kou_{dependent_count}"
    return _round_payroll_amount(_decimal_from_setting(row.get(column)))


def _build_payroll_calculation_values(source, target_month=None, overrides=None):
    overrides = overrides or {}
    base_salary = overrides.get("base_salary", getattr(source, "base_salary", Decimal("0")))
    addition_items = overrides.get("addition_items", getattr(source, "addition_items", None) or [])
    non_taxable_addition_items = overrides.get(
        "non_taxable_addition_items",
        getattr(source, "non_taxable_addition_items", None) or [],
    )
    annuity_settings = _get_annuity_settings()
    income_tax_settings = _get_income_tax_settings()
    manual_deduction_items = _strip_calculated_payroll_items(
        overrides.get("deduction_items", getattr(source, "deduction_items", None) or []),
        annuity_settings=annuity_settings,
    )

    addition_total = _sum_payroll_items(addition_items)
    non_taxable_addition_total = _sum_payroll_items(non_taxable_addition_items)
    manual_deduction_total = _sum_payroll_items(manual_deduction_items)
    taxable_salary = base_salary + addition_total
    gross_salary = base_salary + addition_total + non_taxable_addition_total
    remuneration_base = max(Decimal("0"), gross_salary - manual_deduction_total)

    annuity_standard = _find_annuity_standard(annuity_settings, base_salary)
    employee_birthday = _get_employee_birthday(source, overrides)
    withholding_tax_type, dependent_count = _get_payroll_withholding_info(source, overrides)
    calculated_items = []
    first_stage_total = Decimal("0")
    employment_amount = Decimal("0")

    if annuity_settings:
        annuity_tax_items = annuity_settings.get("tax_items") or []
    else:
        annuity_tax_items = []
    for tax_item in annuity_tax_items:
        tax_item_name = str(tax_item.get("name") or "").strip()
        if not tax_item_name:
            continue
        amount = _calculate_annuity_tax_item_employee_amount(
            annuity_settings,
            annuity_standard,
            tax_item,
            birthday=employee_birthday,
            target_month=target_month,
        )
        first_stage_total += amount
        calculated_items.append({
            "name": tax_item_name,
            "amount": str(amount),
            "payroll_calculated": True,
            "calculation_group": "fixed",
            "calculation_key": str(tax_item.get("key") or ""),
            "calculation_rate": str(_calculate_annuity_tax_item_employee_rate(tax_item)),
        })

    employment_rate = _get_payroll_employment_insurance_employee_rate()
    employment_amount = _round_payroll_amount(
        remuneration_base * employment_rate
    )
    calculated_items.append({
        "name": PAYROLL_EMPLOYMENT_INSURANCE_NAME,
        "amount": str(employment_amount),
        "payroll_calculated": True,
        "calculation_group": "variable",
        "calculation_key": PAYROLL_EMPLOYMENT_INSURANCE_KEY,
        "calculation_rate": str(employment_rate),
        "calculation_base_label": "賃金総額",
    })

    income_tax_base = max(Decimal("0"), taxable_salary - first_stage_total - employment_amount)
    income_tax_amount = _calculate_income_tax_amount(
        income_tax_settings,
        income_tax_base,
        withholding_tax_type,
        dependent_count,
    )
    calculated_items.append({
        "name": PAYROLL_INCOME_TAX_NAME,
        "amount": str(income_tax_amount),
        "payroll_calculated": True,
        "calculation_group": "variable",
        "calculation_key": PAYROLL_INCOME_TAX_KEY,
        "calculation_base_label": "源泉税表",
    })

    calculated_total = _sum_payroll_items(calculated_items)
    allowance_amount = addition_total + non_taxable_addition_total
    net_salary = base_salary + allowance_amount - manual_deduction_total - calculated_total

    values = {
        "base_salary": base_salary,
        "withholding_tax_type": withholding_tax_type,
        "dependent_count": dependent_count,
        "allowance_amount": allowance_amount,
        "deduction_amount": manual_deduction_total,
        "addition_items": addition_items,
        "non_taxable_addition_items": non_taxable_addition_items,
        "deduction_items": manual_deduction_items,
        "automatic_deduction_items": calculated_items,
        "automatic_deduction_amount": calculated_total,
        "net_salary": net_salary,
    }
    if target_month is not None:
        values["payroll_month"] = target_month
    return values


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
    withholding_tax_type, error = _parse_payroll_withholding_tax_type(payload.get("withholding_tax_type"))
    if error:
        return error
    dependent_count, error = _parse_payroll_dependent_count(payload.get("dependent_count"))
    if error:
        return error
    if withholding_tax_type == "otsu":
        dependent_count = 0
    addition_items, error = _parse_payroll_items(payload.get("addition_items"), "addition_items", omit_zero=True)
    if error:
        return error
    non_taxable_addition_items, error = _parse_payroll_items(
        payload.get("non_taxable_addition_items"),
        "non_taxable_addition_items",
        omit_zero=True,
    )
    if error:
        return error
    deduction_items, error = _parse_payroll_items(payload.get("deduction_items"), "deduction_items", omit_zero=True)
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
        withholding_tax_type=withholding_tax_type,
        dependent_count=dependent_count,
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

    if "withholding_tax_type" in payload:
        withholding_tax_type, error = _parse_payroll_withholding_tax_type(payload.get("withholding_tax_type"))
        if error:
            return error
        item.withholding_tax_type = withholding_tax_type

    if "dependent_count" in payload:
        dependent_count, error = _parse_payroll_dependent_count(payload.get("dependent_count"))
        if error:
            return error
        item.dependent_count = dependent_count

    if "addition_items" in payload:
        addition_items, error = _parse_payroll_items(payload.get("addition_items"), "addition_items", omit_zero=True)
        if error:
            return error
        item.addition_items = addition_items

    if "non_taxable_addition_items" in payload:
        non_taxable_addition_items, error = _parse_payroll_items(
            payload.get("non_taxable_addition_items"),
            "non_taxable_addition_items",
            omit_zero=True,
        )
        if error:
            return error
        item.non_taxable_addition_items = non_taxable_addition_items

    if "deduction_items" in payload:
        deduction_items, error = _parse_payroll_items(payload.get("deduction_items"), "deduction_items", omit_zero=True)
        if error:
            return error
        item.deduction_items = deduction_items

    if "remark" in payload:
        item.remark = (payload.get("remark") or "").strip() or None

    if item.withholding_tax_type == "otsu":
        item.dependent_count = 0

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
    automatic_deduction_items, error = _parse_payroll_items(
        payload.get("automatic_deduction_items"),
        "automatic_deduction_items",
    )
    if error:
        return None, error

    amount_values = {}
    for field_name in (
        "attendance_days",
        "base_salary",
        "allowance_amount",
        "deduction_amount",
        "automatic_deduction_amount",
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
            "automatic_deduction_items": automatic_deduction_items,
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
    withholding_tax_type, dependent_count = _get_payroll_withholding_info(
        None,
        overrides={"employee_id": values["employee_id"]},
    )
    values["withholding_tax_type"] = withholding_tax_type
    values["dependent_count"] = dependent_count
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
        calculated_values = _build_payroll_calculation_values(basic, target_month=target_month)
        created_items.append(
            PayrollMonthlyCalculation.build_for_period(
                target_month,
                employee_id=basic.employee_id,
                employee_name=basic.employee_name,
                contract_type=basic.contract_type,
                attendance_days=attendance_map.get(basic.employee_id, Decimal("0")),
                bank_info=None,
                status=0,
                remark=None,
                created_by=login_id,
                updated_by=login_id,
                **calculated_values,
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
@require_http_methods(["POST"])
def payroll_monthly_recalculate_api(request, calculation_id):
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
    item = monthly_objects.filter(
        id=calculation_id,
        payroll_month=target_month,
        deleted_at__isnull=True,
    ).first()
    if not item:
        return api_error("Payroll monthly calculation not found", status=404)

    values, error = _build_monthly_payload(payload, target_month=target_month)
    if error:
        return error
    calculated_values = _build_payroll_calculation_values(item, target_month=target_month, overrides=values)
    for key, value in calculated_values.items():
        setattr(item, key, value)
    item.employee_id = values["employee_id"]
    item.employee_name = values["employee_name"]
    item.contract_type = values["contract_type"]
    item.attendance_days = values["attendance_days"]
    item.status = values["status"]
    item.bank_info = values["bank_info"]
    item.remark = values["remark"]
    item.updated_by = login_id
    item.save()
    return api_success(data={"item": PayrollMonthlyCalculation.serialize(item)})


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
    if "automatic_deduction_items" in payload:
        automatic_deduction_items, error = _parse_payroll_items(
            payload.get("automatic_deduction_items"),
            "automatic_deduction_items",
        )
        if error:
            return error
        item.automatic_deduction_items = automatic_deduction_items
    if "remark" in payload:
        item.remark = (payload.get("remark") or "").strip() or None

    for field_name in (
        "attendance_days",
        "base_salary",
        "allowance_amount",
        "deduction_amount",
        "automatic_deduction_amount",
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
