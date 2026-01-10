import calendar
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from project.api import api_error, api_paginated, api_success
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from order.models import PayRequest, PurchaseOrder, SalesOrder


def _require_login(request):
    if not request.session.get("employee_id"):
        return api_error(
            "Unauthorized",
            status=401,
            legacy={"error": "Unauthorized"},
        )
    return None


def _parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, api_error(
            "Invalid JSON body",
            status=400,
            legacy={"error": "Invalid JSON body"},
        )


def _parse_date(value, field):
    if value in (None, ""):
        return None, None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except (TypeError, ValueError):
        return None, api_error(
            f"Invalid date: {field}",
            status=400,
            legacy={"error": f"Invalid date: {field}"},
        )


def _normalize_number(value):
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    raw = str(value)
    raw = raw.replace(",", "")
    raw = raw.replace("¥", "").replace("￥", "")
    raw = raw.replace("h", "").replace("H", "")
    return raw.strip()


def _parse_decimal(value, field):
    raw = _normalize_number(value)
    if raw == "":
        return Decimal("0"), None
    try:
        return Decimal(raw), None
    except (InvalidOperation, ValueError):
        return None, api_error(
            f"Invalid number: {field}",
            status=400,
            legacy={"error": f"Invalid number: {field}"},
        )


def _parse_int(value, field):
    if value in (None, ""):
        return None, None
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, api_error(
            f"Invalid number: {field}",
            status=400,
            legacy={"error": f"Invalid number: {field}"},
        )


def _is_truthy(value):
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_pay_request_status(value):
    if value in (None, ""):
        return None, api_error(
            "Invalid status",
            status=400,
            legacy={"error": "Invalid status"},
        )
    raw = str(value).strip().lower()
    mapping = {
        "0": "0",
        "1": "1",
        "pending": "0",
        "paid": "1",
        "待支付": "0",
        "已支付": "1",
    }
    if raw in mapping:
        return mapping[raw], None
    return None, api_error(
        "Invalid status",
        status=400,
        legacy={"error": "Invalid status"},
    )


def _dump_json_field(value, default):
    if value in (None, ""):
        return json.dumps(default, ensure_ascii=True)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, str):
        try:
            json.loads(value)
            return value
        except json.JSONDecodeError:
            return json.dumps(value, ensure_ascii=True)
    return json.dumps(value, ensure_ascii=True)


