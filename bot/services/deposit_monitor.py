import asyncio
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional

from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from bot.config import settings
from bot.database.models import Deposit, DepositStatus, Setting, User
from bot.database.session import async_session
from bot.services.audit_logger import audit_logger
from bot.services.blockchain import bsc_validator
from bot.services.deposit_accounting import credit_deposit_in_session
from bot.services.financial_outbox import process_pending_financial_notifications
from bot.utils.i18n import t
from bot.utils.navigation import USER_LAST_MESSAGES, USER_LAST_MESSAGES_IS_MEDIA, render_screen

_CURSOR_SETTING_KEY = "bsc_usdt_deposit_scan_block"
_AMOUNT_QUANTUM = Decimal("0.000001")
last_successful_scan_at: Optional[float] = None
scanner_scan_in_progress = False
scanner_scan_started_at: Optional[float] = None
scanner_scan_phase = "idle"
scanner_last_error_type: Optional[str] = None
scanner_last_error_phase: Optional[str] = None

def safe_scanner_error_detail(exc: Exception) -> str:
    detail = str(exc).strip()
    detail = re.sub(r"https?://[^\s\"'<>]+", "<RPC endpoint>", detail, flags=re.IGNORECASE)
    detail = re.sub(
        r"(?i)\b(authorization|api[_-]?key|token|password)\b\s*[:=]\s*[^\s,&;]+",
        r"\1=[redacted]",
        detail,
    )
    return detail[:240]


def payment_requires_admin_review(
    status: DepositStatus,
    event_time: datetime,
    created_at: datetime,
    expires_at: datetime,
) -> bool:
    return (
        status in (DepositStatus.CANCELLED, DepositStatus.REVIEW)
        or event_time < created_at
        or event_time > expires_at
    )


def _credit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ Ir al catálogo", callback_data="catalog:disponibles:1")],
        [InlineKeyboardButton("👛 Ver billetera", callback_data="wallet:deposit_menu")],
    ])


async def _edit_user_deposit_screen(
    client: Client,
    deposit_id: int,
    user_id: int,
    message_id: Optional[int],
    text: str,
    keyboard: Optional[InlineKeyboardMarkup],
    is_media: bool = False,
) -> None:
    if message_id:
        if is_media:
            try:
                await client.delete_messages(user_id, message_id)
            except Exception:
                pass
            USER_LAST_MESSAGES.pop(user_id, None)
            USER_LAST_MESSAGES_IS_MEDIA.pop(user_id, None)
        else:
            USER_LAST_MESSAGES[user_id] = message_id
            USER_LAST_MESSAGES_IS_MEDIA[user_id] = False
    rendered_message = await render_screen(client, user_id, text, keyboard)
    if rendered_message:
        async with async_session() as session:
            await session.execute(
                update(Deposit)
                .where(Deposit.id == deposit_id)
                .values(user_message_id=rendered_message.id, user_message_is_media=False)
            )
            await session.commit()


async def notify_deposit_referrer(client: Client, referral: Optional[Dict[str, Any]]) -> None:
    if not referral:
        return
    commission = float(referral["commission"])
    balance = float(referral["balance"])
    if referral["language"] == "pt":
        text = f"🎉 Comissão de indicação: +${commission:.6f} USDT\nNovo saldo: ${balance:.6f} USDT"
    elif referral["language"] == "en":
        text = f"🎉 Referral commission: +${commission:.6f} USDT\nNew balance: ${balance:.6f} USDT"
    else:
        text = f"🎉 Comisión de referido: +${commission:.6f} USDT\nNuevo saldo: ${balance:.6f} USDT"
    try:
        await client.send_message(referral["user_id"], text)
    except Exception as exc:
        print(f"[Deposit referral notification error] {type(exc).__name__}")


async def _show_review_to_user(client: Client, deposit: Deposit, user: User) -> None:
    await _edit_user_deposit_screen(
        client,
        deposit.id,
        deposit.user_id,
        deposit.user_message_id,
        t(
            "deposit_review_screen",
            user.language or "es",
            amount=f"{float(deposit.exact_amount):.6f}",
        ),
        None,
        deposit.user_message_is_media,
    )


