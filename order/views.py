import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from order.models import PurchaseOrder, SalesOrder


def _require_login(request):
    if not request.session.get("employee_id"):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    return None


def _parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)


def _parse_date(value, field):
    if value in (None, ""):
        return None, None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except (TypeError, ValueError):
        return None, JsonResponse({"error": f"Invalid date: {field}"}, status=400)


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
        return None, JsonResponse({"error": f"Invalid number: {field}"}, status=400)


def _parse_int(value, field):
    if value in (None, ""):
        return None, None
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, JsonResponse({"error": f"Invalid number: {field}"}, status=400)


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
        "created_by": order.created_by,
        "created_at": created_at.strftime("%Y-%m-%d %H:%M") if created_at else "",
        "updated_by": order.updated_by or "",
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

    if order_no:
        queryset = queryset.filter(order_no__icontains=order_no)
    if project_name:
        queryset = queryset.filter(project_name__icontains=project_name)
    if customer_id:
        try:
            queryset = queryset.filter(customer_id=int(customer_id))
        except ValueError:
            return None, JsonResponse({"error": "Invalid customer_id"}, status=400)
    if technician_name:
        queryset = queryset.filter(technician_name__icontains=technician_name)
    if status:
        queryset = queryset.filter(status=status)

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
        return JsonResponse(
            {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }
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
                return JsonResponse({"error": f"Missing field: {field}"}, status=400)
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
        return JsonResponse({"status": "ok", "item": _serialize_purchase(order)})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def purchase_order_detail_api(request, order_id):
    auth_error = _require_login(request)
    if auth_error:
        return auth_error

    order = PurchaseOrder.objects.filter(id=order_id, deleted_at__isnull=True).first()
    if not order:
        return JsonResponse({"error": "Order not found"}, status=404)

    if request.method == "GET":
        return JsonResponse({"item": _serialize_purchase(order)})

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
        return JsonResponse({"status": "ok", "item": _serialize_purchase(order)})

    return JsonResponse({"error": "Method not allowed"}, status=405)


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
        return JsonResponse(
            {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }
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
                return JsonResponse({"error": f"Missing field: {field}"}, status=400)
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
        return JsonResponse({"status": "ok", "item": _serialize_sales(order)})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def sales_order_detail_api(request, order_id):
    auth_error = _require_login(request)
    if auth_error:
        return auth_error

    order = SalesOrder.objects.filter(id=order_id, deleted_at__isnull=True).first()
    if not order:
        return JsonResponse({"error": "Order not found"}, status=404)

    if request.method == "GET":
        return JsonResponse({"item": _serialize_sales(order)})

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
        return JsonResponse({"status": "ok", "item": _serialize_sales(order)})

    return JsonResponse({"error": "Method not allowed"}, status=405)
