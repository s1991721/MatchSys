import json
import mimetypes
import os
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from employee.models import Employee
from order.models import PurchaseOrder, SalesOrder
from project.api import api_error, api_paginated, api_success
from project import storage
from project.common_tools import (
    paginate_queryset,
    parse_date,
    parse_json_body,
    parse_request_body,
    payload_to_dict,
    require_fields,
    require_login,
)
from project.storage import StorageArea


PURCHASE_STATUSES = {"已创建", "承认中", "已承认", "已取消"}
PURCHASE_APPROVING_NEXT_STATUSES = {"已承认", "已取消"}
PURCHASE_TERMINAL_STATUSES = {"已承认", "已取消"}
SALES_STATUSES = {"已受注", "已取消"}
ORDER_REQUIRED_FIELDS = (
    "order_no",
    "project_name",
    "customer_id",
    "customer_name",
    "status",
    "period_start",
    "period_end",
)


def _model_has_field(model, field_name):
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False


def _sanitize_filename_part(value):
    text = str(value or "").strip()
    safe = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in text)
    return safe.strip("_") or "purchase_order"


def _save_order_pdf(folder, order_no, uploaded_file):
    if not uploaded_file:
        return ""
    original_name = getattr(uploaded_file, "name", "") or ""
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type and content_type != "application/pdf":
        return None
    if original_name and not original_name.lower().endswith(".pdf"):
        return None
    filename = os.path.join(folder, f"{_sanitize_filename_part(order_no)}.pdf")
    storage.save_upload(StorageArea.ORDER, filename, uploaded_file)
    return storage.relative_path(StorageArea.ORDER, filename)


def _order_storage_filename(value):
    path = str(value or "").strip().replace("\\", "/")
    prefix = f"{StorageArea.ORDER}/"
    if path.startswith(prefix):
        return path[len(prefix):]
    return path


def _serve_order_pdf_file(pdf_file):
    if not pdf_file:
        return api_error("File not found", status=404)
    filename = _order_storage_filename(pdf_file)
    try:
        safe_path = storage.path(StorageArea.ORDER, filename)
    except ValueError:
        return api_error("Invalid path")
    if not storage.exists(StorageArea.ORDER, filename):
        return api_error("File not found", status=404)

    content_type, _ = mimetypes.guess_type(safe_path)
    response = FileResponse(
        storage.open_file(StorageArea.ORDER, filename),
        content_type=content_type or "application/pdf",
    )
    response["Content-Disposition"] = "inline"
    return response


def _normalize_purchase_status(value):
    raw = str(value or "").strip()
    if raw in PURCHASE_STATUSES:
        return raw, None
    return None, api_error(
        "Invalid status"
    )


def _normalize_sales_status(value):
    raw = str(value or "").strip()
    if raw in SALES_STATUSES:
        return raw, None
    return None, api_error(
        "Invalid status"
    )


def _serialize_purchase(order):
    created_at = timezone.localtime(order.created_at) if order.created_at else None
    updated_at = timezone.localtime(order.updated_at) if order.updated_at else None
    return {
        "id": order.id,
        "order_no": order.order_no,
        "person_in_charge_id": order.person_in_charge_id or None,
        "person_in_charge": order.person_in_charge,
        "status": order.status,
        "work_content": order.work_content or "",
        "work_place": order.work_place or "",
        "contract_type": order.contract_type or "",
        "payment_terms": order.payment_terms or "",
        "project_name": order.project_name,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "line_items": order.line_items or [],
        "period_start": order.period_start.isoformat() if order.period_start else "",
        "period_end": order.period_end.isoformat() if order.period_end else "",
        "remark": order.remark or "",
        "pdf_file": order.pdf_file or "",
        "created_by": order.created_by,
        "created_at": created_at.strftime("%Y-%m-%d %H:%M") if created_at else "",
        "updated_by": order.updated_by or "",
        "updated_at": updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else "",
    }


