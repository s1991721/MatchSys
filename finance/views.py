from datetime import datetime
from decimal import Decimal
from io import BytesIO
from urllib.parse import quote

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from openpyxl import Workbook

from attendance.models import get_monthly_attendance_models
from employee.models import Employee
from project.api import api_error, api_paginated, api_success
from project.common_tools import is_workday, paginate_queryset, parse_date, parse_json_body, require_login
from .models import PayrollBasicInfo, PayrollMonthlyCalculation


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
        employee_name=employee.name,
        contract_type=contract_type,
        valid_until_date=valid_until_date,
        status=status_value,
        remark=(payload.get("remark") or "").strip() or None,
        created_by=login_id,
        updated_by=login_id,
        **amount_values,
    )
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
        allowance_amount = Decimal("0")
        deduction_amount = basic.income_tax
        social_insurance_amount = (
            basic.health_insurance
            + basic.welfare_pension
            + basic.employment_insurance
        )
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
