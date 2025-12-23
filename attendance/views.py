import json
from datetime import date, datetime, time, timedelta
import re

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Q

from employee.models import Employee
from .models import AttendancePolicy, get_monthly_attendance_models


@csrf_exempt
@require_POST
def attendance_punch_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    payload, error = _parse_json_body(request)
    if error:
        return error

    now = timezone.localtime()
    punch_time_raw = (payload.get("punch_time") or "").strip()
    if punch_time_raw:
        try:
            punch_time_value = datetime.strptime(punch_time_raw, "%H:%M:%S").time()
        except ValueError:
            return JsonResponse({"error": "Invalid punch_time"}, status=400)
    else:
        punch_time_value = now.time().replace(microsecond=0)

    work_start = time(2, 0, 0)
    work_end = time(14, 0, 0)
    punch_type = 1 if work_start <= punch_time_value <= work_end else 2

    employee = Employee.objects.filter(id=employee_id, deleted_at__isnull=True).first()
    if not employee:
        return JsonResponse({"error": "Employee not found"}, status=404)

    punch_model, record_model = get_monthly_attendance_models(now.date())
    punch = _create_attendance_punch(
        punch_model, employee, now, punch_time_value, punch_type, payload
    )
    record = _sync_attendance_record(
        punch_model, record_model, employee, now, punch_type
    )

    return JsonResponse(
        {
            "status": "ok",
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
    )


def _parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)


def _parse_time_value(value, field_name):
    value = (value or "").strip()
    if not value or value in {"--:--", "未打卡"}:
        return None, None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time(), None
        except ValueError:
            continue
    return None, JsonResponse({"error": f"Invalid {field_name}"}, status=400)



def _create_attendance_punch(
    model, employee, now, punch_time_value, punch_type, payload, punch_date=None, remark=""
):
    return model.objects.create(
        employee=employee,
        punch_date=punch_date or now.date(),
        punch_time=punch_time_value,
        punch_type=punch_type,
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        location_text=(payload.get("location_text") or "")[:255],
        remark=remark or "",
        created_by=employee,
        created_at=now,
        updated_by=employee,
        updated_at=now,
    )


