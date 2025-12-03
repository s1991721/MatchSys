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
    limit_str = request.GET.get("limit", "20")

    try:
        limit = max(1, min(50, int(limit_str)))
    except ValueError:
        limit = 20

    target_date = _parse_date(date_str)
    query = keyword or ""

    try:
        msgs = tool.fetch_messages(
            query=query,
            limit=limit,
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

    return JsonResponse({"items": items})
