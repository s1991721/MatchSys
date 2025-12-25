import json
import os

from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from customer.models import Customer
from employee.models import Employee


def _parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)


def _serialize_customer(customer):
    return {
        "id": customer.id,
        "company_name": customer.company_name or "",
        "company_address": customer.company_address or "",
        "contract": customer.contract or "",
        "remark": customer.remark or "",
        "contact1_name": customer.contact1_name or "",
        "contact1_position": customer.contact1_position or "",
        "contact1_email": customer.contact1_email or "",
        "contact1_phone": customer.contact1_phone or "",
        "contact2_name": customer.contact2_name or "",
        "contact2_position": customer.contact2_position or "",
        "contact2_email": customer.contact2_email or "",
        "contact2_phone": customer.contact2_phone or "",
        "contact3_name": customer.contact3_name or "",
        "contact3_position": customer.contact3_position or "",
        "contact3_email": customer.contact3_email or "",
        "contact3_phone": customer.contact3_phone or "",
        "person_in_charge": customer.person_in_charge or "",
        "created_at": customer.created_at.strftime("%Y-%m-%d %H:%M")
        if customer.created_at
        else "",
    }


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


def employee_names_api(request):
    employee_names = (
        Employee.objects.filter(deleted_at__isnull=True)
        .order_by("name")
        .values_list("name", flat=True)
        .distinct()
    )
    return JsonResponse({"names": list(employee_names)})


def _contract_storage_dir():
    return os.path.join(settings.BASE_DIR, "customer_contract")


@csrf_exempt
@require_POST
def customer_contract_upload(request, customer_id):
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "Missing file"}, status=400)

    customer = Customer.objects.filter(pk=customer_id, deleted_at__isnull=True).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    base_dir = _contract_storage_dir()
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

    return JsonResponse({"status": "ok", "path": filename})


@csrf_exempt
def customers_api(request):
    if request.method == "GET":
        company_name = (request.GET.get("company_name") or "").strip()
        person_in_charge = (request.GET.get("person_in_charge") or "").strip()
        queryset = Customer.objects.filter(deleted_at__isnull=True)
        if company_name:
            queryset = queryset.filter(company_name__icontains=company_name)
        if person_in_charge:
            queryset = queryset.filter(person_in_charge__icontains=person_in_charge)
        queryset = queryset.order_by("-created_at", "-id")
        items = [_serialize_customer(customer) for customer in queryset]
        return JsonResponse({"items": items, "total": queryset.count()})

    if request.method == "POST":
        payload, error = _parse_json_body(request)
        if error:
            return error
        if not (payload.get("company_name") or "").strip():
            return JsonResponse({"error": "Missing field: company_name"}, status=400)
        customer = Customer()
        _apply_customer_payload(customer, payload)
        now = timezone.now()
        customer.created_at = now
        customer.updated_at = now
        customer.save()
        return JsonResponse({"status": "ok", "item": _serialize_customer(customer)})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def customer_detail_api(request, customer_id):
    try:
        customer = Customer.objects.get(pk=customer_id, deleted_at__isnull=True)
    except Customer.DoesNotExist:
        return JsonResponse({"error": "Customer not found"}, status=404)

    if request.method == "PUT":
        payload, error = _parse_json_body(request)
        if error:
            return error
        if not (payload.get("company_name") or "").strip():
            return JsonResponse({"error": "Missing field: company_name"}, status=400)
        _apply_customer_payload(customer, payload)
        customer.updated_at = timezone.now()
        customer.save()
        return JsonResponse({"status": "ok", "item": _serialize_customer(customer)})

    if request.method == "GET":
        return JsonResponse({"item": _serialize_customer(customer)})

    return JsonResponse({"error": "Method not allowed"}, status=405)
