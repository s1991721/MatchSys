from datetime import datetime, time

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from employee.models import Employee
from project.api import api_error, api_success
from project.common_tools import parse_json_body, parse_time_value, weekday_label, is_workday, count_workdays
from .models import AttendancePolicy, get_monthly_attendance_models


@csrf_exempt
@require_POST
# 打卡
def attendance_punch_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return api_error("Unauthorized", status=401)

    payload, error = parse_json_body(request)
    if error:
        return error

    now = timezone.localtime()
    punch_time_value = now.time().replace(microsecond=0)

    work_start = time(2, 0, 0)
    work_end = time(14, 0, 0)
    punch_type = 1 if work_start <= punch_time_value <= work_end else 2

    employee = Employee.objects.filter(id=employee_id, deleted_at__isnull=True).first()
    if not employee:
        return api_error("Employee not found", status=404)

    punch_model, record_model = get_monthly_attendance_models(now.date())
    punch = _create_attendance_punch(punch_model, employee, now, punch_time_value, punch_type, payload)
    record = _sync_attendance_record(punch_model, record_model, employee, now)

    payload = {
        "punch": {
            "id": punch.id,
            "date": punch.punch_date.isoformat(),
            "time": punch.punch_time.strftime("%H:%M:%S"),
            "type": punch.punch_type,
        },
        "record": {
            "id": record.id if record else None,
            "type": punch_type if record else None,
            "time": (
                record.start_time.strftime("%H:%M:%S")
                if record and punch_type == 1 and record.start_time
                else record.end_time.strftime("%H:%M:%S")
                if record and punch_type == 2 and record.end_time
                else None
            ),
        },
    }
    return api_success(data=payload)


# 创建打卡记录
def _create_attendance_punch(
        model, employee, now, punch_time_value, punch_type, payload, remark=""
):
    return model.objects.create(
        employee_id=employee.id,
        punch_date=now.date(),
        punch_time=punch_time_value,
        punch_type=punch_type,
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        location_text=(payload.get("location_text") or "")[:255],
        remark=remark or "",
        created_by=employee.id
    )


# 同步考勤记录
def _sync_attendance_record(punch_model, record_model, employee, now):
    punch_queryset = punch_model.objects.filter(
        employee_id=employee.id,
        punch_date=now.date(),
        deleted_at__isnull=True,
    )
    start_punch = punch_queryset.filter(punch_type=1).order_by("punch_time").first()
    end_punch = punch_queryset.filter(punch_type=2).order_by("-punch_time").first()
    if not start_punch and not end_punch:
        return None

    record = record_model.objects.filter(
        employee_id=employee.id,
        punch_date=now.date(),
        deleted_at__isnull=True,
    ).first()

    start_time = start_punch.punch_time if start_punch else None
    end_time = end_punch.punch_time if end_punch else None

    if record:
        update_fields = []
        if start_time is not None:
            record.start_time = start_time
            update_fields.append("start_time")
        if end_time is not None:
            record.end_time = end_time
            update_fields.append("end_time")
        if update_fields:
            record.updated_by = employee.id
            record.updated_at = now
            update_fields.extend(["updated_by", "updated_at"])
            record.save(update_fields=update_fields)
        return record

    record = record_model.objects.create(
        employee_id=employee.id,
        punch_date=now.date(),
        start_time=start_time,
        end_time=end_time,
        created_by=employee.id
    )
    return record


