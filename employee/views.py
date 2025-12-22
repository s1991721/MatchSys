import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import UserLogin


@csrf_exempt
@require_POST
def login_api(request):
    user_name = ""
    password = ""

    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        user_name = (payload.get("user_name") or "").strip()
        password = payload.get("password") or ""
    else:
        user_name = (request.POST.get("user_name") or "").strip()
        password = request.POST.get("password") or ""

    if not user_name or not password:
        return JsonResponse({"error": "Missing user_name or password"}, status=400)

    user_login = (
        UserLogin.objects.select_related("employee")
        .filter(
            user_name=user_name,
            deleted_at__isnull=True,
            employee__deleted_at__isnull=True,
            employee__status=1,
        )
        .first()
    )

    if not user_login or user_login.password != password:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    request.session.cycle_key()
    request.session["employee_id"] = user_login.employee_id
    request.session["employee_name"] = user_login.employee.name
    request.session["user_name"] = user_login.user_name

    return JsonResponse(
        {
            "status": "ok",
            "employee": {
                "id": user_login.employee_id,
                "name": user_login.employee.name,
            },
            "redirect": "/index.html",
        }
    )
