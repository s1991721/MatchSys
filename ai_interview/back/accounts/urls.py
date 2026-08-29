from django.urls import path

from .views import current_user, login


urlpatterns = [
    path("login", login, name="login"),
    path("login/", login),
    path("me", current_user, name="current_user"),
    path("me/", current_user),
]
