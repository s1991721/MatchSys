"""应付管理 API 视图模块。"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from project.api import api_error, api_paginated, api_success
from project.common_tools import paginate_queryset, parse_date, parse_json_body, require_login
from .models import FinancePayable, FinancePayment, FinancePaymentDetail
from .views_common import (
    _parse_decimal_field,
    _parse_finance_month,
    _parse_optional_int,
    _parse_receivable_finance_status,
    _quantize_amount,
    _year_from_request,
)

PAYABLE_DISPLAY_STATUS_LABELS = {
    0: "未付",
    1: "部分支付",
    2: "已付",
    3: "逾期",
    5: "异常",
    6: "核销",
}

def _get_payable_display_status(item, today=None):
    today = today or timezone.localdate()
    if item.finance_status == 1:
        return 5, PAYABLE_DISPLAY_STATUS_LABELS[5]
    if item.finance_status == 2:
        return 6, PAYABLE_DISPLAY_STATUS_LABELS[6]
    if item.outstanding_amount <= 0:
        return 2, PAYABLE_DISPLAY_STATUS_LABELS[2]
    if item.due_date and item.due_date < today:
        return 3, PAYABLE_DISPLAY_STATUS_LABELS[3]
    if item.paid_amount > 0:
        return 1, PAYABLE_DISPLAY_STATUS_LABELS[1]
    return 0, PAYABLE_DISPLAY_STATUS_LABELS[0]


def _serialize_payable(item):
    display_status, display_status_label = _get_payable_display_status(item)
    return {
        "id": item.id,
        "year": item.payable_month.year if item.payable_month else None,
        "purchase_order_id": item.purchase_order_id,
        "source_type": "purchase_order" if item.purchase_order_id else "manual",
        "source_label": "发注" if item.purchase_order_id else "手动",
        "order_no": item.order_no or "",
        "payable_month": item.payable_month.strftime("%Y-%m") if item.payable_month else "",
        "customer_id": item.customer_id,
        "customer_name": item.customer_name,
        "payable_amount": str(item.payable_amount),
        "paid_amount": str(item.paid_amount),
        "outstanding_amount": str(item.outstanding_amount),
        "due_date": item.due_date.isoformat() if item.due_date else "",
        "finance_status": item.finance_status,
        "display_status": display_status,
        "display_status_label": display_status_label,
        "remark": item.remark or "",
    }


def _serialize_payment(item):
    return {
        "id": item.id,
        "year": item.payment_date.year if item.payment_date else None,
        "customer_id": item.customer_id,
        "payee_name": item.payee_name or "",
        "bank_transaction_no": item.bank_transaction_no or "",
        "payment_amount": str(item.payment_amount),
        "payment_date": item.payment_date.isoformat() if item.payment_date else "",
        "remark": item.remark or "",
    }


def _serialize_payment_detail(item):
    return {
        "id": item.id,
        "payment_id": item.payment_id,
        "payable_id": item.payable_id,
        "payment_amount": str(item.payment_amount),
        "remark": item.remark or "",
    }


def _truthy_request_value(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _serialize_payment_for_ledger(
    item,
    details=None,
    payables=None,
    details_loaded=True,
    details_count=None,
    details_amount=None,
):
    details = details or []
    payables = payables or {}
    serialized_details = []
    for detail in details:
        payable = payables.get(detail.payable_id)
        serialized_detail = _serialize_payment_detail(detail)
        serialized_detail.update({
            "source_type": "payable",
            "source_no": (payable.order_no if payable else "") or f"PAYABLE-{detail.payable_id}",
            "source_name": (
                f"{payable.customer_name} / {payable.payable_month.strftime('%Y-%m')}"
                if payable and payable.payable_month
                else ""
            ),
            "payable": _serialize_payable(payable) if payable else None,
        })
        serialized_details.append(serialized_detail)

    item_payload = _serialize_payment(item)
    item_payload.update({
        "type": "payable",
        "type_label": "应付",
        "method": "bank" if item.bank_transaction_no else "other",
        "method_label": "银行转账" if item.bank_transaction_no else "其他",
        "details": serialized_details,
        "details_loaded": details_loaded,
        "details_count": details_count if details_count is not None else len(serialized_details),
        "details_amount": str(_quantize_amount(
            details_amount
            if details_amount is not None
            else sum((detail.payment_amount for detail in details), Decimal("0"))
        )),
    })
    return item_payload


def _parse_payable_display_status(value):
    if value in (None, "", "all"):
        return None, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, api_error("Invalid field: status", status=400)
    if parsed not in PAYABLE_DISPLAY_STATUS_LABELS:
        return None, api_error("Invalid field: status", status=400)
    return parsed, None


def _apply_payable_display_status_filter(qs, status):
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
            paid_amount__gt=0,
            outstanding_amount__gt=0,
        ).filter(Q(due_date__isnull=True) | Q(due_date__gte=today))
    if status == 0:
        return base_qs.filter(
            paid_amount__lte=0,
            outstanding_amount__gt=0,
        ).filter(Q(due_date__isnull=True) | Q(due_date__gte=today))
    return qs


def _get_active_payable(payable_id, year, for_update=False):
    payable_model = FinancePayable.model_for_period(year)
    qs = payable_model.objects.filter(id=payable_id, deleted_at__isnull=True)
    if for_update:
        qs = qs.select_for_update()
    return qs.first()


def _recalculate_payable_amounts(payable, year, updated_by=None):
    detail_model = FinancePaymentDetail.model_for_period(year)
    total = (
        detail_model.objects.filter(
            payable_id=payable.id,
            deleted_at__isnull=True,
        ).aggregate(total=Sum("payment_amount"))["total"]
        or Decimal("0")
    )
    payable.paid_amount = _quantize_amount(total)
    payable.outstanding_amount = _quantize_amount(payable.payable_amount - payable.paid_amount)
    if updated_by is not None:
        payable.updated_by = updated_by
    payable.save(update_fields=["paid_amount", "outstanding_amount", "updated_by", "updated_at"])
    return payable


def _build_payable_values(payload, existing=None):
    values = {}

    if existing is None or "payable_month" in payload:
        month, error = _parse_finance_month(payload.get("payable_month") or payload.get("month"))
        if error:
            return None, error
        if not month:
            return None, api_error("Missing field: payable_month")
        values["payable_month"] = month

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

    if existing is None or "payable_amount" in payload:
        payable_amount, error = _parse_decimal_field(payload, "payable_amount", allow_zero=False)
        if error:
            return None, error
        values["payable_amount"] = payable_amount

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


def _apply_payable_values(item, values):
    for field_name, value in values.items():
        setattr(item, field_name, value)
    if "payable_amount" in values:
        item.outstanding_amount = _quantize_amount(item.payable_amount - item.paid_amount)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_payables_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "POST":
        payload, error = parse_json_body(request)
        if error:
            return error
        if payload.get("purchase_order_id") not in (None, "") or payload.get("order_no") not in (None, ""):
            return api_error("Source fields cannot be created manually", status=400)
        values, error = _build_payable_values(payload)
        if error:
            return error
        payable_model = FinancePayable.model_for_period(values["payable_month"])
        item = payable_model.objects.create(
            purchase_order_id=None,
            order_no=None,
            paid_amount=Decimal("0"),
            outstanding_amount=values["payable_amount"],
            created_by=login_id,
            updated_by=login_id,
            **values,
        )
        return api_success(data={"item": _serialize_payable(item)}, status=201)

    month, error = _parse_finance_month(request.GET.get("month"))
    if error:
        return error
    year, error = _year_from_request(request)
    if error:
        return error

    display_status, error = _parse_payable_display_status(request.GET.get("status"))
    if error:
        return error

    source = (request.GET.get("source") or "").strip()
    if source == "all":
        source = ""
    if source and source not in ("purchase_order", "manual"):
        return api_error("Invalid field: source", status=400)

    qs = FinancePayable.objects_for_period(year).filter(deleted_at__isnull=True)

    if month:
        qs = qs.filter(payable_month=month)

    if source == "purchase_order":
        qs = qs.filter(purchase_order_id__isnull=False)
    elif source == "manual":
        qs = qs.filter(purchase_order_id__isnull=True)

    keyword = (request.GET.get("keyword") or "").strip()
    if keyword:
        qs = qs.filter(Q(customer_name__icontains=keyword) | Q(order_no__icontains=keyword))

    if display_status is not None:
        qs = _apply_payable_display_status_filter(qs, display_status)

    paged, total, page, page_size, total_pages = paginate_queryset(
        qs.order_by("payable_month", "due_date", "id"),
        request,
    )
    return api_paginated(
        items=[_serialize_payable(item) for item in paged],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@require_http_methods(["GET"])
def finance_payables_overview_api(request):
    _login_id, error = require_login(request)
    if error:
        return error

    month, error = _parse_finance_month(request.GET.get("month"), default_current=True)
    if error:
        return error
    payable_model = FinancePayable.model_for_period(month)

    current_qs = payable_model.objects.filter(
        deleted_at__isnull=True,
        payable_month=month,
    )
    current_summary = current_qs.aggregate(
        payable_amount=Sum("payable_amount"),
        paid_amount=Sum("paid_amount"),
        outstanding_amount=Sum("outstanding_amount"),
    )

    historical_rows = (
        payable_model.objects.filter(
            deleted_at__isnull=True,
            finance_status=0,
            payable_month__lt=month,
            outstanding_amount__gt=0,
        )
        .values("payable_month")
        .annotate(
            count=Count("id"),
            payable_amount=Sum("payable_amount"),
            paid_amount=Sum("paid_amount"),
            outstanding_amount=Sum("outstanding_amount"),
        )
        .order_by("-payable_month")
    )

    return api_success(
        data={
            "month": month.strftime("%Y-%m"),
            "summary": {
                "payable_amount": str(_quantize_amount(current_summary["payable_amount"])),
                "paid_amount": str(_quantize_amount(current_summary["paid_amount"])),
                "outstanding_amount": str(_quantize_amount(current_summary["outstanding_amount"])),
            },
            "unbalanced_months": [
                {
                    "month": row["payable_month"].strftime("%Y-%m") if row["payable_month"] else "",
                    "count": row["count"] or 0,
                    "payable_amount": str(_quantize_amount(row["payable_amount"])),
                    "paid_amount": str(_quantize_amount(row["paid_amount"])),
                    "outstanding_amount": str(_quantize_amount(row["outstanding_amount"])),
                }
                for row in historical_rows
            ],
        }
    )


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def finance_payable_detail_api(request, payable_id):
    year, error = _year_from_request(request)
    if error:
        return error
    item = _get_active_payable(payable_id, year)
    if not item:
        return api_error("Finance payable not found", status=404)

    if request.method == "GET":
        return api_success(data={"item": _serialize_payable(item)})

    login_id, error = require_login(request)
    if error:
        return error

    detail_model = FinancePaymentDetail.model_for_period(year)
    if request.method == "DELETE":
        has_payments = detail_model.objects.filter(payable_id=item.id, deleted_at__isnull=True).exists()
        if has_payments:
            return api_error("Payable has payments and cannot be deleted", status=409)
        item.deleted_at = timezone.now()
        item.updated_by = login_id
        item.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        return api_success(data={"deleted": True})

    if item.purchase_order_id:
        return api_error("Purchase order payable cannot be changed manually", status=409)

    payload, error = parse_json_body(request)
    if error:
        return error
    if "purchase_order_id" in payload or "order_no" in payload:
        return api_error("Source fields cannot be changed", status=400)
    values, error = _build_payable_values(payload, existing=item)
    if error:
        return error
    if "payable_month" in values and values["payable_month"].year != year:
        return api_error("Payable month year cannot be changed through this endpoint", status=400)
    if "payable_amount" in values and values["payable_amount"] < item.paid_amount:
        return api_error("Payable amount cannot be less than paid amount", status=409)

    with transaction.atomic():
        item = FinancePayable.model_for_period(year).objects.select_for_update().get(id=item.id)
        _apply_payable_values(item, values)
        item.updated_by = login_id
        item.save()
        if "payable_amount" in values:
            _recalculate_payable_amounts(item, year, login_id)
    return api_success(data={"item": _serialize_payable(item)})


@require_http_methods(["GET"])
def finance_payable_payments_api(request, payable_id):
    _login_id, error = require_login(request)
    if error:
        return error
    year, error = _year_from_request(request)
    if error:
        return error
    payable = _get_active_payable(payable_id, year)
    if not payable:
        return api_error("Finance payable not found", status=404)
    detail_model = FinancePaymentDetail.model_for_period(year)
    details = detail_model.objects.filter(
        payable_id=payable.id,
        deleted_at__isnull=True,
    ).order_by("id")
    payment_model = FinancePayment.model_for_period(year)
    payment_ids = [item.payment_id for item in details]
    payments = {
        item.id: item
        for item in payment_model.objects.filter(id__in=payment_ids, deleted_at__isnull=True)
    }
    return api_success(
        data={
            "items": [
                {
                    **_serialize_payment_detail(detail),
                    "payment": _serialize_payment(payments[detail.payment_id]) if detail.payment_id in payments else None,
                }
                for detail in details
            ]
        }
    )
