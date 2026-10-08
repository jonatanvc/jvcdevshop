from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from bot.handlers.checkout import has_sufficient_stock, is_definitively_rejected
from bot.services.pricing import pricing_service
from bot.services.promos import promo_service
from bot.config import settings


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeSession:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, _statement):
        return self.results.pop(0) if self.results else FakeResult([])


class CheckoutRegressionTests(unittest.TestCase):
    def test_rejects_purchase_when_stock_is_empty_or_insufficient(self):
        self.assertFalse(has_sufficient_stock(0, 1, False))
        self.assertFalse(has_sufficient_stock(2, 3, False))

    def test_accepts_exact_stock_and_infinite_stock(self):
        self.assertTrue(has_sufficient_stock(3, 3, False))
        self.assertTrue(has_sufficient_stock(0, 50, True))

    def test_only_definitive_client_errors_are_refunded(self):
        self.assertTrue(is_definitively_rejected(400))
        for status_code in (408, 409, 425, 429, 500, None):
            with self.subTest(status_code=status_code):
                self.assertFalse(is_definitively_rejected(status_code))


class CatalogAndPromotionRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_catalog_separates_out_of_stock_products(self):
        products = [
            {"id": "empty", "name": "Empty", "price": 1, "stock_count": 0},
            {"id": "available", "name": "Available", "price": 1, "stock_count": 2},
        ]
        pricing_service.invalidate_cache()
        with patch("bot.services.pricing.bunai_api.get_products", new=AsyncMock(return_value=products)):
            available = await pricing_service.get_processed_catalog(FakeSession([FakeResult([])]), "disponibles", True)
            out_of_stock = await pricing_service.get_processed_catalog(FakeSession([]), "agotados", True)

        self.assertEqual([item["product_id"] for item in available], ["available"])
        self.assertEqual([item["product_id"] for item in out_of_stock], ["empty"])
        pricing_service.invalidate_cache()

    async def test_fixed_coupon_discount_never_exceeds_cart(self):
        coupon = SimpleNamespace(
            id=7, is_active=True, expires_at=None, max_uses=0, current_uses=0,
            min_purchase=0, user_limit=1, discount_type="fixed", discount_value=10
        )
        session = FakeSession([FakeResult(coupon), FakeResult(0)])

        valid, _message, _coupon, discount = await promo_service.validate_coupon(
            session, "save", 123, 4.25
        )

        self.assertTrue(valid)
        self.assertEqual(discount, 4.25)

    async def test_coupon_rejects_expired_and_exhausted_codes(self):
        expired = SimpleNamespace(
            id=1, is_active=True, expires_at=datetime.now() - timedelta(seconds=1),
            max_uses=0, current_uses=0, min_purchase=0, user_limit=1
        )
        exhausted = SimpleNamespace(
            id=2, is_active=True, expires_at=None, max_uses=2, current_uses=2,
            min_purchase=0, user_limit=1
        )
        for coupon in (expired, exhausted):
            with self.subTest(coupon_id=coupon.id):
                valid, _message, _coupon, discount = await promo_service.validate_coupon(
                    FakeSession([FakeResult(coupon)]), "SAVE", 123, 20
                )
                self.assertFalse(valid)
                self.assertEqual(discount, 0.0)

    def test_vip_price_uses_configured_discount(self):
        public_price = 10.0
        expected = round(public_price * (1 - settings.VIP_DISCOUNT_PERCENT / 100), 2)
        self.assertEqual(pricing_service.calculate_vip_price(public_price), expected)


if __name__ == "__main__":
    unittest.main()