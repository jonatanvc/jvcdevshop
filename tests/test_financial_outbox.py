import json
import unittest
from decimal import Decimal
from types import SimpleNamespace

from bot.database.models import FinancialNotification
from bot.services.deposit_accounting import enqueue_deposit_notifications


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)


class FinancialOutboxTests(unittest.TestCase):
    def test_deposit_queues_audit_and_user_events_with_stable_keys(self):
        session = FakeSession()
        deposit = SimpleNamespace(
            id=14, tx_hash="0xabc", log_message_id=9,
            user_message_id=21, user_message_is_media=False
        )
        user = SimpleNamespace(
            telegram_id=123, username="buyer", first_name="Buyer", language="es"
        )

        enqueue_deposit_notifications(session, deposit, user, Decimal("5.5"), Decimal("8.5"), None)

        self.assertEqual([item.event_key for item in session.added], [
            "deposit:14:audit", "deposit:14:user"
        ])
        self.assertTrue(all(isinstance(item, FinancialNotification) for item in session.added))
        self.assertEqual(json.loads(session.added[1].payload)["user_message_id"], 21)

    def test_referral_commission_is_queued_in_same_transaction(self):
        session = FakeSession()
        deposit = SimpleNamespace(
            id=15, tx_hash="0xdef", log_message_id=None,
            user_message_id=None, user_message_is_media=False
        )
        user = SimpleNamespace(
            telegram_id=124, username=None, first_name="Buyer", language="en"
        )
        referral = {
            "user_id": 456,
            "language": "pt",
            "balance": Decimal("12.5"),
            "commission": Decimal("0.5"),
        }

        enqueue_deposit_notifications(session, deposit, user, Decimal("10"), Decimal("10"), referral)

        self.assertEqual([item.event_type for item in session.added], ["audit", "user", "referral"])
        referral_payload = json.loads(session.added[2].payload)
        self.assertEqual(referral_payload["user_id"], 456)
        self.assertEqual(referral_payload["commission"], "0.5")


if __name__ == "__main__":
    unittest.main()