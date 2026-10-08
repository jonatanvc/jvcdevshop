from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Deposit, DepositStatus, User


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

    return {
        "user_id": user.telegram_id,
        "balance": Decimal(user.balance),
        "language": user.language or "es",
        "referral": referral,
    }