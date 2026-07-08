"""支付记录 API 视图模块。"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from project.api import api_error, api_success
from project.common_tools import paginate_queryset, parse_date, parse_json_body, require_login, shift_month
from .models import FinancePayable, FinancePayment, FinancePaymentDetail
from .views_common import _parse_decimal_field, _parse_finance_month, _parse_optional_int, _quantize_amount, _year_from_request
from .views_payables import (
    _recalculate_payable_amounts,
    _serialize_payable,
    _serialize_payment,
    _serialize_payment_detail,
    _serialize_payment_for_ledger,
    _truthy_request_value,
)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def finance_payments_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "GET":
        month, error = _parse_finance_month(request.GET.get("month"))
        if error:
            return error
        year, error = _year_from_request(request)
        if error:
            return error
        qs = FinancePayment.objects_for_period(year).filter(deleted_at__isnull=True)
        if month:
            qs = qs.filter(payment_date__gte=month, payment_date__lt=shift_month(month, 1))
        customer_id, error = _parse_optional_int(request.GET.get("customer_id"), "customer_id")
        if error:
            return error
        if customer_id is not None:
            qs = qs.filter(customer_id=customer_id)
        keyword = (request.GET.get("keyword") or "").strip()
        if keyword:
            qs = qs.filter(Q(payee_name__icontains=keyword) | Q(bank_transaction_no__icontains=keyword))

        summary_total = qs.aggregate(total=Sum("payment_amount"))["total"] or Decimal("0")

        payment_type = (request.GET.get("type") or "").strip()
        if payment_type == "all":
            payment_type = ""
        if payment_type and payment_type != "payable":
            qs = qs.none()

        paged, total, page, page_size, total_pages = paginate_queryset(
            qs.order_by("-payment_date", "-id"),
            request,
        )
        paged = list(paged)
        details_by_payment = {}
        detail_stats_by_payment = {}
        payables_by_id = {}
        include_details = _truthy_request_value(request.GET.get("include_details"))
        if paged:
            detail_model = FinancePaymentDetail.model_for_period(year)
            detail_qs = detail_model.objects.filter(
                payment_id__in=[item.id for item in paged],
                deleted_at__isnull=True,
            )
            detail_stats_by_payment = {
                row["payment_id"]: row
                for row in detail_qs.values("payment_id").annotate(
                    count=Count("id"),
                    amount=Sum("payment_amount"),
                )
            }
            if include_details:
                details = list(detail_qs.order_by("id"))
                for detail in details:
                    details_by_payment.setdefault(detail.payment_id, []).append(detail)
                payable_ids = {detail.payable_id for detail in details}
                if payable_ids:
                    payable_model = FinancePayable.model_for_period(year)
                    payables_by_id = {
                        item.id: item
                        for item in payable_model.objects.filter(id__in=payable_ids, deleted_at__isnull=True)
                    }
        return api_success(
            data={
                "items": [
                    _serialize_payment_for_ledger(
                        item,
                        details_by_payment.get(item.id, []),
                        payables_by_id,
                        details_loaded=include_details,
                        details_count=(detail_stats_by_payment.get(item.id) or {}).get("count", 0),
                        details_amount=(detail_stats_by_payment.get(item.id) or {}).get("amount", Decimal("0")),
                    )
                    for item in paged
                ],
                "summary": {
                    "total_amount": str(_quantize_amount(summary_total)),
                    "salary_amount": "0.00",
                    "payable_amount": str(_quantize_amount(summary_total)),
                    "reimbursement_amount": "0.00",
                    "other_amount": "0.00",
                },
            },
            meta={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        )

    payload, error = parse_json_body(request)
    if error:
        return error
    payment_date, error = parse_date(payload.get("payment_date"), "payment_date")
    if error:
        return error
    if not payment_date:
        return api_error("Missing field: payment_date")
    payment_amount, error = _parse_decimal_field(payload, "payment_amount", allow_zero=False)
    if error:
        return error
    customer_id, error = _parse_optional_int(payload.get("customer_id"), "customer_id")
    if error:
        return error
    allocations = payload.get("allocations")
    if not isinstance(allocations, list) or not allocations:
        return api_error("Missing field: allocations")

    payment_year = payment_date.year
    payable_model = FinancePayable.model_for_period(payment_year)
    payment_model = FinancePayment.model_for_period(payment_year)
    detail_model = FinancePaymentDetail.model_for_period(payment_year)

    parsed_allocations = []
    total_allocated = Decimal("0")
    for index, allocation in enumerate(allocations, start=1):
        if not isinstance(allocation, dict):
            return api_error(f"Invalid field: allocations[{index}]", status=400)
        payable_id, error = _parse_optional_int(allocation.get("payable_id"), f"allocations[{index}].payable_id")
        if error:
            return error
        if not payable_id:
            return api_error(f"Missing field: allocations[{index}].payable_id")
        amount, error = _parse_decimal_field(allocation, "payment_amount", allow_zero=False)
        if error:
            return error
        total_allocated += amount
        parsed_allocations.append((payable_id, amount, (allocation.get("remark") or "").strip() or None))

    payable_ids = [item[0] for item in parsed_allocations]
    if len(payable_ids) != len(set(payable_ids)):
        return api_error("Duplicate payable allocation", status=400)

    total_allocated = _quantize_amount(total_allocated)
    payment_amount = _quantize_amount(payment_amount)
    if total_allocated != payment_amount:
        return api_error("Payment amount must equal allocation total", status=400)

    with transaction.atomic():
        payables = {
            item.id: item
            for item in payable_model.objects.select_for_update().filter(
                id__in=payable_ids,
                deleted_at__isnull=True,
            )
        }
        if len(payables) != len(set(payable_ids)):
            return api_error("Finance payable not found", status=404)
        if any(item.finance_status == 2 for item in payables.values()):
            return api_error("Written-off payable cannot be paid", status=409)
        customer_ids = {item.customer_id for item in payables.values()}
        if len(customer_ids) > 1:
            return api_error("Payment allocations must belong to one customer", status=400)
        if customer_id is not None and customer_ids and customer_id not in customer_ids:
            return api_error("Payment customer does not match payable customer", status=400)
        resolved_customer_id = customer_id if customer_id is not None else next(iter(customer_ids), None)
        for payable_id, amount, _remark in parsed_allocations:
            payable = payables[payable_id]
            if amount > payable.outstanding_amount:
                return api_error("Payment amount exceeds payable outstanding amount", status=409)

        payment = payment_model.objects.create(
            customer_id=resolved_customer_id,
            payee_name=(payload.get("payee_name") or "").strip() or None,
            bank_transaction_no=(payload.get("bank_transaction_no") or "").strip() or None,
            payment_amount=payment_amount,
            payment_date=payment_date,
            remark=(payload.get("remark") or "").strip() or None,
            created_by=login_id,
            updated_by=login_id,
        )
        details = []
        for payable_id, amount, remark in parsed_allocations:
            details.append(
                detail_model.objects.create(
                    payment_id=payment.id,
                    payable_id=payable_id,
                    payment_amount=amount,
                    remark=remark,
                    created_by=login_id,
                    updated_by=login_id,
                )
            )
        updated_payables = [
            _recalculate_payable_amounts(payable, payment_year, login_id)
            for payable in payables.values()
        ]

    return api_success(
        data={
            "item": _serialize_payment(payment),
            "details": [_serialize_payment_detail(item) for item in details],
            "payables": [_serialize_payable(item) for item in updated_payables],
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def finance_payment_detail_api(request, payment_id):
    year, error = _year_from_request(request)
    if error:
        return error
    payment_model = FinancePayment.model_for_period(year)
    detail_model = FinancePaymentDetail.model_for_period(year)
    payment = payment_model.objects.filter(id=payment_id, deleted_at__isnull=True).first()
    if not payment:
        return api_error("Finance payment not found", status=404)

    if request.method == "GET":
        details = list(detail_model.objects.filter(
            payment_id=payment.id,
            deleted_at__isnull=True,
        ).order_by("id"))
        payable_model = FinancePayable.model_for_period(year)
        payables = {
            item.id: item
            for item in payable_model.objects.filter(
                id__in=[detail.payable_id for detail in details],
                deleted_at__isnull=True,
            )
        }
        return api_success(
            data={
                "item": _serialize_payment_for_ledger(payment, details, payables),
                "details": [
                    _serialize_payment_for_ledger(payment, [detail], payables)["details"][0]
                    for detail in details
                ],
            }
        )

    login_id, error = require_login(request)
    if error:
        return error

    if request.method == "PUT":
        payload, error = parse_json_body(request)
        if error:
            return error
        detail_id, error = _parse_optional_int(payload.get("detail_id"), "detail_id")
        if error:
            return error
        remark = (payload.get("remark") or "").strip() or None
        with transaction.atomic():
            payment = payment_model.objects.select_for_update().get(id=payment.id)
            if detail_id:
                detail = detail_model.objects.select_for_update().filter(
                    id=detail_id,
                    payment_id=payment.id,
                    deleted_at__isnull=True,
                ).first()
                if not detail:
                    return api_error("Finance payment detail not found", status=404)
                detail.remark = remark
                detail.updated_by = login_id
                detail.save(update_fields=["remark", "updated_by", "updated_at"])
            else:
                payment.remark = remark
                payment.updated_by = login_id
                payment.save(update_fields=["remark", "updated_by", "updated_at"])
        details = list(detail_model.objects.filter(
            payment_id=payment.id,
            deleted_at__isnull=True,
        ).order_by("id"))
        payable_model = FinancePayable.model_for_period(year)
        payables = {
            item.id: item
            for item in payable_model.objects.filter(
                id__in=[detail.payable_id for detail in details],
                deleted_at__isnull=True,
            )
        }
        return api_success(
            data={
                "item": _serialize_payment_for_ledger(payment, details, payables),
                "details": [
                    _serialize_payment_for_ledger(payment, [detail], payables)["details"][0]
                    for detail in details
                ],
            }
        )

    with transaction.atomic():
        payment = payment_model.objects.select_for_update().get(id=payment.id)
        details = list(
            detail_model.objects.select_for_update().filter(
                payment_id=payment.id,
                deleted_at__isnull=True,
            )
        )
        payment.deleted_at = timezone.now()
        payment.updated_by = login_id
        payment.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        now = timezone.now()
        for detail in details:
            detail.deleted_at = now
            detail.updated_by = login_id
            detail.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        payable_model = FinancePayable.model_for_period(year)
        payables = payable_model.objects.select_for_update().filter(
            id__in=[item.payable_id for item in details],
            deleted_at__isnull=True,
        )
        updated_payables = [
            _recalculate_payable_amounts(payable, year, login_id)
            for payable in payables
        ]
    return api_success(
        data={
            "deleted": True,
            "payables": [_serialize_payable(item) for item in updated_payables],
        }
    )
