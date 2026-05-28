from django.http import JsonResponse

from project.error_codes import ErrorCode, SUCCESS_CODE


def api_success(data=None, meta=None, status=200):
    payload = {
        "success": True,
        "code": SUCCESS_CODE,
        "message": "OK",
        "data": data,
        "meta": meta or {},
    }
    return JsonResponse(payload, status=status)


def api_error(error, message=None, status=200):
    if isinstance(error, ErrorCode):
        code = error.code
        resolved_message = message if message is not None else error.message
    else:
        code = error
        resolved_message = message
    payload = {
        "success": False,
        "code": code,
        "message": resolved_message,
        "data": None,
        "meta": {},
    }
    return JsonResponse(payload, status=status)


def api_paginated(
        items,
        page,
        page_size,
        total,
        total_pages
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
        meta=meta,
    )
