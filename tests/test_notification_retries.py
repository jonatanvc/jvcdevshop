import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from bot.handlers import support
from bot.database.models import TicketMessage
from bot.main import daily_backup_worker
from bot.services.stock_watcher import StockWatcher


class FakeAlert:
    user_id = 12345


class NotificationRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_ticket_message_model_contains_retry_state(self):
        self.assertIn("admin_notification_pending", TicketMessage.__table__.columns)
        self.assertIn("admin_notification_kind", TicketMessage.__table__.columns)
        self.assertIn("user_notification_pending", TicketMessage.__table__.columns)

    async def test_stock_alert_delivery_reports_telegram_failure(self):
        watcher = StockWatcher()
        client = AsyncMock()
        client.send_message.side_effect = OSError("Telegram unavailable")

        with patch("bot.services.stock_watcher.asyncio.sleep", new=AsyncMock()):
            delivered = await watcher._deliver_restock_alert(
                client, FakeAlert(), "es", "Producto", 3.5, 2, "product-1"
            )

        self.assertFalse(delivered)

    async def test_ticket_notification_stays_pending_when_send_fails(self):
        client = AsyncMock()
        client.send_message.side_effect = OSError("Telegram unavailable")

        with patch.object(support, "_mark_admin_notification_delivered", new=AsyncMock()) as mark_delivered:
            delivered = await support.notify_admins_ticket_update(
                client, 10, 12345, "customer", "Need help", None, None, 77
            )

        self.assertFalse(delivered)
        mark_delivered.assert_not_awaited()

    async def test_ticket_notification_is_marked_delivered_after_send(self):
        client = AsyncMock()

        with patch.object(support, "_mark_admin_notification_delivered", new=AsyncMock()) as mark_delivered:
            delivered = await support.notify_admins_ticket_update(
                client, 10, 12345, "customer", "Need help", None, None, 77
            )

        self.assertTrue(delivered)
        mark_delivered.assert_awaited_once_with(77)

    async def test_pending_ticket_notifications_are_retried(self):
        ticket_message = type("Message", (), {
            "id": 77,
            "message_text": "Need help",
            "media_file_id": None,
            "media_type": None,
            "admin_notification_kind": "update",
        })()
        ticket = type("Ticket", (), {"id": 10, "user_id": 12345})()
        user = type("User", (), {"username": "customer"})()
        result = type("Result", (), {"all": lambda self: [(ticket_message, ticket, user)]})()

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def execute(self, _statement):
                return result

        client = AsyncMock()
        with patch.object(support, "async_session", return_value=FakeSession()), patch.object(
            support, "notify_admins_ticket_update", new=AsyncMock()
        ) as retry_update:
            await support.retry_pending_admin_ticket_notifications(client)

        retry_update.assert_awaited_once_with(
            client, 10, 12345, "customer", "Need help", None, None, 77
        )

    async def test_pending_admin_replies_are_retried_to_the_user(self):
        ticket_message = type("Message", (), {"id": 88, "message_text": "We fixed it"})()
        ticket = type("Ticket", (), {"id": 10, "user_id": 12345})()
        result = type("Result", (), {"all": lambda self: [(ticket_message, ticket)]})()

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def execute(self, _statement):
                return result

        client = AsyncMock()
        with patch.object(support, "async_session", return_value=FakeSession()), patch.object(
            support, "_deliver_admin_ticket_reply_dm", new=AsyncMock(return_value=True)
        ) as retry_reply:
            await support.retry_pending_user_ticket_notifications(client)

        retry_reply.assert_awaited_once_with(client, 12345, 10, "We fixed it", 88)

    async def test_failed_admin_reply_dm_remains_pending(self):
        client = AsyncMock()
        client.send_message.side_effect = OSError("Telegram unavailable")

        with patch.object(support, "_mark_user_notification_delivered", new=AsyncMock()) as mark_delivered:
            delivered = await support._deliver_admin_ticket_reply_dm(
                client, 12345, 10, "We fixed it", 88
            )

        self.assertFalse(delivered)
        mark_delivered.assert_not_awaited()

    async def test_daily_backup_runs_before_waiting_for_interval(self):
        client = AsyncMock()
        with patch("bot.main.backup_service.send_automated_backup", new=AsyncMock()) as send_backup, patch(
            "bot.main.asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)
        ):
            with self.assertRaises(asyncio.CancelledError):
                await daily_backup_worker(client)

        send_backup.assert_awaited_once_with(client)


if __name__ == "__main__":
    unittest.main()