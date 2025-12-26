from django.http import JsonResponse

ERROR_CODE_MAP = {
    400: "ERR_VALIDATION",
    401: "ERR_AUTH",
    403: "ERR_FORBIDDEN",
    404: "ERR_NOT_FOUND",
    405: "ERR_METHOD_NOT_ALLOWED",
    409: "ERR_CONFLICT",
    500: "ERR_SERVER",
}


def _resolve_error_code(status, code=None):
    if code:
        return code
    return ERROR_CODE_MAP.get(status, "ERR_UNKNOWN")


def api_success(data=None, message="", code="OK", meta=None, legacy=None, status=200):
    payload = {
        "success": True,
        "code": code,
        "message": message or "",
        "data": data,
        "meta": meta or {},
    }
    return JsonResponse(payload, status=status)


def api_error(message, status=400, code=None, meta=None, legacy=None):
    payload = {
        "success": False,
        "code": _resolve_error_code(status, code),
        "message": message or "",
        "data": None,
        "meta": meta or {},
    }
    return JsonResponse(payload, status=status)


def api_paginated(
    items,
    page,
    page_size,
    total,
    total_pages,
    message="",
    code="OK",
    legacy=None,
    status=200,
):
    meta = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
    data = {"items": items}
    return api_success(
        data=data,
        message=message,
        code=code,
        meta=meta,
        status=status,
    )