async def process_incoming_transfer(client: Client, event: Dict[str, Any]) -> bool:
    """Processes one confirmed USDT event. False asks the scanner to retry without advancing its cursor."""
    event_time = datetime.fromtimestamp(event["timestamp"], timezone.utc).replace(tzinfo=None)
    event_amount = event["amount"].quantize(_AMOUNT_QUANTUM, rounding=ROUND_DOWN)
    tx_hash = event["tx_hash"].lower()

    async with async_session() as session:
        candidates = (await session.execute(
            select(Deposit).where(
                Deposit.auto_monitor.is_(True),
                Deposit.exact_amount == event_amount,
                Deposit.status.in_([
                    DepositStatus.PENDING,
                    DepositStatus.EXPIRED,
                    DepositStatus.CANCELLED,
                    DepositStatus.REVIEW,
                ]),
            ).order_by(Deposit.created_at.desc()).limit(2)
        )).scalars().all()

    if not candidates:
        return True
    if len(candidates) != 1:
        await audit_logger.log_system_alert(
            client,
            "TRANSFERENCIA BSC AMBIGUA",
            f"No se pudo asociar automáticamente <code>{tx_hash}</code> por importe repetido ({event_amount:.6f} USDT).",
        )
        return True

    candidate = candidates[0]
    verification = await bsc_validator.verify_deposit(tx_hash, float(candidate.exact_amount))
    if not verification.get("success"):
        print(f"[Deposit monitor retry] {verification.get('error', 'BSC validation failed')}")
        return False

    needs_review = False
    credit_result = None
    log_message_id = candidate.log_message_id
    user_message_id = candidate.user_message_id
    user_message_is_media = candidate.user_message_is_media
    deposit_id = candidate.id
    user_id = candidate.user_id
    credited_amount = event_amount

    try:
        async with async_session() as session:
            deposit = await session.scalar(
                select(Deposit).where(Deposit.id == deposit_id).with_for_update()
            )
            if not deposit:
                return True
            if deposit.status == DepositStatus.CONFIRMED:
                return True
            if deposit.status == DepositStatus.REVIEW and deposit.tx_hash != tx_hash:
                return True
            already_in_review = deposit.status == DepositStatus.REVIEW
            if deposit.status == DepositStatus.VERIFYING:
                return True
            if deposit.status not in (
                DepositStatus.PENDING,
                DepositStatus.EXPIRED,
                DepositStatus.CANCELLED,
                DepositStatus.REVIEW,
            ):
                return True

            duplicate = await session.scalar(
                select(Deposit.id).where(Deposit.tx_hash == tx_hash, Deposit.id != deposit_id)
            )
            if duplicate:
                print(f"[Deposit monitor duplicate transfer] tx={tx_hash} deposit={deposit_id} existing={duplicate}")
                return True

            deposit.tx_hash = tx_hash
            deposit.block_number = event["block_number"]
            log_message_id = deposit.log_message_id
            user_message_id = deposit.user_message_id
            user_message_is_media = deposit.user_message_is_media
            user = await session.scalar(select(User).where(User.telegram_id == user_id))
            if not user:
                return True

            needs_review = already_in_review or payment_requires_admin_review(
                deposit.status, event_time, deposit.created_at, deposit.expires_at
            )
            if needs_review:
                deposit.status = DepositStatus.REVIEW
                await session.commit()
            else:
                credit_result = await credit_deposit_in_session(
                    session, deposit, credited_amount, event["block_number"]
                )
                await session.commit()

        if needs_review:
            new_log_id = await audit_logger.log_deposit_review(
                client=client,
                deposit_id=deposit_id,
                user_id=user_id,
                username=user.username,
                first_name=user.first_name or "Usuario",
                amount=float(candidate.exact_amount),
                tx_hash=tx_hash,
                log_message_id=log_message_id,
            )
            if not new_log_id:
                return False
            if new_log_id and new_log_id != log_message_id:
                async with async_session() as session:
                    deposit = await session.get(Deposit, deposit_id)
                    if deposit:
                        deposit.log_message_id = new_log_id
                        await session.commit()
            candidate.user_message_id = user_message_id
            candidate.user_message_is_media = user_message_is_media
            await _show_review_to_user(client, candidate, user)
            return True

        if not credit_result:
            return True
        await process_pending_financial_notifications(client, deposit_id=deposit_id)
        return True
    except IntegrityError:
        return True
    except Exception as exc:
        print(f"[Deposit monitor process error] {type(exc).__name__}: {exc}")
        return False


async def scan_deposit_transfers_once(client: Client) -> None:
    global last_successful_scan_at, scanner_scan_phase
    global scanner_last_error_type, scanner_last_error_phase
    scanner_scan_phase = "reading_cursor"
    async with async_session() as session:
        cursor_setting = await session.get(Setting, _CURSOR_SETTING_KEY)

    if cursor_setting:
        start_block = int(cursor_setting.value) + 1
    else:
        scanner_scan_phase = "reading_confirmed_block"
        latest_confirmed = await bsc_validator.get_confirmed_block_number()
        start_block = max(0, latest_confirmed - settings.BSC_INITIAL_SCAN_BLOCKS)

    scanner_scan_phase = "fetching_transfers"
    last_scanned_block, events = await bsc_validator.scan_incoming_transfers(start_block)
    for index, event in enumerate(events, start=1):
        scanner_scan_phase = f"processing_transfer_{index}_of_{len(events)}"
        if not await process_incoming_transfer(client, event):
            scanner_last_error_type = "TransferProcessingError"
            scanner_last_error_phase = scanner_scan_phase
            return

    if last_scanned_block < start_block:
        last_successful_scan_at = time.monotonic()
        scanner_last_error_type = None
        scanner_last_error_phase = None
        scanner_scan_phase = "idle"
        return
    scanner_scan_phase = "saving_cursor"
    async with async_session() as session:
        cursor_setting = await session.get(Setting, _CURSOR_SETTING_KEY)
        if cursor_setting:
            cursor_setting.value = str(last_scanned_block)
        else:
            session.add(Setting(key=_CURSOR_SETTING_KEY, value=str(last_scanned_block)))
        await session.commit()
    last_successful_scan_at = time.monotonic()
    scanner_last_error_type = None
    scanner_last_error_phase = None
    scanner_scan_phase = "idle"


async def deposit_monitor_worker(client: Client) -> None:
    global scanner_scan_in_progress, scanner_scan_started_at
    global scanner_last_error_type, scanner_last_error_phase
    while True:
        scanner_scan_in_progress = True
        scanner_scan_started_at = time.monotonic()
        try:
            await scan_deposit_transfers_once(client)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            scanner_last_error_type = type(exc).__name__
            scanner_last_error_phase = scanner_scan_phase
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            status_detail = f" status={status_code}" if status_code is not None else ""
            error_detail = safe_scanner_error_detail(exc)
            print(
                f"[Deposit monitor error] phase={scanner_scan_phase} "
                f"type={scanner_last_error_type}{status_detail} detail={error_detail}"
            )
        finally:
            scanner_scan_in_progress = False
        await asyncio.sleep(max(3, settings.BSC_MONITOR_INTERVAL_SECONDS))