def _load_json_field(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _serialize_purchase(order):
    created_at = timezone.localtime(order.created_at) if order.created_at else None
    updated_at = timezone.localtime(order.updated_at) if order.updated_at else None
    return {
        "id": order.id,
        "order_no": order.order_no,
        "person_in_charge": order.person_in_charge,
        "status": order.status,
        "project_name": order.project_name,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "technician_name": order.technician_name or "",
        "price": str(order.price) if order.price is not None else "",
        "working_hours": str(order.working_hours) if order.working_hours is not None else "",
        "period_start": order.period_start.isoformat() if order.period_start else "",
        "period_end": order.period_end.isoformat() if order.period_end else "",
        "remark": order.remark or "",
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
        "person_in_charge": order.person_in_charge,
        "status": order.status,
        "purchase_id": order.purchase_id,
        "project_name": order.project_name,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "technician_id": order.technician_id or 0,
        "technician_name": order.technician_name or "",
        "price": str(order.price) if order.price is not None else "",
        "working_hours": str(order.working_hours) if order.working_hours is not None else "",
        "period_start": order.period_start.isoformat() if order.period_start else "",
        "period_end": order.period_end.isoformat() if order.period_end else "",
        "remark": order.remark or "",
        "created_by": order.created_by,
        "created_at": created_at.strftime("%Y-%m-%d %H:%M") if created_at else "",
        "updated_by": order.updated_by or "",
        "updated_at": updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else "",
    }


def _serialize_pay_request(request_item):
    created_at = timezone.localtime(request_item.created_at) if request_item.created_at else None
    updated_at = timezone.localtime(request_item.updated_at) if request_item.updated_at else None
    return {
        "id": request_item.id,
        "request_no": request_item.request_no,
        "order_no": request_item.order_no or "",
        "status": request_item.status,
        "customer_id": request_item.customer_id,
        "customer_name": request_item.customer_name,
        "total_amount": str(request_item.total_amount) if request_item.total_amount is not None else "",
        "request_date": request_item.request_date.isoformat() if request_item.request_date else "",
        "due_date": request_item.due_date.isoformat() if request_item.due_date else "",
        "details": _load_json_field(request_item.details, []),
        "tax_breakdown": _load_json_field(request_item.tax_breakdown, {}),
        "attachments": _load_json_field(request_item.attachments, []),
        "remark": request_item.remark or "",
        "created_by": request_item.created_by,
        "created_at": created_at.strftime("%Y-%m-%d %H:%M") if created_at else "",
        "updated_by": request_item.updated_by or "",
        "updated_at": updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else "",
    }


def _apply_purchase_payload(order, payload):
    if "order_no" in payload:
        order.order_no = (payload.get("order_no") or "").strip()
    if "person_in_charge" in payload:
        order.person_in_charge = (payload.get("person_in_charge") or "").strip()
    if "status" in payload:
        order.status = (payload.get("status") or "").strip()
    if "project_name" in payload:
        order.project_name = (payload.get("project_name") or "").strip()
    if "customer_name" in payload:
        order.customer_name = (payload.get("customer_name") or "").strip()
    if "technician_name" in payload:
        order.technician_name = (payload.get("technician_name") or "").strip()
    if "customer_id" in payload:
        value, error = _parse_int(payload.get("customer_id"), "customer_id")
        if error:
            return error
        order.customer_id = value or 0
    if "remark" in payload:
        order.remark = (payload.get("remark") or "").strip()

    if "price" in payload:
        value, error = _parse_decimal(payload.get("price"), "price")
        if error:
            return error
        order.price = value

    if "working_hours" in payload:
        value, error = _parse_decimal(payload.get("working_hours"), "working_hours")
        if error:
            return error
        order.working_hours = value

    if "period_start" in payload:
        value, error = _parse_date(payload.get("period_start"), "period_start")
        if error:
            return error
        if value:
            order.period_start = value

    if "period_end" in payload:
        value, error = _parse_date(payload.get("period_end"), "period_end")
        if error:
            return error
        if value:
            order.period_end = value

    return None


def _apply_sales_payload(order, payload):
    if "order_no" in payload:
        order.order_no = (payload.get("order_no") or "").strip()
    if "person_in_charge" in payload:
        order.person_in_charge = (payload.get("person_in_charge") or "").strip()
    if "status" in payload:
        order.status = (payload.get("status") or "").strip()
    if "project_name" in payload:
        order.project_name = (payload.get("project_name") or "").strip()
    if "customer_name" in payload:
        order.customer_name = (payload.get("customer_name") or "").strip()
    if "technician_name" in payload:
        order.technician_name = (payload.get("technician_name") or "").strip()
    if "customer_id" in payload:
        value, error = _parse_int(payload.get("customer_id"), "customer_id")
        if error:
            return error
        order.customer_id = value or 0
    if "remark" in payload:
        order.remark = (payload.get("remark") or "").strip()

    if "purchase_id" in payload:
        value, error = _parse_int(payload.get("purchase_id"), "purchase_id")
        if error:
            return error
        order.purchase_id = value or 0

    if "technician_id" in payload:
        value, error = _parse_int(payload.get("technician_id"), "technician_id")
        if error:
            return error
        order.technician_id = value or None

    if "price" in payload:
        value, error = _parse_decimal(payload.get("price"), "price")
        if error:
            return error
        order.price = value

    if "working_hours" in payload:
        value, error = _parse_decimal(payload.get("working_hours"), "working_hours")
        if error:
            return error
        order.working_hours = value

    if "period_start" in payload:
        value, error = _parse_date(payload.get("period_start"), "period_start")
        if error:
            return error
        if value:
            order.period_start = value

    if "period_end" in payload:
        value, error = _parse_date(payload.get("period_end"), "period_end")
        if error:
            return error
        if value:
            order.period_end = value

    return None


def _apply_pay_request_payload(request_item, payload):
    if "request_no" in payload:
        request_item.request_no = (payload.get("request_no") or "").strip()
    if "order_no" in payload:
        request_item.order_no = (payload.get("order_no") or "").strip()
    if "status" in payload:
        value, error = _normalize_pay_request_status(payload.get("status"))
        if error:
            return error
        request_item.status = value
    if "customer_name" in payload:
        request_item.customer_name = (payload.get("customer_name") or "").strip()
    if "remark" in payload:
        request_item.remark = (payload.get("remark") or "").strip()

    if "customer_id" in payload:
        value, error = _parse_int(payload.get("customer_id"), "customer_id")
        if error:
            return error
        request_item.customer_id = value or 0

    if "total_amount" in payload:
        value, error = _parse_decimal(payload.get("total_amount"), "total_amount")
        if error:
            return error
        request_item.total_amount = value

    if "request_date" in payload:
        value, error = _parse_date(payload.get("request_date"), "request_date")
        if error:
            return error
        if value:
            request_item.request_date = value

    if "due_date" in payload:
        value, error = _parse_date(payload.get("due_date"), "due_date")
        if error:
            return error
        request_item.due_date = value

    if "details" in payload:
        request_item.details = _dump_json_field(payload.get("details"), [])
    if "tax_breakdown" in payload:
        request_item.tax_breakdown = _dump_json_field(payload.get("tax_breakdown"), {})
    if "attachments" in payload:
        request_item.attachments = _dump_json_field(payload.get("attachments"), [])

    return None


def _paginate_queryset(queryset, request):
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
    total = queryset.count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * page_size
    return queryset[offset: offset + page_size], total, page, page_size, total_pages


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
                "Invalid customer_id",
                status=400,
                legacy={"error": "Invalid customer_id"},
            )
    if technician_name:
        queryset = queryset.filter(technician_name__icontains=technician_name)
    if status:
        queryset = queryset.filter(status=status)
    if _is_truthy(only_self):
        current_user = request.session.get("employee_id")
        queryset = queryset.filter(created_by=current_user, updated_by=current_user)

    if created_start:
        start_date, error = _parse_date(created_start, "created_start")
        if error:
            return None, error
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)

    if created_end:
        end_date, error = _parse_date(created_end, "created_end")
        if error:
            return None, error
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

    return queryset, None


