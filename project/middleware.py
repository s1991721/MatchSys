from django.shortcuts import redirect


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
        if path in {"/login.html", "/favicon.ico", "/favicon.png"}:
            return True
        if path.startswith(("/api/", "/admin/", "/static/")):
            return True
        return False