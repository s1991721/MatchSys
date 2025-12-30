import os

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from customer.models import Customer
from employee.models import Employee
from project.api import api_error, api_paginated, api_success
from project.common_tools import contract_storage_dir, parse_json_body


def _apply_customer_payload(customer, payload):
    customer.company_name = (payload.get("company_name") or "").strip()
    customer.company_address = (payload.get("company_address") or "").strip()
    customer.remark = (payload.get("remark") or "").strip()
    customer.contact1_name = (payload.get("contact1_name") or "").strip()
    customer.contact1_position = (payload.get("contact1_position") or "").strip()
    customer.contact1_email = (payload.get("contact1_email") or "").strip()
    customer.contact1_phone = (payload.get("contact1_phone") or "").strip()
    customer.contact2_name = (payload.get("contact2_name") or "").strip()
    customer.contact2_position = (payload.get("contact2_position") or "").strip()
    customer.contact2_email = (payload.get("contact2_email") or "").strip()
    customer.contact2_phone = (payload.get("contact2_phone") or "").strip()
    customer.contact3_name = (payload.get("contact3_name") or "").strip()
    customer.contact3_position = (payload.get("contact3_position") or "").strip()
    customer.contact3_email = (payload.get("contact3_email") or "").strip()
    customer.contact3_phone = (payload.get("contact3_phone") or "").strip()
    customer.person_in_charge = (payload.get("person_in_charge") or "").strip()
    if "contract" in payload:
        customer.contract = (payload.get("contract") or "").strip()


@require_GET
def employee_names_api(request):
    employee_names = (
        Employee.objects.filter(deleted_at__isnull=True)
        .order_by("name")
        .values_list("name", flat=True)
        .distinct()
    )
    names = list(employee_names)
    return api_success(data={"names": names})


@csrf_exempt
@require_POST
def customer_contract_upload(request, customer_id):
    upload = request.FILES.get("file")
    if not upload:
        return api_error(
            "Missing file"
        )

    customer = Customer.objects.filter(pk=customer_id, deleted_at__isnull=True).first()
    if not customer:
        return api_error("Customer not found", status=404)

    base_dir = contract_storage_dir()
    os.makedirs(base_dir, exist_ok=True)

    _, ext = os.path.splitext(upload.name or "")
    filename = f"customer_{customer_id}{ext or ''}"
    dest_path = os.path.join(base_dir, filename)

    with open(dest_path, "wb") as handle:
        for chunk in upload.chunks():
            handle.write(chunk)

    customer.contract = filename
    customer.updated_at = timezone.now()
    customer.save(update_fields=["contract", "updated_at"])

    return api_success(data={"path": filename})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def customers_api(request):
    if request.method == "GET":
        company_name = (request.GET.get("company_name") or "").strip()
        person_in_charge = (request.GET.get("person_in_charge") or "").strip()
        try:
            page = int(request.GET.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(request.GET.get("page_size", 10))
        except (TypeError, ValueError):
            page_size = 10
        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        queryset = Customer.objects.filter(deleted_at__isnull=True)
        if company_name:
            queryset = queryset.filter(company_name__icontains=company_name)
        if person_in_charge:
            queryset = queryset.filter(person_in_charge__icontains=person_in_charge)
        queryset = queryset.order_by("-created_at", "-id")
        total = queryset.count()
        total_pages = max((total + page_size - 1) // page_size, 1)
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * page_size
        items = [
            Customer.serialize(customer)
            for customer in queryset[offset: offset + page_size]
        ]
        return api_paginated(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    if request.method == "POST":
        payload, error = parse_json_body(request)
        if error:
            return error
        if not (payload.get("company_name") or "").strip():
            return api_error("Missing field: company_name")
        customer = Customer()
        _apply_customer_payload(customer, payload)
        now = timezone.now()
        customer.created_at = now
        customer.updated_at = now
        customer.save()
        item = Customer.serialize(customer)
        return api_success(data={"item": item})

    return api_error("Method not allowed", status=405)


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def customer_detail_api(request, customer_id):
    try:
        customer = Customer.objects.get(pk=customer_id, deleted_at__isnull=True)
    except Customer.DoesNotExist:
        return api_error("Customer not found", status=404)

    if request.method == "PUT":
        payload, error = parse_json_body(request)
        if error:
            return error
        if not (payload.get("company_name") or "").strip():
            return api_error("Missing field: company_name")
        _apply_customer_payload(customer, payload)
        customer.updated_at = timezone.now()
        customer.save()
        item = Customer.serialize(customer)
        return api_success(data={"item": item})

    if request.method == "GET":
        item = Customer.serialize(customer)
        return api_success(data={"item": item})

    return api_error("Method not allowed", status=405)