def _apply_pay_request_filters(queryset, request):
    request_no = (request.GET.get("request_no") or "").strip()
    order_no = (request.GET.get("order_no") or "").strip()
    customer_name = (request.GET.get("customer_name") or "").strip()
    status = (request.GET.get("status") or "").strip()
    keyword = (request.GET.get("keyword") or "").strip()
    month = (request.GET.get("month") or "").strip()

    if request_no:
        queryset = queryset.filter(request_no__icontains=request_no)
    if order_no:
        queryset = queryset.filter(order_no__icontains=order_no)
    if customer_name:
        queryset = queryset.filter(customer_name__icontains=customer_name)
    if status:
        normalized, error = _normalize_pay_request_status(status)
        if error:
            return None, error
        queryset = queryset.filter(status=normalized)
    if keyword:
        queryset = queryset.filter(
            Q(request_no__icontains=keyword)
            | Q(order_no__icontains=keyword)
            | Q(customer_name__icontains=keyword)
        )
    if month:
        try:
            year, month_value = month.split("-", 1)
            year = int(year)
            month_value = int(month_value)
            last_day = calendar.monthrange(year, month_value)[1]
            start_date = datetime(year, month_value, 1).date()
            end_date = datetime(year, month_value, last_day).date()
        except (ValueError, calendar.IllegalMonthError):
            return None, api_error(
                "Invalid month",
                status=400,
                legacy={"error": "Invalid month"},
            )
        queryset = queryset.filter(request_date__gte=start_date, request_date__lte=end_date)

    return queryset, None


