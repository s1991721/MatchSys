import json
import logging

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError

from project.api import api_error
from project.error_codes import ErrorCode
from project.tenancy import COOKIE, SALT, TASK_SALT, TASK_PATHS, tenant_context
from tenant_management.services import managed_schema, normalize_domain, require_enabled, TenantDisabled

logger = logging.getLogger(__name__)


class TenantRoutingMiddleware:
    """Runs outside SessionMiddleware so DB sessions also use the tenant schema."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        domain = None
        schema = None
        task = False
        try:
            if request.path == '/api/login' and request.method == 'POST':
                payload = json.loads(request.body)
                email = payload.get('user_name', '').strip()
                validate_email(email)
                domain = normalize_domain(email.rsplit('@', 1)[1])
            elif request.path.startswith('/api/line/webhook'):
                # The webhook verifies LINE's signature using this tenant's secret.
                domain = normalize_domain(request.GET.get('tenant_domain', ''))
            elif request.headers.get('X-MatchSys-Task'):
                if request.path not in TASK_PATHS:
                    return api_error(ErrorCode.LOGIN_REQUIRED, status=401)
                token = signing.loads(request.headers['X-MatchSys-Task'], salt=TASK_SALT, max_age=60)
                if token.get('path') != request.path:
                    raise ValueError('Invalid task path')
                domain = normalize_domain(token['domain'])
                task = True
            elif not request.path.startswith('/tenant-management/'):
                value = request.get_signed_cookie(COOKIE, default=None, salt=SALT, max_age=settings.SESSION_COOKIE_AGE)
                if value:
                    domain = normalize_domain(value)
            if domain:
                schema = managed_schema(domain)
                require_enabled(schema)
                claimed = request.headers.get('X-Tenant-Domain')
                if claimed and normalize_domain(claimed) != domain:
                    return api_error(ErrorCode.FORBIDDEN, '租户标识与登录公司不一致', status=403)
        except TenantDisabled as exc:
            return api_error(ErrorCode.FORBIDDEN, str(exc), status=403)
        except (ValueError, TypeError, AttributeError, KeyError, ValidationError, signing.BadSignature, DatabaseError):
            if request.path == '/api/login':
                return api_error(ErrorCode.LOGIN_INVALID_CREDENTIALS, status=401)
            return api_error(ErrorCode.LOGIN_REQUIRED, status=401)
        request.tenant_domain = domain
        request.tenant_task = task
        if not domain and request.path.startswith('/api/'):
            return api_error(ErrorCode.LOGIN_REQUIRED, '请使用公司邮箱登录', status=401)
        if not domain:
            request.COOKIES.pop(settings.SESSION_COOKIE_NAME, None)
        with tenant_context(domain, schema or (None if request.path.startswith('/tenant-management/') else '!')):
            response = self.get_response(request)
        if getattr(request, 'tenant_login_success', False):
            response.set_signed_cookie(COOKIE, domain, salt=SALT,
                max_age=settings.SESSION_COOKIE_AGE, httponly=True,
                secure=settings.SESSION_COOKIE_SECURE, samesite='Lax')
        elif request.path == '/api/logout':
            response.delete_cookie(COOKIE)
        elif domain and not task and response.status_code < 400:
            response.set_signed_cookie(COOKIE, domain, salt=SALT,
                max_age=settings.SESSION_COOKIE_AGE, httponly=True,
                secure=settings.SESSION_COOKIE_SECURE, samesite='Lax')
        return response


class TenantSessionBindingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (request.path.startswith('/api/') and request.path != '/api/login'
                and not request.path.startswith('/api/line/webhook')
                and not getattr(request, 'tenant_task', False)):
            if (not request.session.get('employee_id')
                    or request.session.get('tenant_domain') != request.tenant_domain):
                return api_error(ErrorCode.LOGIN_REQUIRED, status=401)
        return self.get_response(request)
