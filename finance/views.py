from decimal import Decimal

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from employee.models import Employee
from project.api import api_error, api_paginated, api_success
from project.common_tools import paginate_queryset, parse_date, parse_json_body, require_login
from .models import PayrollBasicInfo


def _parse_decimal_field(payload, field_name):
    value = payload.get(field_name)
    if value in (None, ""):
        return Decimal("0"), None
    try:
        parsed = Decimal(str(value))
    except Exception:
        return None, api_error(f"Invalid field: {field_name}", status=400)
    if parsed < 0:
        return None, api_error(f"Invalid field: {field_name}", status=400)
    return parsed, None


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
            matching_ids = Employee.objects.filter(
                deleted_at__isnull=True,
                name__icontains=keyword,
            ).values_list("id", flat=True)
            qs = qs.filter(employee_id__in=matching_ids)

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

    if not Employee.objects.filter(id=employee_id, deleted_at__isnull=True).exists():
        return api_error("Employee not found", status=404)

    if PayrollBasicInfo.objects.filter(employee_id=employee_id, deleted_at__isnull=True).exists():
        return api_error("Payroll basic info already exists", status=409)

    contract_type, error = _parse_payroll_contract_type(payload.get("contract_type", 0))
    if error:
        return error
    status_value, error = _parse_payroll_status(payload.get("status", 1))
    if error:
        return error
    valid_until_date, error = parse_date(payload.get("valid_until_date"), "valid_until_date")
    if error:
        return error

    amount_values = {}
    for field_name in (
        "base_salary",
        "health_insurance",
        "welfare_pension",
        "employment_insurance",
        "income_tax",
    ):
        value, error = _parse_decimal_field(payload, field_name)
        if error:
            return error
        amount_values[field_name] = value

    item = PayrollBasicInfo.objects.create(
        employee_id=employee_id,
        contract_type=contract_type,
        valid_until_date=valid_until_date,
        status=status_value,
        remark=(payload.get("remark") or "").strip() or None,
        created_by=login_id,
        updated_by=login_id,
        **amount_values,
    )
    employee = Employee.objects.filter(id=item.employee_id, deleted_at__isnull=True).first()
    return api_success(data={"item": PayrollBasicInfo.serialize(item, employee)})


@csrf_exempt
@require_http_methods(["GET", "PUT"])
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

    if "valid_until_date" in payload:
        valid_until_date, error = parse_date(payload.get("valid_until_date"), "valid_until_date")
        if error:
            return error
        item.valid_until_date = valid_until_date

    for field_name in (
        "base_salary",
        "health_insurance",
        "welfare_pension",
        "employment_insurance",
        "income_tax",
    ):
        if field_name in payload:
            value, error = _parse_decimal_field(payload, field_name)
            if error:
                return error
            setattr(item, field_name, value)

    if "remark" in payload:
        item.remark = (payload.get("remark") or "").strip() or None

    item.updated_by = login_id
    item.save()
    employee = Employee.objects.filter(id=item.employee_id, deleted_at__isnull=True).first()
    return api_success(data={"item": PayrollBasicInfo.serialize(item, employee)})