@csrf_exempt
@require_POST
# 修改考勤
def attendance_record_edit_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return api_error("Unauthorized", status=401)

    payload, error = parse_json_body(request)
    if error:
        return error

    date_raw = (payload.get("date") or "").strip()
    remark = (payload.get("remark") or "").strip()
    if not date_raw:
        return api_error("Missing date")
    if not remark:
        return api_error("Missing remark")

    try:
        target_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
    except ValueError:
        return api_error("Invalid date")

    start_time_value, error = parse_time_value(payload.get("start_time"))
    if error:
        return error

    end_time_value, error = parse_time_value(payload.get("end_time"))
    if error:
        return error

    original_start, error = parse_time_value(payload.get("original_start_time"))
    if error:
        return error

    original_end, error = parse_time_value(payload.get("original_end_time"))
    if error:
        return error

    employee = Employee.objects.filter(id=employee_id, deleted_at__isnull=True).first()
    if not employee:
        return api_error("Employee not found", status=404)

    punch_model, record_model = get_monthly_attendance_models(target_date)

    final_start = start_time_value if start_time_value is not None else original_start
    final_end = end_time_value if end_time_value is not None else original_end

    if final_start is None or final_end is None:
        return api_error("Missing start_time or end_time")

    defaults = {
        "start_time": final_start,
        "end_time": final_end,
        "remark": remark,
        "created_by": employee.id,
        "updated_by": employee.id,
    }
    record, created = record_model.objects.get_or_create(
        employee_id=employee.id,
        punch_date=target_date,
        defaults=defaults,
    )
    if not created:
        record.start_time = final_start
        record.end_time = final_end
        record.remark = remark
        record.updated_by = employee.id
        record.save()

    payload = {
        "record": {
            "date": target_date.isoformat(),
            "start_time": final_start.strftime("%H:%M"),
            "end_time": final_end.strftime("%H:%M"),
            "remark": remark,
        },
    }
    return api_success(data=payload)


@require_GET
# 获取今天的考勤记录
def attendance_record_today_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return api_error("Unauthorized", status=401)

    today = timezone.localdate()
    record_model = get_monthly_attendance_models(today)[1]
    record = record_model.objects.filter(
        employee_id=employee_id,
        punch_date=today,
        deleted_at__isnull=True,
    ).first()

    payload = {
        "date": today.isoformat(),
        "start_time": record.start_time.strftime("%H:%M:%S")
        if record and record.start_time
        else "",
        "end_time": record.end_time.strftime("%H:%M:%S")
        if record and record.end_time
        else "",
    }
    return api_success(data=payload)


@require_GET
# 每月汇总 出勤-迟到-缺勤
def my_attendance_summary_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return api_error("Unauthorized", status=401)

    target_date = request.GET.get("date")
    target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    record_model = get_monthly_attendance_models(target_date)[1]
    records = record_model.objects.filter(
        employee_id=employee_id,
        deleted_at__isnull=True,
    )

    workdays = count_workdays(target_date)
    attendance_days = sum(
        1
        for record in records
        if is_workday(record.punch_date)
        and (record.start_time is not None or record.end_time is not None)
    )

    policy = AttendancePolicy.objects.filter(
        employee_id=employee_id,
        deleted_at__isnull=True,
    ).first()
    if not policy and employee_id != 1:
        policy = AttendancePolicy.objects.filter(
            employee_id=1,
            deleted_at__isnull=True,
        ).first()
    if policy and policy.work_start_time:
        late_days = records.filter(start_time__gt=policy.work_start_time).count()
    else:
        late_days = 0

    absent_days = max(workdays - attendance_days, 0)

    payload = {
        "month": target_date.strftime("%Y-%m"),
        "summary": {
            "attendance_days": attendance_days,
            "late_days": late_days,
            "absent_days": absent_days,
        },
    }
    return api_success(data=payload)


@require_GET
# 获取某月所有天的考勤详情
def my_attendance_detail_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return api_error("Unauthorized", status=401)

    target_date = request.GET.get("date")
    target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    record_model = get_monthly_attendance_models(target_date)[1]
    records = record_model.objects.filter(
        employee_id=employee_id,
        deleted_at__isnull=True,
    ).order_by("-punch_date")

    payload = []
    for record in records:
        payload.append(
            {
                "date": record.punch_date.isoformat(),
                "display_date": f"{record.punch_date.month}月{record.punch_date.day}日",
                "start_time": record.start_time.strftime("%H:%M") if record.start_time else "",
                "end_time": record.end_time.strftime("%H:%M") if record.end_time else "",
                "remark": record.remark or ""
            }
        )

    response_payload = {
        "month": target_date.strftime("%Y-%m"),
        "records": payload,
    }
    return api_success(data=response_payload)


