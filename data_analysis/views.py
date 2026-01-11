import calendar
from datetime import date, timedelta

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from employee.models import Technician
from bpmatch.models import SentEmailLog, MailTechnicianInfo
from order.models import PurchaseOrder, SalesOrder
from project.api import api_success
from project.common_tools import require_login, shift_month


def _add_months(value: date, months: int) -> date:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@csrf_exempt
@require_GET
def home_match_stats_api(request):
    login_id, error = require_login(request)
    if error:
        return error

    now = timezone.localtime(timezone.now())
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_last_week = start_of_week - timedelta(days=7)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_yesterday = start_of_today - timedelta(days=1)
    start_of_two_weeks = now - timedelta(days=14)
    today = now.date()
    start_date = today - timedelta(days=1)
    end_date = _add_months(today, 1)
    start_of_month = today.replace(day=1)
    start_of_next_month = shift_month(start_of_month, 1)
    start_of_last_month = shift_month(start_of_month, -1)
    start_of_month_after_next = shift_month(start_of_month, 2)

    base_queryset = SentEmailLog.objects.filter(
        created_by=login_id,
        deleted_at__isnull=True,
        mail_type__in=[0, 1, 2],
    )

    week_count = base_queryset.filter(
        sent_at__gte=start_of_week,
        sent_at__lte=now,
    ).count()
    last_week_count = base_queryset.filter(
        sent_at__gte=start_of_last_week,
        sent_at__lt=start_of_week,
    ).count()

    week_delta_percent = None
    week_direction = "flat"
    if last_week_count:
        diff = week_count - last_week_count
        week_delta_percent = (diff / last_week_count) * 100
        if diff > 0:
            week_direction = "up"
        elif diff < 0:
            week_direction = "down"
    elif week_count:
        week_delta_percent = 100.0
        week_direction = "up"

    today_count = base_queryset.filter(
        sent_at__gte=start_of_today,
        sent_at__lte=now,
    ).count()
    yesterday_count = base_queryset.filter(
        sent_at__gte=start_of_yesterday,
        sent_at__lt=start_of_today,
    ).count()

    day_delta_percent = None
    day_direction = "flat"
    if yesterday_count:
        diff = today_count - yesterday_count
        day_delta_percent = (diff / yesterday_count) * 100
        if diff > 0:
            day_direction = "up"
        elif diff < 0:
            day_direction = "down"
    elif today_count:
        day_delta_percent = 100.0
        day_direction = "up"

    purchase_month_count = PurchaseOrder.objects.filter(
        deleted_at__isnull=True,
        period_start__gte=start_of_month,
        period_start__lt=start_of_next_month,
    ).count()
    sales_month_count = SalesOrder.objects.filter(
        deleted_at__isnull=True,
        period_start__gte=start_of_month,
        period_start__lt=start_of_next_month,
    ).count()
    purchase_last_month_count = PurchaseOrder.objects.filter(
        deleted_at__isnull=True,
        period_start__gte=start_of_last_month,
        period_start__lt=start_of_month,
    ).count()
    sales_last_month_count = SalesOrder.objects.filter(
        deleted_at__isnull=True,
        period_start__gte=start_of_last_month,
        period_start__lt=start_of_month,
    ).count()

    month_entry_count = purchase_month_count + sales_month_count
    last_month_entry_count = purchase_last_month_count + sales_last_month_count

    month_delta_percent = None
    month_direction = "flat"
    if last_month_entry_count:
        diff = month_entry_count - last_month_entry_count
        month_delta_percent = (diff / last_month_entry_count) * 100
        if diff > 0:
            month_direction = "up"
        elif diff < 0:
            month_direction = "down"
    elif month_entry_count:
        month_delta_percent = 100.0
        month_direction = "up"

    monthly_sales_techs = Technician.objects.filter(
        spot_contract_deadline__isnull=False,
        spot_contract_deadline__lt=start_of_next_month,
        business_status__in=[0, 1, 2],
    ).order_by("spot_contract_deadline", "employee_id")
    monthly_sales_items = [
        {
            "employee_id": tech.employee_id,
            "name": tech.name,
            "remark": tech.remark or "",
            "business_status": tech.business_status,
        }
        for tech in monthly_sales_techs
    ]

    entry_orders = []
    purchase_entries = PurchaseOrder.objects.filter(
        deleted_at__isnull=True,
        period_start__gte=start_date,
        period_start__lte=end_date,
    )
    sales_entries = SalesOrder.objects.filter(
        deleted_at__isnull=True,
        period_start__gte=start_date,
        period_start__lte=end_date,
    )
    entry_orders.extend(purchase_entries)
    entry_orders.extend(sales_entries)

    total_days = (end_date - today).days or 1
    entry_items = []
    for order in entry_orders:
        period_start = order.period_start
        remaining_days = (period_start - today).days if period_start else total_days
        progress = (1 - (remaining_days / total_days)) * 100
        progress = max(0, min(100, round(progress)))
        entry_items.append(
            {
                "technician_name": order.technician_name or "",
                "customer_name": order.customer_name or "",
                "period_start": period_start.isoformat() if period_start else "",
                "progress": progress,
            }
        )
    entry_items.sort(key=lambda item: item["period_start"])

    next_month_sales_techs = Technician.objects.filter(
        spot_contract_deadline__gte=start_of_next_month,
        spot_contract_deadline__lt=start_of_month_after_next,
    ).order_by("spot_contract_deadline", "employee_id")
    next_month_sales_items = [
        {
            "employee_id": tech.employee_id,
            "name": tech.name,
            "spot_contract_deadline": tech.spot_contract_deadline.isoformat()
            if tech.spot_contract_deadline
            else "",
            "business_status": tech.business_status,
        }
        for tech in next_month_sales_techs
    ]

    two_weeks_count = MailTechnicianInfo.objects.filter(
        date__gte=start_of_two_weeks,
        date__lte=now,
    ).count()

    payload = {
        "week_count": week_count,
        "last_week_count": last_week_count,
        "week_delta_percent": week_delta_percent,
        "week_direction": week_direction,
        "today_count": today_count,
        "yesterday_count": yesterday_count,
        "day_delta_percent": day_delta_percent,
        "day_direction": day_direction,
        "month_entry_count": month_entry_count,
        "last_month_entry_count": last_month_entry_count,
        "month_delta_percent": month_delta_percent,
        "month_direction": month_direction,
        "two_weeks_count": two_weeks_count,
        "monthly_sales_techs": monthly_sales_items,
        "entry_items": entry_items,
        "next_month_sales_techs": next_month_sales_items,
    }
    return api_success(data=payload)
