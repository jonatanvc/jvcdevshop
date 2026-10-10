import unittest

from bot.handlers.catalog import build_catalog_keyboard, build_product_calculator_keyboard
from bot.handlers.wallet import get_movement_emoji
from bot.utils.emojis import get_service_custom_emoji_id, parse_emojis, parse_keyboard
from bot.utils.i18n import t


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


class CatalogStockCategoryEmojiTests(unittest.TestCase):
    def test_category_stock_emojis_use_the_correct_visual_ids_in_all_languages(self):
        for language in ("es", "en", "pt"):
            with self.subTest(language=language):
                available_header = parse_emojis(t("catalog_header_disponibles", language, count=1))
                out_of_stock_header = parse_emojis(t("catalog_header_agotados", language, count=1))
                available_option = parse_emojis(t("cat_opt_disponibles", language, count=1))
                out_of_stock_option = parse_emojis(t("cat_opt_agotados", language, count=1))

                self.assertIn("<emoji id=5211182849297762045>🟢</emoji>", available_header)
                self.assertIn("<emoji id=5208429100951159058>🔴</emoji>", out_of_stock_header)
                self.assertIn("<emoji id=5211182849297762045>🟢</emoji>", available_option)
                self.assertIn("<emoji id=5208429100951159058>🔴</emoji>", out_of_stock_option)


class ProductNoteButtonTests(unittest.TestCase):
    def test_note_button_is_available_only_when_product_has_a_note(self):
        for has_note in (True, False):
            with self.subTest(has_note=has_note):
                keyboard = build_product_calculator_keyboard(
                    product_id="product-1",
                    filter_mode="disponibles",
                    page=1,
                    qty=1,
                    can_buy=True,
                    has_stock=True,
                    is_alert_active=False,
                    total_price=2.0,
                    bot_username="shop_bot",
                    has_note=has_note,
                    lang="es",
                    stock_count=5,
                )
                buttons = [button for row in keyboard.inline_keyboard for button in row]
                note_buttons = [button for button in buttons if button.callback_data.startswith("pnote:")]

                self.assertEqual(bool(note_buttons), has_note)
                if has_note:
                    self.assertEqual(note_buttons[0].text, t("btn_view_note", "es"))


if __name__ == "__main__":
    unittest.main()