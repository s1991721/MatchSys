"""URL configuration for the AI Interview backend."""

from django.urls import include, path

urlpatterns = [
    path("api/", include("accounts.urls")),
    # 面试业务与已有账户接口共用 /api/ 前缀和当前服务的 session。
    path("api/", include("interviews.urls")),
]
