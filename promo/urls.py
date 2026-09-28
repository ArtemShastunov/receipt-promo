"""URL'ы приложения promo."""

from django.urls import path

from . import api, views


app_name = "promo"

urlpatterns = [
    path("", views.receipt_create, name="receipt_create"),
    path("cabinet/", views.cabinet, name="cabinet"),
    path("api/receipts/", api.receipts_list, name="api_receipts"),
]
