import os
import sys

from django.apps import AppConfig
from django.conf import settings as django_settings


class SettingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "settings"

    def ready(self):
        enabled = os.getenv("ENABLE_SCHEDULER", "true").lower() in ("1", "true", "yes")
        if not enabled:
            return
        if any(
            command in sys.argv
            for command in (
                "migrate",
                "makemigrations",
                "collectstatic",
                "shell",
                "createsuperuser",
            )
        ):
            return
        if (
            "runserver" in sys.argv
            and django_settings.DEBUG
            and os.environ.get("RUN_MAIN") != "true"
        ):
            return
        from .task_scheduler import start_scheduler

        start_scheduler()
