import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from bot.services.blockchain import parse_incoming_usdt_transfer
from bot.services.deposit_monitor import payment_requires_admin_review
from bot.database.models import DepositStatus
from bot.utils.i18n import t


class BSCTransferParsingTests(unittest.TestCase):
    def setUp(self):
        self.contract = "0x" + "1" * 40
        self.wallet = "0x" + "2" * 40
        self.log = {
            "address": self.contract,
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x" + "0" * 64,
                "0x" + "0" * 24 + "2" * 40,
            ],
            "data": hex(5 * 10**18),
            "transactionHash": "0x" + "a" * 64,
            "blockNumber": "0x10",
            "logIndex": "0x2",
        }

    def test_parses_incoming_transfer_for_configured_token_and_wallet(self):
        event = parse_incoming_usdt_transfer(self.log, self.contract, self.wallet)

        self.assertEqual(event["amount"], Decimal("5"))
        self.assertEqual(event["block_number"], 16)
        self.assertEqual(event["log_index"], 2)
        self.assertEqual(event["tx_hash"], "0x" + "a" * 64)

    def test_ignores_other_token_and_recipient_logs(self):
        wrong_token = dict(self.log, address="0x" + "3" * 40)
        wrong_recipient = dict(self.log, topics=[*self.log["topics"][:2], "0x" + "0" * 24 + "4" * 40])

        self.assertIsNone(parse_incoming_usdt_transfer(wrong_token, self.contract, self.wallet))
        self.assertIsNone(parse_incoming_usdt_transfer(wrong_recipient, self.contract, self.wallet))


class DepositExpiryPolicyTests(unittest.TestCase):
    def test_payment_before_expiry_is_eligible_for_automatic_credit(self):
        created_at = datetime(2026, 1, 1, 12, 0, 0)

        self.assertFalse(payment_requires_admin_review(
            DepositStatus.PENDING,
            created_at + timedelta(minutes=29),
            created_at,
            created_at + timedelta(minutes=30),
        ))

    def test_payment_after_expiry_requires_admin_review(self):
        created_at = datetime(2026, 1, 1, 12, 0, 0)

        self.assertTrue(payment_requires_admin_review(
            DepositStatus.EXPIRED,
            created_at + timedelta(minutes=30, seconds=1),
            created_at,
            created_at + timedelta(minutes=30),
        ))

    def test_cancelled_invoice_always_requires_review(self):
        created_at = datetime(2026, 1, 1, 12, 0, 0)

        self.assertTrue(payment_requires_admin_review(
            DepositStatus.CANCELLED,
            created_at + timedelta(minutes=1),
            created_at,
            created_at + timedelta(minutes=30),
        ))

    def test_review_state_never_auto_credits_on_retry(self):
        created_at = datetime(2026, 1, 1, 12, 0, 0)

        self.assertTrue(payment_requires_admin_review(
            DepositStatus.REVIEW,
            created_at + timedelta(minutes=1),
            created_at,
            created_at + timedelta(minutes=30),
        ))


class DepositTranslationTests(unittest.TestCase):
    def test_invoice_and_review_texts_format_for_supported_languages(self):
        for language in ("es", "en", "pt"):
            invoice = t(
                "invoice_title",
                language,
                exact_val="2.123456",
                wallet="0x" + "1" * 40,
                expiry_minutes=30,
            )
            review = t("deposit_review_screen", language, amount="2.123456")
            expired = t("deposit_expired_screen", language, amount="2.123456")

            self.assertNotIn("{expiry_minutes}", invoice)
            self.assertNotIn("{amount}", review)
            self.assertNotIn("{amount}", expired)


if __name__ == "__main__":
    unittest.main()