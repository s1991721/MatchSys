from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

from .gmailTool import GmailTool

tool = GmailTool()  # 复用单例，避免重复 OAuth


def _parse_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


@csrf_exempt
@require_GET
def messages(request):
    keyword = request.GET.get("keyword", "").strip()
    date_str = request.GET.get("date", "").strip()
    page_str = request.GET.get("page", "1").strip()
    page_size_str = request.GET.get("page_size", "").strip()
    limit_str = request.GET.get("limit", "").strip()

    try:
        parsed_page = int(page_str)
        page = parsed_page if parsed_page > 0 else 1
    except ValueError:
        page = 1

    try:
        parsed_size = int(page_size_str or limit_str or 20)
        page_size = min(max(parsed_size, 1), 100)
    except ValueError:
        page_size = 20

    target_date = _parse_date(date_str)
    query = keyword or ""

    try:
        msgs, has_next = tool.fetch_messages(
            query=query,
            page=page,
            page_size=page_size,
            start_date=target_date,
            end_date=target_date,
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    items = []
    for m in msgs:
        items.append({
            "id": m.get("id") or "",
            "title": m.get("subject") or "(无标题)",
            "desc": m.get("from") or "",
            "detail": m.get("body") or "",
            "date": m.get("date") or "",
        })

    return JsonResponse({
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
    })
