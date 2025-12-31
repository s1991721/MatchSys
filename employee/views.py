import mimetypes
import os
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from project.api import api_error, api_paginated, api_success
from project.common_tools import parse_date, parse_json_body, years_ago, ss_storage_dir
from .models import Employee, Technician, UserLogin


@csrf_exempt
@require_POST
# 登录
def login_api(request):
    payload, error = parse_json_body(request)
    if error:
        return error

    user_name = (payload.get("user_name") or "").strip()
    password = payload.get("password") or ""

    if not user_name or not password:
        return api_error(
            "Missing user_name or password",
            status=400,
        )

    user_login = (
        UserLogin.objects.filter(
            user_name=user_name,
            password=password,
            deleted_at__isnull=True
        )
        .first()
    )

    if not user_login:
        return api_error(
            "Invalid credentials",
            status=401,
        )

    request.session.cycle_key()
    request.session["employee_id"] = user_login.employee_id
    request.session["employee_name"] = user_login.employee_name
    request.session["role_id"] = user_login.role_id
    request.session["menu_list"] = user_login.menu_list or ""

    return api_success(data={
        "role_id": user_login.role_id,
        "menu_list": user_login.menu_list or "",
    })


@csrf_exempt
@require_POST
# 登出
def logout_api(request):
    request.session.flush()
    return api_success()


@csrf_exempt
@require_http_methods(["GET", "PUT", "PATCH", "DELETE"])
# 获取用户详情、更新用户信息、删除用户
def employee_detail_api(request, employee_id):
    employee = Employee.objects.filter(id=employee_id, deleted_at__isnull=True).first()
    if not employee:
        return api_error(
            "Employee not found",
            status=404,
        )

    if request.method == "GET":
        item = Employee.serialize(employee)
        return api_success(data={"item": item})

    if request.method == "DELETE":
        login_id = request.session.get("employee_id")
        if login_id:
            employee.deleted_at = timezone.now()
            employee.updated_by = login_id
            employee.save()
            return api_success()
        return api_error(status=401, message="请先登录")

    payload, error = parse_json_body(request)
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
    if "department_name" in payload:
        employee.department_name = (payload.get("department_name") or "").strip() or None
    if "position_name" in payload:
        employee.position_name = (payload.get("position_name") or "").strip() or None
    if "hire_date" in payload:
        value, error = parse_date(payload.get("hire_date"))
        if error:
            return error
        employee.hire_date = value
    if "leave_date" in payload:
        value, error = parse_date(payload.get("leave_date"))
        if error:
            return error
        employee.leave_date = value
    if "birthday" in payload:
        value, error = parse_date(payload.get("birthday"))
        if error:
            return error
        employee.birthday = value
    if "emergency_contact_name" in payload:
        employee.emergency_contact_name = (payload.get("emergency_contact_name") or "").strip() or None
    if "emergency_contact_phone" in payload:
        employee.emergency_contact_phone = (payload.get("emergency_contact_phone") or "").strip() or None
    if "emergency_contact_relationship" in payload:
        employee.emergency_contact_relationship = (payload.get("emergency_contact_relationship") or "").strip() or None

    if not employee.name:
        return api_error(
            "Missing field: name"
        )
    employee.updated_by = request.session.get("employee_id")

    employee.save()
    if request.session.get("employee_id") == employee.id:
        request.session["employee_name"] = employee.name
        request.session["employee_department_name"] = employee.department_name
        request.session["employee_position_name"] = employee.position_name
    item = Employee.serialize(employee)
    return api_success(data=item)


@csrf_exempt
@require_POST
# 修改密码
def change_password_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return api_error(
            "Unauthorized",
            status=401,
        )

    payload, error = parse_json_body(request)
    if error:
        return error

    old_password = (payload.get("old_password") or "").strip()
    new_password = (payload.get("new_password") or "").strip()

    if not old_password or not new_password:
        return api_error(
            "Missing old_password or new_password",
            status=400,
        )
    if old_password == new_password:
        return api_error(
            "New password must be different",
            status=400,
        )

    user_login = UserLogin.objects.filter(
        employee_id=employee_id,
        deleted_at__isnull=True,
    ).first()
    if not user_login:
        return api_error(
            "User not found",
            status=404,
        )
    if user_login.password != old_password:
        return api_error(
            "Invalid current password",
            status=400,
        )

    user_login.password = new_password
    user_login.save(update_fields=["password", "updated_at"])

    return api_success()


