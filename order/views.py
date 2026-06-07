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
from finance.models import FinanceReceivable
from order.models import PayRequest, PurchaseOrder, SalesOrder
from project.api import api_error, api_paginated, api_success
from project.error_codes import ErrorCode
from project import storage
from project.common_tools import (
    is_pdf_upload,
    paginate_queryset,
    parse_date,
    parse_json_body,
    parse_request_body,
    payload_to_dict,
    require_fields,
    require_login,
    shift_month,
)
from project.storage import StorageArea


PURCHASE_STATUSES = {"已创建", "承认中", "已承认", "已取消"}
PURCHASE_APPROVING_NEXT_STATUSES = {"已承认", "已取消"}
PURCHASE_TERMINAL_STATUSES = {"已承认", "已取消"}
SALES_STATUSES = {"已受注", "已取消"}
PAY_REQUEST_STATUSES = {"待付款", "已付款", "已取消"}
ORDER_REQUIRED_FIELDS = (
    "order_no",
    "project_name",
    "customer_id",
    "customer_name",
    "status",
    "period_start",
    "period_end",
)
PAY_REQUEST_REQUIRED_FIELDS = (
    "request_no",
    "customer_id",
    "customer_name",
    "status",
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
    if not is_pdf_upload(uploaded_file):
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
        return api_error(ErrorCode.FILE_NOT_FOUND, status=404)
    filename = _order_storage_filename(pdf_file)
    try:
        safe_path = storage.path(StorageArea.ORDER, filename)
    except ValueError:
        return api_error(ErrorCode.FILE_PATH_INVALID)
    if not storage.exists(StorageArea.ORDER, filename):
        return api_error(ErrorCode.FILE_NOT_FOUND, status=404)

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
        ErrorCode.ORDER_STATUS_INVALID
    )


def _normalize_sales_status(value):
    raw = str(value or "").strip()
    if raw in SALES_STATUSES:
        return raw, None
    return None, api_error(
        ErrorCode.ORDER_STATUS_INVALID
    )


def _normalize_pay_request_status(value):
    raw = str(value or "").strip()
    if raw in PAY_REQUEST_STATUSES:
        return raw, None
    return None, api_error(ErrorCode.ORDER_STATUS_INVALID)


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


def _parse_pay_request_details(raw_details):
    if raw_details in (None, ""):
        return []
    if isinstance(raw_details, list):
        return raw_details
    try:
        details = json.loads(raw_details)
    except (TypeError, json.JSONDecodeError):
        return []
    return details if isinstance(details, list) else []


