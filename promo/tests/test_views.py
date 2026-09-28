"""Тесты views приложения promo."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from promo.models import Receipt


User = get_user_model()


class ReceiptCreateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")
        self.client.force_login(self.user)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("promo:receipt_create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_renders_form(self):
        response = self.client.get(reverse("promo:receipt_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Регистрация чека")

    def test_post_redirects_to_cabinet(self):
        """Обычный POST (не AJAX) — редирект в кабинет."""
        from django.conf import settings
        from datetime import timedelta
        mid = settings.PROMO_START + timedelta(days=1)

        response = self.client.post(reverse("promo:receipt_create"), {
            "fn": "1234567890123456",
            "fd": "12345",
            "fp": "67890",
            "purchase_datetime": mid.astimezone(settings.PROMO_TZ).strftime("%Y-%m-%dT%H:%M"),
            "amount": "1500.00",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("promo:cabinet"))

    def test_ajax_post_returns_json_201(self):
        from django.conf import settings
        from datetime import timedelta
        mid = settings.PROMO_START + timedelta(days=1)

        response = self.client.post(
            reverse("promo:receipt_create"),
            {
                "fn": "1234567890123456",
                "fd": "12345",
                "fp": "67890",
                "purchase_datetime": mid.astimezone(settings.PROMO_TZ).strftime("%Y-%m-%dT%H:%M"),
                "amount": "1500.00",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["receipt"]["status"], "pending")

    def test_ajax_post_returns_errors_json_400(self):
        from django.conf import settings
        from datetime import timedelta
        mid = settings.PROMO_START + timedelta(days=1)

        response = self.client.post(
            reverse("promo:receipt_create"),
            {
                "fn": "123",  # невалидно
                "fd": "12345",
                "fp": "67890",
                "purchase_datetime": mid.astimezone(settings.PROMO_TZ).strftime("%Y-%m-%dT%H:%M"),
                "amount": "1500.00",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertIn("fn", data["errors"])


class CabinetViewTests(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user(username="u1", password="p")
        self.u2 = User.objects.create_user(username="u2", password="p")

        # 15 чеков у u1, 5 у u2 — проверим пагинацию и изоляцию
        for i in range(15):
            Receipt.objects.create(
                user=self.u1,
                fn=f"{i:016d}", fd=str(i), fp=str(i),
                amount=Decimal("1500.00"),
                purchase_datetime="2026-10-01T10:00:00+03:00",
            )
        for i in range(5):
            Receipt.objects.create(
                user=self.u2,
                fn=f"9{i:015d}", fd=str(i), fp=str(i),
                amount=Decimal("2000.00"),
                purchase_datetime="2026-10-01T10:00:00+03:00",
            )

    def test_login_required(self):
        response = self.client.get(reverse("promo:cabinet"))
        self.assertEqual(response.status_code, 302)

    def test_pagination_10_per_page(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("promo:cabinet"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page"].object_list), 10)

    def test_second_page(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("promo:cabinet") + "?page=2")
        self.assertEqual(len(response.context["page"].object_list), 5)

    def test_only_own_receipts(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("promo:cabinet"))
        for receipt in response.context["page"].object_list:
            self.assertEqual(receipt.user_id, self.u1.id)
