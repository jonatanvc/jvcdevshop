import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.handlers.catalog import build_catalog_keyboard, get_product_note, translate_note_or_original
from bot.handlers.virtual_numbers import execute_vnum_search, get_virtual_voucher_price_for_rating


class FakeResult:
    def scalar_one_or_none(self):
        return SimpleNamespace(is_vip=False, vip_expires_at=None)


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def execute(self, _statement):
        return FakeResult()


class SearchResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    def test_bunai_search_keyboard_preserves_search_pagination(self):
        keyboard = build_catalog_keyboard(
            items=[{"name": "Service", "product_id": "svc-1", "user_price": 2.0}],
            page=2,
            total_pages=3,
            filter_mode="todos",
            search_mode=True,
        )

        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, "catalog_search_page:1")
        self.assertEqual(keyboard.inline_keyboard[1][2].callback_data, "catalog_search_page:3")
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, "catalog_search_refresh:2")

    async def test_product_note_falls_back_to_original_when_translation_is_unavailable(self):
        original_note = "Redeem the code within 12 hours."
        with patch("bot.handlers.catalog.translate_text", new=AsyncMock(return_value="")):
            self.assertEqual(await translate_note_or_original(original_note, "es"), original_note)

        with patch("bot.handlers.catalog.translate_text", new=AsyncMock(side_effect=RuntimeError("offline"))):
            self.assertEqual(await translate_note_or_original(original_note, "es"), original_note)

    async def test_product_note_uses_translation_when_available(self):
        with patch("bot.handlers.catalog.translate_text", new=AsyncMock(return_value="Canjea el código en 12 horas.")):
            translated = await translate_note_or_original("Redeem the code within 12 hours.", "es")

        self.assertEqual(translated, "Canjea el código en 12 horas.")

    def test_product_note_uses_catalog_cache_when_provider_returns_no_data(self):
        cached_catalog = [{"product_id": "svc-1", "note": "Original provider note."}]
        with patch("bot.handlers.catalog.pricing_service._cached_catalog", cached_catalog):
            self.assertEqual(get_product_note(None, "svc-1"), "Original provider note.")

    def test_product_note_uses_catalog_cache_when_provider_omits_note_field(self):
        cached_catalog = [{"product_id": "svc-1", "note": "Original provider note."}]
        with patch("bot.handlers.catalog.pricing_service._cached_catalog", cached_catalog):
            self.assertEqual(get_product_note({"id": "svc-1"}, "svc-1"), "Original provider note.")

    def test_product_note_prefers_fresh_provider_data_over_cache(self):
        cached_catalog = [{"product_id": "svc-1", "note": "Old note."}]
        with patch("bot.handlers.catalog.pricing_service._cached_catalog", cached_catalog):
            self.assertEqual(get_product_note({"note": "Current note."}, "svc-1"), "Current note.")

        def test_virtual_voucher_rating_uses_stored_public_price(self):
            order = SimpleNamespace(voucher_total_price=9.99, price_usdt=3.0)

            self.assertEqual(get_virtual_voucher_price_for_rating(order, is_owner=True), 9.99)

        def test_legacy_owner_virtual_voucher_is_not_rewritten_at_cost(self):
            order = SimpleNamespace(voucher_total_price=None, price_usdt=3.0)

            self.assertIsNone(get_virtual_voucher_price_for_rating(order, is_owner=True))

        def test_non_owner_legacy_virtual_voucher_uses_paid_price(self):
            order = SimpleNamespace(voucher_total_price=None, price_usdt=4.25)

            self.assertEqual(get_virtual_voucher_price_for_rating(order, is_owner=False), 4.25)

    async def test_fivesim_search_page_uses_cached_offers(self):
        cached_offers = [{
            "country": "portugal",
            "cost_usd": 1.0,
            "rate": 95.0,
            "stock": 4,
        }]
        with (
            patch("bot.handlers.virtual_numbers.async_session", FakeSession),
            patch("bot.handlers.virtual_numbers.render_screen", new=AsyncMock()) as render,
            patch("bot.handlers.virtual_numbers.fivesim_api.get_service_offers", new=AsyncMock()) as get_offers,
        ):
            await execute_vnum_search(
                client=object(),
                user_id=123,
                service_code="whatsapp",
                query="portugal",
                page=1,
                offers=cached_offers,
            )

        get_offers.assert_not_awaited()
        render.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()