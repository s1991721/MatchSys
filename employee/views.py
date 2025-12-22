import json
from datetime import datetime

import mimetypes
import os
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .models import Employee, Technician, UserLogin


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
    request.session["employee_position_name"] = user_login.employee.position_name
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
    if isinstance(value, int):
        if 1 <= value <= 12:
            today = timezone.localdate()
            return today.replace(month=value, day=1), None
        return None, JsonResponse({"error": f"Invalid date: {field}"}, status=400)
    if isinstance(value, str):
        if value.isdigit():
            month = int(value)
            if 1 <= month <= 12:
                today = timezone.localdate()
                return today.replace(month=month, day=1), None
            return None, JsonResponse({"error": f"Invalid date: {field}"}, status=400)
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


def _years_ago(today, years):
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, month=2, day=28)


def _serialize_technician(tech):
    contract_labels = {
        0: "未定",
        1: "长期",
        2: "短期",
        3: "现场",
    }
    business_labels = {
        0: "待机",
        1: "可用",
        2: "忙碌",
        3: "不可用",
    }
    ss_path = tech.ss or ""
    ss_url = f"/api/ss/{ss_path}" if ss_path else ""
    return {
        "employee_id": tech.employee_id,
        "name": tech.name,
        "name_mask": tech.name_mask,
        "birthday": tech.birthday.isoformat() if tech.birthday else "",
        "nationality": tech.nationality or "",
        "price": str(tech.price) if tech.price is not None else "",
        "introduction": tech.introduction or "",
        "contract_type": tech.contract_type,
        "contract_label": contract_labels.get(tech.contract_type, ""),
        "spot_contract_deadline": tech.spot_contract_deadline.isoformat()
        if tech.spot_contract_deadline
        else "",
        "business_status": tech.business_status,
        "business_label": business_labels.get(tech.business_status, ""),
        "ss": ss_path,
        "ss_url": ss_url,
        "remark": tech.remark or "",
    }


def _parse_decimal(value, field):
    if value in (None, ""):
        return None, None
    try:
        return Decimal(str(value)), None
    except (InvalidOperation, ValueError):
        return None, JsonResponse({"error": f"Invalid number: {field}"}, status=400)


def _normalize_smallint(value, field):
    if value in (None, ""):
        return None, None
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, JsonResponse({"error": f"Invalid value: {field}"}, status=400)


def _ss_storage_dir():
    return os.path.join(settings.BASE_DIR, "ss")


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
@require_http_methods(["GET", "POST"])
def technicians_api(request):
    if request.method == "POST":
        payload, error = _parse_json_body(request)
        if error:
            return error

        employee_id, error = _normalize_smallint(payload.get("employee_id"), "employee_id")
        if error:
            return error
        if employee_id is None:
            return JsonResponse({"error": "Missing field: employee_id"}, status=400)
        if Technician.objects.filter(employee_id=employee_id).exists():
            return JsonResponse({"error": "Employee ID already exists"}, status=400)

        name_mask = (payload.get("name_mask") or "").strip()
        if not name_mask:
            return JsonResponse({"error": "Missing field: name_mask"}, status=400)

        name = (payload.get("name") or "").strip()
        if not name:
            return JsonResponse({"error": "Missing field: name"}, status=400)

        birthday, error = _parse_date(payload.get("birthday"), "birthday")
        if error:
            return error
        spot_deadline, error = _parse_date(
            payload.get("spot_contract_deadline"), "spot_contract_deadline"
        )
        if error:
            return error

        price, error = _parse_decimal(payload.get("price"), "price")
        if error:
            return error

        contract_type, error = _normalize_smallint(payload.get("contract_type"), "contract_type")
        if error:
            return error
        business_status, error = _normalize_smallint(payload.get("business_status"), "business_status")
        if error:
            return error
        ss_value = (payload.get("ss") or "").strip() or None

        tech = Technician.objects.create(
            employee_id=employee_id,
            name=name,
            name_mask=name_mask,
            birthday=birthday,
            nationality=(payload.get("nationality") or "").strip() or None,
            price=price,
            introduction=(payload.get("introduction") or "").strip() or None,
            contract_type=contract_type if contract_type is not None else 0,
            spot_contract_deadline=spot_deadline,
            business_status=business_status if business_status is not None else 0,
            ss=ss_value,
            remark=(payload.get("remark") or "").strip() or None,
        )

        return JsonResponse({"status": "ok", "item": _serialize_technician(tech)})

    qs = Technician.objects.all()

    age_min, error = _normalize_smallint(request.GET.get("age_min"), "age_min")
    if error:
        return error
    age_max, error = _normalize_smallint(request.GET.get("age_max"), "age_max")
    if error:
        return error
    price_max, error = _parse_decimal(request.GET.get("price_max"), "price_max")
    if error:
        return error
    contract_type, error = _normalize_smallint(request.GET.get("contract_type"), "contract_type")
    if error:
        return error
    business_status, error = _normalize_smallint(request.GET.get("business_status"), "business_status")
    if error:
        return error

    nationality = (request.GET.get("nationality") or "").strip()
    if nationality:
        qs = qs.filter(nationality=nationality)

    if price_max is not None:
        qs = qs.filter(price__lte=price_max)

    if contract_type is not None:
        qs = qs.filter(contract_type=contract_type)

    if business_status is not None:
        qs = qs.filter(business_status=business_status)

    if age_min is not None or age_max is not None:
        today = timezone.localdate()
        if age_min is not None:
            max_birth = _years_ago(today, age_min)
            qs = qs.filter(birthday__lte=max_birth)
        if age_max is not None:
            min_birth = _years_ago(today, age_max)
            qs = qs.filter(birthday__gte=min_birth)

    items = [_serialize_technician(tech) for tech in qs.order_by("employee_id")]
    return JsonResponse({"items": items})


