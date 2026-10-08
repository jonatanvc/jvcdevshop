import re
import unittest

from bot.services.vouchers import VoucherService
from bot.utils.emojis import (
    PREMIUM_RECEIPT_EMOJI_IDS,
    PREMIUM_RECEIPT_LOGO,
    parse_emojis,
    receipt_logo_for_user,
)


class ReceiptBrandingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()