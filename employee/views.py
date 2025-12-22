import json
from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .models import Employee, UserLogin


@csrf_exempt
@require_POST
def login_api(request):
    user_name = ""
    password = ""

    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        user_name = (payload.get("user_name") or "").strip()
        password = payload.get("password") or ""
    else:
        user_name = (request.POST.get("user_name") or "").strip()
        password = request.POST.get("password") or ""

    if not user_name or not password:
        return JsonResponse({"error": "Missing user_name or password"}, status=400)

    user_login = (
        UserLogin.objects.select_related("employee")
        .filter(
            user_name=user_name,
            deleted_at__isnull=True,
            employee__deleted_at__isnull=True,
            employee__status=1,
        )
        .first()
    )

    if not user_login or user_login.password != password:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    request.session.cycle_key()
    request.session["employee_id"] = user_login.employee_id
    request.session["employee_name"] = user_login.employee.name
    request.session["user_name"] = user_login.user_name

    return JsonResponse(
        {
            "status": "ok",
            "employee": {
                "id": user_login.employee_id,
                "name": user_login.employee.name,
            },
            "redirect": "index.html",
        }
    )


def _parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)


def _parse_date(value, field):
    if value in (None, ""):
        return None, None
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date(), None
        except ValueError:
            return None, JsonResponse({"error": f"Invalid date: {field}"}, status=400)
    return None, JsonResponse({"error": f"Invalid date: {field}"}, status=400)


def _normalize_status(value):
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    raw = str(value).strip().lower()
    mapping = {"active": 1, "leave": 0, "disabled": 2}
    if raw in mapping:
        return mapping[raw]
    try:
        return int(raw)
    except ValueError:
        return None