@csrf_exempt
def purchase_orders_api(request):
    auth_error = _require_login(request)
    if auth_error:
        return auth_error

    if request.method == "GET":
        queryset = PurchaseOrder.objects.filter(deleted_at__isnull=True).order_by("-created_at", "-id")
        queryset, error = _apply_filters(queryset, request)
        if error:
            return error
        paged, total, page, page_size, total_pages = _paginate_queryset(queryset, request)
        items = [_serialize_purchase(order) for order in paged]
        return api_paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    if request.method == "POST":
        payload, error = _parse_json_body(request)
        if error:
            return error
        required_fields = [
            "order_no",
            "project_name",
            "customer_id",
            "customer_name",
            "person_in_charge",
            "status",
            "period_start",
            "period_end",
        ]
        for field in required_fields:
            if str(payload.get(field) or "").strip() == "":
                return api_error(
                    f"Missing field: {field}",
                    status=400,
                    legacy={"error": f"Missing field: {field}"},
                )
        order = PurchaseOrder()
        apply_error = _apply_purchase_payload(order, payload)
        if apply_error:
            return apply_error
        now = timezone.now()
        current_user = request.session.get("employee_name") or request.session.get("user_name") or "系统"
        order.created_by = current_user
        order.updated_by = current_user
        order.created_at = now
        order.updated_at = now
        order.save()
        item = _serialize_purchase(order)
        return api_success(data={"item": item}, legacy={"status": "ok", "item": item})

    return api_error(
        "Method not allowed",
        status=405,
        legacy={"error": "Method not allowed"},
    )


@csrf_exempt
def purchase_order_detail_api(request, order_id):
    auth_error = _require_login(request)
    if auth_error:
        return auth_error

    order = PurchaseOrder.objects.filter(id=order_id, deleted_at__isnull=True).first()
    if not order:
        return api_error(
            "Order not found",
            status=404,
            legacy={"error": "Order not found"},
        )

    if request.method == "GET":
        item = _serialize_purchase(order)
        return api_success(data={"item": item}, legacy={"item": item})

    if request.method == "PUT":
        payload, error = _parse_json_body(request)
        if error:
            return error
        apply_error = _apply_purchase_payload(order, payload)
        if apply_error:
            return apply_error
        order.updated_by = request.session.get("employee_name") or request.session.get("user_name") or "系统"
        order.updated_at = timezone.now()
        order.save()
        item = _serialize_purchase(order)
        return api_success(data={"item": item}, legacy={"status": "ok", "item": item})

    return api_error(
        "Method not allowed",
        status=405,
        legacy={"error": "Method not allowed"},
    )


@csrf_exempt
def sales_orders_api(request):
    auth_error = _require_login(request)
    if auth_error:
        return auth_error

    if request.method == "GET":
        queryset = SalesOrder.objects.filter(deleted_at__isnull=True).order_by("-created_at", "-id")
        queryset, error = _apply_filters(queryset, request)
        if error:
            return error
        paged, total, page, page_size, total_pages = _paginate_queryset(queryset, request)
        items = [_serialize_sales(order) for order in paged]
        return api_paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    if request.method == "POST":
        payload, error = _parse_json_body(request)
        if error:
            return error
        required_fields = [
            "order_no",
            "purchase_id",
            "project_name",
            "customer_id",
            "customer_name",
            "person_in_charge",
            "status",
            "period_start",
            "period_end",
        ]
        for field in required_fields:
            if str(payload.get(field) or "").strip() == "":
                return api_error(
                    f"Missing field: {field}",
                    status=400,
                    legacy={"error": f"Missing field: {field}"},
                )
        order = SalesOrder()
        apply_error = _apply_sales_payload(order, payload)
        if apply_error:
            return apply_error
        now = timezone.now()
        current_user = request.session.get("employee_name") or request.session.get("user_name") or "系统"
        order.created_by = current_user
        order.updated_by = current_user
        order.created_at = now
        order.updated_at = now
        order.save()
        item = _serialize_sales(order)
        return api_success(data={"item": item}, legacy={"status": "ok", "item": item})

    return api_error(
        "Method not allowed",
        status=405,
        legacy={"error": "Method not allowed"},
    )


