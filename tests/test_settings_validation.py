import unittest

from pydantic import ValidationError

from bot.config import Settings


def build_settings(**overrides):
    values = {
        "API_ID": 12345,
        "API_HASH": "api-hash",
        "BOT_TOKEN": "12345:token",
        "ADMIN_IDS_RAW": "111,222",
        "BUNAI_API_KEY": "bunai-key",
        "ADMIN_WALLET_BSC": "0x" + "1" * 40,
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
    }
    values.update(overrides)
    return Settings(**values)


class SettingsSecurityTests(unittest.TestCase):
    def test_only_first_admin_id_is_owner(self):
        settings = build_settings()

        self.assertTrue(settings.is_owner(111))
        self.assertFalse(settings.is_owner(222))
        self.assertEqual(settings.admin_ids, [111, 222])

    def test_rejects_invalid_blockchain_and_expiry_limits(self):
        for field, value in (
            ("MIN_BLOCK_CONFIRMATIONS", 0),
            ("BSC_MONITOR_INTERVAL_SECONDS", 2),
            ("BSC_INITIAL_SCAN_BLOCKS", 0),
            ("DEPOSIT_EXPIRY_MINUTES", 0),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                build_settings(**{field: value})

    def test_rejects_duplicate_admin_ids(self):
        with self.assertRaises(ValidationError):
            build_settings(ADMIN_IDS_RAW="111,111")


if __name__ == "__main__":
    unittest.main()