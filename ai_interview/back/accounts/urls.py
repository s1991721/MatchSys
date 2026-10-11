from django.urls import path

from .views import current_user, login, update_account


urlpatterns = [
    path("account", update_account, name="update_account"),
    path("account/", update_account),
    path("login", login, name="login"),
    path("login/", login),
    path("me", current_user, name="current_user"),
    path("me/", current_user),
]
