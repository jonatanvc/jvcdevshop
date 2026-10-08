import unittest
from decimal import Decimal
from unittest.mock import patch

from bot.handlers.wallet import choose_deposit_exact_amount


class DepositAmountTests(unittest.TestCase):
    def test_selects_an_amount_not_used_by_an_older_invoice(self):
        reserved = {Decimal("10.000001"), Decimal("10.000002")}

        selected = choose_deposit_exact_amount(10.0, reserved)

        self.assertNotIn(selected, reserved)
        self.assertGreater(selected, Decimal("10.000000"))
        self.assertLessEqual(selected, Decimal("11.000000"))
        self.assertEqual(selected.as_tuple().exponent, -6)

    def test_returns_none_when_all_suffixes_are_reserved(self):
        with patch("bot.handlers.wallet.DEPOSIT_AMOUNT_SUFFIX_MAX", 5):
            reserved = {Decimal("10.000001"), Decimal("10.000002"), Decimal("10.000003"), Decimal("10.000004")}

            self.assertIsNone(choose_deposit_exact_amount(10.0, reserved))


if __name__ == "__main__":
    unittest.main()