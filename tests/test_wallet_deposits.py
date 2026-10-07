import unittest
from decimal import Decimal

from bot.handlers.wallet import choose_deposit_exact_amount


class DepositAmountTests(unittest.TestCase):
    def test_selects_the_only_unreserved_amount(self):
        reserved = {
            Decimal(str(round(10.0 + suffix / 10000.0, 4)))
            for suffix in range(100, 1000)
        }
        expected = Decimal("10.0555")
        reserved.remove(expected)

        self.assertEqual(choose_deposit_exact_amount(10.0, reserved), expected)

    def test_returns_none_when_all_suffixes_are_reserved(self):
        reserved = {
            Decimal(str(round(10.0 + suffix / 10000.0, 4)))
            for suffix in range(100, 1000)
        }

        self.assertIsNone(choose_deposit_exact_amount(10.0, reserved))


if __name__ == "__main__":
    unittest.main()