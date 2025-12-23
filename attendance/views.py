import json
from datetime import datetime, time

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from employee.models import Employee
from .models import get_monthly_attendance_models


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



def _create_attendance_punch(model, employee, now, punch_time_value, punch_type, payload):
    return model.objects.create(
        employee=employee,
        punch_date=now.date(),
        punch_time=punch_time_value,
        punch_type=punch_type,
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        location_text=(payload.get("location_text") or "")[:255],
        created_by=employee,
        created_at=now,
        updated_by=employee,
        updated_at=now,
    )


def _sync_attendance_record(punch_model, record_model, employee, now, punch_type):
    punch_queryset = punch_model.objects.filter(
        employee=employee,
        punch_date=now.date(),
        punch_type=punch_type,
        deleted_at__isnull=True,
    )
    punch_order = "punch_time" if punch_type == 1 else "-punch_time"
    selected_punch = punch_queryset.order_by(punch_order).first()
    if not selected_punch:
        return None

    defaults = {
        "start_time": selected_punch.punch_time if punch_type == 1 else None,
        "end_time": selected_punch.punch_time if punch_type == 2 else None,
        "created_by": employee,
        "created_at": now,
        "updated_by": employee,
        "updated_at": now,
    }

    record, created = record_model.objects.get_or_create(
        employee=employee,
        punch_date=selected_punch.punch_date,
        defaults=defaults,
    )
    if not created:
        if punch_type == 1:
            record.start_time = selected_punch.punch_time
            update_fields = ["start_time"]
        else:
            record.end_time = selected_punch.punch_time
            update_fields = ["end_time"]
        record.updated_by = employee
        record.updated_at = now
        update_fields.extend(["updated_by", "updated_at"])
        record.save(update_fields=update_fields)
    return record



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
