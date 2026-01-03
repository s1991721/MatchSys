from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from project.api import api_error, api_success
from project.common_tools import parse_json_body, require_login
from settings.models import SysSettings

SECTION_DEFAULTS = {
    "business-email": {
        "auth_filename": "",
        "auth_json": "",
    },
    "match": {
        "cycle_days": 14,
    },
    "ai": {
        "mode": "local",
        "local_model": "",
        "cloud_model": "",
        "cloud_api_key": "",
    },
    "backup": {
        "host": "",
        "port": "",
        "database": "",
        "user": "",
        "password": "",
        "ssl_mode": "require",
        "note": "",
    },
    "sendin": [],
    "tasks": [],
}


def _get_setting(section):
    return SysSettings.objects.filter(name=section, deleted_at__isnull=True).first()


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def sys_settings_section_api(request, section):
    login_id, error = require_login(request)
    if error:
        return error

    if section not in SECTION_DEFAULTS:
        return api_error("Unknown settings section", status=404)

    if request.method == "GET":
        record = _get_setting(section)
        settings_payload = record.settings if record else SECTION_DEFAULTS[section]
        return api_success(data={"name": section, "settings": settings_payload})

    payload, error = parse_json_body(request)
    if error:
        return error
    if "settings" not in payload:
        return api_error("Missing field: settings")

    settings_payload = payload.get("settings")
    record = _get_setting(section)
    if record:
        record.settings = settings_payload
        record.updated_by = login_id
    else:
        record = SysSettings(
            name=section,
            settings=settings_payload,
            created_by=login_id,
        )
    record.save()
    return api_success(data={"name": section, "settings": record.settings})