def _serialize_sales(order):
    created_at = timezone.localtime(order.created_at) if order.created_at else None
    updated_at = timezone.localtime(order.updated_at) if order.updated_at else None
    return {
        "id": order.id,
        "order_no": order.order_no,
        "person_in_charge_id": order.person_in_charge_id or None,
        "person_in_charge": order.person_in_charge,
        "status": order.status,
        "purchase_id": order.purchase_id,
        "project_name": order.project_name,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "technician_id": order.technician_id or 0,
        "technician_name": order.technician_name or "",
        "price": str(order.price) if order.price is not None else "",
        "line_items": order.line_items or [],
        "period_start": order.period_start.isoformat() if order.period_start else "",
        "period_end": order.period_end.isoformat() if order.period_end else "",
        "remark": order.remark or "",
        "pdf_file": order.pdf_file or "",
        "created_by": order.created_by,
        "created_at": created_at.strftime("%Y-%m-%d %H:%M") if created_at else "",
        "updated_by": order.updated_by or "",
        "updated_at": updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else "",
    }


def _current_user(request):
    return request.session.get("employee_name") or request.session.get("user_name") or "系统"


def _set_created_audit(instance, current_user, now):
    instance.created_by = current_user
    instance.updated_by = current_user
    instance.created_at = now
    instance.updated_at = now


def _set_updated_audit(instance, request):
    instance.updated_by = _current_user(request)
    instance.updated_at = timezone.now()


def _require_person_in_charge(payload):
    if payload.get("person_in_charge_id") or str(payload.get("person_in_charge") or "").strip():
        return None
    return api_error("Missing field: person_in_charge")


