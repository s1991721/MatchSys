from django.middleware.csrf import rotate_token
from django.shortcuts import redirect, render
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.http import require_http_methods, require_POST

from . import credentials


def credential_signature():
    return salted_hmac(
        "tenant_management.credentials",
        credentials.ADMIN_USERNAME + credentials.ADMIN_PASSWORD_HASH,
    ).hexdigest()


def is_authenticated(request):
    return request.platform_session.get("credential_signature") == credential_signature()


@never_cache
@xframe_options_deny
@require_http_methods(["GET", "POST"])
def login(request):
    if is_authenticated(request):
        return redirect("tenant_management:dashboard")
    error = ""
    username = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        if credentials.authenticate(username, request.POST.get("password", "")):
            request.platform_session.flush()
            request.platform_session["credential_signature"] = credential_signature()
            rotate_token(request)
            return redirect("tenant_management:dashboard")
        error = "账号或密码错误"
    return render(request, "tenant_management/login.html", {
        "error": error, "username": username,
    })


@never_cache
@xframe_options_deny
@require_http_methods(["GET"])
def dashboard(request):
    if not is_authenticated(request):
        return redirect("tenant_management:login")
    return render(request, "tenant_management/dashboard.html", {
        "username": credentials.ADMIN_USERNAME,
    })


@never_cache
@require_POST
def logout(request):
    request.platform_session.flush()
    return redirect("tenant_management:login")
