"""Тесты формы регистрации чека."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from promo.forms import ReceiptForm
from promo.models import Receipt


User = get_user_model()


class ReceiptFormTests(TestCase):
    """Проверяем серверную валидацию ReceiptForm."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="u", password="p")

    def _valid_payload(self, **overrides) -> dict:
        """Собирает корректный payload с возможностью переопределить поля."""
        # Берём середину периода акции, чтобы тест не зависел от границ
        mid = settings.PROMO_START + (settings.PROMO_END - settings.PROMO_START) / 2
        payload = {
            "fn": "1234567890123456",
            "fd": "12345",
            "fp": "67890",
            "purchase_datetime": mid.astimezone(settings.PROMO_TZ).strftime("%Y-%m-%dT%H:%M"),
            "amount": "1500.00",
        }
        payload.update(overrides)
        return payload

    def test_valid_form(self):
        form = ReceiptForm(data=self._valid_payload(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_date_before_promo_rejected(self):
        before = settings.PROMO_START - timedelta(days=1)
        data = self._valid_payload(
            purchase_datetime=before.astimezone(settings.PROMO_TZ).strftime("%Y-%m-%dT%H:%M")
        )
        form = ReceiptForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("purchase_datetime", form.errors)

    def test_date_after_promo_rejected(self):
        after = settings.PROMO_END + timedelta(days=1)
        data = self._valid_payload(
            purchase_datetime=after.astimezone(settings.PROMO_TZ).strftime("%Y-%m-%dT%H:%M")
        )
        form = ReceiptForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("purchase_datetime", form.errors)

    def test_amount_below_min_rejected(self):
        data = self._valid_payload(amount="999.99")
        form = ReceiptForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_amount_equal_min_accepted(self):
        data = self._valid_payload(amount=str(settings.PROMO_MIN_AMOUNT))
        form = ReceiptForm(data=data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_fn_must_be_16_digits(self):
        for bad_fn in ["123", "1" * 17, "abcdefghijklmnop", "123456789012345a"]:
            with self.subTest(fn=bad_fn):
                form = ReceiptForm(data=self._valid_payload(fn=bad_fn), user=self.user)
                self.assertFalse(form.is_valid())
                self.assertIn("fn", form.errors)

    def test_fd_and_fp_digits_only(self):
        form = ReceiptForm(data=self._valid_payload(fd="abc"), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("fd", form.errors)

        form = ReceiptForm(data=self._valid_payload(fp="xyz"), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("fp", form.errors)

    def test_duplicate_pending_rejected(self):
        Receipt.objects.create(
            user=self.user,
            fn="1234567890123456", fd="12345", fp="67890",
            amount=Decimal("1500.00"),
            purchase_datetime=settings.PROMO_START + timedelta(days=1),
            status=Receipt.Status.PENDING,
        )
        form = ReceiptForm(data=self._valid_payload(), user=self.user)
        self.assertFalse(form.is_valid())
        # Ошибка общей валидации (связка полей), попадает в __all__
        self.assertIn("__all__", form.errors)

    def test_duplicate_accepted_rejected(self):
        Receipt.objects.create(
            user=self.user,
            fn="1234567890123456", fd="12345", fp="67890",
            amount=Decimal("1500.00"),
            purchase_datetime=settings.PROMO_START + timedelta(days=1),
            status=Receipt.Status.ACCEPTED,
        )
        form = ReceiptForm(data=self._valid_payload(), user=self.user)
        self.assertFalse(form.is_valid())

    def test_rejected_can_be_resubmitted(self):
        """Отклонённый чек не блокирует повторную подачу."""
        Receipt.objects.create(
            user=self.user,
            fn="1234567890123456", fd="12345", fp="67890",
            amount=Decimal("1500.00"),
            purchase_datetime=settings.PROMO_START + timedelta(days=1),
            status=Receipt.Status.REJECTED,
            reject_reason="Плохое фото",
        )
        form = ReceiptForm(data=self._valid_payload(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_save_sets_pending_status_and_user(self):
        form = ReceiptForm(data=self._valid_payload(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        receipt = form.save()
        self.assertEqual(receipt.status, Receipt.Status.PENDING)
        self.assertEqual(receipt.user, self.user)