def _list_orders(queryset, request, serializer):
    queryset, error = _apply_filters(queryset, request)
    if error:
        return error
    paged, total, page, page_size, total_pages = paginate_queryset(queryset, request)
    return api_paginated(
        items=[serializer(order) for order in paged],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def _apply_person_in_charge(order, payload):
    if "person_in_charge_id" not in payload and "person_in_charge" not in payload:
        return None
    raw_person_id = payload.get("person_in_charge_id")
    if raw_person_id not in (None, ""):
        try:
            person_id = int(raw_person_id)
        except (TypeError, ValueError):
            return api_error("Invalid number: person_in_charge_id")
    else:
        person_id = None
    if person_id:
        employee = Employee.objects.filter(id=person_id, deleted_at__isnull=True).first()
        order.person_in_charge_id = person_id
        order.person_in_charge = employee.name if employee else (payload.get("person_in_charge") or "").strip()
        return None
    if "person_in_charge" in payload:
        order.person_in_charge = (payload.get("person_in_charge") or "").strip()
    order.person_in_charge_id = None
    return None


def _parse_line_items(raw_items, require_dict_items=False):
    if raw_items in (None, ""):
        return [], None
    if isinstance(raw_items, list):
        items = raw_items
    else:
        try:
            items = json.loads(raw_items)
        except (TypeError, json.JSONDecodeError):
            return None, api_error("Invalid JSON: line_items")
    if not isinstance(items, list):
        return None, api_error("Invalid JSON: line_items")
    if require_dict_items and any(not isinstance(item, dict) for item in items):
        return None, api_error("Invalid JSON: line_items")
    return items, None


def _apply_purchase_payload(order, payload):
    if "order_no" in payload:
        order.order_no = (payload.get("order_no") or "").strip()
    owner_error = _apply_person_in_charge(order, payload)
    if owner_error:
        return owner_error
    if "status" in payload:
        value, error = _normalize_purchase_status(payload.get("status"))
        if error:
            return error
        order.status = value
    if "work_content" in payload:
        order.work_content = (payload.get("work_content") or "").strip()
    if "work_place" in payload:
        order.work_place = (payload.get("work_place") or "").strip()
    if "contract_type" in payload:
        order.contract_type = (payload.get("contract_type") or "").strip()
    if "payment_terms" in payload:
        order.payment_terms = (payload.get("payment_terms") or "").strip()
    if "project_name" in payload:
        order.project_name = (payload.get("project_name") or "").strip()
    if "customer_name" in payload:
        order.customer_name = (payload.get("customer_name") or "").strip()
    if "customer_id" in payload:
        try:
            order.customer_id = int(payload.get("customer_id") or 0)
        except (TypeError, ValueError):
            return api_error("Invalid number: customer_id")
    if "remark" in payload:
        order.remark = (payload.get("remark") or "").strip()

    if "line_items" in payload:
        items, error = _parse_line_items(payload.get("line_items"))
        if error:
            return error
        order.line_items = items

    if "period_start" in payload:
        value, error = parse_date(payload.get("period_start"), "period_start")
        if error:
            return error
        if value:
            order.period_start = value

    if "period_end" in payload:
        value, error = parse_date(payload.get("period_end"), "period_end")
        if error:
            return error
        if value:
            order.period_end = value

    return None


def _update_purchase_order_from_request(request, order):
    payload, error = parse_request_body(request)
    if error:
        return error
    payload_keys = set(payload.keys())
    if order.status in PURCHASE_TERMINAL_STATUSES:
        return api_error("Order is locked")
    if order.status == "承认中":
        if payload_keys != {"status"} or request.FILES:
            return api_error("Order is locked")
        next_status, status_error = _normalize_purchase_status(payload.get("status"))
        if status_error:
            return status_error
        if next_status not in PURCHASE_APPROVING_NEXT_STATUSES:
            return api_error("Invalid status")
    apply_error = _apply_purchase_payload(order, payload)
    if apply_error:
        return apply_error
    pdf_file = request.FILES.get("pdf_file")
    if pdf_file:
        saved_pdf = _save_order_pdf("purchase", order.order_no, pdf_file)
        if saved_pdf is None:
            return api_error("Invalid PDF file")
        order.pdf_file = saved_pdf
    _set_updated_audit(order, request)
    order.save()
    item = _serialize_purchase(order)
    return api_success(data={"item": item})


def _apply_sales_payload(order, payload):
    if "order_no" in payload:
        order.order_no = (payload.get("order_no") or "").strip()
    owner_error = _apply_person_in_charge(order, payload)
    if owner_error:
        return owner_error
    if "status" in payload:
        value, error = _normalize_sales_status(payload.get("status"))
        if error:
            return error
        order.status = value
    if "project_name" in payload:
        order.project_name = (payload.get("project_name") or "").strip()
    if "customer_name" in payload:
        order.customer_name = (payload.get("customer_name") or "").strip()
    if "technician_name" in payload:
        order.technician_name = (payload.get("technician_name") or "").strip()
    if "customer_id" in payload:
        try:
            order.customer_id = int(payload.get("customer_id") or 0)
        except (TypeError, ValueError):
            return api_error("Invalid number: customer_id")
    if "remark" in payload:
        order.remark = (payload.get("remark") or "").strip()

    if "purchase_id" in payload:
        raw_purchase_id = payload.get("purchase_id")
        if raw_purchase_id in (None, ""):
            order.purchase_id = None
        else:
            try:
                order.purchase_id = int(raw_purchase_id)
            except (TypeError, ValueError):
                return api_error("Invalid number: purchase_id")

    if "technician_id" in payload:
        raw_technician_id = payload.get("technician_id")
        if raw_technician_id in (None, ""):
            order.technician_id = None
        else:
            try:
                order.technician_id = int(raw_technician_id) or None
            except (TypeError, ValueError):
                return api_error("Invalid number: technician_id")

    if "price" in payload:
        try:
            order.price = Decimal(str(payload.get("price") or "0"))
        except (InvalidOperation, ValueError):
            return api_error("Invalid number: price")

    if "line_items" in payload:
        items, error = _parse_line_items(payload.get("line_items"), require_dict_items=True)
        if error:
            return error
        order.line_items = items

    if "period_start" in payload:
        value, error = parse_date(payload.get("period_start"), "period_start")
        if error:
            return error
        if value:
            order.period_start = value

    if "period_end" in payload:
        value, error = parse_date(payload.get("period_end"), "period_end")
        if error:
            return error
        if value:
            order.period_end = value

    return None


def _build_sales_line_payload(base_payload, item, line_items):
    payload = base_payload.copy()
    # Each input line becomes one sales_order row: in-house lines use technician_id, BP lines use purchase_id.
    technician_id = item.get("technician_id")
    purchase_id = item.get("purchase_id")
    if technician_id not in (None, ""):
        purchase_id = None
    payload["technician_id"] = technician_id
    payload["technician_name"] = item.get("technician_name") or ""
    payload["purchase_id"] = purchase_id
    payload["price"] = item.get("price") or ""
    payload["line_items"] = line_items
    return payload


def _build_sales_orders(payload, line_items, pdf_file, current_user, now):
    saved_pdf = _save_order_pdf("sales", payload.get("order_no"), pdf_file)
    if saved_pdf is None:
        return None, api_error("Invalid PDF file")

    orders = []
    for index, line_item in enumerate(line_items, start=1):
        line_payload = _build_sales_line_payload(payload, line_item, line_items)
        if not line_payload.get("technician_id") and not line_payload.get("purchase_id"):
            return None, api_error(f"Missing field: line_items[{index}].purchase_id")
        if not str(line_payload.get("technician_name") or "").strip():
            return None, api_error(f"Missing field: line_items[{index}].technician_name")
        order = SalesOrder()
        apply_error = _apply_sales_payload(order, line_payload)
        if apply_error:
            return None, apply_error
        order.pdf_file = saved_pdf
        _set_created_audit(order, current_user, now)
        orders.append(order)
    return orders, None


def _apply_filters(queryset, request):
    order_no = (request.GET.get("order_no") or "").strip()
    project_name = (request.GET.get("project_name") or "").strip()
    customer_id = (request.GET.get("customer_id") or "").strip()
    technician_name = (request.GET.get("technician_name") or "").strip()
    status = (request.GET.get("status") or "").strip()
    created_start = request.GET.get("created_start")
    created_end = request.GET.get("created_end")
    only_self = request.GET.get("only_self")

    if order_no:
        queryset = queryset.filter(order_no__icontains=order_no)
    if project_name:
        queryset = queryset.filter(project_name__icontains=project_name)
    if customer_id:
        try:
            queryset = queryset.filter(customer_id=int(customer_id))
        except ValueError:
            return None, api_error(
                "Invalid customer_id"
            )
    if technician_name:
        if _model_has_field(queryset.model, "technician_name"):
            queryset = queryset.filter(technician_name__icontains=technician_name)
    if status:
        queryset = queryset.filter(status=status)
    if only_self == "1":
        current_user = _current_user(request)
        queryset = queryset.filter(created_by=current_user, updated_by=current_user)

    if created_start:
        start_date, error = parse_date(created_start, "created_start")
        if error:
            return None, error
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)

    if created_end:
        end_date, error = parse_date(created_end, "created_end")
        if error:
            return None, error
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

    return queryset, None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def purchase_orders_api(request):
    _login_id, error = require_login(request)
    if error:
        return error

    if request.method == "GET":
        queryset = PurchaseOrder.objects.filter(deleted_at__isnull=True).order_by("-created_at", "-id")
        return _list_orders(queryset, request, _serialize_purchase)

    if request.method == "POST":
        payload, error = parse_request_body(request)
        if error:
            return error
        payload = payload_to_dict(payload)
        payload["status"] = "已创建"
        required_error = require_fields(payload, ORDER_REQUIRED_FIELDS) or _require_person_in_charge(payload)
        if required_error:
            return required_error
        order = PurchaseOrder()
        apply_error = _apply_purchase_payload(order, payload)
        if apply_error:
            return apply_error
        now = timezone.now()
        _set_created_audit(order, _current_user(request), now)
        pdf_file = request.FILES.get("pdf_file")
        if pdf_file:
            saved_pdf = _save_order_pdf("purchase", order.order_no, pdf_file)
            if saved_pdf is None:
                return api_error("Invalid PDF file")
            order.pdf_file = saved_pdf
        order.save()
        item = _serialize_purchase(order)
        return api_success(data={"item": item})

    return api_error(
        "Method not allowed",
        status=405
    )


