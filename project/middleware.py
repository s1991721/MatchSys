from django.conf import settings
from django.shortcuts import redirect

from project.api import api_error


class SessionLoginRequiredMiddleware:
    """Redirect anonymous users away from protected pages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if self._should_skip(path) or request.session.get("employee_id"):
            return self.get_response(request)
        return redirect("/login.html")

    @staticmethod
    def _should_skip(path: str) -> bool:
        if path in {
            "/login.html",
            "/favicon.ico",
            "/favicon.png",
            "/favicon-32.png",
            "/common.css",
            "/components.css",
            "/common.js",
            "/i18n.js",
        }:
            return True
        if path.startswith(("/api/", "/admin/", "/static/")):
            return True
        return False


class ApiExceptionMiddleware:
    """Return a unified JSON error for unhandled API exceptions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not request.path.startswith("/api/"):
            return None
        message = "Internal server error"
        if settings.DEBUG:
            message = str(exception)
        return api_error(message, status=500)