@csrf_exempt
@require_http_methods(["PUT", "PATCH", "DELETE"])
def technician_detail_api(request, employee_id):
    tech = Technician.objects.filter(employee_id=employee_id).first()
    if not tech:
        return JsonResponse({"error": "Technician not found"}, status=404)

    if request.method == "DELETE":
        tech.delete()
        return JsonResponse({"status": "ok"})

    payload, error = _parse_json_body(request)
    if error:
        return error

    if "name_mask" in payload:
        tech.name_mask = (payload.get("name_mask") or "").strip()
    if "birthday" in payload:
        value, error = _parse_date(payload.get("birthday"), "birthday")
        if error:
            return error
        tech.birthday = value
    if "name" in payload:
        tech.name = (payload.get("name") or "").strip()
    if "nationality" in payload:
        tech.nationality = (payload.get("nationality") or "").strip() or None
    if "price" in payload:
        value, error = _parse_decimal(payload.get("price"), "price")
        if error:
            return error
        tech.price = value
    if "introduction" in payload:
        tech.introduction = (payload.get("introduction") or "").strip() or None
    if "contract_type" in payload:
        value, error = _normalize_smallint(payload.get("contract_type"), "contract_type")
        if error:
            return error
        tech.contract_type = value if value is not None else 0
    if "spot_contract_deadline" in payload:
        value, error = _parse_date(payload.get("spot_contract_deadline"), "spot_contract_deadline")
        if error:
            return error
        tech.spot_contract_deadline = value
    if "business_status" in payload:
        value, error = _normalize_smallint(payload.get("business_status"), "business_status")
        if error:
            return error
        tech.business_status = value if value is not None else 0
    if "ss" in payload:
        tech.ss = (payload.get("ss") or "").strip() or None
    if "remark" in payload:
        tech.remark = (payload.get("remark") or "").strip() or None

    # Do not allow employee_id updates for existing technicians.

    if not tech.name_mask:
        return JsonResponse({"error": "Missing field: name_mask"}, status=400)
    if not tech.name:
        return JsonResponse({"error": "Missing field: name"}, status=400)

    tech.save()
    return JsonResponse({"status": "ok", "item": _serialize_technician(tech)})


@csrf_exempt
@require_POST
def technician_ss_upload(request, employee_id):
    if not request.session.get("employee_id"):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "Missing file"}, status=400)

    tech = Technician.objects.filter(employee_id=employee_id).first()
    if not tech:
        return JsonResponse({"error": "Technician not found"}, status=404)

    base_dir = _ss_storage_dir()
    os.makedirs(base_dir, exist_ok=True)

    _, ext = os.path.splitext(upload.name or "")
    safe_name = os.path.basename(tech.name_mask).strip()
    if not safe_name:
        safe_name = str(employee_id)
    filename = f"{safe_name}{ext or ''}"
    dest_path = os.path.join(base_dir, filename)
    if os.path.exists(dest_path):
        return JsonResponse({"error": "File already exists"}, status=409)

    with open(dest_path, "wb") as handle:
        for chunk in upload.chunks():
            handle.write(chunk)

    rel_path = filename
    if tech:
        tech.ss = rel_path
        tech.save(update_fields=["ss"])

    return JsonResponse({"status": "ok", "path": rel_path, "url": f"/api/ss/{rel_path}"})


@require_http_methods(["GET"])
def technician_ss_download(request, path):
    if not request.session.get("employee_id"):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    base_dir = os.path.realpath(_ss_storage_dir())
    safe_path = os.path.realpath(os.path.join(base_dir, path))
    if not safe_path.startswith(base_dir + os.sep):
        return JsonResponse({"error": "Invalid path"}, status=400)
    if not os.path.exists(safe_path):
        return JsonResponse({"error": "File not found"}, status=404)

    content_type, _ = mimetypes.guess_type(safe_path)
    response = FileResponse(open(safe_path, "rb"), content_type=content_type or "application/octet-stream")
    response["Content-Disposition"] = "inline"
    return response


@csrf_exempt
@require_http_methods(["GET", "PUT", "PATCH", "DELETE"])
def employee_detail_api(request, employee_id):
    employee = Employee.objects.filter(id=employee_id, deleted_at__isnull=True).first()
    if not employee:
        return JsonResponse({"error": "Employee not found"}, status=404)

    if request.method == "GET":
        return JsonResponse({"item": _serialize_employee(employee)})

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
