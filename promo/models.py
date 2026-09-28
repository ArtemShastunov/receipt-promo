"""Модели приложения promo."""

from django.conf import settings
from django.db import models


class Receipt(models.Model):
    """Чек покупателя, зарегистрированный в промо-акции."""

    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        ACCEPTED = "accepted", "Принят"
        REJECTED = "rejected", "Отклонён"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="receipts",
        verbose_name="Пользователь",
    )
    fn = models.CharField("ФН", max_length=16)
    fd = models.CharField("ФД", max_length=10)
    fp = models.CharField("ФП", max_length=10)
    purchase_datetime = models.DateTimeField("Дата и время покупки")
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    status = models.CharField(
        "Статус",
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reject_reason = models.TextField("Причина отказа", blank=True)
    photo = models.ImageField(
        "Фото чека",
        upload_to="receipts/%Y/%m/",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField("Дата регистрации", auto_now_add=True)

    class Meta:
        ordering = ["-purchase_datetime"]
        verbose_name = "Чек"
        verbose_name_plural = "Чеки"
        constraints = [
            models.UniqueConstraint(
                fields=["fn", "fd", "fp"],
                name="uniq_receipt_fn_fd_fp_active",
                condition=models.Q(status__in=["pending", "accepted"]),
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-purchase_datetime"]),
        ]

    def __str__(self) -> str:
        return f"{self.fn}-{self.fd}-{self.fp} ({self.amount} руб.)"
