import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.utils import timezone

from project.api import api_error
from project.error_codes import ErrorCode
from project.tenancy import tenant_cache_key
from settings.activation_code import is_activation_code_valid
from settings.models import SysSettings

logger = logging.getLogger(__name__)


class SessionLoginRequiredMiddleware:
    """Enforce activation and login checks for protected resources."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if self._should_skip(path):
            return self.get_response(request)

        if (not getattr(request, "tenant_domain", None)
                or request.session.get("tenant_domain") != request.tenant_domain):
            return self._login_required_response(path)

        if not self._check_activation():
            return self._activation_required_response(path)

        if request.session.get("employee_id"):
            return self.get_response(request)
        return self._login_required_response(path)

    @staticmethod
    def _should_skip(path: str) -> bool:
        if path in {
            "/login.html",
            "/favicon.ico",
            "/favicon.png",
            "/favicon-16.png",
            "/favicon-32.png",
            "/favicon-48.png",
            "/aomera-logo-mark-navy.png",
            "/common.css",
            "/components.css",
            "/common.js",
            "/i18n.js",
            "/case_exhibit.html",
            "/api/case-exhibits.csv",
        }:
            return True

        if path in {
            "/api/time-to-save",
            "/api/time-to-clean",
            "/api/time-to-backup",
            "/api/time-to-sync-my-mails",
            "/api/time-to-save-day",
        }:
            return True

        if path.startswith(("/static/", "/admin/", "/tenant-management/")):
            return True

        if path == "/api/login":
            return True

        if path.startswith("/api/activation"):
            return True

        if path.startswith("/api/line/webhook"):
            return True

        return False

    @staticmethod
    def _check_activation() -> bool:
        if cache.get(tenant_cache_key("activation_valid")) is True:
            return True
        record = SysSettings.objects.filter(name="activation", deleted_at__isnull=True).first()
        if not record:
            return False
        settings_payload = record.settings or {}
        token = str(settings_payload.get("code") or "").strip()
        if not token:
            return False
        valid, _payload, _reason = is_activation_code_valid(token, now=timezone.now())
        if valid:
            cache.set(tenant_cache_key("activation_valid"), True, timeout=3600)
        return valid

    @staticmethod
    def _activation_required_response(path: str) -> HttpResponse:
        if path.startswith("/api/"):
            return api_error(ErrorCode.ACTIVATION_REQUIRED, status=403)
        return HttpResponse(
            "<!doctype html><html><head><meta charset='utf-8'></head>"
            "<body><script>window.top.location.replace('/login.html?activation=1');</script></body></html>",
            status=401,
        )

    @staticmethod
    def _login_required_response(path: str) -> HttpResponse:
        if path.startswith("/api/"):
            return api_error(ErrorCode.LOGIN_REQUIRED, "请先登录", status=401)
        return HttpResponse(
            "<!doctype html><html><head><meta charset='utf-8'></head>"
            "<body><script>window.top.location.replace('/login.html');</script></body></html>",
            status=401,
        )


class ApiExceptionMiddleware:
    """Return a unified JSON error for unhandled API exceptions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not request.path.startswith("/api/"):
            return None
        logger.exception("Unhandled API exception on %s", request.path)
        message = "Internal server error"
        if settings.DEBUG:
            message = str(exception)
        return api_error(ErrorCode.SERVER, message, status=500)
