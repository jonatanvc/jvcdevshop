import unittest

from bot.handlers.catalog import build_catalog_keyboard
from bot.handlers.wallet import get_movement_emoji
from bot.utils.emojis import get_service_custom_emoji_id, parse_emojis, parse_keyboard


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


class StatusEmojiMappingTests(unittest.TestCase):
    def test_wallet_credits_use_green_and_debits_use_red_premium_ids(self):
        credit = parse_emojis(get_movement_emoji(True))
        debit = parse_emojis(get_movement_emoji(False))

        self.assertIn("<emoji id=5208429100951159058>🟢</emoji>", credit)
        self.assertIn("<emoji id=5211182849297762045>🔴</emoji>", debit)

    def test_negative_symbols_do_not_reuse_the_green_dot_custom_emoji(self):
        parsed = parse_emojis("❌ ⛔ 🚫")

        self.assertEqual(parsed, "❌ ⛔ 🚫")


if __name__ == "__main__":
    unittest.main()