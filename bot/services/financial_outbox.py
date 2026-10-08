import asyncio
import html
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, update

from bot.database.models import Deposit, FinancialNotification
from bot.database.session import async_session
from bot.services.audit_logger import audit_logger
from bot.utils.emojis import parse_emojis, parse_keyboard
from bot.utils.i18n import t
from bot.utils.navigation import (
    USER_LAST_MESSAGES,
    USER_LAST_MESSAGES_IS_MEDIA,
    render_screen,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _deliver_user_confirmation(client: Client, payload: Dict[str, Any]) -> bool:
    user_id = int(payload["user_id"])
    old_message_id = payload.get("user_message_id")
    if old_message_id and payload.get("user_message_is_media"):
        try:
            await client.delete_messages(user_id, int(old_message_id))
        except Exception:
            pass
        USER_LAST_MESSAGES.pop(user_id, None)
        USER_LAST_MESSAGES_IS_MEDIA.pop(user_id, None)
    elif old_message_id:
        USER_LAST_MESSAGES[user_id] = int(old_message_id)
        USER_LAST_MESSAGES_IS_MEDIA[user_id] = False

    lang = payload.get("language") or "es"
    text = t(
        "deposit_success_title",
        lang,
        amount=f"{float(payload['amount']):.6f}",
        balance=f"{float(payload['balance']):.6f}",
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")],
        [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")],
    ])
    message = await render_screen(client, user_id, text, keyboard)
    if not message:
        return False

    async with async_session() as session:
        await session.execute(
            update(Deposit)
            .where(Deposit.id == int(payload["deposit_id"]))
            .values(user_message_id=message.id, user_message_is_media=False)
        )
        await session.commit()
    return True


async def _deliver_referral_notification(client: Client, payload: Dict[str, Any]) -> bool:
    commission = float(payload["commission"])
    balance = float(payload["balance"])
    referred_username = payload.get("referred_username")
    referred_label = (
        f"@{html.escape(referred_username)}"
        if referred_username else f"usuario #{int(payload['referred_user_id'])}"
    )
    lang = payload.get("language") or "es"
    if lang == "en":
        text = (
            "🎉 <b>Referral commission received</b>\n\n"
            f"Your referral {referred_label} deposited funds.\n"
            f"➕ Commission: <code>+${commission:.6f} USDT</code>\n"
            f"👛 New balance: <code>${balance:.6f} USDT</code>"
        )
    elif lang == "pt":
        text = (
            "🎉 <b>Comissão de indicação recebida</b>\n\n"
            f"Seu indicado {referred_label} adicionou saldo.\n"
            f"➕ Comissão: <code>+${commission:.6f} USDT</code>\n"
            f"👛 Novo saldo: <code>${balance:.6f} USDT</code>"
        )
    else:
        text = (
            "🎉 <b>Comisión de referido recibida</b>\n\n"
            f"Tu referido {referred_label} recargó saldo.\n"
            f"➕ Comisión: <code>+${commission:.6f} USDT</code>\n"
            f"👛 Nuevo saldo: <code>${balance:.6f} USDT</code>"
        )
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("👛 Ver billetera", callback_data="wallet:deposit_menu")
    ]])
    await client.send_message(
        chat_id=int(payload["user_id"]),
        text=parse_emojis(text),
        reply_markup=parse_keyboard(markup),
        disable_web_page_preview=True,
    )
    return True


async def _dispatch_notification(client: Client, event_type: str, payload: Dict[str, Any]) -> bool:
    if event_type == "audit":
        return await audit_logger.log_deposit_confirmed(
            client=client,
            user_id=int(payload["user_id"]),
            username=payload.get("username"),
            first_name=payload.get("first_name") or "Usuario",
            amount=float(payload["amount"]),
            tx_hash=payload.get("tx_hash") or "",
            new_balance=float(payload["balance"]),
            deposit_id=int(payload["deposit_id"]),
            log_message_id=payload.get("log_message_id"),
        )
    if event_type == "user":
        return await _deliver_user_confirmation(client, payload)
    if event_type == "referral":
        return await _deliver_referral_notification(client, payload)
    raise ValueError(f"Tipo de notificación financiera desconocido: {event_type}")


async def process_pending_financial_notifications(
    client: Client,
    deposit_id: Optional[int] = None,
    limit: int = 50,
) -> int:
    now = _utc_now()
    async with async_session() as session:
        stmt = (
            select(FinancialNotification)
            .where(
                FinancialNotification.delivered_at.is_(None),
                FinancialNotification.next_attempt_at <= now,
            )
            .order_by(FinancialNotification.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if deposit_id is not None:
            stmt = stmt.where(FinancialNotification.event_key.like(f"deposit:{deposit_id}:%"))
        events = (await session.execute(stmt)).scalars().all()
        claimed = []
        lease_until = now + timedelta(minutes=2)
        for event in events:
            event.attempts += 1
            event.next_attempt_at = lease_until
            claimed.append((event.id, event.event_type, event.payload, event.attempts))
        await session.commit()

    delivered_count = 0
    for event_id, event_type, raw_payload, attempts in claimed:
        try:
            delivered = await _dispatch_notification(client, event_type, json.loads(raw_payload))
            if not delivered:
                raise RuntimeError("El destino no confirmó la entrega de la notificación")
        except Exception as exc:
            retry_delay = min(3600, 5 * (2 ** min(attempts - 1, 10)))
            async with async_session() as session:
                await session.execute(
                    update(FinancialNotification)
                    .where(FinancialNotification.id == event_id)
                    .values(
                        next_attempt_at=_utc_now() + timedelta(seconds=retry_delay),
                        last_error=str(exc)[:1000],
                    )
                )
                await session.commit()
            print(f"[FinancialOutbox retry] id={event_id} error={type(exc).__name__}")
            continue

        async with async_session() as session:
            await session.execute(
                update(FinancialNotification)
                .where(FinancialNotification.id == event_id)
                .values(delivered_at=_utc_now(), last_error=None)
            )
            await session.commit()
        delivered_count += 1
    return delivered_count


async def financial_notification_worker(client: Client) -> None:
    while True:
        try:
            await process_pending_financial_notifications(client)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[FinancialOutbox worker] {type(exc).__name__}: {exc}")
        await asyncio.sleep(10)