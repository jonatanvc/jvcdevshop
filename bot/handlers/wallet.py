import random
import math
import re
import html
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Set, Optional
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Deposit, DepositStatus, Order, VirtualNumberOrder
from bot.services.blockchain import bsc_validator
from bot.services.deposit_accounting import credit_deposit_in_session
from bot.services.financial_outbox import process_pending_financial_notifications
from bot.services.audit_logger import audit_logger
from bot.services.qr_generator import get_wallet_qr_media
from bot.services.promos import promo_service
from bot.utils.navigation import render_screen, USER_LAST_MESSAGES, USER_LAST_MESSAGES_IS_MEDIA
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.emojis import parse_emojis, parse_keyboard

USER_STATES: Dict[int, Dict[str, Any]] = {}
_ACTIVE_HASH_VERIFICATIONS: Set[str] = set()
DEPOSIT_AMOUNT_SUFFIX_MAX = 1_000_000

def get_movement_emoji(is_credit: bool) -> str:
    return "🟢" if is_credit else "🔴"

def choose_deposit_exact_amount(base_amount: float, reserved_amounts: Set[Decimal]) -> Optional[Decimal]:
    base = Decimal(str(base_amount)).quantize(Decimal("0.000001"))
    suffix_count = DEPOSIT_AMOUNT_SUFFIX_MAX - 1
    start = random.randrange(1, DEPOSIT_AMOUNT_SUFFIX_MAX)
    for offset in range(suffix_count):
        suffix = ((start + offset - 1) % suffix_count) + 1
        exact_amount = base + Decimal(suffix) / Decimal("1000000")
        if exact_amount not in reserved_amounts:
            return exact_amount
    return None

def get_deposit_menu_keyboard(lang: str = "es", active_coupon: Optional[str] = None) -> InlineKeyboardMarkup:
    """Botonera con montos rápidos de recarga y opciones de tarjetas de regalo y cupones"""
    coupon_btn = (
        InlineKeyboardButton(f"🎟️ Quitar Cupón ({active_coupon})", callback_data="wallet:remove_coupon")
        if active_coupon
        else InlineKeyboardButton("🎟️ Reclamar Cupón de Descuento", callback_data="wallet:redeem_coupon")
    )
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💵 2 USDT", callback_data="deposit:amount:2"),
            InlineKeyboardButton("💵 5 USDT", callback_data="deposit:amount:5"),
            InlineKeyboardButton("💵 10 USDT", callback_data="deposit:amount:10")
        ],
        [
            InlineKeyboardButton("💵 20 USDT", callback_data="deposit:amount:20"),
            InlineKeyboardButton("💵 50 USDT", callback_data="deposit:amount:50"),
            InlineKeyboardButton(t("btn_custom_amount", lang), callback_data="deposit:custom")
        ],
        [
            InlineKeyboardButton("🎁 Canjear Tarjeta de Regalo", callback_data="wallet:redeem_gift")
        ],
        [
            coupon_btn
        ],
        [
            InlineKeyboardButton(t("btn_back", lang), callback_data="menu_main")
        ]
    ])