def _sync_attendance_record(punch_model, record_model, employee, now, punch_type):
    punch_queryset = punch_model.objects.filter(
        employee=employee,
        punch_date=now.date(),
        deleted_at__isnull=True,
    )
    start_punch = punch_queryset.filter(punch_type=1).order_by("punch_time").first()
    end_punch = punch_queryset.filter(punch_type=2).order_by("-punch_time").first()
    if not start_punch and not end_punch:
        return None

    record = record_model.objects.filter(
        employee=employee,
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
            record.updated_by = employee
            record.updated_at = now
            update_fields.extend(["updated_by", "updated_at"])
            record.save(update_fields=update_fields)
        return record

    record = record_model.objects.create(
        employee=employee,
        punch_date=now.date(),
        start_time=start_time,
        end_time=end_time,
        created_by=employee,
        created_at=now,
        updated_by=employee,
        updated_at=now,
    )
    return record


@csrf_exempt
@require_POST
def attendance_record_edit_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    payload, error = _parse_json_body(request)
    if error:
        return error

    date_raw = (payload.get("date") or "").strip()
    remark = (payload.get("remark") or "").strip()
    if not date_raw:
        return JsonResponse({"error": "Missing date"}, status=400)
    if not remark:
        return JsonResponse({"error": "Missing remark"}, status=400)

    try:
        target_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Invalid date"}, status=400)

    start_time_value, error = _parse_time_value(payload.get("start_time"), "start_time")
    if error:
        return error
    end_time_value, error = _parse_time_value(payload.get("end_time"), "end_time")
    if error:
        return error
    original_start, error = _parse_time_value(
        payload.get("original_start_time"), "original_start_time"
    )
    if error:
        return error
    original_end, error = _parse_time_value(
        payload.get("original_end_time"), "original_end_time"
    )
    if error:
        return error

    employee = Employee.objects.filter(id=employee_id, deleted_at__isnull=True).first()
    if not employee:
        return JsonResponse({"error": "Employee not found"}, status=404)

    now = timezone.localtime()
    punch_model, record_model = get_monthly_attendance_models(target_date)

    final_start = start_time_value if start_time_value is not None else original_start
    final_end = end_time_value if end_time_value is not None else original_end

    if final_start is None or final_end is None:
        return JsonResponse({"error": "Missing start_time or end_time"}, status=400)

    start_changed = final_start != original_start
    end_changed = final_end != original_end

    if start_changed:
        _create_attendance_punch(
            punch_model,
            employee,
            now,
            final_start,
            1,
            {},
            punch_date=target_date,
            remark=remark,
        )
    if end_changed:
        _create_attendance_punch(
            punch_model,
            employee,
            now,
            final_end,
            2,
            {},
            punch_date=target_date,
            remark=remark,
        )

    defaults = {
        "start_time": final_start,
        "end_time": final_end,
        "remark": remark,
        "created_by": employee,
        "created_at": now,
        "updated_by": employee,
        "updated_at": now,
    }
    record, created = record_model.objects.get_or_create(
        employee=employee,
        punch_date=target_date,
        defaults=defaults,
    )
    if not created:
        record.start_time = final_start
        record.end_time = final_end
        record.remark = remark
        record.updated_by = employee
        record.updated_at = now
        record.save(
            update_fields=[
                "start_time",
                "end_time",
                "remark",
                "updated_by",
                "updated_at",
            ]
        )

    return JsonResponse(
        {
            "status": "ok",
            "record": {
                "date": target_date.isoformat(),
                "start_time": final_start.strftime("%H:%M"),
                "end_time": final_end.strftime("%H:%M"),
                "remark": remark,
            },
        }
    )



@require_GET
def attendance_record_today_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    today = timezone.localdate()
    record_model = get_monthly_attendance_models(today)[1]
    record = record_model.objects.filter(
        employee_id=employee_id,
        punch_date=today,
        deleted_at__isnull=True,
    ).first()

    return JsonResponse(
        {
            "date": today.isoformat(),
            "start_time": record.start_time.strftime("%H:%M:%S") if record and record.start_time else "",
            "end_time": record.end_time.strftime("%H:%M:%S") if record and record.end_time else "",
        }
    )


def _shift_month(value, offset):
    year = value.year + (value.month - 1 + offset) // 12
    month = (value.month - 1 + offset) % 12 + 1
    return date(year, month, 1)


def _resolve_attendance_month(request):
    value = (request.GET.get("month") or request.GET.get("date") or "").strip()
    today = timezone.localdate()
    if not value or value.lower() in {"current", "this", "now"}:
        return today
    if value.lower() in {"previous", "prev", "last"}:
        return _shift_month(today, -1)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return today
    if re.fullmatch(r"\d{4}-\d{2}", value):
        year, month = value.split("-")
        try:
            return date(int(year), int(month), 1)
        except ValueError:
            return today
    if re.fullmatch(r"\d{6}", value):
        try:
            return date(int(value[:4]), int(value[4:6]), 1)
        except ValueError:
            return today
    return today


@require_GET
def my_attendance_summary_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    target_date = _resolve_attendance_month(request)
    record_model = get_monthly_attendance_models(target_date)[1]
    records = record_model.objects.filter(
        employee_id=employee_id,
        deleted_at__isnull=True,
    )

    attendance_days = records.filter(
        Q(start_time__isnull=False) | Q(end_time__isnull=False)
    ).count()

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

    absent_days = records.filter(
        Q(start_time__isnull=True) | Q(end_time__isnull=True)
    ).count()

    return JsonResponse(
        {
            "month": target_date.strftime("%Y-%m"),
            "summary": {
                "attendance_days": attendance_days,
                "late_days": late_days,
                "absent_days": absent_days,
            },
        }
    )


@require_GET
def my_attendance_detail_api(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    target_date = _resolve_attendance_month(request)
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
                "remark": record.remark or "",
                "has_missing": not (record.start_time and record.end_time),
            }
        )

    return JsonResponse(
        {
            "month": target_date.strftime("%Y-%m"),
            "records": payload,
        }
    )
