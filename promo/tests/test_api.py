"""Тесты JSON API."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from promo.models import Receipt


User = get_user_model()


class ReceiptsApiTests(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user(username="u1", password="p")
        self.u2 = User.objects.create_user(username="u2", password="p")

        Receipt.objects.create(
            user=self.u1,
            fn="1" * 16, fd="1", fp="1",
            amount=Decimal("1500.00"),
            purchase_datetime="2026-10-01T10:00:00+03:00",
        )
        Receipt.objects.create(
            user=self.u2,
            fn="2" * 16, fd="2", fp="2",
            amount=Decimal("2000.00"),
            purchase_datetime="2026-10-01T10:00:00+03:00",
        )

    def test_login_required(self):
        response = self.client.get(reverse("promo:api_receipts"))
        self.assertEqual(response.status_code, 302)

    def test_returns_only_own_receipts(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("promo:api_receipts"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["fn"], "1" * 16)

    def test_query_params_dont_leak_other_users(self):
        """Никакие query-параметры не позволяют увидеть чужие чеки."""
        self.client.force_login(self.u1)
        for params in [
            {"user": self.u2.id},
            {"user_id": self.u2.id},
            {"all": "1"},
            {"all": "true"},
            {"id": self.u2.id},
            {"username": "u2"},
        ]:
            with self.subTest(params=params):
                response = self.client.get(reverse("promo:api_receipts"), params)
                data = response.json()
                self.assertEqual(data["count"], 1)
                self.assertEqual(data["results"][0]["fn"], "1" * 16)

    def test_post_not_allowed(self):
        self.client.force_login(self.u1)
        response = self.client.post(reverse("promo:api_receipts"))
        self.assertEqual(response.status_code, 405)

    def test_response_shape(self):
        self.client.force_login(self.u1)
        response = self.client.get(reverse("promo:api_receipts"))
        data = response.json()
        self.assertIn("count", data)
        self.assertIn("results", data)
        receipt = data["results"][0]
        for key in ("id", "fn", "fd", "fp", "amount", "status",
                    "status_display", "reject_reason",
                    "purchase_datetime", "created_at"):
            self.assertIn(key, receipt)
