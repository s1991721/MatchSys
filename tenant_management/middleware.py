from django.conf import settings
from django.contrib.sessions.backends.file import SessionStore
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.exceptions import SessionInterrupted


COOKIE_NAME = "matchsys_platform_session"
COOKIE_PATH = "/tenant-management/"


class PlatformSessionMiddleware:
    """Separate server-side platform sessions, without a business database."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(COOKIE_PATH):
            return self.get_response(request)
        session = request.platform_session = SessionStore(
            request.COOKIES.get(COOKIE_NAME)
        )
        response = self.get_response(request)
        if session.is_empty():
            if COOKIE_NAME in request.COOKIES:
                response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)
        elif response.status_code < 500:
            try:
                session.save()
            except UpdateError as exc:
                raise SessionInterrupted("平台会话已退出，请重新登录。") from exc
            response.set_cookie(
                COOKIE_NAME, session.session_key,
                max_age=settings.SESSION_COOKIE_AGE, path=COOKIE_PATH,
                secure=settings.SESSION_COOKIE_SECURE, httponly=True,
                samesite="Strict",
            )
        return response
