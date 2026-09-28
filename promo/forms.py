"""Формы приложения promo."""

from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Receipt
from .services import is_within_promo, localize_user_datetime


class ReceiptForm(forms.ModelForm):
    """Форма регистрации чека.

    Валидация серверная — единственно надёжная. Клиентский JS только
    улучшает UX, но не заменяет эти проверки.
    """

    class Meta:
        model = Receipt
        fields = ["fn", "fd", "fp", "purchase_datetime", "amount", "photo"]
        widgets = {
            "purchase_datetime": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Единый класс для всех полей — CSS-стилизация
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " input").strip()

        # datetime-local отдаёт строку без секунд; явно задаём допустимые форматы
        self.fields["purchase_datetime"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ]

    # ---------- Полевые валидаторы ----------

    def clean_fn(self) -> str:
        fn = (self.cleaned_data["fn"] or "").strip()
        if not fn.isdigit() or len(fn) != 16:
            raise ValidationError("ФН — ровно 16 цифр.")
        return fn

    def clean_fd(self) -> str:
        fd = (self.cleaned_data["fd"] or "").strip()
        if not fd.isdigit() or not (1 <= len(fd) <= 10):
            raise ValidationError("ФД — только цифры, до 10 знаков.")
        return fd

    def clean_fp(self) -> str:
        fp = (self.cleaned_data["fp"] or "").strip()
        if not fp.isdigit() or not (1 <= len(fp) <= 10):
            raise ValidationError("ФП — только цифры, до 10 знаков.")
        return fp

    def clean_purchase_datetime(self):
        dt = self.cleaned_data["purchase_datetime"]
        dt = localize_user_datetime(dt)
        if not is_within_promo(dt):
            start = timezone.localtime(settings.PROMO_START, settings.PROMO_TZ)
            end = timezone.localtime(settings.PROMO_END, settings.PROMO_TZ)
            raise ValidationError(
                "Дата покупки должна входить в период акции: "
                f"{start:%d.%m.%Y %H:%M} — {end:%d.%m.%Y %H:%M} (МСК)."
            )
        return dt

    def clean_amount(self) -> Decimal:
        amount: Decimal = self.cleaned_data["amount"]
        if amount < settings.PROMO_MIN_AMOUNT:
            raise ValidationError(
                f"Сумма чека должна быть не меньше {settings.PROMO_MIN_AMOUNT:.0f} руб."
            )
        return amount

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo:
            return photo

        max_bytes = settings.PROMO_MAX_PHOTO_MB * 1024 * 1024
        if photo.size > max_bytes:
            raise ValidationError(f"Файл больше {settings.PROMO_MAX_PHOTO_MB} МБ.")

        allowed = {"image/jpeg", "image/png", "image/webp"}
        content_type = getattr(photo, "content_type", None)
        if content_type and content_type not in allowed:
            raise ValidationError("Допустимы только JPG, PNG или WEBP.")

        return photo

    # ---------- Межполевая валидация ----------

    def clean(self):
        cleaned = super().clean()
        fn = cleaned.get("fn")
        fd = cleaned.get("fd")
        fp = cleaned.get("fp")

        if fn and fd and fp:
            # Уникальность ФН+ФД+ФП среди «живых» чеков.
            # Отклонённые не учитываем — пользователь может подать чек
            # заново после исправления.
            qs = (
                Receipt.objects
                .filter(fn=fn, fd=fd, fp=fp)
                .exclude(status=Receipt.Status.REJECTED)
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    {"__all__": "Чек с такими ФН, ФД и ФП уже зарегистрирован."}
                )
        return cleaned

    def save(self, commit: bool = True) -> Receipt:
        obj: Receipt = super().save(commit=False)
        if self.user and not obj.pk:
            obj.user = self.user
        if not obj.pk:
            obj.status = Receipt.Status.PENDING
        if commit:
            obj.save()
        return obj
