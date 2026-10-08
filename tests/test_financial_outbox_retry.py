import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.services import financial_outbox


class FakeResult:
    def __init__(self, event):
        self.event = event

    def scalars(self):
        return self

    def all(self):
        return [self.event]


class FakeSession:
    def __init__(self, event):
        self.event = event
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        if len(self.statements) == 1:
            return FakeResult(self.event)
        return None

    async def commit(self):
        pass


class FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FinancialOutboxRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_delivery_persists_retry_and_keeps_event_pending(self):
        event = SimpleNamespace(
            id=7,
            event_type="user",
            payload=json.dumps({"user_id": 12}),
            attempts=0,
            next_attempt_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session = FakeSession(event)
        session_context = lambda: FakeSessionContext(session)

        with (
            patch.object(financial_outbox, "async_session", side_effect=session_context),
            patch.object(
                financial_outbox,
                "_dispatch_notification",
                new=AsyncMock(side_effect=RuntimeError("Telegram unavailable")),
            ),
        ):
            delivered = await financial_outbox.process_pending_financial_notifications(
                client=object(),
                deposit_id=3,
            )

        self.assertEqual(delivered, 0)
        self.assertEqual(event.attempts, 1)
        self.assertEqual(len(session.statements), 2)
        retry_update = str(session.statements[1])
        self.assertIn("next_attempt_at", retry_update)
        self.assertIn("last_error", retry_update)


if __name__ == "__main__":
    unittest.main()