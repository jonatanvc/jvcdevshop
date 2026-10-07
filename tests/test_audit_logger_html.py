import unittest
from unittest.mock import AsyncMock

from bot.services.audit_logger import AuditLogger


class AuditLoggerHtmlTests(unittest.IsolatedAsyncioTestCase):
    async def test_virtual_activation_escapes_user_and_provider_fields(self):
        logger = AuditLogger()
        logger._send_log = AsyncMock()

        await logger.log_virtual_number_activation(
            client=None,
            user_id=123,
            username=None,
            first_name="<b>Attacker</b>",
            order_id=1,
            service_name="whatsapp",
            country_code="portugal",
            phone="<code>123</code>",
            code="<a href='bad'>456</a>",
            price_usdt=1.0,
        )

        message = logger._send_log.await_args.args[1]
        self.assertIn("&lt;b&gt;Attacker&lt;/b&gt;", message)
        self.assertIn("&lt;code&gt;123&lt;/code&gt;", message)
        self.assertIn("&lt;a href=&#x27;bad&#x27;&gt;456&lt;/a&gt;", message)
        self.assertNotIn("<a href='bad'>", message)

    async def test_purchase_escapes_supplier_product_and_delivery(self):
        logger = AuditLogger()
        logger._send_log = AsyncMock()

        await logger.log_purchase(
            client=None,
            user_id=123,
            username="user",
            first_name="User",
            order_id=1,
            product_name="<b>Product</b>",
            paid_price=1.0,
            remaining_balance=2.0,
            provider_order_id="<id>",
            delivered_items="mail@example.test|<script>alert(1)</script>",
        )

        message = logger._send_log.await_args.args[1]
        self.assertIn("&lt;b&gt;Product&lt;/b&gt;", message)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", message)
        self.assertIn("&lt;id&gt;", message)
        self.assertNotIn("<script>", message)


if __name__ == "__main__":
    unittest.main()