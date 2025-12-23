import json
from datetime import datetime, time

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from employee.models import Employee
from .models import AttendancePunch


def _parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)


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

    punch = AttendancePunch.objects.create(
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

    return JsonResponse(
        {
            "status": "ok",
            "punch": {
                "id": punch.id,
                "date": punch.punch_date.isoformat(),
                "time": punch.punch_time.strftime("%H:%M:%S"),
                "type": punch.punch_type,
            },
        }
    )