@csrf_exempt
@require_http_methods(["GET"])
# 获取部门列表
def employee_departments_api(request):
    departments = (
        Employee.objects.filter(deleted_at__isnull=True)
        .exclude(department_name__isnull=True)
        .exclude(department_name__exact="")
        .values_list("department_name", flat=True)
        .distinct()
        .order_by("department_name")
    )
    dept_list = list(departments)
    return api_success(data={"departments": dept_list})


@csrf_exempt
@require_http_methods(["GET", "POST"])
# 获取员工列表
def employees_api(request):
    if request.method == "POST":
        login_id = request.session.get("employee_id")
        if not login_id:
            return api_error(status=401, message="employee id is required")
        payload, error = parse_json_body(request)
        if error:
            return error

        name = (payload.get("name") or "").strip()
        if not name:
            return api_error(
                "Missing field: name"
            )

        email = (payload.get("email") or "").strip()
        if not email:
            return api_error(
                "Missing field: email"
            )

        if UserLogin.objects.filter(user_name=email, deleted_at__isnull=True).exists():
            return api_error(
                "User login already exists"
            )

        hire_date, error = parse_date(payload.get("hire_date"))
        if error:
            return error
        leave_date, error = parse_date(payload.get("leave_date"))
        if error:
            return error
        birthday, error = parse_date(payload.get("birthday"))
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
                emergency_contact_relationship=(payload.get("emergency_contact_relationship") or "").strip() or None,
                hire_date=hire_date,
                leave_date=leave_date,
                department_name=(payload.get("department_name") or "").strip() or None,
                position_name=(payload.get("position_name") or "").strip() or None,
                created_by=login_id
            )
            UserLogin.objects.create(
                employee_id=employee.id,
                employee_name=employee.name,
                user_name=email,
                password="123456",
                created_by=login_id
            )

        item = Employee.serialize(employee)
        return api_success(data={"item": item})

    if request.method == "GET":
        keyword = (request.GET.get("keyword") or "").strip()
        department = (request.GET.get("department") or "").strip()
        try:
            page = int(request.GET.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(request.GET.get("page_size") or 10)
        except (TypeError, ValueError):
            page_size = 10
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10

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

        total = qs.count()
        total_pages = (total + page_size - 1) // page_size if page_size else 1
        if total_pages < 1:
            total_pages = 1
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * page_size
        items = [Employee.serialize(emp) for emp in qs.order_by("id")[offset:offset + page_size]]

        return api_paginated(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages
        )
    return None


@csrf_exempt
@require_http_methods(["GET", "POST"])
# 新增技术者、获取技术者列表
def technicians_api(request):
    if request.method == "POST":
        login_id = request.session.get("employee_id")
        if not login_id:
            return api_error(status=401, message="employee id is required")

        payload, error = parse_json_body(request)
        if error:
            return error

        employee_id = payload.get("employee_id")

        if employee_id is None:
            return api_error("Missing field: employee_id")

        if Technician.objects.filter(employee_id=employee_id).exists():
            return api_error("Employee ID already exists")

        name_mask = (payload.get("name_mask") or "").strip()
        if not name_mask:
            return api_error("Missing field: name_mask")

        name = (payload.get("name") or "").strip()
        if not name:
            return api_error("Missing field: name")

        birthday, error = parse_date(payload.get("birthday"))
        if error:
            return error

        spot_deadline, error = parse_date(payload.get("spot_contract_deadline"))
        if error:
            return error

        price = Decimal(str(payload.get("price")))

        contract_type = payload.get("contract_type")

        business_status = payload.get("business_status")

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

        item = Technician.serialize(tech)
        return api_success(data={"item": item})

    if request.method == "GET":
        filters = {}

        keyword = (request.GET.get("keyword") or "").strip()
        age_max = request.GET.get("age_max")
        nationality = (request.GET.get("nationality") or "").strip()
        price_max = request.GET.get("price_max")
        contract_type = request.GET.get("contract_type")
        business_status = request.GET.get("business_status")

        if nationality:
            filters["nationality"] = nationality

        if price_max is not None:
            filters["price__lte"] = price_max

        if contract_type is not None:
            filters["contract_type"] = contract_type

        if business_status is not None:
            filters["business_status"] = business_status

        qs = Technician.objects.filter(**filters)
        if keyword:
            qs = qs.filter(Q(name__icontains=keyword) | Q(name_mask__icontains=keyword))

        if age_max is not None:
            today = timezone.localdate()
            min_birth = years_ago(today, age_max)
            qs = qs.filter(birthday__gte=min_birth)

        site_contract_value = (request.GET.get("site_contract") or "").strip()
        if site_contract_value:
            site_date, error = parse_date(site_contract_value)
            if error:
                return error
            if site_date:
                qs = qs.filter(spot_contract_deadline=site_date)

        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))

        page = max(page, 1)
        page_size = min(page_size, 100)

        total = qs.count()
        total_pages = max((total + page_size - 1) // page_size, 1)
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * page_size
        items = [
            Technician.serialize(tech)
            for tech in qs.order_by("employee_id")[offset: offset + page_size]
        ]
        return api_paginated(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )
    return None


@csrf_exempt
@require_http_methods(["PUT", "PATCH", "DELETE"])
# 删除技术者、更新技术者
def technician_detail_api(request, employee_id):
    tech = Technician.objects.filter(employee_id=employee_id).first()
    if not tech:
        return api_error("Technician not found", status=404)

    if request.method == "DELETE":
        tech.delete()
        return api_success()

    payload, error = parse_json_body(request)
    if error:
        return error

    if "name_mask" in payload:
        tech.name_mask = (payload.get("name_mask") or "").strip()
    if "birthday" in payload:
        value, error = parse_date(payload.get("birthday"))
        if error:
            return error
        tech.birthday = value
    if "name" in payload:
        tech.name = (payload.get("name") or "").strip()
    if "nationality" in payload:
        tech.nationality = (payload.get("nationality") or "").strip() or None
    if "price" in payload:
        tech.price = payload.get("price")
    if "introduction" in payload:
        tech.introduction = (payload.get("introduction") or "").strip() or None

    if "contract_type" in payload:
        value = payload.get("contract_type")
        tech.contract_type = value if value is not None else 0

    if "spot_contract_deadline" in payload:
        value, error = parse_date(payload.get("spot_contract_deadline"))
        if error:
            return error
        tech.spot_contract_deadline = value

    if "business_status" in payload:
        value = payload.get("business_status")
        tech.business_status = value if value is not None else 0

    if "ss" in payload:
        tech.ss = (payload.get("ss") or "").strip() or None
    if "remark" in payload:
        tech.remark = (payload.get("remark") or "").strip() or None

    # Do not allow employee_id updates for existing technicians.

    if not tech.name_mask:
        return api_error("Missing field: name_mask")
    if not tech.name:
        return api_error("Missing field: name")

    login_id = request.session.get("employee_id")
    if login_id:
        tech.updated_by = login_id
        tech.save()
        item = Technician.serialize(tech)
        return api_success(data={"item": item})
    return api_error(status=401, message="请先登录")


@csrf_exempt
@require_POST
# 上传ss
def technician_ss_upload(request, employee_id):
    if not request.session.get("employee_id"):
        return api_error("Unauthorized", status=401)

    upload = request.FILES.get("file")
    if not upload:
        return api_error("Missing file")

    tech = Technician.objects.filter(employee_id=employee_id).first()
    if not tech:
        return api_error("Technician not found", status=404)

    base_dir = ss_storage_dir()
    os.makedirs(base_dir, exist_ok=True)

    _, ext = os.path.splitext(upload.name or "")
    safe_name = os.path.basename(tech.name_mask).strip()
    if not safe_name:
        safe_name = str(employee_id)
    filename = f"{safe_name}{ext or ''}"
    dest_path = os.path.join(base_dir, filename)

    with open(dest_path, "wb") as handle:
        for chunk in upload.chunks():
            handle.write(chunk)

    rel_path = filename
    if tech:
        tech.ss = rel_path
        tech.save(update_fields=["ss"])

    payload = {"path": rel_path, "url": f"/api/ss/{rel_path}"}
    return api_success(data=payload)


@require_http_methods(["GET"])
# 下载ss
def technician_ss_download(request, path):
    if not request.session.get("employee_id"):
        return api_error("Unauthorized", status=401)

    base_dir = os.path.realpath(ss_storage_dir())
    safe_path = os.path.realpath(os.path.join(base_dir, path))
    if not safe_path.startswith(base_dir + os.sep):
        return api_error("Invalid path")
    if not os.path.exists(safe_path):
        return api_error("File not found", status=404)

    content_type, _ = mimetypes.guess_type(safe_path)
    response = FileResponse(open(safe_path, "rb"), content_type=content_type or "application/octet-stream")
    response["Content-Disposition"] = "inline"
    return response
