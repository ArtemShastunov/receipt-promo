"""Утилиты приложения promo.

Здесь живёт бизнес-логика, не привязанная к Django ORM:
- парсинг строки из QR-кода чека,
- интерпретация пользовательского времени в часовом поясе акции,
- проверка «попадает ли дата в период акции».
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs

from django.conf import settings
from django.utils import timezone


def parse_qr(raw: str) -> dict:
    """Разбирает строку из QR-кода чека.

    Поддерживаемые ключи (по стандарту ФНС):
      t  — дата и время покупки в формате YYYYMMDDTHHMM[SS]
      s  — сумма в рублях (может быть с точкой или запятой)
      fn — ФН (16 цифр)
      i  — ФД (номер фискального документа)
      fp — ФП (фискальный признак)

    Возвращает dict с ключами: fn, fd, fp, amount (str | None),
    purchase_datetime (aware datetime | None).
    Кидает ValueError, если строка совсем не парсится.
    """
    if not raw or not raw.strip():
        raise ValueError("Пустая строка")

    raw = raw.strip()

    # Некоторые QR приходят как URL с параметрами (https://...?t=...&s=...),
    # другие — как голая query-string (t=...&s=...). Отрезаем всё до '?'.
    qs = raw.split("?", 1)[1] if raw.startswith(("http://", "https://")) and "?" in raw else raw

    parsed = parse_qs(qs, keep_blank_values=False)

    def first(key: str) -> str | None:
        values = parsed.get(key)
        return values[0] if values else None

    result: dict = {
        "fn": first("fn"),
        "fd": first("i") or first("fd"),
        "fp": first("fp"),
        "amount": None,
        "purchase_datetime": None,
    }

    amount_raw = first("s")
    if amount_raw:
        try:
            result["amount"] = str(Decimal(amount_raw.replace(",", ".")))
        except InvalidOperation as exc:
            raise ValueError("Не удалось разобрать сумму из QR") from exc

    datetime_raw = first("t")
    if datetime_raw:
        for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
            try:
                naive = datetime.strptime(datetime_raw, fmt)
            except ValueError:
                continue
            # QR приходит без часового пояса. Трактуем как локальное время
            # акции (Europe/Moscow по умолчанию).
            result["purchase_datetime"] = timezone.make_aware(naive, settings.PROMO_TZ)
            break

    return result


def localize_user_datetime(dt: datetime) -> datetime:
    """Приводит дату, введённую пользователем, к aware в часовом поясе акции.

    Пользователь вводит через datetime-local время БЕЗ пояса. Считаем,
    что он имел в виду время акции (PROMO_TZ), и делаем его aware.
    Если дата уже aware — возвращаем без изменений.
    """
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, settings.PROMO_TZ)
    return dt


def is_within_promo(dt: datetime) -> bool:
    """Проверяет, попадает ли дата в период акции.

    Границы включительно с обеих сторон: start <= dt <= end.
    Оба аргумента — aware datetime. settings.PROMO_START / PROMO_END
    тоже aware (мы их парсим из ISO с offset'ом).
    """
    return settings.PROMO_START <= dt <= settings.PROMO_END
