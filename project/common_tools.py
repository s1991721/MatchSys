import json
from datetime import datetime

from project.api import api_error

def parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, api_error(
            "Invalid JSON body"
        )


def parse_date(value):
    if value in (None, ""):
        return None, None
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date(), None
        except ValueError:
            return None, api_error(
                "Invalid date"
            )
    return None, api_error(
        "Invalid date"
    )
