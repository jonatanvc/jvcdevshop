import random
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Set, Optional
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from sqlalchemy import select, update
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Deposit, DepositStatus, Order, VirtualNumberOrder
from bot.services.blockchain import bsc_validator
from bot.services.audit_logger import audit_logger
from bot.services.qr_generator import get_wallet_qr_media
from bot.services.promos import promo_service
from bot.utils.navigation import render_screen, USER_LAST_MESSAGES, USER_LAST_MESSAGES_IS_MEDIA
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.emojis import parse_emojis, parse_keyboard

USER_STATES: Dict[int, Dict[str, Any]] = {}
_ACTIVE_HASH_VERIFICATIONS: Set[str] = set()

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
            InlineKeyboardButton("📜 Historial de Movimientos", callback_data="wallet:transactions:1")
        ],
        [
            InlineKeyboardButton(t("btn_back", lang), callback_data="menu_main")
        ]
    ])

def get_invoice_keyboard(deposit_id: int, lang: str = "es") -> InlineKeyboardMarkup:
    """Botonera de la pantalla de pago: NO permite salir al menú principal sin cancelar primero"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_show_qr", lang), callback_data=f"deposit:show_qr:{deposit_id}")
        ],
        [
            InlineKeyboardButton(t("btn_submit_hash", lang), callback_data=f"deposit:submit_hash:{deposit_id}")
        ],
        [
            InlineKeyboardButton(t("btn_verify_payment", lang), callback_data=f"deposit:submit_hash:{deposit_id}")
        ],
        [
            InlineKeyboardButton(t("btn_cancel_request", lang), callback_data=f"deposit:cancel:{deposit_id}")
        ]
    ])

async def create_deposit_invoice(client: Client, user_id: int, username: str, first_name: str, base_amount: float, target, lang: str = "es") -> None:
    """Crea la solicitud de depósito y guarda el log_message_id para editar el mismo mensaje en logs"""
    async with async_session() as session:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at = now + timedelta(minutes=30)

        # Si ya existe una solicitud PENDING activa previa, la marcamos como expirada
        cancel_old_stmt = (
            update(Deposit)
            .where(Deposit.user_id == user_id, Deposit.status == DepositStatus.PENDING)
            .values(status=DepositStatus.EXPIRED)
        )
        await session.execute(cancel_old_stmt)

        for _ in range(50):
            rand_suffix = random.randint(100, 999) / 10000.0
            exact_val = round(base_amount + rand_suffix, 4)
            exact_dec = Decimal(str(exact_val))

            dup_stmt = select(Deposit).where(
                Deposit.exact_amount == exact_dec,
                Deposit.status == DepositStatus.PENDING,
                Deposit.expires_at > now
            )
            dup_res = await session.execute(dup_stmt)
            if not dup_res.scalar_one_or_none():
                break

        # Notificar solicitud en canal de auditoría y capturar el ID del mensaje
        log_msg_id = await audit_logger.log_deposit_request(
            client=client,
            user_id=user_id,
            username=username,
            first_name=first_name,
            base_amount=base_amount,
            exact_amount=float(exact_dec)
        )

        new_deposit = Deposit(
            user_id=user_id,
            base_amount=Decimal(str(base_amount)),
            exact_amount=exact_dec,
            status=DepositStatus.PENDING,
            expires_at=expires_at,
            created_at=now,
            log_message_id=log_msg_id
        )
        session.add(new_deposit)
        await session.commit()
        await session.refresh(new_deposit)
        deposit_id = new_deposit.id

    invoice_text = t(
        "invoice_title",
        lang,
        exact_val=f"{exact_val:.4f}",
        wallet=settings.ADMIN_WALLET_BSC
    )

    await render_screen(client, target, invoice_text, get_invoice_keyboard(deposit_id, lang))

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
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            balance = float(user.balance) if user else 0.0
            active_coupon = getattr(user, "active_coupon_code", None) if user else None
            lang = getattr(user, "language", "es") or "es"

            # Comprobar si el usuario tiene una solicitud de depósito activa pendiente
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            active_stmt = select(Deposit).where(
                Deposit.user_id == user_id,
                Deposit.status == DepositStatus.PENDING,
                Deposit.expires_at > now
            )
            active_res = await session.execute(active_stmt)
            active_dep = active_res.scalar_one_or_none()

            # Si tiene una solicitud activa, mostrarle la factura para que pague o cancele antes de continuar
            if active_dep:
                exact_val = float(active_dep.exact_amount)
                invoice_text = t(
                    "invoice_title",
                    lang,
                    exact_val=f"{exact_val:.4f}",
                    wallet=settings.ADMIN_WALLET_BSC
                )
                await render_screen(client, callback, invoice_text, get_invoice_keyboard(active_dep.id, lang))
                return

        coupon_info = ""
        if active_coupon:
            coupon_info = (
                f"\n\n🎟️ <b>Cupón Activo:</b> <code>{active_coupon}</code>\n"
                f"<i>(Se aplicará automáticamente un descuento en tu próxima compra del catálogo)</i>"
            )

        text = t("wallet_title", lang, balance=f"{balance:.4f}", min_dep=f"{settings.MIN_DEPOSIT_USDT:.2f}") + coupon_info
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
            exact_val=f"{exact_val:.4f}",
            wallet=settings.ADMIN_WALLET_BSC
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_submit_hash", lang), callback_data=f"deposit:submit_hash:{deposit_id}")],
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
            await callback.answer()
        except Exception as e:
            await callback.answer(f"Error: {e}", show_alert=True)

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
            exact_val=f"{exact_val:.4f}",
            wallet=settings.ADMIN_WALLET_BSC
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
        async with async_session() as session:
            stmt = select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id)
            res = await session.execute(stmt)
            dep = res.scalar_one_or_none()

            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

            if dep and dep.status == DepositStatus.PENDING:
                dep.status = DepositStatus.EXPIRED
                amount_cancelled = float(dep.exact_amount)
                log_msg_id = dep.log_message_id
                await session.commit()

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

        cancel_text = t("deposit_cancelled_screen", lang, amount=f"{amount_cancelled:.4f}")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_new_deposit", lang), callback_data="wallet:deposit_menu")],
            [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
        ])

        await callback.answer("Solicitud cancelada.")
        await render_screen(client, callback, cancel_text, keyboard)

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
                    exact_val=f"{exact_val:.4f}",
                    wallet=settings.ADMIN_WALLET_BSC
                )
                await render_screen(client, user_id, invoice_text, get_invoice_keyboard(active_dep.id, lang))
                return

        coupon_info = ""
        if active_coupon:
            coupon_info = (
                f"\n\n🎟️ <b>Cupón Activo:</b> <code>{active_coupon}</code>\n"
                f"<i>(Se aplicará automáticamente un descuento en tu próxima compra del catálogo)</i>"
            )

        text = t("wallet_title", lang, balance=f"{balance:.4f}", min_dep=f"{settings.MIN_DEPOSIT_USDT:.2f}") + coupon_info
        await render_screen(client, user_id, text, get_deposit_menu_keyboard(lang, active_coupon))

    @app.on_message(filters.private & filters.text & ~filters.command(["start", "admin", "buscar", "search", "catalogo", "catalog", "pedidos", "orders", "depositar", "deposit", "saldo", "wallet", "soporte", "support", "ayuda", "help", "del", "dep"]), group=2)
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
            except ValueError:
                err_text = f"❌ Error. {t('custom_amount_prompt', lang, min_dep=f'{settings.MIN_DEPOSIT_USDT:.2f}')}"
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_back", lang), callback_data="wallet:deposit_menu")]])
                await render_screen(client, user_id, err_text, kb)
                return

            if amount < settings.MIN_DEPOSIT_USDT:
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

                log_msg_id = None
                async with async_session() as session:
                    stmt = select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id).with_for_update()
                    res = await session.execute(stmt)
                    deposit = res.scalar_one_or_none()

                    if not deposit or deposit.status == DepositStatus.CONFIRMED:
                        kb = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]])
                        await render_screen(client, user_id, "❌ Solicitud no disponible o ya confirmada.", kb)
                        return

                    dup_stmt = select(Deposit).where(Deposit.tx_hash == tx_hash).with_for_update()
                    dup_res = await session.execute(dup_stmt)
                    if dup_res.scalar_one_or_none():
                        kb = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]])
                        await render_screen(client, user_id, "❌ Este Hash / TxID ya fue utilizado y acreditado anteriormente.", kb)
                        return

                    val_res = await bsc_validator.verify_deposit(tx_hash, float(deposit.exact_amount))

                    if not val_res.get("success"):
                        err_msg = val_res.get("error", "Invalid Tx")
                        retry_kb = InlineKeyboardMarkup([
                            [InlineKeyboardButton(t("btn_submit_hash", lang), callback_data=f"deposit:submit_hash:{deposit_id}")],
                            [InlineKeyboardButton(t("btn_cancel_request", lang), callback_data=f"deposit:cancel:{deposit_id}")]
                        ])
                        await render_screen(client, user_id, f"❌ <b>Error:</b>\n{err_msg}", retry_kb)
                        return

                    credited_amount = Decimal(str(val_res["amount"]))
                    deposit.status = DepositStatus.CONFIRMED
                    deposit.tx_hash = tx_hash
                    deposit.confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    log_msg_id = deposit.log_message_id

                    user_stmt = select(User).where(User.telegram_id == user_id).with_for_update()
                    u_res = await session.execute(user_stmt)
                    user = u_res.scalar_one_or_none()
                    user.balance += credited_amount
                    new_balance = float(user.balance)

                    if user.referred_by:
                        ref_stmt = select(User).where(User.telegram_id == user.referred_by).with_for_update()
                        ref_res = await session.execute(ref_stmt)
                        referrer = ref_res.scalar_one_or_none()
                        if referrer:
                            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                            is_ref_vip = bool(referrer.is_vip and referrer.vip_expires_at and referrer.vip_expires_at > now_utc)
                            comm_pct = settings.VIP_REFERRAL_COMMISSION_PERCENT if is_ref_vip else settings.REFERRAL_COMMISSION_PERCENT
                            comm_rate = Decimal(str(comm_pct)) / Decimal("100")
                            commission = credited_amount * comm_rate
                            referrer.balance += commission

                            ref_uid = referrer.telegram_id
                            ref_lang = referrer.language or "es"
                            ref_new_bal = float(referrer.balance)
                            ref_comm_val = float(commission)
                            user_tag = f"@{message.from_user.username}" if message.from_user.username else f"Usuario #{user_id}"

                            try:
                                ref_msg = (
                                    f"🎉 <b>¡Comisión de Referido Recibida!</b>\n\n"
                                    f"Tu referido <b>{user_tag}</b> acaba de realizar una recarga de saldo.\n\n"
                                    f"➕ <b>Comisión acreditada:</b> <code>+${ref_comm_val:.2f} USDT</code>\n"
                                    f"👛 <b>Tu nuevo saldo:</b> <code>${ref_new_bal:.2f} USDT</code>\n\n"
                                    f"<i>¡Gracias por recomendar nuestro servicio!</i>"
                                )
                                if ref_lang == "en":
                                    ref_msg = (
                                        f"🎉 <b>Referral Commission Received!</b>\n\n"
                                        f"Your referral <b>{user_tag}</b> has just completed a balance deposit.\n\n"
                                        f"➕ <b>Credited Commission:</b> <code>+${ref_comm_val:.2f} USDT</code>\n"
                                        f"👛 <b>Your New Balance:</b> <code>${ref_new_bal:.2f} USDT</code>\n\n"
                                        f"<i>Thank you for sharing our store!</i>"
                                    )
                                elif ref_lang == "pt":
                                    ref_msg = (
                                        f"🎉 <b>Comissão de Indicação Recebida!</b>\n\n"
                                        f"Seu indicado <b>{user_tag}</b> acabou de recarregar saldo.\n\n"
                                        f"➕ <b>Comissão creditada:</b> <code>+${ref_comm_val:.2f} USDT</code>\n"
                                        f"👛 <b>Seu novo saldo:</b> <code>${ref_new_bal:.2f} USDT</code>\n\n"
                                        f"<i>Obrigado por recomendar nosso serviço!</i>"
                                    )
                                asyncio.create_task(client.send_message(
                                    chat_id=ref_uid,
                                    text=parse_emojis(ref_msg),
                                    reply_markup=parse_keyboard(InlineKeyboardMarkup([[InlineKeyboardButton("👛 Ver Mi Billetera", callback_data="wallet:deposit_menu")]])),
                                    disable_web_page_preview=True
                                ))
                            except Exception as e:
                                print(f"[ReferralDM Error]: {e}")

                    await session.commit()
            finally:
                _ACTIVE_HASH_VERIFICATIONS.discard(tx_hash)

            # EDITAR el mismo mensaje en el canal de logs
            await audit_logger.log_deposit_confirmed(
                client=client,
                user_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name or "Usuario",
                amount=float(credited_amount),
                tx_hash=tx_hash,
                new_balance=new_balance,
                deposit_id=deposit_id,
                log_message_id=log_msg_id
            )

            success_text = t("deposit_success_title", lang, amount=f"{float(credited_amount):.4f}", balance=f"{new_balance:.4f}")
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")],
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
            ])
            await render_screen(client, user_id, success_text, keyboard)
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
            first_name = message.from_user.first_name or "Usuario"
            user_mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
            audit_text = (
                f"🎁 <b>TARJETA DE REGALO CANJEADA</b>\n\n"
                f"👤 <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
                f"💵 <b>Monto Acreditado:</b> <code>+${amount:.2f} USDT</code>\n"
                f"💳 <b>Nuevo Saldo Total:</b> <code>${new_balance:.2f} USDT</code>\n"
                f"🏷️ <b>Código:</b> <code>{code}</code>"
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
            ord_stmt = select(Order).where(Order.user_id == user_id)
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
                "amount": f"+${float(d.exact_amount):.2f} USDT",
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
            icon = "🟢" if ev["is_credit"] else "🔴"
            lines.append(
                f"{icon} <b>{ev['title']}</b>\n"
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

        buttons.append([InlineKeyboardButton(t("btn_back", lang), callback_data="wallet:deposit_menu")])
        await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))
