import unittest

from bot.handlers.catalog import build_catalog_keyboard
from bot.utils.emojis import get_service_custom_emoji_id, parse_keyboard


class PortugalCatalogEmojiTests(unittest.TestCase):
    def test_portugal_service_names_match_exact_and_variant_names(self):
        cases = (
            ("WhatsApp Portugal", "5334998226636390258"),
            ("WhatsApp - Portugal (5 min)", "5334998226636390258"),
            ("Telegram Portugal", "5330237710655306682"),
            ("Telegram_Portugal OTP", "5330237710655306682"),
        )

        for name, expected_id in cases:
            with self.subTest(name=name):
                self.assertEqual(get_service_custom_emoji_id(name), expected_id)

    def test_catalog_button_keeps_portugal_custom_emoji_through_parser(self):
        cases = (
            ("WhatsApp Portugal", "5334998226636390258"),
            ("Telegram Portugal", "5330237710655306682"),
        )

        for name, expected_id in cases:
            with self.subTest(name=name):
                keyboard = build_catalog_keyboard(
                    [{"name": name, "product_id": "portugal-test", "user_price": 1.0}],
                    page=1,
                    total_pages=1,
                    filter_mode="todos",
                )
                parsed = parse_keyboard(keyboard)
                self.assertEqual(parsed.inline_keyboard[0][0].icon_custom_emoji_id, expected_id)


if __name__ == "__main__":
    unittest.main()