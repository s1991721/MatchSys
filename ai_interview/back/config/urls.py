"""URL configuration for the AI Interview backend."""

from django.urls import include, path


urlpatterns = [
    path("api/", include("accounts.urls")),
]
