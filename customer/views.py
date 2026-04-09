import json
import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from django.conf import settings as django_settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from customer.models import Customer
from employee.models import Employee
from project.api import api_error, api_paginated, api_success
from project.common_tools import contract_storage_dir, parse_json_body
from settings.LINE import (
    get_line_message_content,
    get_line_channel_secret,
    verify_line_signature,
)

logger = logging.getLogger(__name__)


def _line_card_storage_dir() -> Path:
    return Path(django_settings.BASE_DIR) / "line_uploads" / "cards"


def _guess_image_suffix(content_type: str) -> str:
    ctype = str(content_type or "").lower()
    if "jpeg" in ctype or "jpg" in ctype:
        return ".jpg"
    if "png" in ctype:
        return ".png"
    if "webp" in ctype:
        return ".webp"
    if "gif" in ctype:
        return ".gif"
    if "bmp" in ctype:
        return ".bmp"
    return ".bin"


@require_GET
# 一次性获取全部员工姓名，前端自己过滤
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
# 上传与客户公司的契约
def customer_contract_upload(request, customer_id):
    login_id = request.session.get("employee_id")
    if not login_id:
        return api_error(status=401, message="employee id is required")

    upload = request.FILES.get("file")
    if not upload:
        return api_error("Missing file")

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
    customer.updated_by = login_id
    customer.save()

    return api_success(data={"path": filename})


# 上传名片，添加客户
@csrf_exempt
@require_POST
def customer_card_ocr_api(request):
    login_id = request.session.get("employee_id")
    if not login_id:
        return api_error(status=401, message="employee id is required")

    upload = request.FILES.get("file")
    if not upload:
        return api_error("Missing file")

    suffix = Path(upload.name or "").suffix
    temp_path = None
    try:
        from customer.card_ocr import parse_card

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            for chunk in upload.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        result = parse_card(temp_path)
        return api_success(data={"result": result})
    except Exception as exc:
        return api_error(f"OCR failed: {exc}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

# LINE webhook
@csrf_exempt
@require_POST
def line_webhook_api(request):
    request_body = request.body or b""
    signature = request.META.get("HTTP_X_LINE_SIGNATURE", "")
    channel_secret = get_line_channel_secret()
    if not channel_secret:
        return api_error("Missing LINE channel secret", status=500)
    if not verify_line_signature(request_body, signature, channel_secret):
        return api_error("Invalid LINE signature", status=403)

    try:
        payload = json.loads(request_body.decode("utf-8") if request_body else "{}")
    except json.JSONDecodeError:
        return api_error("Invalid JSON body")

    events = payload.get("events")
    if not isinstance(events, list):
        events = []

    image_event_count = 0
    downloaded_count = 0
    errors = []
    saved_files = []
    base_dir = _line_card_storage_dir()
    os.makedirs(base_dir, exist_ok=True)

    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") != "message":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("type") != "image":
            continue

        image_event_count += 1
        message_id = str(message.get("id") or "").strip()
        if not message_id:
            errors.append("message_id is empty")
            continue

        try:
            content_result = get_line_message_content(message_id)
            content = content_result.get("content") or b""
            content_length = content_result.get("content_length", 0)
            if content_length <= 0:
                errors.append(f"empty image content: {message_id}")
                continue

            content_type = str(content_result.get("content_type") or "").strip()
            suffix = _guess_image_suffix(content_type)
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            filename = f"line_{timestamp}_{message_id}_{uuid.uuid4().hex[:8]}{suffix}"
            file_path = base_dir / filename
            with open(file_path, "wb") as handle:
                handle.write(content)

            downloaded_count += 1
            saved_files.append(
                {
                    "message_id": message_id,
                    "content_type": content_type,
                    "file_name": filename,
                    "relative_path": str(Path("line_uploads") / "cards" / filename),
                    "size": content_length,
                }
            )
        except Exception:
            logger.exception("line webhook image download failed message_id=%s", message_id)
            errors.append(f"download failed: {message_id}")

    return api_success(
        data={
            "received_events": len(events),
            "image_events": image_event_count,
            "downloaded_images": downloaded_count,
            "saved_files": saved_files,
            "errors": errors,
        }
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
# 获取客户公司列表、添加客户公司
def customers_api(request):
    login_id = request.session.get("employee_id")
    if not login_id:
        return api_error(status=401, message="employee id is required")

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
        Customer.get_customer_by_payload(customer, payload)
        customer.created_by = login_id
        customer.save()
        item = Customer.serialize(customer)
        return api_success(data={"item": item})

    return api_error("Method not allowed", status=405)


@csrf_exempt
@require_http_methods(["PUT", "GET"])
# 更新客户公司信息、获取客户公司信息
def customer_detail_api(request, customer_id):
    login_id = request.session.get("employee_id")
    if not login_id:
        return api_error(status=401, message="employee id is required")

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
        Customer.get_customer_by_payload(customer, payload)
        customer.updated_by = login_id
        customer.save()
        item = Customer.serialize(customer)
        return api_success(data={"item": item})

    if request.method == "GET":
        item = Customer.serialize(customer)
        return api_success(data={"item": item})

    return api_error("Method not allowed", status=405)
