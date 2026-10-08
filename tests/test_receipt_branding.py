import re
import unittest

from bot.services.vouchers import VoucherService
from bot.utils.emojis import (
    PREMIUM_RECEIPT_EMOJI_IDS,
    PREMIUM_RECEIPT_LOGO,
    parse_emojis,
    receipt_logo_for_user,
)


class ReceiptBrandingTests(unittest.IsolatedAsyncioTestCase):
    def test_logo_keeps_the_requested_custom_emoji_order(self):
        self.assertEqual(PREMIUM_RECEIPT_EMOJI_IDS, (
            "5136410999137502847",
            "5136496292893034692",
            "5138836891155564408",
            "5138839944877311987",
            "5136498470441453359",
        ))
        actual_ids = re.findall(r"<emoji id=(\d+)>", PREMIUM_RECEIPT_LOGO)
        self.assertEqual(actual_ids, list(PREMIUM_RECEIPT_EMOJI_IDS))
        self.assertEqual(parse_emojis(PREMIUM_RECEIPT_LOGO), PREMIUM_RECEIPT_LOGO)

    def test_user_logo_is_hidden_for_vips_and_owner(self):
        self.assertEqual(receipt_logo_for_user(is_vip=True), "")
        self.assertEqual(receipt_logo_for_user(is_vip=False, is_owner=True), "")
        self.assertEqual(receipt_logo_for_user(is_vip=False), PREMIUM_RECEIPT_LOGO)

    def test_parser_redacts_provider_names_inside_html(self):
        sanitized = parse_emojis(
            "Error de BunaiStore y Bunai Store: <code>https://api.bunaistore.shop/v1 "
            "5SIM.net, 5 SIM y https://www.5sim.net</code>"
        )

        self.assertNotRegex(sanitized.lower(), r"bunai\s*store|5\s*sim")
        self.assertGreaterEqual(sanitized.count("proveedor externo"), 6)

    def test_public_vouchers_end_with_the_premium_logo(self):
        service = VoucherService()
        product_receipt = service._format_product_voucher_text(
            order_id=5,
            product_name="Test service",
            qty=1,
            total_price=2.5,
            user_id=123,
            username="buyer",
            first_name="Buyer",
            now_str="2026-10-08 12:00:00",
        )
        virtual_receipt = service._format_virtual_number_voucher_text(
            order_id=6,
            service_name="whatsapp",
            country_code="usa",
            phone="+15555550100",
            price_usdt=1.5,
            user_id=123,
            username="buyer",
            first_name="Buyer",
            now_str="2026-10-08 12:00:00",
        )

        self.assertTrue(product_receipt.endswith(PREMIUM_RECEIPT_LOGO))
        self.assertTrue(virtual_receipt.endswith(PREMIUM_RECEIPT_LOGO))

    async def test_published_voucher_sends_all_premium_custom_emoji_ids(self):
        from unittest.mock import AsyncMock, Mock

        service = VoucherService()
        service.channel_id = -100123
        service._get_bot_username = AsyncMock(return_value="shop_bot")
        client = Mock()
        client.send_message = AsyncMock(return_value=Mock(id=87))

        message_id = await service.publish_product_voucher(
            client=client,
            order_id=5,
            product_name="Test service",
            qty=1,
            total_price=2.5,
            user_id=123,
            username="buyer",
            first_name="Buyer",
        )

        self.assertEqual(message_id, 87)
        sent_text = client.send_message.await_args.kwargs["text"]
        sent_ids = re.findall(r"<emoji id=(\d+)>❗</emoji>", sent_text)
        self.assertEqual(sent_ids, list(PREMIUM_RECEIPT_EMOJI_IDS))
        self.assertEqual(client.send_message.await_args.kwargs["chat_id"], -100123)

    async def test_published_virtual_voucher_sends_all_premium_custom_emoji_ids(self):
        from unittest.mock import AsyncMock, Mock

        service = VoucherService()
        service.channel_id = -100123
        service._get_bot_username = AsyncMock(return_value="shop_bot")
        client = Mock()
        client.send_message = AsyncMock(return_value=Mock(id=88))

        message_id = await service.publish_virtual_number_voucher(
            client=client,
            order_id=6,
            service_name="whatsapp",
            country_code="usa",
            phone="+15555550100",
            price_usdt=1.5,
            user_id=123,
            username="buyer",
            first_name="Buyer",
        )

        self.assertEqual(message_id, 88)
        sent_text = client.send_message.await_args.kwargs["text"]
        sent_ids = re.findall(r"<emoji id=(\d+)>❗</emoji>", sent_text)
        self.assertEqual(sent_ids, list(PREMIUM_RECEIPT_EMOJI_IDS))
        self.assertEqual(client.send_message.await_args.kwargs["chat_id"], -100123)


if __name__ == "__main__":
    unittest.main()