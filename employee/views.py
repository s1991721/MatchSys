from django.shortcuts import redirect, render

from .models import UserLogin

def login_view(request):
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if request.method == "POST":
        user_name = (request.POST.get("user_name") or "").strip()
        password = request.POST.get("password") or ""

        if not user_name or not password:
            return render(
                request,
                "login.html",
                {
                    "error": "请输入账号和密码。",
                    "user_name": user_name,
                    "next": next_url,
                },
            )

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
            return render(
                request,
                "login.html",
                {
                    "error": "账号或密码错误。",
                    "user_name": user_name,
                    "next": next_url,
                },
            )

        request.session.cycle_key()
        request.session["employee_id"] = user_login.employee_id
        request.session["employee_name"] = user_login.employee.name
        request.session["user_name"] = user_login.user_name
        return redirect(next_url or "/index.html")

    return render(request, "login.html", {"next": next_url})