@csrf_exempt
def sales_order_detail_api(request, order_id):
    auth_error = _require_login(request)
    if auth_error:
        return auth_error

    order = SalesOrder.objects.filter(id=order_id, deleted_at__isnull=True).first()
    if not order:
        return api_error(
            "Order not found",
            status=404,
            legacy={"error": "Order not found"},
        )

    if request.method == "GET":
        item = _serialize_sales(order)
        return api_success(data={"item": item}, legacy={"item": item})

    if request.method == "PUT":
        payload, error = _parse_json_body(request)
        if error:
            return error
        apply_error = _apply_sales_payload(order, payload)
        if apply_error:
            return apply_error
        order.updated_by = request.session.get("employee_name") or request.session.get("user_name") or "系统"
        order.updated_at = timezone.now()
        order.save()
        item = _serialize_sales(order)
        return api_success(data={"item": item}, legacy={"status": "ok", "item": item})

    return api_error(
        "Method not allowed",
        status=405,
        legacy={"error": "Method not allowed"},
    )


@csrf_exempt
def pay_requests_api(request):
    auth_error = _require_login(request)
    if auth_error:
        return auth_error

    if request.method == "GET":
        queryset = PayRequest.objects.filter(deleted_at__isnull=True).order_by(
            "-request_date",
            "-created_at",
            "-id",
        )
        queryset, error = _apply_pay_request_filters(queryset, request)
        if error:
            return error
        paged, total, page, page_size, total_pages = _paginate_queryset(queryset, request)
        items = [_serialize_pay_request(item) for item in paged]
        return api_paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    if request.method == "POST":
        payload, error = _parse_json_body(request)
        if error:
            return error
        required_fields = [
            "request_no",
            "customer_id",
            "customer_name",
            "status",
        ]
        for field in required_fields:
            if str(payload.get(field) or "").strip() == "":
                return api_error(
                    f"Missing field: {field}",
                    status=400,
                    legacy={"error": f"Missing field: {field}"},
                )
        request_item = PayRequest()
        apply_error = _apply_pay_request_payload(request_item, payload)
        if apply_error:
            return apply_error
        if not request_item.request_date:
            request_item.request_date = timezone.localdate()
        now = timezone.now()
        current_user = request.session.get("employee_name") or request.session.get("user_name") or "系统"
        request_item.created_by = current_user
        request_item.updated_by = current_user
        request_item.created_at = now
        request_item.updated_at = now
        request_item.save()
        item = _serialize_pay_request(request_item)
        return api_success(data={"item": item}, legacy={"status": "ok", "item": item})

    return api_error(
        "Method not allowed",
        status=405,
        legacy={"error": "Method not allowed"},
    )


@csrf_exempt
def pay_request_detail_api(request, request_id):
    auth_error = _require_login(request)
    if auth_error:
        return auth_error

    request_item = PayRequest.objects.filter(id=request_id, deleted_at__isnull=True).first()
    if not request_item:
        return api_error(
            "Pay request not found",
            status=404,
            legacy={"error": "Pay request not found"},
        )

    if request.method == "GET":
        item = _serialize_pay_request(request_item)
        return api_success(data={"item": item}, legacy={"item": item})

    if request.method == "PUT":
        payload, error = _parse_json_body(request)
        if error:
            return error
        apply_error = _apply_pay_request_payload(request_item, payload)
        if apply_error:
            return apply_error
        request_item.updated_by = request.session.get("employee_name") or request.session.get("user_name") or "系统"
        request_item.updated_at = timezone.now()
        request_item.save()
        item = _serialize_pay_request(request_item)
        return api_success(data={"item": item}, legacy={"status": "ok", "item": item})

    return api_error(
        "Method not allowed",
        status=405,
        legacy={"error": "Method not allowed"},
    )
