"""Views приложения promo."""

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ReceiptForm
from .models import Receipt


PAGE_SIZE = 10


def _is_ajax(request) -> bool:
    """Определяет, пришёл ли запрос через fetch (наш JS)."""
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


@login_required
@require_http_methods(["GET", "POST"])
def receipt_create(request):
    """Форма регистрации чека.

    GET  — показать пустую форму.
    POST — провалидировать и сохранить. Для AJAX-запросов отвечаем JSON'ом
    (успех или список ошибок по полям), для обычных — редиректим в кабинет.
    """
    if request.method == "POST":
        form = ReceiptForm(request.POST, request.FILES, user=request.user)

        if form.is_valid():
            receipt = form.save()
            if _is_ajax(request):
                return JsonResponse(
                    {
                        "ok": True,
                        "message": "Чек принят и отправлен на проверку.",
                        "receipt": {
                            "id": receipt.id,
                            "fn": receipt.fn,
                            "fd": receipt.fd,
                            "fp": receipt.fp,
                            "amount": str(receipt.amount),
                            "status": receipt.status,
                            "status_display": receipt.get_status_display(),
                            "purchase_datetime": receipt.purchase_datetime.isoformat(),
                        },
                    },
                    status=201,
                )
            return redirect("promo:cabinet")

        if _is_ajax(request):
            return JsonResponse(
                {"ok": False, "errors": form.errors.get_json_data()},
                status=400,
            )
    else:
        form = ReceiptForm(user=request.user)

    return render(request, "promo/receipt_form.html", {"form": form})


@login_required
def cabinet(request):
    """Личный кабинет: список чеков текущего пользователя, пагинация по 10."""
    qs = (
        Receipt.objects
        .filter(user=request.user)
        .only(
            "id",
            "purchase_datetime",
            "amount",
            "status",
            "reject_reason",
            "created_at",
        )
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "promo/cabinet.html",
        {"page": page, "paginator": paginator},
    )
