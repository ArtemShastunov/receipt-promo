"""JSON API приложения promo."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Receipt


@login_required
@require_GET
def receipts_list(request):
    """GET /api/receipts/ — чеки текущего пользователя.

    Важно: queryset фильтруется ТОЛЬКО по request.user. Никакие query-
    параметры (?user_id=, ?all=1) не расширяют выборку — их просто нет
    в коде.
    """
    qs = (
        Receipt.objects
        .filter(user=request.user)
        .values(
            "id", "fn", "fd", "fp",
            "amount", "status", "reject_reason",
            "purchase_datetime", "created_at",
        )
        .order_by("-purchase_datetime")
    )

    results = [
        {
            "id": row["id"],
            "fn": row["fn"],
            "fd": row["fd"],
            "fp": row["fp"],
            "amount": str(row["amount"]),
            "status": row["status"],
            "status_display": Receipt.Status(row["status"]).label,
            "reject_reason": row["reject_reason"],
            "purchase_datetime": row["purchase_datetime"].isoformat(),
            "created_at": row["created_at"].isoformat(),
        }
        for row in qs
    ]

    return JsonResponse(
        {"count": len(results), "results": results},
        json_dumps_params={"ensure_ascii": False},
    )
