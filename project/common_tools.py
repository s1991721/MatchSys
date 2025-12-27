import json
from project.api import api_error

def parse_json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        return json.loads(raw or "{}"), None
    except json.JSONDecodeError:
        return None, api_error(
            "Invalid JSON body",
            status=400,
        )