def _serialize_pay_request(pay_request):
    created_at = timezone.localtime(pay_request.created_at) if pay_request.created_at else None
    updated_at = timezone.localtime(pay_request.updated_at) if pay_request.updated_at else None
    details = _parse_pay_request_details(pay_request.details)
    return {
        "id": pay_request.id,
        "request_no": pay_request.request_no,
        "order_no": pay_request.order_no or "",
        "subject": pay_request.subject or "",
        "status": pay_request.status,
        "customer_id": pay_request.customer_id,
        "customer_name": pay_request.customer_name,
        "total_amount": str(pay_request.total_amount) if pay_request.total_amount is not None else "0.00",
        "due_date": pay_request.due_date.isoformat() if pay_request.due_date else "",
        "details": details,
        "pdf_file": pay_request.pdf_file or "",
        "remark": pay_request.remark or "",
        "created_by": pay_request.created_by,
        "created_at": created_at.strftime("%Y-%m-%d %H:%M") if created_at else "",
        "updated_by": pay_request.updated_by or "",
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


def _decimal_from_value(value):
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_pay_request_details_payload(raw_details):
    if raw_details in (None, ""):
        return [], None
    if isinstance(raw_details, list):
        details = raw_details
    else:
        try:
            details = json.loads(raw_details)
        except (TypeError, json.JSONDecodeError):
            return None, api_error(ErrorCode.ORDER_DETAILS_INVALID_JSON)
    if not isinstance(details, list) or any(not isinstance(item, dict) for item in details):
        return None, api_error(ErrorCode.ORDER_DETAILS_INVALID_JSON)
    return details, None


def _calculate_pay_request_total(details):
    total = Decimal("0")
    for item in details:
        amount = _decimal_from_value(item.get("amount"))
        if not amount:
            qty = _decimal_from_value(item.get("qty") or "1")
            price = _decimal_from_value(item.get("price"))
            amount = qty * price
        total += amount + _decimal_from_value(item.get("tax"))
    return total.quantize(Decimal("0.01"))


def _calculate_receivable_outstanding(receivable_amount, received_amount):
    outstanding = _decimal_from_value(receivable_amount) - _decimal_from_value(received_amount)
    if outstanding < 0:
        outstanding = Decimal("0")
    return outstanding.quantize(Decimal("0.01"))


def _sync_pay_request_receivable(pay_request, employee_id):
    now = timezone.now()
    receivable = FinanceReceivable.objects.filter(pay_request_id=pay_request.id).first()

    if pay_request.status == "已取消":
        if receivable and receivable.deleted_at is None:
            receivable.deleted_at = now
            receivable.updated_by = employee_id
            receivable.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        return receivable

    receivable_amount = _decimal_from_value(pay_request.total_amount).quantize(Decimal("0.01"))
    if receivable:
        receivable.pay_request_id = pay_request.id
        receivable.request_no = pay_request.request_no or None
        receivable.customer_id = pay_request.customer_id or None
        receivable.customer_name = pay_request.customer_name
        receivable.receivable_amount = receivable_amount
        receivable.outstanding_amount = _calculate_receivable_outstanding(
            receivable.receivable_amount,
            receivable.received_amount,
        )
        receivable.due_date = pay_request.due_date
        receivable.updated_by = employee_id
        receivable.deleted_at = None
        receivable.save()
        return receivable

    return FinanceReceivable.objects.create(
        pay_request_id=pay_request.id,
        request_no=pay_request.request_no or None,
        customer_id=pay_request.customer_id or None,
        customer_name=pay_request.customer_name,
        receivable_amount=receivable_amount,
        received_amount=Decimal("0.00"),
        outstanding_amount=receivable_amount,
        due_date=pay_request.due_date,
        finance_status=0,
        remark=None,
        created_by=employee_id,
        updated_by=employee_id,
    )


def _apply_pay_request_payload(pay_request, payload):
    if "request_no" in payload:
        pay_request.request_no = (payload.get("request_no") or "").strip()
    if "order_no" in payload:
        pay_request.order_no = (payload.get("order_no") or "").strip()
    if "subject" in payload:
        pay_request.subject = (payload.get("subject") or "").strip()
    if "status" in payload:
        value, error = _normalize_pay_request_status(payload.get("status"))
        if error:
            return error
        pay_request.status = value
    if "customer_name" in payload:
        pay_request.customer_name = (payload.get("customer_name") or "").strip()
    if "customer_id" in payload:
        try:
            pay_request.customer_id = int(payload.get("customer_id") or 0)
        except (TypeError, ValueError):
            return api_error(ErrorCode.ORDER_CUSTOMER_ID_INVALID)
    if "due_date" in payload:
        value, error = parse_date(payload.get("due_date"), "due_date")
        if error:
            return error
        pay_request.due_date = value
    if "remark" in payload:
        pay_request.remark = (payload.get("remark") or "").strip()
    if "details" in payload:
        details, error = _parse_pay_request_details_payload(payload.get("details"))
        if error:
            return error
        pay_request.details = json.dumps(details, ensure_ascii=False)
        pay_request.total_amount = _calculate_pay_request_total(details)
    return None


def _require_person_in_charge(payload):
    if payload.get("person_in_charge_id") or str(payload.get("person_in_charge") or "").strip():
        return None
    return api_error(ErrorCode.ORDER_PERSON_IN_CHARGE_REQUIRED)


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
            return api_error(ErrorCode.ORDER_PERSON_IN_CHARGE_ID_INVALID)
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
            return None, api_error(ErrorCode.ORDER_LINE_ITEMS_INVALID_JSON)
    if not isinstance(items, list):
        return None, api_error(ErrorCode.ORDER_LINE_ITEMS_INVALID_JSON)
    if require_dict_items and any(not isinstance(item, dict) for item in items):
        return None, api_error(ErrorCode.ORDER_LINE_ITEMS_INVALID_JSON)
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
            return api_error(ErrorCode.ORDER_CUSTOMER_ID_INVALID)
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
        return api_error(ErrorCode.ORDER_LOCKED)
    if order.status == "承认中":
        if payload_keys != {"status"} or request.FILES:
            return api_error(ErrorCode.ORDER_LOCKED)
        next_status, status_error = _normalize_purchase_status(payload.get("status"))
        if status_error:
            return status_error
        if next_status not in PURCHASE_APPROVING_NEXT_STATUSES:
            return api_error(ErrorCode.ORDER_STATUS_INVALID)
    apply_error = _apply_purchase_payload(order, payload)
    if apply_error:
        return apply_error
    pdf_file = request.FILES.get("pdf_file")
    if pdf_file:
        saved_pdf = _save_order_pdf("purchase", order.order_no, pdf_file)
        if saved_pdf is None:
            return api_error(ErrorCode.ORDER_PDF_INVALID)
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
            return api_error(ErrorCode.ORDER_CUSTOMER_ID_INVALID)
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
                return api_error(ErrorCode.ORDER_PURCHASE_ID_INVALID)

    if "technician_id" in payload:
        raw_technician_id = payload.get("technician_id")
        if raw_technician_id in (None, ""):
            order.technician_id = None
        else:
            try:
                order.technician_id = int(raw_technician_id) or None
            except (TypeError, ValueError):
                return api_error(ErrorCode.ORDER_TECHNICIAN_ID_INVALID)

    if "price" in payload:
        try:
            order.price = Decimal(str(payload.get("price") or "0"))
        except (InvalidOperation, ValueError):
            return api_error(ErrorCode.ORDER_PRICE_INVALID)

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
        return None, api_error(ErrorCode.ORDER_PDF_INVALID)

    orders = []
    for index, line_item in enumerate(line_items, start=1):
        line_payload = _build_sales_line_payload(payload, line_item, line_items)
        if not line_payload.get("technician_id") and not line_payload.get("purchase_id"):
            return None, api_error(ErrorCode.ORDER_LINE_ITEM_PURCHASE_ID_REQUIRED, f"Missing field: line_items[{index}].purchase_id")
        if not str(line_payload.get("technician_name") or "").strip():
            return None, api_error(ErrorCode.ORDER_LINE_ITEM_TECHNICIAN_NAME_REQUIRED, f"Missing field: line_items[{index}].technician_name")
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
                ErrorCode.ORDER_INVALID_CUSTOMER_ID
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
                return api_error(ErrorCode.ORDER_PDF_INVALID)
            order.pdf_file = saved_pdf
        order.save()
        item = _serialize_purchase(order)
        return api_success(data={"item": item})

    return api_error(
        ErrorCode.METHOD_NOT_ALLOWED,
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
            ErrorCode.METHOD_NOT_ALLOWED,
            status=405
        )

    order = PurchaseOrder.objects.filter(id=order_id, deleted_at__isnull=True).first()
    if not order:
        return api_error(
            ErrorCode.PURCHASE_ORDER_NOT_FOUND
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
        return api_error(ErrorCode.FILE_NOT_FOUND, status=404)

    return _serve_order_pdf_file(order.pdf_file)


def _apply_pay_request_filters(queryset, request):
    request_no = (request.GET.get("request_no") or "").strip()
    customer_name = (request.GET.get("customer_name") or "").strip()
    status = (request.GET.get("status") or "").strip()
    month = (request.GET.get("month") or "").strip()

    if request_no:
        queryset = queryset.filter(request_no__icontains=request_no)
    if customer_name:
        queryset = queryset.filter(customer_name__icontains=customer_name)
    if status:
        queryset = queryset.filter(status=status)
    if month:
        try:
            start = timezone.datetime.strptime(month, "%Y-%m").date().replace(day=1)
        except ValueError:
            return None, api_error(ErrorCode.PAY_REQUEST_MONTH_INVALID)
        end = shift_month(start, 1)
        queryset = queryset.filter(created_at__date__gte=start, created_at__date__lt=end)
    return queryset, None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def pay_requests_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "GET":
        queryset = PayRequest.objects.filter(deleted_at__isnull=True).order_by("-created_at", "-id")
        queryset, filter_error = _apply_pay_request_filters(queryset, request)
        if filter_error:
            return filter_error
        paged, total, page, page_size, total_pages = paginate_queryset(queryset, request)
        return api_paginated(
            items=[_serialize_pay_request(item) for item in paged],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    payload, error = parse_request_body(request)
    if error:
        return error
    payload = payload_to_dict(payload)
    payload["status"] = payload.get("status") or "待付款"
    required_error = require_fields(payload, PAY_REQUEST_REQUIRED_FIELDS)
    if required_error:
        return required_error

    pay_request = PayRequest()
    apply_error = _apply_pay_request_payload(pay_request, payload)
    if apply_error:
        return apply_error
    if not _parse_pay_request_details(pay_request.details):
        return api_error(ErrorCode.PAY_REQUEST_DETAILS_REQUIRED)
    now = timezone.now()
    _set_created_audit(pay_request, _current_user(request), now)
    pdf_file = request.FILES.get("pdf_file")
    if pdf_file:
        saved_pdf = _save_order_pdf("pay_request", pay_request.request_no, pdf_file)
        if saved_pdf is None:
            return api_error(ErrorCode.ORDER_PDF_INVALID)
        pay_request.pdf_file = saved_pdf
    with transaction.atomic():
        pay_request.save()
        _sync_pay_request_receivable(pay_request, login_id)
    return api_success(data={"item": _serialize_pay_request(pay_request)})


@csrf_exempt
@require_http_methods(["GET"])
def pay_request_detail_api(request, pay_request_id):
    _login_id, error = require_login(request)
    if error:
        return error

    pay_request = PayRequest.objects.filter(id=pay_request_id, deleted_at__isnull=True).first()
    if not pay_request:
        return api_error(ErrorCode.PAY_REQUEST_NOT_FOUND)
    return api_success(data={"item": _serialize_pay_request(pay_request)})


@csrf_exempt
@require_http_methods(["POST"])
def pay_request_update_api(request, pay_request_id):
    login_id, error = require_login(request)
    if error:
        return error

    pay_request = PayRequest.objects.filter(id=pay_request_id, deleted_at__isnull=True).first()
    if not pay_request:
        return api_error(ErrorCode.PAY_REQUEST_NOT_FOUND)

    payload, error = parse_request_body(request)
    if error:
        return error
    payload = payload_to_dict(payload)
    apply_error = _apply_pay_request_payload(pay_request, payload)
    if apply_error:
        return apply_error
    pdf_file = request.FILES.get("pdf_file")
    if pdf_file:
        saved_pdf = _save_order_pdf("pay_request", pay_request.request_no, pdf_file)
        if saved_pdf is None:
            return api_error(ErrorCode.ORDER_PDF_INVALID)
        pay_request.pdf_file = saved_pdf
    _set_updated_audit(pay_request, request)
    with transaction.atomic():
        pay_request.save()
        _sync_pay_request_receivable(pay_request, login_id)
    return api_success(data={"item": _serialize_pay_request(pay_request)})


@require_http_methods(["GET"])
def pay_request_pdf_api(request, pay_request_id):
    return _order_pdf_response(request, PayRequest, pay_request_id)


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
            return api_error(ErrorCode.ORDER_LINE_ITEMS_REQUIRED)
        pdf_file = request.FILES.get("pdf_file")
        if not pdf_file:
            return api_error(ErrorCode.ORDER_PDF_REQUIRED)
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
        ErrorCode.METHOD_NOT_ALLOWED,
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
            ErrorCode.SALES_ORDER_NOT_FOUND
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
        ErrorCode.METHOD_NOT_ALLOWED,
        status=405
    )