def _serialize_employee(emp):
    if emp.status == 1:
        status_key = "active"
        status_label = "在岗"
    elif emp.status == 0:
        status_key = "leave"
        status_label = "离职"
    else:
        status_key = "disabled"
        status_label = "停用"

    return {
        "id": emp.id,
        "name": emp.name,
        "gender": emp.gender,
        "birthday": emp.birthday.isoformat() if emp.birthday else "",
        "department": emp.department_name or "",
        "position": emp.position_name or "",
        "phone": emp.phone or "",
        "email": emp.email or "",
        "address": emp.address or "",
        "emergency_contact_name": emp.emergency_contact_name or "",
        "emergency_contact_phone": emp.emergency_contact_phone or "",
        "emergency_contact_relationship": emp.emergency_contact_relationship or "",
        "hire_date": emp.hire_date.isoformat() if emp.hire_date else "",
        "leave_date": emp.leave_date.isoformat() if emp.leave_date else "",
        "status": status_key,
        "status_label": status_label,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def employees_api(request):
    if request.method == "POST":
        payload, error = _parse_json_body(request)
        if error:
            return error

        name = (payload.get("name") or "").strip()
        if not name:
            return JsonResponse({"error": "Missing field: name"}, status=400)

        email = (payload.get("email") or "").strip()
        if not email:
            return JsonResponse({"error": "Missing field: email"}, status=400)

        if UserLogin.objects.filter(user_name=email, deleted_at__isnull=True).exists():
            return JsonResponse({"error": "User login already exists"}, status=400)

        status = _normalize_status(payload.get("status"))
        if status is None:
            status = 1

        hire_date, error = _parse_date(payload.get("hire_date"), "hire_date")
        if error:
            return error
        leave_date, error = _parse_date(payload.get("leave_date"), "leave_date")
        if error:
            return error
        birthday, error = _parse_date(payload.get("birthday"), "birthday")
        if error:
            return error

        with transaction.atomic():
            employee = Employee.objects.create(
                name=name,
                gender=payload.get("gender") or None,
                birthday=birthday,
                phone=(payload.get("phone") or "").strip() or None,
                email=email,
                address=(payload.get("address") or "").strip() or None,
                emergency_contact_name=(payload.get("emergency_contact_name") or "").strip() or None,
                emergency_contact_phone=(payload.get("emergency_contact_phone") or "").strip() or None,
                emergency_contact_relationship=(payload.get("emergency_contact_relationship") or "").strip()
                or None,
                hire_date=hire_date,
                leave_date=leave_date,
                department_name=(payload.get("department") or payload.get("department_name") or "").strip()
                or None,
                position_name=(payload.get("position") or payload.get("position_name") or "").strip()
                or None,
                status=status,
            )
            UserLogin.objects.create(
                employee=employee,
                user_name=email,
                password="123456",
            )

        return JsonResponse({"status": "ok", "item": _serialize_employee(employee)})

    keyword = (request.GET.get("keyword") or "").strip()
    department = (request.GET.get("department") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = Employee.objects.filter(deleted_at__isnull=True)

    if keyword:
        qs = qs.filter(
            Q(name__icontains=keyword)
            | Q(email__icontains=keyword)
            | Q(phone__icontains=keyword)
            | Q(department_name__icontains=keyword)
            | Q(position_name__icontains=keyword)
        )

    if department and department != "all":
        qs = qs.filter(department_name=department)

    status_map = {
        "active": 1,
        "leave": 0,
        "disabled": 2,
    }
    if status and status in status_map:
        qs = qs.filter(status=status_map[status])

    items = [_serialize_employee(emp) for emp in qs.order_by("id")]

    departments = (
        Employee.objects.filter(deleted_at__isnull=True)
        .exclude(department_name__isnull=True)
        .exclude(department_name__exact="")
        .values_list("department_name", flat=True)
        .distinct()
        .order_by("department_name")
    )
    dept_list = list(departments)

    stats = {
        "total": len(items),
        "active": sum(1 for item in items if item["status"] == "active"),
        "leave": sum(1 for item in items if item["status"] == "leave"),
        "disabled": sum(1 for item in items if item["status"] == "disabled"),
    }

    return JsonResponse(
        {
            "items": items,
            "departments": dept_list,
            "stats": stats,
        }
    )


@csrf_exempt
@require_http_methods(["PUT", "PATCH", "DELETE"])
def employee_detail_api(request, employee_id):
    employee = Employee.objects.filter(id=employee_id, deleted_at__isnull=True).first()
    if not employee:
        return JsonResponse({"error": "Employee not found"}, status=404)

    if request.method == "DELETE":
        employee.deleted_at = timezone.now()
        employee.save(update_fields=["deleted_at"])
        return JsonResponse({"status": "ok"})

    payload, error = _parse_json_body(request)
    if error:
        return error

    if "name" in payload:
        employee.name = (payload.get("name") or "").strip()
    if "gender" in payload:
        employee.gender = payload.get("gender") or None
    if "phone" in payload:
        employee.phone = (payload.get("phone") or "").strip() or None
    if "email" in payload:
        employee.email = (payload.get("email") or "").strip() or None
    if "address" in payload:
        employee.address = (payload.get("address") or "").strip() or None
    if "department" in payload or "department_name" in payload:
        employee.department_name = (
            payload.get("department") or payload.get("department_name") or ""
        ).strip() or None
    if "position" in payload or "position_name" in payload:
        employee.position_name = (
            payload.get("position") or payload.get("position_name") or ""
        ).strip() or None
    if "status" in payload:
        status = _normalize_status(payload.get("status"))
        if status is None:
            return JsonResponse({"error": "Invalid status"}, status=400)
        employee.status = status

    if "hire_date" in payload:
        value, error = _parse_date(payload.get("hire_date"), "hire_date")
        if error:
            return error
        employee.hire_date = value
    if "leave_date" in payload:
        value, error = _parse_date(payload.get("leave_date"), "leave_date")
        if error:
            return error
        employee.leave_date = value
    if "birthday" in payload:
        value, error = _parse_date(payload.get("birthday"), "birthday")
        if error:
            return error
        employee.birthday = value
    if "emergency_contact_name" in payload:
        employee.emergency_contact_name = (
            payload.get("emergency_contact_name") or ""
        ).strip() or None
    if "emergency_contact_phone" in payload:
        employee.emergency_contact_phone = (
            payload.get("emergency_contact_phone") or ""
        ).strip() or None
    if "emergency_contact_relationship" in payload:
        employee.emergency_contact_relationship = (
            payload.get("emergency_contact_relationship") or ""
        ).strip() or None

    if not employee.name:
        return JsonResponse({"error": "Missing field: name"}, status=400)

    employee.save()
    return JsonResponse({"status": "ok", "item": _serialize_employee(employee)})
