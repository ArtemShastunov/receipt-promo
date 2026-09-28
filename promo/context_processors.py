"""Контекст-процессоры приложения promo.

Функция promo_period автоматически добавляет в контекст каждого шаблона
настройки акции, чтобы в base.html можно было писать {{ PROMO_START }}
без явной передачи из каждой вьюхи.
"""

from django.conf import settings
from django.utils import timezone


def promo_period(request) -> dict:
    """Возвращает параметры промо-акции для использования в шаблонах."""
    start = timezone.localtime(settings.PROMO_START, settings.PROMO_TZ)
    end = timezone.localtime(settings.PROMO_END, settings.PROMO_TZ)
    return {
        "PROMO_START": start,
        "PROMO_END": end,
        "PROMO_MIN_AMOUNT": settings.PROMO_MIN_AMOUNT,
        "PROMO_MAX_PHOTO_MB": settings.PROMO_MAX_PHOTO_MB,
    }
