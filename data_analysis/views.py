import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from employee.models import Employee
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
        business_status__in=[0, 1, 2],
    ).filter(
        Q(spot_contract_deadline__lt=start_of_next_month)
        | Q(spot_contract_deadline__isnull=True)
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


def _order_monthly_stats(employee_id, start_of_month):
    """按月统计发注数与受注数。"""
    labels = []
    purchase_counts = []
    sales_counts = []

    months = [shift_month(start_of_month, -offset) for offset in range(6, -1, -1)]
    for month_start in months:
        month_end = shift_month(month_start, 1)
        label = f"{month_start.year}-{month_start.month:02d}"
        labels.append(label)
        if employee_id:
            purchase_counts.append(
                PurchaseOrder.objects.filter(
                    deleted_at__isnull=True,
                    period_start__gte=month_start,
                    period_start__lt=month_end,
                    person_in_charge_id=employee_id,
                ).count()
            )
            sales_counts.append(
                SalesOrder.objects.filter(
                    deleted_at__isnull=True,
                    period_start__gte=month_start,
                    period_start__lt=month_end,
                    person_in_charge_id=employee_id,
                ).count()
            )
        else:
            purchase_counts.append(0)
            sales_counts.append(0)

    return {
        "order_month_labels": labels,
        "order_purchase_counts": purchase_counts,
        "order_sales_counts": sales_counts,
    }


def _decimal_value(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _format_amount(value):
    return format(_decimal_value(value), ".2f")


def _load_technician_map(orders):
    tech_ids = {order.technician_id for order in orders if order.technician_id}
    tech_map = {}
    if tech_ids:
        for tech in Technician.objects.filter(employee_id__in=tech_ids):
            tech_map[tech.employee_id] = tech
    return tech_map


def _load_employee_names(employee_ids):
    name_map = {}
    if employee_ids:
        for employee in Employee.objects.filter(id__in=employee_ids, deleted_at__isnull=True):
            name_map[employee.id] = employee.name
    return name_map


def _rank_records(items, key, reverse=True, limit=3):
    sorted_items = sorted(items, key=lambda item: item[key], reverse=reverse)
    ranked = []
    for index, item in enumerate(sorted_items[:limit], start=1):
        ranked.append({"rank": index, **item})
    return ranked


def _sum_diffs_by_key(orders, key_getter, name_getter):
    totals = defaultdict(Decimal)
    names = {}
    for order in orders:
        key = key_getter(order)
        if key is None:
            continue
        diff = _decimal_value(order.price) - _decimal_value(name_getter["tech_price"](order))
        totals[key] += diff
        if key not in names:
            names[key] = name_getter["name"](order)
    return totals, names


def _analysis_payload(today):
    year_start = today.replace(month=1, day=1)
    year_end = date(today.year + 1, 1, 1)
    month_start = today.replace(day=1)
    month_end = shift_month(month_start, 1)

    active_orders = list(
        SalesOrder.objects.filter(
            deleted_at__isnull=True,
            period_start__lte=today,
            period_end__gte=today,
        )
    )
    year_orders = list(
        SalesOrder.objects.filter(
            deleted_at__isnull=True,
            period_start__gte=year_start,
            period_start__lt=year_end,
        )
    )
    month_orders = list(
        SalesOrder.objects.filter(
            deleted_at__isnull=True,
            period_start__gte=month_start,
            period_start__lt=month_end,
        )
    )
    tech_map = _load_technician_map(active_orders + year_orders + month_orders)
    employee_name_map = _load_employee_names(
        {order.person_in_charge_id for order in month_orders if order.person_in_charge_id}
    )

    def tech_price(order):
        tech = tech_map.get(order.technician_id)
        return tech.price if tech and tech.price is not None else Decimal("0")

    def tech_name(order):
        tech = tech_map.get(order.technician_id)
        return tech.name if tech else (order.technician_name or "")

    def employee_name(order):
        if order.person_in_charge_id in employee_name_map:
            return employee_name_map[order.person_in_charge_id]
        return order.person_in_charge or ""

    current_items = []
    for order in active_orders:
        diff = _decimal_value(order.price) - _decimal_value(tech_price(order))
        current_items.append(
            {
                "employee_name": tech_name(order),
                "amount": diff,
            }
        )

    current_top_profit = _rank_records(current_items, "amount", reverse=True, limit=3)
    current_low_profit = _rank_records(current_items, "amount", reverse=False, limit=3)

    year_totals, year_names = _sum_diffs_by_key(
        year_orders,
        lambda order: order.technician_id,
        {"tech_price": tech_price, "name": tech_name},
    )
    yearly_items = [
        {
            "employee_name": year_names.get(tech_id, ""),
            "amount": total,
        }
        for tech_id, total in year_totals.items()
    ]
    yearly_top_profit = _rank_records(yearly_items, "amount", reverse=True, limit=3)

    customer_totals = defaultdict(Decimal)
    customer_names = {}
    for order in year_orders:
        diff = _decimal_value(order.price) - _decimal_value(tech_price(order))
        customer_totals[order.customer_id] += diff
        if order.customer_id not in customer_names:
            customer_names[order.customer_id] = order.customer_name or ""
    customer_items = [
        {"customer_name": customer_names.get(customer_id, ""), "amount": total}
        for customer_id, total in customer_totals.items()
    ]
    top_profit_customers = _rank_records(customer_items, "amount", reverse=True, limit=3)

    customer_order_counts = defaultdict(int)
    customer_order_names = {}
    for order in year_orders:
        customer_order_counts[order.customer_id] += 1
        if order.customer_id not in customer_order_names:
            customer_order_names[order.customer_id] = order.customer_name or ""
    top_order_customers = _rank_records(
        [
            {
                "customer_name": customer_order_names.get(customer_id, ""),
                "order_count": count,
            }
            for customer_id, count in customer_order_counts.items()
        ],
        "order_count",
        reverse=True,
        limit=3,
    )

    month_order_counts = defaultdict(int)
    month_profit_totals = defaultdict(Decimal)
    month_person_names = {}
    for order in month_orders:
        if not order.person_in_charge_id:
            continue
        month_order_counts[order.person_in_charge_id] += 1
        diff = _decimal_value(order.price) - _decimal_value(tech_price(order))
        month_profit_totals[order.person_in_charge_id] += diff
        if order.person_in_charge_id not in month_person_names:
            month_person_names[order.person_in_charge_id] = employee_name(order)

    monthly_order_volume = _rank_records(
        [
            {
                "employee_name": month_person_names.get(person_id, ""),
                "order_count": count,
            }
            for person_id, count in month_order_counts.items()
        ],
        "order_count",
        reverse=True,
        limit=3,
    )
    monthly_profit = _rank_records(
        [
            {
                "employee_name": month_person_names.get(person_id, ""),
                "amount": total,
                "order_count": month_order_counts.get(person_id, 0),
            }
            for person_id, total in month_profit_totals.items()
        ],
        "amount",
        reverse=True,
        limit=3,
    )

    def format_amount_items(items):
        for item in items:
            if "amount" in item:
                item["amount"] = _format_amount(item["amount"])
        return items

    return {
        "current_top_profit_employees": format_amount_items(current_top_profit),
        "current_low_profit_employees": format_amount_items(current_low_profit),
        "yearly_top_profit_employees": format_amount_items(yearly_top_profit),
        "top_profit_customers": format_amount_items(top_profit_customers),
        "top_order_customers": top_order_customers,
        "monthly_order_volume": monthly_order_volume,
        "monthly_sales_profit": format_amount_items(monthly_profit),
    }


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
    payload.update(
        _order_monthly_stats(request.session.get("employee_id"), start_of_month)
    )

    return api_success(data=payload)


@csrf_exempt
@require_GET
def analysis_stats_api(request):
    """汇总数据分析页面统计数据并返回。"""
    login_id, error = require_login(request)
    if error:
        return error

    _ = login_id
    today = timezone.localdate()
    payload = _analysis_payload(today)
    return api_success(data=payload)
