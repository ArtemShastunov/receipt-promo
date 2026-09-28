"""Настройка админки для модератора."""

import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone

from .models import Receipt


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    """Интерфейс модератора: список чеков, смена статуса, CSV-экспорт."""

    list_display = (
        "id", "user", "fn", "fd", "fp",
        "purchase_datetime", "amount", "status", "created_at",
    )
    list_filter = ("status", "created_at", "purchase_datetime")
    search_fields = ("fn", "fd", "fp", "user__username", "user__email")
    list_select_related = ("user",)
    date_hierarchy = "purchase_datetime"

    # Реквизиты чека менять нельзя: это «сырые» данные от пользователя.
    # Модератор меняет только статус и причину отказа.
    readonly_fields = (
        "user", "fn", "fd", "fp", "purchase_datetime", "amount",
        "photo", "created_at",
    )

    fieldsets = (
        ("Реквизиты чека", {
            "fields": ("user", "fn", "fd", "fp", "purchase_datetime", "amount", "photo"),
        }),
        ("Модерация", {
            "fields": ("status", "reject_reason"),
            "description": "При отказе обязательно укажите причину — её увидит пользователь.",
        }),
        ("Служебное", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )

    actions = ["export_accepted_csv"]

    @admin.action(description="Выгрузить принятые чеки в CSV")
    def export_accepted_csv(self, request, queryset):
        accepted = queryset.filter(status=Receipt.Status.ACCEPTED)
        if not accepted.exists():
            self.message_user(
                request,
                "Среди выбранных чеков нет принятых.",
                level=messages.WARNING,
            )
            return

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        filename = f"accepted_receipts_{timezone.now():%Y%m%d_%H%M}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # BOM, чтобы Excel понял UTF-8 и не показывал кракозябры
        response.write("\ufeff")

        writer = csv.writer(response)
        writer.writerow(
            ["id", "user", "ФН", "ФД", "ФП", "Дата покупки", "Сумма", "Статус", "Создан"]
        )
        current_tz = timezone.get_current_timezone()
        for receipt in accepted.select_related("user"):
            writer.writerow([
                receipt.id,
                receipt.user.username,
                receipt.fn,
                receipt.fd,
                receipt.fp,
                receipt.purchase_datetime.astimezone(current_tz).strftime("%Y-%m-%d %H:%M"),
                receipt.amount,
                receipt.get_status_display(),
                receipt.created_at.astimezone(current_tz).strftime("%Y-%m-%d %H:%M"),
            ])

    def save_model(self, request, obj, form, change):
        # Если статус не «отклонён» — причину отказа очищаем.
        # Иначе модератор отклонил, потом передумал, а причина осталась висеть.
        if obj.status != Receipt.Status.REJECTED:
            obj.reject_reason = ""
        super().save_model(request, obj, form, change)
