import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.handlers.catalog import build_catalog_keyboard
from bot.handlers.virtual_numbers import execute_vnum_search


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