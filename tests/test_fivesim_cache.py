import unittest
from unittest.mock import patch

from bot.services.fivesim_client import FiveSimClient


class FakeResponse:
    status_code = 200

    def json(self):
        return {"fresh": True}


class FakeHttpClient:
    async def get(self, _url, params=None):
        return FakeResponse()


class FailingHttpClient:
    async def get(self, _url, params=None):
        raise OSError("offline")


class FiveSimPriceCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_expiry_is_independent_per_query_key(self):
        client = FiveSimClient()
        client._prices_cache["portugal:whatsapp"] = ({"stale": True}, 900.0)
        client._prices_cache["spain:whatsapp"] = ({"fresh": True}, 1020.0)
        client._get_client = lambda: FakeHttpClient()

        with patch("bot.services.fivesim_client.time.time", return_value=1000.0):
            result = await client.get_raw_prices(country="portugal", product="whatsapp")

        self.assertEqual(result, {"fresh": True})
        self.assertEqual(client._prices_cache["portugal:whatsapp"], ({"fresh": True}, 1030.0))
        self.assertEqual(client._prices_cache["spain:whatsapp"], ({"fresh": True}, 1020.0))

    async def test_expired_entry_is_fallback_when_network_fails(self):
        client = FiveSimClient()
        client._prices_cache["portugal:whatsapp"] = ({"stale": True}, 900.0)
        client._get_client = lambda: FailingHttpClient()

        with patch("bot.services.fivesim_client.time.time", return_value=1000.0):
            result = await client.get_raw_prices(country="portugal", product="whatsapp")

        self.assertEqual(result, {"stale": True})


if __name__ == "__main__":
    unittest.main()