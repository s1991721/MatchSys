"""应收管理 API 视图模块。"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from project.api import api_error, api_paginated, api_success
from project.common_tools import paginate_queryset, parse_date, parse_json_body, require_login, shift_month
from .models import FinanceReceivable, FinanceReceipt
from .views_common import (
    _parse_decimal_field,
    _parse_optional_int,
    _parse_receivable_finance_status,
    _parse_receivable_month,
    _quantize_amount,
)

RECEIVABLE_DISPLAY_STATUS_LABELS = {
    0: "未收",
    1: "部分入金",
    2: "已收",
    3: "逾期",
    5: "异常",
    6: "核销",
}

def _get_receivable_display_status(item, today=None):
    today = today or timezone.localdate()
    if item.finance_status == 1:
        return 5, RECEIVABLE_DISPLAY_STATUS_LABELS[5]
    if item.finance_status == 2:
        return 6, RECEIVABLE_DISPLAY_STATUS_LABELS[6]
    if item.outstanding_amount <= 0:
        return 2, RECEIVABLE_DISPLAY_STATUS_LABELS[2]
    if item.due_date and item.due_date < today:
        return 3, RECEIVABLE_DISPLAY_STATUS_LABELS[3]
    if item.received_amount > 0:
        return 1, RECEIVABLE_DISPLAY_STATUS_LABELS[1]
    return 0, RECEIVABLE_DISPLAY_STATUS_LABELS[0]


def _serialize_receivable(item):
    display_status, display_status_label = _get_receivable_display_status(item)
    return {
        "id": item.id,
        "pay_request_id": item.pay_request_id,
        "source_type": "request" if item.pay_request_id else "manual",
        "source_label": "请求书" if item.pay_request_id else "手动",
        "request_no": item.request_no or "",
        "customer_id": item.customer_id,
        "customer_name": item.customer_name,
        "receivable_amount": str(item.receivable_amount),
        "received_amount": str(item.received_amount),
        "outstanding_amount": str(item.outstanding_amount),
        "due_date": item.due_date.isoformat() if item.due_date else "",
        "finance_status": item.finance_status,
        "display_status": display_status,
        "display_status_label": display_status_label,
        "remark": item.remark or "",
    }


def _serialize_receipt(item):
    return {
        "id": item.id,
        "receivable_id": item.receivable_id,
        "customer_id": item.customer_id,
        "payer_name": item.payer_name or "",
        "bank_transaction_no": item.bank_transaction_no or "",
        "receipt_amount": str(item.receipt_amount),
        "receipt_date": item.receipt_date.isoformat() if item.receipt_date else "",
        "remark": item.remark or "",
    }


def _parse_receivable_month(value):
    value = (value or "").strip()
    if not value:
        return None, None
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1), None
    except ValueError:
        return None, api_error("Invalid field: month", status=400)


def _parse_receivable_display_status(value):
    if value in (None, "", "all"):
        return None, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: status", status=400)
    if parsed not in RECEIVABLE_DISPLAY_STATUS_LABELS:
        return None, api_error("Invalid field: status", status=400)
    return parsed, None


def _parse_receivable_finance_status(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: finance_status", status=400)
    if parsed not in (0, 1, 2):
        return None, api_error("Invalid field: finance_status", status=400)
    return parsed, None


def _parse_optional_int(value, field_name):
    if value in (None, ""):
        return None, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error(f"Invalid field: {field_name}", status=400)
    if parsed < 0:
        return None, api_error(f"Invalid field: {field_name}", status=400)
    return parsed, None


def _apply_receivable_display_status_filter(qs, status):
    today = timezone.localdate()
    if status == 5:
        return qs.filter(finance_status=1)
    if status == 6:
        return qs.filter(finance_status=2)
    base_qs = qs.filter(finance_status=0)
    if status == 2:
        return base_qs.filter(outstanding_amount__lte=0)
    if status == 3:
        return base_qs.filter(outstanding_amount__gt=0, due_date__lt=today)
    if status == 1:
        return base_qs.filter(
            received_amount__gt=0,
            outstanding_amount__gt=0,
        ).filter(Q(due_date__isnull=True) | Q(due_date__gte=today))
    if status == 0:
        return base_qs.filter(
            received_amount__lte=0,
            outstanding_amount__gt=0,
        ).filter(Q(due_date__isnull=True) | Q(due_date__gte=today))
    return qs


def _parse_decimal_field(payload, field_name, allow_zero=True):
    value = payload.get(field_name)
    if value in (None, ""):
        return Decimal("0"), None
    try:
        parsed = Decimal(str(value))
    except Exception:
        return None, api_error(f"Invalid field: {field_name}", status=400)
    if parsed < 0 or (not allow_zero and parsed <= 0):
        return None, api_error(f"Invalid field: {field_name}", status=400)
    return parsed, None


def _recalculate_receivable_amounts(receivable, updated_by=None):
    total = (
        FinanceReceipt.objects.filter(
            receivable_id=receivable.id,
            deleted_at__isnull=True,
        ).aggregate(total=Sum("receipt_amount"))["total"]
        or Decimal("0")
    )
    receivable.received_amount = _quantize_amount(total)
    receivable.outstanding_amount = _quantize_amount(receivable.receivable_amount - receivable.received_amount)
    if updated_by is not None:
        receivable.updated_by = updated_by
    receivable.save(update_fields=["received_amount", "outstanding_amount", "updated_by", "updated_at"])
    return receivable


def _get_active_receivable(receivable_id, for_update=False):
    qs = FinanceReceivable.objects.filter(id=receivable_id, deleted_at__isnull=True)
    if for_update:
        qs = qs.select_for_update()
    return qs.first()


def _build_receivable_values(payload, existing=None):
    values = {}

    if existing is None or "customer_id" in payload:
        customer_id, error = _parse_optional_int(payload.get("customer_id"), "customer_id")
        if error:
            return None, error
        values["customer_id"] = customer_id

    if existing is None or "customer_name" in payload:
        customer_name = (payload.get("customer_name") or "").strip()
        if not customer_name:
            return None, api_error("Missing field: customer_name")
        values["customer_name"] = customer_name

    if existing is None or "receivable_amount" in payload:
        receivable_amount, error = _parse_decimal_field(payload, "receivable_amount", allow_zero=False)
        if error:
            return None, error
        values["receivable_amount"] = receivable_amount

    if existing is None or "due_date" in payload:
        due_date, error = parse_date(payload.get("due_date"), "due_date")
        if error:
            return None, error
        values["due_date"] = due_date

    if existing is None or "finance_status" in payload:
        finance_status, error = _parse_receivable_finance_status(payload.get("finance_status", 0))
        if error:
            return None, error
        values["finance_status"] = finance_status

    if existing is None or "remark" in payload:
        values["remark"] = (payload.get("remark") or "").strip() or None

    return values, None


def _apply_receivable_values(item, values):
    for field_name, value in values.items():
        setattr(item, field_name, value)
    if "receivable_amount" in values:
        item.outstanding_amount = _quantize_amount(item.receivable_amount - item.received_amount)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_receivables_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "POST":
        payload, error = parse_json_body(request)
        if error:
            return error
        if payload.get("pay_request_id") not in (None, "") or payload.get("request_no") not in (None, ""):
            return api_error("Source fields cannot be created manually", status=400)
        values, error = _build_receivable_values(payload)
        if error:
            return error
        item = FinanceReceivable.objects.create(
            pay_request_id=None,
            request_no=None,
            received_amount=Decimal("0"),
            outstanding_amount=values["receivable_amount"],
            created_by=login_id,
            updated_by=login_id,
            **values,
        )
        return api_success(data={"item": _serialize_receivable(item)}, status=201)

    month, error = _parse_receivable_month(request.GET.get("month"))
    if error:
        return error

    display_status, error = _parse_receivable_display_status(request.GET.get("status"))
    if error:
        return error

    source = (request.GET.get("source") or "").strip()
    if source == "all":
        source = ""
    if source and source not in ("request", "manual"):
        return api_error("Invalid field: source", status=400)

    qs = FinanceReceivable.objects.filter(deleted_at__isnull=True)

    if month:
        qs = qs.filter(due_date__gte=month, due_date__lt=shift_month(month, 1))

    if source == "request":
        qs = qs.filter(pay_request_id__isnull=False)
    elif source == "manual":
        qs = qs.filter(pay_request_id__isnull=True)

    if display_status is not None:
        qs = _apply_receivable_display_status_filter(qs, display_status)

    paged, total, page, page_size, total_pages = paginate_queryset(
        qs.order_by("due_date", "id"),
        request,
    )
    return api_paginated(
        items=[_serialize_receivable(item) for item in paged],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@require_http_methods(["GET"])
def finance_receivables_overview_api(request):
    _login_id, error = require_login(request)
    if error:
        return error

    month, error = _parse_receivable_month(request.GET.get("month"))
    if error:
        return error
    month = month or timezone.localdate().replace(day=1)
    next_month = shift_month(month, 1)

    current_qs = FinanceReceivable.objects.filter(
        deleted_at__isnull=True,
        due_date__gte=month,
        due_date__lt=next_month,
    )
    current_summary = current_qs.aggregate(
        receivable_amount=Sum("receivable_amount"),
        received_amount=Sum("received_amount"),
        outstanding_amount=Sum("outstanding_amount"),
    )

    historical_rows = (
        FinanceReceivable.objects.filter(
            deleted_at__isnull=True,
            finance_status=0,
            due_date__lt=month,
            outstanding_amount__gt=0,
        )
        .annotate(month=TruncMonth("due_date"))
        .values("month")
        .annotate(
            count=Count("id"),
            receivable_amount=Sum("receivable_amount"),
            received_amount=Sum("received_amount"),
            outstanding_amount=Sum("outstanding_amount"),
        )
        .order_by("-month")
    )

    return api_success(
        data={
            "month": month.strftime("%Y-%m"),
            "summary": {
                "receivable_amount": str(_quantize_amount(current_summary["receivable_amount"])),
                "received_amount": str(_quantize_amount(current_summary["received_amount"])),
                "outstanding_amount": str(_quantize_amount(current_summary["outstanding_amount"])),
            },
            "unbalanced_months": [
                {
                    "month": row["month"].strftime("%Y-%m") if row["month"] else "",
                    "count": row["count"] or 0,
                    "receivable_amount": str(_quantize_amount(row["receivable_amount"])),
                    "received_amount": str(_quantize_amount(row["received_amount"])),
                    "outstanding_amount": str(_quantize_amount(row["outstanding_amount"])),
                }
                for row in historical_rows
            ],
        }
    )


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def finance_receivable_detail_api(request, receivable_id):
    item = _get_active_receivable(receivable_id)
    if not item:
        return api_error("Finance receivable not found", status=404)

    if request.method == "GET":
        return api_success(data={"item": _serialize_receivable(item)})

    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "DELETE":
        has_receipts = FinanceReceipt.objects.filter(receivable_id=item.id, deleted_at__isnull=True).exists()
        if has_receipts:
            return api_error("Receivable has receipts and cannot be deleted", status=409)
        item.deleted_at = timezone.now()
        item.updated_by = login_id
        item.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        return api_success(data={"deleted": True})

    payload, error = parse_json_body(request)
    if error:
        return error
    if "pay_request_id" in payload or "request_no" in payload:
        return api_error("Source fields cannot be changed", status=400)
    values, error = _build_receivable_values(payload, existing=item)
    if error:
        return error

    with transaction.atomic():
        item = FinanceReceivable.objects.select_for_update().get(id=item.id)
        _apply_receivable_values(item, values)
        item.updated_by = login_id
        item.save()
        if "receivable_amount" in values:
            _recalculate_receivable_amounts(item, login_id)
    return api_success(data={"item": _serialize_receivable(item)})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_receivable_receipts_api(request, receivable_id):
    login_id, error = require_login(request)
    if error:
        return error

    receivable = _get_active_receivable(receivable_id)
    if not receivable:
        return api_error("Finance receivable not found", status=404)

    if request.method == "GET":
        items = FinanceReceipt.objects.filter(
            receivable_id=receivable.id,
            deleted_at__isnull=True,
        ).order_by("receipt_date", "id")
        return api_success(data={"items": [_serialize_receipt(item) for item in items]})

    if receivable.finance_status == 2:
        return api_error("Written-off receivable cannot receive payments", status=409)

    payload, error = parse_json_body(request)
    if error:
        return error
    amount, error = _parse_decimal_field(payload, "receipt_amount", allow_zero=False)
    if error:
        return error
    receipt_date, error = parse_date(payload.get("receipt_date"), "receipt_date")
    if error:
        return error
    if not receipt_date:
        return api_error("Missing field: receipt_date")
    customer_id, error = _parse_optional_int(payload.get("customer_id"), "customer_id")
    if error:
        return error

    with transaction.atomic():
        receivable = _get_active_receivable(receivable_id, for_update=True)
        if not receivable:
            return api_error("Finance receivable not found", status=404)
        if receivable.finance_status == 2:
            return api_error("Written-off receivable cannot receive payments", status=409)
        item = FinanceReceipt.objects.create(
            receivable_id=receivable.id,
            customer_id=customer_id,
            payer_name=(payload.get("payer_name") or "").strip() or None,
            bank_transaction_no=(payload.get("bank_transaction_no") or "").strip() or None,
            receipt_amount=amount,
            receipt_date=receipt_date,
            remark=(payload.get("remark") or "").strip() or None,
            created_by=login_id,
            updated_by=login_id,
        )
        _recalculate_receivable_amounts(receivable, login_id)
    return api_success(
        data={"item": _serialize_receipt(item), "receivable": _serialize_receivable(receivable)},
        status=201,
    )


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def finance_receipt_detail_api(request, receipt_id):
    item = FinanceReceipt.objects.filter(id=receipt_id, deleted_at__isnull=True).first()
    if not item:
        return api_error("Finance receipt not found", status=404)

    receivable = _get_active_receivable(item.receivable_id)
    if not receivable:
        return api_error("Finance receivable not found", status=404)

    if request.method == "GET":
        return api_success(data={"item": _serialize_receipt(item)})

    login_id, error = require_login(request)
    if error:
        return error

    if receivable.finance_status == 2:
        return api_error("Written-off receivable receipt cannot be changed", status=409)

    with transaction.atomic():
        receivable = _get_active_receivable(item.receivable_id, for_update=True)
        if not receivable:
            return api_error("Finance receivable not found", status=404)
        if receivable.finance_status == 2:
            return api_error("Written-off receivable receipt cannot be changed", status=409)

        item = FinanceReceipt.objects.select_for_update().get(id=item.id)
        if request.method == "DELETE":
            item.deleted_at = timezone.now()
            item.updated_by = login_id
            item.save(update_fields=["deleted_at", "updated_by", "updated_at"])
            _recalculate_receivable_amounts(receivable, login_id)
            return api_success(data={"deleted": True, "receivable": _serialize_receivable(receivable)})

        payload, error = parse_json_body(request)
        if error:
            return error
        if "receipt_amount" in payload:
            amount, error = _parse_decimal_field(payload, "receipt_amount", allow_zero=False)
            if error:
                return error
            item.receipt_amount = amount
        if "receipt_date" in payload:
            receipt_date, error = parse_date(payload.get("receipt_date"), "receipt_date")
            if error:
                return error
            if not receipt_date:
                return api_error("Missing field: receipt_date")
            item.receipt_date = receipt_date
        if "customer_id" in payload:
            customer_id, error = _parse_optional_int(payload.get("customer_id"), "customer_id")
            if error:
                return error
            item.customer_id = customer_id
        if "payer_name" in payload:
            item.payer_name = (payload.get("payer_name") or "").strip() or None
        if "bank_transaction_no" in payload:
            item.bank_transaction_no = (payload.get("bank_transaction_no") or "").strip() or None
        if "remark" in payload:
            item.remark = (payload.get("remark") or "").strip() or None
        item.updated_by = login_id
        item.save()
        _recalculate_receivable_amounts(receivable, login_id)
    return api_success(data={"item": _serialize_receipt(item), "receivable": _serialize_receivable(receivable)})