@csrf_exempt
@require_http_methods(["POST"])
def purchase_order_update_api(request, order_id):
    _login_id, error = require_login(request)
    if error:
        return error

    if request.method != "POST":
        return api_error(
            "Method not allowed",
            status=405
        )

    order = PurchaseOrder.objects.filter(id=order_id, deleted_at__isnull=True).first()
    if not order:
        return api_error(
            "Order not found",
            status=404
        )

    return _update_purchase_order_from_request(request, order)


# PDF文件预览
@require_http_methods(["GET"])
def purchase_order_pdf_api(request, order_id):
    return _order_pdf_response(request, PurchaseOrder, order_id)


@require_http_methods(["GET"])
def sales_order_pdf_api(request, order_id):
    return _order_pdf_response(request, SalesOrder, order_id)


def _order_pdf_response(request, model, order_id):
    _login_id, error = require_login(request)
    if error:
        return error

    order = model.objects.filter(id=order_id, deleted_at__isnull=True).first()
    if not order or not order.pdf_file:
        return api_error("File not found", status=404)

    return _serve_order_pdf_file(order.pdf_file)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def sales_orders_api(request):
    _login_id, error = require_login(request)
    if error:
        return error

    if request.method == "GET":
        queryset = SalesOrder.objects.filter(deleted_at__isnull=True).order_by("-created_at", "-id")
        return _list_orders(queryset, request, _serialize_sales)

    if request.method == "POST":
        payload, error = parse_request_body(request)
        if error:
            return error
        payload = payload_to_dict(payload)
        payload["status"] = "已受注"
        required_error = require_fields(payload, ORDER_REQUIRED_FIELDS) or _require_person_in_charge(payload)
        if required_error:
            return required_error
        line_items, error = _parse_line_items(payload.get("line_items"), require_dict_items=True)
        if error:
            return error
        if not line_items:
            return api_error("Missing field: line_items")
        pdf_file = request.FILES.get("pdf_file")
        if not pdf_file:
            return api_error("Missing field: pdf_file")
        now = timezone.now()
        orders, error = _build_sales_orders(payload, line_items, pdf_file, _current_user(request), now)
        if error:
            return error
        with transaction.atomic():
            for order in orders:
                order.save()
        items = [_serialize_sales(order) for order in orders]
        return api_success(data={"item": items[0] if items else None, "items": items, "created_count": len(items)})

    return api_error(
        "Method not allowed",
        status=405
    )


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def sales_order_detail_api(request, order_id):
    _login_id, error = require_login(request)
    if error:
        return error

    order = SalesOrder.objects.filter(id=order_id, deleted_at__isnull=True).first()
    if not order:
        return api_error(
            "Order not found",
            status=404
        )

    if request.method == "GET":
        item = _serialize_sales(order)
        return api_success(data={"item": item})

    if request.method == "PUT":
        payload, error = parse_json_body(request)
        if error:
            return error
        apply_error = _apply_sales_payload(order, payload)
        if apply_error:
            return apply_error
        _set_updated_audit(order, request)
        order.save()
        item = _serialize_sales(order)
        return api_success(data={"item": item})

    return api_error(
        "Method not allowed",
        status=405
    )
