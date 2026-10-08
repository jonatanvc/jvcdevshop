import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Deposit, DepositStatus, FinancialNotification, User


def enqueue_deposit_notifications(
    session: AsyncSession,
    deposit: Deposit,
    user: User,
    amount: Decimal,
    balance: Decimal,
    referral: Optional[Dict[str, Any]],
) -> None:
    common_payload = {
        "deposit_id": deposit.id,
        "user_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name or "Usuario",
        "language": user.language or "es",
        "amount": str(amount),
        "balance": str(balance),
        "tx_hash": deposit.tx_hash or "",
        "log_message_id": deposit.log_message_id,
        "user_message_id": deposit.user_message_id,
        "user_message_is_media": deposit.user_message_is_media,
    }
    notifications = [
        ("audit", {key: common_payload[key] for key in (
            "deposit_id", "user_id", "username", "first_name", "amount", "balance", "tx_hash", "log_message_id"
        )}),
        ("user", {key: common_payload[key] for key in (
            "deposit_id", "user_id", "language", "amount", "balance", "user_message_id", "user_message_is_media"
        )}),
    ]
    if referral:
        notifications.append(("referral", {
            "user_id": referral["user_id"],
            "language": referral["language"],
            "balance": str(referral["balance"]),
            "commission": str(referral["commission"]),
            "referred_user_id": user.telegram_id,
            "referred_username": user.username,
        }))

    for event_type, payload in notifications:
        session.add(FinancialNotification(
            event_key=f"deposit:{deposit.id}:{event_type}",
            event_type=event_type,
            payload=json.dumps(payload),
        ))


async def credit_deposit_in_session(
    session: AsyncSession,
    deposit: Deposit,
    amount: Decimal,
    block_number: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Acredita un depósito dentro de la transacción actual, incluyendo su comisión de referido."""
    if deposit.status == DepositStatus.CONFIRMED:
        return None

    user = await session.scalar(
        select(User).where(User.telegram_id == deposit.user_id).with_for_update()
    )
    if not user:
        raise RuntimeError(f"No existe el usuario {deposit.user_id} del depósito {deposit.id}")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    deposit.status = DepositStatus.CONFIRMED
    deposit.confirmed_at = now
    deposit.verification_started_at = None
    if block_number is not None:
        deposit.block_number = block_number
    user.balance += amount

    referral = None
    if user.referred_by:
        referrer = await session.scalar(
            select(User).where(User.telegram_id == user.referred_by).with_for_update()
        )
        if referrer:
            is_vip = bool(referrer.is_vip and referrer.vip_expires_at and referrer.vip_expires_at > now)
            commission_percent = (
                settings.VIP_REFERRAL_COMMISSION_PERCENT
                if is_vip else settings.REFERRAL_COMMISSION_PERCENT
            )
            commission = amount * Decimal(str(commission_percent)) / Decimal("100")
            referrer.balance += commission
            deposit.referral_commission_amount = commission
            referral = {
                "user_id": referrer.telegram_id,
                "balance": Decimal(referrer.balance),
                "commission": commission,
                "language": referrer.language or "es",
            }

    enqueue_deposit_notifications(session, deposit, user, amount, Decimal(user.balance), referral)

    return {
        "user_id": user.telegram_id,
        "balance": Decimal(user.balance),
        "language": user.language or "es",
        "referral": referral,
    }