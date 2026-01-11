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
    """按月份偏移日期并保持天数在目标月份范围内。"""
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _match_base_queryset(login_id):
    """按用户范围构建 match 相关邮件记录的基础查询集。"""
    return SentEmailLog.objects.filter(
        created_by=login_id,
        deleted_at__isnull=True,
        mail_type__in=[0, 1, 2],
    )


def _calc_delta(current_value, previous_value):
    """计算当前值与上期值的变化比例和方向。"""
    if previous_value:
        diff = current_value - previous_value
        percent = (diff / previous_value) * 100
        direction = "up" if diff > 0 else "down" if diff < 0 else "flat"
        return percent, direction
    if current_value:
        return 100.0, "up"
    return None, "flat"


def _week_match_stats(queryset, now, start_of_week, start_of_last_week):
    """计算本周 match 数及相对上周变化。"""
    week_count = queryset.filter(sent_at__gte=start_of_week, sent_at__lte=now).count()
    last_week_count = queryset.filter(
        sent_at__gte=start_of_last_week, sent_at__lt=start_of_week
    ).count()
    delta_percent, direction = _calc_delta(week_count, last_week_count)
    return {
        "week_count": week_count,
        "last_week_count": last_week_count,
        "week_delta_percent": delta_percent,
        "week_direction": direction,
    }


def _day_match_stats(queryset, now, start_of_today, start_of_yesterday):
    """计算今日 match 数及相对昨日变化。"""
    today_count = queryset.filter(sent_at__gte=start_of_today, sent_at__lte=now).count()
    yesterday_count = queryset.filter(
        sent_at__gte=start_of_yesterday, sent_at__lt=start_of_today
    ).count()
    delta_percent, direction = _calc_delta(today_count, yesterday_count)
    return {
        "today_count": today_count,
        "yesterday_count": yesterday_count,
        "day_delta_percent": delta_percent,
        "day_direction": direction,
    }


def _month_entry_stats(start_of_month, start_of_next_month, start_of_last_month):
    """计算当月入场人数及相对上月变化。"""
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
    delta_percent, direction = _calc_delta(month_entry_count, last_month_entry_count)
    return {
        "month_entry_count": month_entry_count,
        "last_month_entry_count": last_month_entry_count,
        "month_delta_percent": delta_percent,
        "month_direction": direction,
    }


def _monthly_sales_techs(start_of_next_month):
    """查询当月营业技术者列表。"""
    monthly_sales_techs = Technician.objects.filter(
        spot_contract_deadline__isnull=False,
        spot_contract_deadline__lt=start_of_next_month,
        business_status__in=[0, 1, 2],
    ).order_by("spot_contract_deadline", "employee_id")
    return [
        {
            "employee_id": tech.employee_id,
            "name": tech.name,
            "remark": tech.remark or "",
            "business_status": tech.business_status,
        }
        for tech in monthly_sales_techs
    ]


def _entry_items(today, start_date, end_date):
    """生成当月入场进度条所需的数据列表。"""
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
    entry_orders = list(purchase_entries) + list(sales_entries)

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
    return entry_items


def _two_weeks_count(start_of_two_weeks, now):
    """统计两周内求案件人数。"""
    return MailTechnicianInfo.objects.filter(
        date__gte=start_of_two_weeks,
        date__lte=now,
    ).count()


def _next_month_sales_techs(start_of_next_month, start_of_month_after_next):
    """查询下月营业技术者列表。"""
    next_month_sales_techs = Technician.objects.filter(
        spot_contract_deadline__gte=start_of_next_month,
        spot_contract_deadline__lt=start_of_month_after_next,
    ).order_by("spot_contract_deadline", "employee_id")
    return [
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


@csrf_exempt
@require_GET
def home_match_stats_api(request):
    """汇总首页统计数据并返回。"""
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
    match_queryset = _match_base_queryset(login_id)

    payload = {}
    payload.update(
        _week_match_stats(match_queryset, now, start_of_week, start_of_last_week)
    )
    payload.update(
        _day_match_stats(match_queryset, now, start_of_today, start_of_yesterday)
    )
    payload.update(
        _month_entry_stats(start_of_month, start_of_next_month, start_of_last_month)
    )
    payload["monthly_sales_techs"] = _monthly_sales_techs(start_of_next_month)
    payload["two_weeks_count"] = _two_weeks_count(start_of_two_weeks, now)
    payload["entry_items"] = _entry_items(today, start_date, end_date)
    payload["next_month_sales_techs"] = _next_month_sales_techs(
        start_of_next_month, start_of_month_after_next
    )

    return api_success(data=payload)
