import unittest
from decimal import Decimal

from bot.services.blockchain import bsc_validator


class BlockchainTransferTests(unittest.TestCase):
    def test_sums_all_official_usdt_transfers_to_admin_wallet(self):
        recipient = "0x" + "0" * 24 + bsc_validator.admin_wallet
        transfer_topic = "0x" + bsc_validator.transfer_topic
        logs = [
            {
                "address": "0x" + bsc_validator.usdt_contract,
                "topics": [transfer_topic, "0x" + "0" * 64, recipient],
                "data": hex(4 * 10**17),
            },
            {
                "address": "0x" + bsc_validator.usdt_contract,
                "topics": [transfer_topic, "0x" + "0" * 64, recipient],
                "data": hex(6 * 10**17),
            },
            {
                "address": "0x" + bsc_validator.usdt_contract,
                "topics": [transfer_topic, "0x" + "0" * 64, "0x" + "0" * 24 + "1" * 40],
                "data": hex(5 * 10**18),
            },
            {
                "address": "0x" + "1" * 40,
                "topics": [transfer_topic, "0x" + "0" * 64, recipient],
                "data": hex(5 * 10**18),
            },
        ]

        found, amount = bsc_validator._sum_admin_usdt_transfers(logs)

        self.assertTrue(found)
        self.assertEqual(amount, Decimal("1"))

    def test_rejects_malformed_destination_topic(self):
        logs = [{
            "address": "0x" + bsc_validator.usdt_contract,
            "topics": ["0x" + bsc_validator.transfer_topic, "0x" + "0" * 64, "0x12"],
            "data": hex(10**18),
        }]

        found, amount = bsc_validator._sum_admin_usdt_transfers(logs)

        self.assertFalse(found)
        self.assertEqual(amount, Decimal("0"))


if __name__ == "__main__":
    unittest.main()