@require_GET
# 全体人员，每月考勤汇总列表
def attendance_summary_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return api_error("Unauthorized", status=401)

    target_date = request.GET.get("month")
    target_date = datetime.strptime(target_date, "%Y-%m").date()
    name_filter = (request.GET.get("name") or "").strip()

    employees_qs = Employee.objects.filter(deleted_at__isnull=True).order_by("id")
    if name_filter:
        employees_qs = employees_qs.filter(name__icontains=name_filter)

    employees = list(employees_qs)
    if not employees:
        response_payload = {
            "month": target_date.strftime("%Y-%m"),
            "employees": [],
        }
        return api_success(data=response_payload)

    employee_ids = [emp.id for emp in employees]
    record_model = get_monthly_attendance_models(target_date)[1]
    records = record_model.objects.filter(
        employee_id__in=employee_ids,
        deleted_at__isnull=True,
    ).order_by("employee_id", "punch_date")

    policies = AttendancePolicy.objects.filter(
        employee_id__in=employee_ids,
        deleted_at__isnull=True,
    )
    policy_map = {policy.employee_id: policy for policy in policies}
    default_policy = AttendancePolicy.objects.filter(
        employee_id=1,
        deleted_at__isnull=True,
    ).first()

    summary_map = {
        emp_id: {"attendance_days": 0, "late_days": 0}
        for emp_id in employee_ids
    }
    workdays = count_workdays(target_date)

    for record in records:
        policy = policy_map.get(record.employee_id) or default_policy
        start_time = record.start_time
        end_time = record.end_time
        has_start = start_time is not None
        has_end = end_time is not None
        has_any = has_start or has_end
        workday = is_workday(record.punch_date)
        is_missing = not (has_start and has_end)
        is_late = bool(
            policy and policy.work_start_time and has_start and start_time > policy.work_start_time
        )

        summary = summary_map[record.employee_id]
        if has_any and workday:
            summary["attendance_days"] += 1
        if is_late and workday:
            summary["late_days"] += 1

    payload = []
    month_label = target_date.strftime("%Y-%m")
    for emp in employees:
        summary = summary_map.get(emp.id, {})
        attendance_days = summary.get("attendance_days", 0)
        absent_days = max(workdays - attendance_days, 0)
        late_days = summary.get("late_days", 0)
        status = "normal"
        if absent_days:
            status = "warning"
        elif late_days:
            status = "alert"

        payload.append(
            {
                "employee_id": emp.id,
                "name": emp.name,
                "month": month_label,
                "attendance_days": attendance_days,
                "absence_days": absent_days,
                "annual_leave": 0,
                "status": status,
            }
        )

    response_payload = {"month": month_label, "employees": payload}
    return api_success(data=response_payload)


@require_GET
# employee_id员工在month月的考勤详情
def attendance_detail_api(request, employee_id):
    login_id = request.session.get("employee_id")
    if not login_id:
        return api_error("Unauthorized", status=401)

    target_date = request.GET.get("month")
    target_date = datetime.strptime(target_date, "%Y-%m").date()
    employee = Employee.objects.filter(id=employee_id, deleted_at__isnull=True).first()
    if not employee:
        return api_error("Employee not found", status=404)

    record_model = get_monthly_attendance_models(target_date)[1]
    records = record_model.objects.filter(
        employee_id=employee_id,
        deleted_at__isnull=True,
    ).order_by("punch_date")

    policy = AttendancePolicy.objects.filter(
        employee_id=employee_id,
        deleted_at__isnull=True,
    ).first()
    if not policy and employee_id != 1:
        policy = AttendancePolicy.objects.filter(
            employee_id=1,
            deleted_at__isnull=True,
        ).first()

    details = []
    for record in records:
        start_time = record.start_time
        end_time = record.end_time
        has_start = start_time is not None
        has_end = end_time is not None
        is_missing = not (has_start and has_end)
        is_late = bool(
            policy and policy.work_start_time and has_start and start_time > policy.work_start_time
        )

        note = "正常"
        if is_missing:
            note = "缺卡"
        elif is_late:
            note = "迟到"

        details.append(
            {
                "date": record.punch_date.isoformat(),
                "day": weekday_label(record.punch_date),
                "clock_in": start_time.strftime("%H:%M") if has_start else "未打卡",
                "clock_out": end_time.strftime("%H:%M") if has_end else "未打卡",
                "note": note,
            }
        )

    response_payload = {
        "month": target_date.strftime("%Y-%m"),
        "employee": {
            "employee_id": employee.id,
            "name": employee.name,
        },
        "details": details,
    }
    return api_success(data=response_payload)
