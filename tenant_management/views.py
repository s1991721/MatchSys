import logging

from django.db import DatabaseError
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect, render
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.http import require_http_methods, require_POST

from . import credentials, services

logger = logging.getLogger(__name__)


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
@require_http_methods(["GET", "POST"])
def dashboard(request):
    if not is_authenticated(request):
        return redirect("tenant_management:login")
    error = ""
    message = request.platform_session.pop("notice", "")
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            domain = request.POST.get("email_domain", "")
            if action == "create":
                if "email_domain_label" in request.POST:
                    label = request.POST.get("email_domain_label", "").strip()
                    if not label or "." in label or "@" in label:
                        raise ValueError("请只填写邮箱域名中间部分，例如 XXXX，不需要 @ 或 .com")
                    domain = label + ".com"
                services.create_tenant(request.POST.get("company_name", ""), domain, request.POST.get("password", ""))
                notice = "租户创建成功，管理员账号：admin@" + services.normalize_domain(domain)
            elif action == "password":
                services.update_password(domain, request.POST.get("password", ""))
                notice = "管理员密码已更新"
            elif action in {"disable", "enable"}:
                services.set_enabled(domain, action == "enable")
                notice = "租户已启用" if action == "enable" else "租户已停用，现有登录会话已失效"
            elif action == "delete":
                if request.POST.get("confirmation") != domain:
                    raise ValueError("请输入完整邮箱域名确认删除")
                services.delete_tenant(domain)
                notice = "租户已删除"
            else:
                raise ValueError("不支持的操作")
            request.platform_session["notice"] = notice
            return redirect("tenant_management:dashboard")
        except ValueError as exc:
            error = str(exc)
        except DatabaseError:
            logger.exception("Tenant management operation failed")
            error = "操作失败，请检查数据库权限和初始化日志后重试"
    try:
        tenants = services.list_tenants()
    except DatabaseError:
        logger.exception("Unable to list tenants")
        tenants = []
        error = error or "无法读取租户列表，请检查数据库连接及权限"
    return render(request, "tenant_management/dashboard.html", {
        "username": credentials.ADMIN_USERNAME,
        "tenants": tenants, "error": error, "message": message,
    })


@never_cache
@require_POST
def logout(request):
    request.platform_session.flush()
    return redirect("tenant_management:login")