def get_invoice_keyboard(deposit_id: int, lang: str = "es") -> InlineKeyboardMarkup:
    """Botonera de pago directo; la detección de transferencias es automática."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_show_qr", lang), callback_data=f"deposit:show_qr:{deposit_id}")
        ],
        [
            InlineKeyboardButton(t("btn_cancel_request", lang), callback_data=f"deposit:cancel:{deposit_id}")
        ]
    ])

async def create_deposit_invoice(client: Client, user_id: int, username: str, first_name: str, base_amount: float, target, lang: str = "es") -> None:
    """Crea la solicitud de depósito y guarda el log_message_id para editar el mismo mensaje en logs"""
    async with async_session() as session:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at = now + timedelta(minutes=settings.DEPOSIT_EXPIRY_MINUTES)
        await session.execute(select(func.pg_advisory_xact_lock(75103001, 1)))

        verifying_stmt = select(Deposit.id).where(
            Deposit.user_id == user_id,
            Deposit.status == DepositStatus.VERIFYING
        )
        if await session.scalar(verifying_stmt):
            await render_screen(client, target, t("verifying_tx", lang), None)
            return

        # Replaced invoices are not eligible for automatic credit if paid later.
        cancel_old_stmt = (
            update(Deposit)
            .where(Deposit.user_id == user_id, Deposit.status == DepositStatus.PENDING)
            .values(status=DepositStatus.CANCELLED)
        )
        await session.execute(cancel_old_stmt)
        reserved_res = await session.execute(
            select(Deposit.exact_amount)
        )
        reserved_amounts = set(reserved_res.scalars())
        exact_dec = choose_deposit_exact_amount(base_amount, reserved_amounts)
        if exact_dec is None:
            await session.rollback()
            await render_screen(
                client,
                target,
                "No hay importes de depósito disponibles en este momento. Inténtalo de nuevo más tarde.",
                None
            )
            return
        exact_val = float(exact_dec)

        new_deposit = Deposit(
            user_id=user_id,
            base_amount=Decimal(str(base_amount)),
            exact_amount=exact_dec,
            status=DepositStatus.PENDING,
            auto_monitor=True,
            expires_at=expires_at,
            created_at=now,
            log_message_id=None
        )
        session.add(new_deposit)
        await session.commit()
        await session.refresh(new_deposit)
        deposit_id = new_deposit.id

    log_msg_id = await audit_logger.log_deposit_request(
        client=client,
        user_id=user_id,
        username=username,
        first_name=first_name,
        base_amount=base_amount,
        exact_amount=float(exact_dec)
    )
    if log_msg_id:
        async with async_session() as session:
            await session.execute(
                update(Deposit)
                .where(Deposit.id == deposit_id)
                .values(log_message_id=log_msg_id)
            )
            await session.commit()

    invoice_text = t(
        "invoice_title",
        lang,
        exact_val=f"{exact_val:.6f}",
        wallet=settings.ADMIN_WALLET_BSC,
        expiry_minutes=settings.DEPOSIT_EXPIRY_MINUTES,
    )
    invoice_message = await render_screen(client, target, invoice_text, get_invoice_keyboard(deposit_id, lang))
    if invoice_message:
        async with async_session() as session:
            await session.execute(
                update(Deposit)
                .where(Deposit.id == deposit_id)
                .values(user_message_id=invoice_message.id, user_message_is_media=False)
            )
            await session.commit()

def register_wallet_handlers(app: Client):
    @app.on_callback_query(filters.regex(r"^(wallet:(deposit_menu|topup)|wallet_main|account:wallet)$"))
    async def cb_deposit_menu(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        async with async_session() as session:
            res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = res.scalar_one_or_none()
            balance = float(user.balance) if user else 0.0
            active_coupon = getattr(user, "active_coupon_code", None) if user else None
            lang = getattr(user, "language", "es") or "es"
            verifying_stmt = select(Deposit.id).where(
                Deposit.user_id == user_id,
                Deposit.status == DepositStatus.VERIFYING
            )
            if await session.scalar(verifying_stmt):
                await render_screen(client, callback, t("verifying_tx", lang), None)
                return
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            active_stmt = select(Deposit).where(
                Deposit.user_id == user_id,
                Deposit.status == DepositStatus.PENDING,
                Deposit.expires_at > now
            )
            active_res = await session.execute(active_stmt)
            active_dep = active_res.scalar_one_or_none()

            if active_dep:
                invoice_text = t(
                    "invoice_title",
                    lang,
                    exact_val=f"{float(active_dep.exact_amount):.6f}",
                    wallet=settings.ADMIN_WALLET_BSC,
                    expiry_minutes=settings.DEPOSIT_EXPIRY_MINUTES,
                )
                invoice_message = await render_screen(
                    client, callback, invoice_text, get_invoice_keyboard(active_dep.id, lang)
                )
                if invoice_message:
                    active_dep.user_message_id = invoice_message.id
                    active_dep.user_message_is_media = False
                    await session.commit()
                return

        coupon_info = ""
        if active_coupon:
            coupon_info = (
                f"\n\n🎟 <b>Cupón Activo:</b> <code>{active_coupon}</code>\n"
                "<i>(Se aplicará automáticamente un descuento en tu próxima compra del catálogo)</i>"
            )

        text = t(
            "wallet_title",
            lang,
            balance=f"{balance:.6f}",
            min_dep=f"{settings.MIN_DEPOSIT_USDT:.2f}"
        ) + coupon_info
        await render_screen(client, callback, text, get_deposit_menu_keyboard(lang, active_coupon))

    @app.on_callback_query(filters.regex(r"^deposit:amount:(\d+)$"))
    async def cb_deposit_fixed(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        amount = float(callback.matches[0].group(1))

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        await create_deposit_invoice(
            client=client,
            user_id=user_id,
            username=callback.from_user.username or "",
            first_name=callback.from_user.first_name or "Usuario",
            base_amount=amount,
            target=callback,
            lang=lang
        )

    @app.on_callback_query(filters.regex("^deposit:custom$"))
    async def cb_deposit_custom(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        USER_STATES[user_id] = {"action": "waiting_amount"}

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        text = t("custom_amount_prompt", lang, min_dep=f"{settings.MIN_DEPOSIT_USDT:.2f}")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_back", lang), callback_data="wallet:deposit_menu")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^deposit:show_qr:(\d+)$"))
    async def cb_show_qr(client: Client, callback: CallbackQuery):
        """Muestra el QR eliminando el mensaje anterior para que nunca queden fotos duplicadas"""
        user_id = callback.from_user.id
        deposit_id = int(callback.matches[0].group(1))

        async with async_session() as session:
            stmt = select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id)
            res = await session.execute(stmt)
            deposit = res.scalar_one_or_none()

            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

            if not deposit:
                await callback.answer("❌ Error", show_alert=True)
                return

            exact_val = float(deposit.exact_amount)

        qr_media = get_wallet_qr_media()

        caption = t(
            "qr_caption",
            lang,
            exact_val=f"{exact_val:.6f}",
            wallet=settings.ADMIN_WALLET_BSC
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_back_to_invoice", lang), callback_data=f"deposit:view_inv:{deposit_id}")]
        ])

        # Eliminar el mensaje de texto anterior antes de enviar la foto del QR
        try:
            await callback.message.delete()
        except Exception:
            pass

        try:
            photo_msg = await client.send_photo(
                chat_id=callback.message.chat.id,
                photo=qr_media,
                caption=parse_emojis(caption),
                parse_mode=ParseMode.HTML,
                reply_markup=parse_keyboard(keyboard)
            )
            USER_LAST_MESSAGES[user_id] = photo_msg.id
            USER_LAST_MESSAGES_IS_MEDIA[user_id] = True
            async with async_session() as session:
                await session.execute(
                    update(Deposit)
                    .where(Deposit.id == deposit_id, Deposit.user_id == user_id)
                    .values(user_message_id=photo_msg.id, user_message_is_media=True)
                )
                await session.commit()
            await callback.answer()
        except Exception:
            await callback.answer("No se pudo completar la acción.", show_alert=True)

    @app.on_callback_query(filters.regex(r"^deposit:view_inv:(\d+)$"))
    async def cb_view_invoice(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        deposit_id = int(callback.matches[0].group(1))

        async with async_session() as session:
            stmt = select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id)
            res = await session.execute(stmt)
            deposit = res.scalar_one_or_none()

            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

            if not deposit or deposit.status != DepositStatus.PENDING:
                await cb_deposit_menu(client, callback)
                return

            exact_val = float(deposit.exact_amount)

        invoice_text = t(
            "invoice_title",
            lang,
            exact_val=f"{exact_val:.6f}",
            wallet=settings.ADMIN_WALLET_BSC,
            expiry_minutes=settings.DEPOSIT_EXPIRY_MINUTES,
        )

        await render_screen(client, callback, invoice_text, get_invoice_keyboard(deposit_id, lang))

    @app.on_callback_query(filters.regex(r"^deposit:submit_hash:(\d+)$"))
    async def cb_submit_hash(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        deposit_id = int(callback.matches[0].group(1))

        USER_STATES[user_id] = {
            "action": "waiting_hash",
            "deposit_id": deposit_id
        }

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        text = t("submit_hash_prompt", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_back_to_invoice", lang), callback_data=f"deposit:view_inv:{deposit_id}")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^deposit:cancel:(\d+)$"))
    async def cb_deposit_cancel(client: Client, callback: CallbackQuery):
        """Cancela la solicitud de depósito y EDITA el mismo mensaje en el canal de logs"""
        user_id = callback.from_user.id
        deposit_id = int(callback.matches[0].group(1))
        USER_STATES.pop(user_id, None)

        amount_cancelled = 0.0
        log_msg_id = None
        is_verifying = False
        async with async_session() as session:
            stmt = select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id)
            res = await session.execute(stmt)
            dep = res.scalar_one_or_none()

            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

            if dep and dep.status == DepositStatus.PENDING:
                dep.status = DepositStatus.CANCELLED
                amount_cancelled = float(dep.exact_amount)
                log_msg_id = dep.log_message_id
                await session.commit()
            elif dep and dep.status == DepositStatus.VERIFYING:
                is_verifying = True

        if is_verifying:
            await callback.answer("El pago ya se está verificando y no se puede cancelar.", show_alert=True)
            return

        # EDITAR el mismo mensaje en el canal de logs
        await audit_logger.log_deposit_cancelled(
            client=client,
            user_id=user_id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name or "Usuario",
            amount_cancelled=amount_cancelled,
            deposit_id=deposit_id,
            log_message_id=log_msg_id
        )

        cancel_text = t("deposit_cancelled_screen", lang, amount=f"{amount_cancelled:.6f}")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_new_deposit", lang), callback_data="wallet:deposit_menu")],
            [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
        ])

        await callback.answer("Solicitud cancelada.")
        await render_screen(client, callback, cancel_text, keyboard)

    @app.on_callback_query(filters.regex(r"^deposit:review:add:(\d+)$"))
    async def cb_deposit_review_add(client: Client, callback: CallbackQuery):
        admin_id = callback.from_user.id
        if not settings.is_owner(admin_id):
            await callback.answer("Solo un administrador puede aprobar depósitos.", show_alert=True)
            return
        if not callback.message or callback.message.chat.id != settings.LOG_GROUP_ID:
            await callback.answer("Este botón solo funciona en el canal de logs.", show_alert=True)
            return

        deposit_id = int(callback.matches[0].group(1))
        await callback.answer("Revalidando la transacción en BSC...")

        async with async_session() as session:
            deposit = await session.get(Deposit, deposit_id)
            if not deposit or deposit.status != DepositStatus.REVIEW or not deposit.tx_hash:
                await client.send_message(settings.LOG_GROUP_ID, f"DEP_{deposit_id}: ya fue revisado o no está disponible.")
                return
            tx_hash = deposit.tx_hash
            expected_amount = float(deposit.exact_amount)

        verification = await bsc_validator.verify_deposit(tx_hash, expected_amount)
        if not verification.get("success"):
            error = html.escape(str(verification.get("error", "Transacción no válida")))
            await client.send_message(
                settings.LOG_GROUP_ID,
                f"⚠️ DEP_{deposit_id} sigue pendiente: {error}",
            )
            return

        credit_result = None
        try:
            async with async_session() as session:
                deposit = await session.scalar(
                    select(Deposit).where(Deposit.id == deposit_id).with_for_update()
                )
                if not deposit or deposit.status != DepositStatus.REVIEW or deposit.tx_hash != tx_hash:
                    await client.send_message(settings.LOG_GROUP_ID, f"DEP_{deposit_id}: ya fue procesado.")
                    return

                duplicate = await session.scalar(
                    select(Deposit.id).where(Deposit.tx_hash == tx_hash, Deposit.id != deposit_id)
                )
                if duplicate:
                    await client.send_message(settings.LOG_GROUP_ID, f"DEP_{deposit_id}: el hash ya pertenece a otro depósito.")
                    return

                amount = Decimal(str(deposit.exact_amount))
                credit_result = await credit_deposit_in_session(
                    session, deposit, amount, deposit.block_number
                )
                await session.commit()
        except IntegrityError:
            await client.send_message(settings.LOG_GROUP_ID, f"DEP_{deposit_id}: el hash ya fue utilizado.")
            return

        if not credit_result:
            return
        await process_pending_financial_notifications(client, deposit_id=deposit_id)

    @app.on_callback_query(filters.regex(r"^wallet:redeem_gift$"))
    async def cb_wallet_redeem_gift(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass
        user_id = callback.from_user.id
        USER_STATES[user_id] = {"action": "waiting_gift_code"}

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        text = (
            "🎁 <b>CANJEAR TARJETA DE REGALO</b>\n\n"
            "Ingresa el código de tu tarjeta de regalo para acreditar saldo USDT de inmediato en tu billetera.\n\n"
            "<i>Ejemplo: Envía un mensaje con <code>GIFT-ABCD-1234</code></i>\n\n"
            "• El saldo acreditado nunca expira.\n"
            "• Puedes usarlo para comprar cualquier servicio digital del catálogo."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_back", lang), callback_data="wallet:deposit_menu")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^wallet:redeem_coupon$"))
    async def cb_wallet_redeem_coupon(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass
        user_id = callback.from_user.id
        USER_STATES[user_id] = {"action": "waiting_coupon_code"}

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        text = (
            "🎟️ <b>RECLAMAR CUPÓN DE DESCUENTO</b>\n\n"
            "Ingresa el código promocional para activarlo en tu cuenta.\n\n"
            "<i>Ejemplo: Envía un mensaje con <code>PROMO10</code> o <code>BIENVENIDA</code></i>\n\n"
            "• El descuento se calculará y aplicará automáticamente en tu próxima compra.\n"
            "• Puedes cambiar o quitar tu cupón activo en cualquier momento desde tu billetera."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_back", lang), callback_data="wallet:deposit_menu")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^wallet:remove_coupon$"))
    async def cb_wallet_remove_coupon(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        USER_STATES.pop(user_id, None)

        async with async_session() as session:
            await session.execute(
                update(User).where(User.telegram_id == user_id).values(active_coupon_code=None)
            )
            await session.commit()

        try:
            await callback.answer("🎟️ Cupón retirado con éxito.", show_alert=False)
        except Exception:
            pass

        await cb_deposit_menu(client, callback)

    @app.on_message(filters.command(["depositar", "deposit", "saldo", "wallet"]) & filters.private)
    async def cmd_deposit(client: Client, message: Message):
        user_id = message.from_user.id
        try:
            await message.delete()
        except Exception:
            pass

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            balance = float(user.balance) if user else 0.0
            active_coupon = getattr(user, "active_coupon_code", None) if user else None
            lang = getattr(user, "language", "es") or "es"

            verifying_stmt = select(Deposit.id).where(
                Deposit.user_id == user_id,
                Deposit.status == DepositStatus.VERIFYING
            )
            if await session.scalar(verifying_stmt):
                await render_screen(client, user_id, t("verifying_tx", lang), None)
                return

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            active_stmt = select(Deposit).where(
                Deposit.user_id == user_id,
                Deposit.status == DepositStatus.PENDING,
                Deposit.expires_at > now
            )
            active_res = await session.execute(active_stmt)
            active_dep = active_res.scalar_one_or_none()

            if active_dep:
                exact_val = float(active_dep.exact_amount)
                invoice_text = t(
                    "invoice_title",
                    lang,
                    exact_val=f"{exact_val:.6f}",
                    wallet=settings.ADMIN_WALLET_BSC,
                    expiry_minutes=settings.DEPOSIT_EXPIRY_MINUTES,
                )
                invoice_message = await render_screen(
                    client, user_id, invoice_text, get_invoice_keyboard(active_dep.id, lang)
                )
                if invoice_message:
                    active_dep.user_message_id = invoice_message.id
                    active_dep.user_message_is_media = False
                    await session.commit()
                return

        coupon_info = ""
        if active_coupon:
            coupon_info = (
                f"\n\n🎟️ <b>Cupón Activo:</b> <code>{active_coupon}</code>\n"
                f"<i>(Se aplicará automáticamente un descuento en tu próxima compra del catálogo)</i>"
            )

        text = t("wallet_title", lang, balance=f"{balance:.6f}", min_dep=f"{settings.MIN_DEPOSIT_USDT:.2f}") + coupon_info
        await render_screen(client, user_id, text, get_deposit_menu_keyboard(lang, active_coupon))

    @app.on_message(filters.private & filters.text & ~filters.command(["start", "admin", "orderresolve", "vnumresolve", "buscar", "search", "catalogo", "catalog", "pedidos", "orders", "depositar", "deposit", "saldo", "wallet", "soporte", "support", "ayuda", "help", "del", "dep"]), group=2)
    async def handle_text_inputs(client: Client, message: Message):
        user_id = message.from_user.id
        state = USER_STATES.get(user_id)
        if not state:
            message.continue_propagation()
            return

        try:
            await message.delete()
        except Exception:
            pass

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        action = state.get("action")

        # 1. Esperando monto personalizado
        if action == "waiting_amount":
            text_val = message.text.strip().replace(",", ".")
            try:
                amount = float(text_val)
            except (ValueError, TypeError):
                amount = None

            if amount is None or math.isnan(amount) or math.isinf(amount) or amount < settings.MIN_DEPOSIT_USDT or amount > 10000.0:
                err_text = f"⚠️ {t('custom_amount_prompt', lang, min_dep=f'{settings.MIN_DEPOSIT_USDT:.2f}')}"
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_back", lang), callback_data="wallet:deposit_menu")]])
                await render_screen(client, user_id, err_text, kb)
                return

            USER_STATES.pop(user_id, None)
            await create_deposit_invoice(
                client=client,
                user_id=user_id,
                username=message.from_user.username or "",
                first_name=message.from_user.first_name or "Usuario",
                base_amount=amount,
                target=user_id,
                lang=lang
            )

        # 2. Esperando TxHash
        elif action == "waiting_hash":
            deposit_id = state.get("deposit_id")
            tx_hash = message.text.strip().lower()

            if not re.match(r'^(0x)?[a-f0-9]{64}$', tx_hash):
                retry_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_submit_hash", lang), callback_data=f"deposit:submit_hash:{deposit_id}")],
                    [InlineKeyboardButton(t("btn_cancel_request", lang), callback_data=f"deposit:cancel:{deposit_id}")]
                ])
                await render_screen(client, user_id, "❌ <b>Formato de Hash / TxID Inválido</b>\n\nEl Hash de transacción de BSC (BEP-20) debe tener 64 caracteres hexadecimales (ejemplo: <code>0xabc123...</code>). Verifica y vuelve a intentarlo.", retry_kb)
                return
            if not tx_hash.startswith("0x"):
                tx_hash = f"0x{tx_hash}"

            if tx_hash in _ACTIVE_HASH_VERIFICATIONS:
                await message.reply_text("⏳ Este hash ya está siendo verificado en este momento. Por favor espera.")
                return

            _ACTIVE_HASH_VERIFICATIONS.add(tx_hash)
            USER_STATES.pop(user_id, None)

            try:
                await render_screen(
                    client,
                    user_id,
                    t("verifying_tx", lang),
                    None
                )

                try:
                    async with async_session() as session:
                        stmt = select(Deposit).where(
                            Deposit.id == deposit_id,
                            Deposit.user_id == user_id
                        ).with_for_update()
                        res = await session.execute(stmt)
                        deposit = res.scalar_one_or_none()
                        now = datetime.now(timezone.utc).replace(tzinfo=None)
                        if not deposit or deposit.status != DepositStatus.PENDING or deposit.expires_at <= now:
                            if deposit and deposit.status == DepositStatus.PENDING:
                                deposit.status = DepositStatus.EXPIRED
                                await session.commit()
                            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]])
                            await render_screen(client, user_id, "❌ La solicitud de depósito ya venció, fue cancelada o no está disponible.", kb)
                            return

                        duplicate = await session.scalar(
                            select(Deposit.id).where(
                                Deposit.tx_hash == tx_hash,
                                Deposit.id != deposit_id
                            )
                        )
                        if duplicate:
                            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]])
                            await render_screen(client, user_id, "❌ Este Hash / TxID ya fue utilizado o está siendo verificado.", kb)
                            return

                        deposit.status = DepositStatus.VERIFYING
                        deposit.tx_hash = tx_hash
                        deposit.verification_started_at = now
                        expected_amount = float(deposit.exact_amount)
                        await session.commit()
                except IntegrityError:
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]])
                    await render_screen(client, user_id, "❌ Este Hash / TxID ya fue utilizado o está siendo verificado.", kb)
                    return

                try:
                    val_res = await bsc_validator.verify_deposit(tx_hash, expected_amount)
                except Exception as exc:
                    val_res = {"success": False, "error": str(exc)}

                if not val_res.get("success"):
                    async with async_session() as session:
                        stmt = select(Deposit).where(
                            Deposit.id == deposit_id,
                            Deposit.user_id == user_id
                        ).with_for_update()
                        res = await session.execute(stmt)
                        deposit = res.scalar_one_or_none()
                        if deposit and deposit.status == DepositStatus.VERIFYING and deposit.tx_hash == tx_hash:
                            now = datetime.now(timezone.utc).replace(tzinfo=None)
                            deposit.status = DepositStatus.PENDING if deposit.expires_at > now else DepositStatus.EXPIRED
                            deposit.tx_hash = None
                            deposit.verification_started_at = None
                            await session.commit()

                    err_msg = val_res.get("error", "Invalid Tx")
                    retry_kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton(t("btn_submit_hash", lang), callback_data=f"deposit:submit_hash:{deposit_id}")],
                        [InlineKeyboardButton(t("btn_cancel_request", lang), callback_data=f"deposit:cancel:{deposit_id}")]
                    ])
                    await render_screen(client, user_id, f"❌ <b>Error:</b>\n{html.escape(str(err_msg))}", retry_kb)
                    return

                async with async_session() as session:
                    stmt = select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id).with_for_update()
                    res = await session.execute(stmt)
                    deposit = res.scalar_one_or_none()

                    if not deposit or deposit.status != DepositStatus.VERIFYING or deposit.tx_hash != tx_hash:
                        kb = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]])
                        await render_screen(client, user_id, "❌ La verificación del depósito dejó de estar disponible. Inténtalo de nuevo.", kb)
                        return

                    credited_amount = Decimal(str(val_res["amount"]))
                    credit_result = await credit_deposit_in_session(
                        session,
                        deposit,
                        credited_amount,
                        val_res.get("block_number"),
                    )
                    new_balance = float(credit_result["balance"])

                    await session.commit()
            finally:
                _ACTIVE_HASH_VERIFICATIONS.discard(tx_hash)

            await process_pending_financial_notifications(client, deposit_id=deposit_id)
            return

        # 3. Esperando Código de Tarjeta de Regalo
        elif action == "waiting_gift_code":
            code = message.text.strip().upper()
            USER_STATES.pop(user_id, None)

            async with async_session() as session:
                ok, msg, amount = await promo_service.redeem_gift_card(session, code, user_id)
                user_stmt = select(User).where(User.telegram_id == user_id)
                u_res = await session.execute(user_stmt)
                user = u_res.scalar_one_or_none()
                new_balance = float(user.balance) if user else 0.0

            if not ok:
                err_text = f"{msg}\n\n<i>Verifica que hayas escrito el código correctamente.</i>"
                retry_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Intentar de Nuevo", callback_data="wallet:redeem_gift")],
                    [InlineKeyboardButton("🔙 Volver a Billetera", callback_data="wallet:deposit_menu")]
                ])
                await render_screen(client, user_id, err_text, retry_kb)
                return

            # Log a canal de auditoría
            username = message.from_user.username
            first_name = html.escape(message.from_user.first_name or "Usuario")
            user_mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
            audit_text = (
                f"🎁 <b>TARJETA DE REGALO CANJEADA</b>\n\n"
                f"👤 <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
                f"💵 <b>Monto Acreditado:</b> <code>+${amount:.2f} USDT</code>\n"
                f"💳 <b>Nuevo Saldo Total:</b> <code>${new_balance:.2f} USDT</code>\n"
                f"🏷️ <b>Código:</b> <code>{html.escape(code)}</code>"
            )
            try:
                await audit_logger._send_log(client, audit_text)
            except Exception:
                pass

            succ_text = (
                f"🎉 <b>¡TARJETA DE REGALO CANJEADA CON ÉXITO!</b>\n\n"
                f"💵 <b>Saldo Acreditado:</b> <code>+${amount:.2f} USDT</code>\n"
                f"💳 <b>Tu Nuevo Saldo:</b> <code>${new_balance:.2f} USDT</code>\n\n"
                f"<i>¡Ya puedes usar tu saldo para comprar cualquier servicio digital en el catálogo!</i>"
            )
            succ_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Ir al Catálogo", callback_data="catalog:disponibles:1")],
                [InlineKeyboardButton("💳 Ver Mi Billetera", callback_data="wallet:deposit_menu")]
            ])
            await render_screen(client, user_id, succ_text, succ_kb)
            return

        # 4. Esperando Código de Cupón de Descuento
        elif action == "waiting_coupon_code":
            code = message.text.strip().upper()
            USER_STATES.pop(user_id, None)

            async with async_session() as session:
                ok, msg, c_obj, disc = await promo_service.validate_coupon(
                    session=session,
                    code=code,
                    user_id=user_id,
                    cart_amount=999.0
                )
                if not ok or not c_obj:
                    err_text = f"{msg}\n\n<i>Verifica que hayas escrito el código correctamente.</i>"
                    retry_kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Intentar de Nuevo", callback_data="wallet:redeem_coupon")],
                        [InlineKeyboardButton("🔙 Volver a Billetera", callback_data="wallet:deposit_menu")]
                    ])
                    await render_screen(client, user_id, err_text, retry_kb)
                    return

                await session.execute(
                    update(User).where(User.telegram_id == user_id).values(active_coupon_code=c_obj.code)
                )
                await session.commit()

            if c_obj.discount_type == "percent":
                benefit_str = f"{float(c_obj.discount_value):.0f}% de descuento"
            else:
                benefit_str = f"${float(c_obj.discount_value):.2f} USDT de descuento"

            succ_text = (
                f"🎉 <b>¡CUPÓN ACTIVADO CON ÉXITO!</b>\n\n"
                f"🎟️ <b>Cupón:</b> <code>{c_obj.code}</code>\n"
                f"🏷️ <b>Beneficio:</b> <code>{benefit_str}</code>\n\n"
                f"<i>¡Se aplicará automáticamente un descuento en tu próxima compra del catálogo!</i>"
            )
            succ_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Ir al Catálogo", callback_data="catalog:disponibles:1")],
                [InlineKeyboardButton("💳 Ver Mi Billetera", callback_data="wallet:deposit_menu")]
            ])
            await render_screen(client, user_id, succ_text, succ_kb)
            return

    # ==========================================
    # 📜 5. HISTORIAL Y EXTRACTO DE MOVIMIENTOS
    # ==========================================

    @app.on_callback_query(filters.regex(r"^wallet:transactions:(\d+)$"))
    async def cb_wallet_transactions(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        page = int(callback.matches[0].group(1))
        page_size = 5

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"
            bal = float(user.balance) if user else 0.0

            # 1. Obtener depósitos confirmados
            dep_stmt = (
                select(Deposit)
                .where(Deposit.user_id == user_id, Deposit.status == DepositStatus.CONFIRMED)
            )
            dep_res = await session.execute(dep_stmt)
            deposits = dep_res.scalars().all()

            # 2. Obtener órdenes de productos
            ord_stmt = select(Order).where(
                Order.user_id == user_id,
                Order.status == "COMPLETED"
            )
            ord_res = await session.execute(ord_stmt)
            orders = ord_res.scalars().all()

            # 3. Obtener órdenes de números virtuales
            vnum_stmt = select(VirtualNumberOrder).where(VirtualNumberOrder.user_id == user_id)
            vnum_res = await session.execute(vnum_stmt)
            vnums = vnum_res.scalars().all()

        # Construir lista combinada de movimientos
        events = []
        for d in deposits:
            events.append({
                "type": "deposit",
                "date": d.confirmed_at or d.created_at,
                "title": "Recarga de Saldo (USDT BEP-20)",
                "amount": f"+${float(d.exact_amount):.6f} USDT",
                "is_credit": True
            })

        for o in orders:
            events.append({
                "type": "order",
                "date": o.created_at,
                "title": f"Compra: {o.product_name[:25]}",
                "amount": f"-${float(o.total_price):.2f} USDT",
                "is_credit": False
            })

        for v in vnums:
            if v.status in ["RECEIVED", "FINISHED"]:
                events.append({
                    "type": "vnum",
                    "date": v.created_at,
                    "title": f"Número Virtual: {v.service_name.upper()} ({v.country.upper()})",
                    "amount": f"-${float(v.price_usdt):.2f} USDT",
                    "is_credit": False
                })
            elif v.is_refunded:
                events.append({
                    "type": "refund",
                    "date": v.created_at,
                    "title": f"Reembolso Número: {v.service_name.upper()}",
                    "amount": f"+${float(v.price_usdt):.2f} USDT",
                    "is_credit": True
                })

        # Ordenar por fecha descendente
        events.sort(key=lambda x: x["date"] or datetime.min, reverse=True)

        total_events = len(events)
        if total_events == 0:
            empty_text = (
                f"📜 <b>HISTORIAL DE MOVIMIENTOS</b>\n\n"
                f"💳 <b>Saldo Actual:</b> <code>${bal:.2f} USDT</code>\n\n"
                f"<i>Aún no tienes movimientos registrados en tu billetera.</i>"
            )
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_back", lang), callback_data="wallet:deposit_menu")]])
            await render_screen(client, callback, empty_text, keyboard)
            return

        total_pages = max(1, (total_events + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size
        page_events = events[offset:offset + page_size]

        lines = []
        for ev in page_events:
            d_str = ev["date"].strftime("%Y-%m-%d %H:%M") if ev["date"] else "N/A"
            icon = get_movement_emoji(ev["is_credit"])
            safe_title = html.escape(ev['title'])
            lines.append(
                f"{icon} <b>{safe_title}</b>\n"
                f"   💵 <code>{ev['amount']}</code> | 🕒 <code>{d_str}</code>"
            )

        header = (
            f"📜 <b>EXTRACTO DE MOVIMIENTOS</b>\n\n"
            f"💳 <b>Saldo Actual:</b> <code>${bal:.2f} USDT</code>\n"
            f"📄 <b>Página:</b> <code>{page}/{total_pages}</code> ({total_events} registros)\n\n"
        )
        text = header + "\n\n".join(lines)

        buttons = []
        if total_pages > 1:
            nav_row = []
            if page > 1:
                nav_row.append(InlineKeyboardButton("◀️", callback_data=f"wallet:transactions:{page - 1}"))
            else:
                nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))
            nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
            if page < total_pages:
                nav_row.append(InlineKeyboardButton("▶️", callback_data=f"wallet:transactions:{page + 1}"))
            else:
                nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))
            buttons.append(nav_row)

        buttons.append([InlineKeyboardButton(t("btn_back", lang), callback_data="account:view")])
        await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))
