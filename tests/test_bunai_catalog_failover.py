import unittest
from unittest.mock import AsyncMock, Mock

from bot.services.bunai_client import BunaiAPIClient, CatalogUnavailableError


class BunaiCatalogFailoverTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_success_is_valid_catalog_data(self):
        response = Mock(status_code=200)
        response.json.return_value = []
        client = Mock()
        client.get = AsyncMock(return_value=response)
        api = BunaiAPIClient()
        api._get_client = Mock(return_value=client)

        self.assertEqual(await api.get_products(force_refresh=True), [])

    async def test_provider_failure_uses_last_good_catalog(self):
        good_response = Mock(status_code=200)
        good_response.json.return_value = [{"id": "service-1", "name": "Service"}]
        error_response = Mock(status_code=503)
        client = Mock()
        client.get = AsyncMock(side_effect=[good_response, error_response])
        api = BunaiAPIClient()
        api._get_client = Mock(return_value=client)

        good_catalog = await api.get_products(force_refresh=True)
        stale_catalog = await api.get_products(force_refresh=True)

        self.assertEqual(stale_catalog, good_catalog)

    async def test_provider_failure_without_cache_is_not_empty_success(self):
        response = Mock(status_code=503)
        client = Mock()
        client.get = AsyncMock(return_value=response)
        api = BunaiAPIClient()
        api._get_client = Mock(return_value=client)

        with self.assertRaises(CatalogUnavailableError):
            await api.get_products(force_refresh=True)


if __name__ == "__main__":
    unittest.main()