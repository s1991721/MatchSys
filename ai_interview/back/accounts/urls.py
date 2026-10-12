from django.urls import path

from .views import csrf_token, current_user, login, logout, update_account

urlpatterns = [
    # CSRF 获取入口不要求登录；退出登录仍受 CSRF 中间件保护。
    path("csrf", csrf_token, name="csrf_token"),
    path("csrf/", csrf_token),
    path("logout", logout, name="logout"),
    path("logout/", logout),
    path("account", update_account, name="update_account"),
    path("account/", update_account),
    path("login", login, name="login"),
    path("login/", login),
    path("me", current_user, name="current_user"),
    path("me/", current_user),
]
