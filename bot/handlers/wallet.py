import random
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Any
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from sqlalchemy import select, update
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Deposit, DepositStatus
from bot.services.blockchain import bsc_validator
from bot.services.audit_logger import audit_logger
from bot.services.qr_generator import get_wallet_qr_media
from bot.utils.navigation import render_screen, USER_LAST_MESSAGES, USER_LAST_MESSAGES_IS_MEDIA
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.emojis import parse_emojis, parse_keyboard

USER_STATES: Dict[int, Dict[str, Any]] = {}

def get_deposit_menu_keyboard(lang: str = "es") -> InlineKeyboardMarkup:
    """Botonera con montos rápidos de recarga traducida"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💵 2 USDT", callback_data="deposit:amount:2"),
            InlineKeyboardButton("💵 5 USDT", callback_data="deposit:amount:5"),
            InlineKeyboardButton("💵 10 USDT", callback_data="deposit:amount:10")
        ],
        [
            InlineKeyboardButton("💵 20 USDT", callback_data="deposit:amount:20"),
            InlineKeyboardButton("💵 50 USDT", callback_data="deposit:amount:50")
        ],
        [
            InlineKeyboardButton(t("btn_custom_amount", lang), callback_data="deposit:custom")
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
        now = datetime.utcnow()
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

    @app.on_callback_query(filters.regex(r"^wallet:(deposit_menu|topup)$"))
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
            lang = getattr(user, "language", "es") or "es"

            # Comprobar si el usuario tiene una solicitud de depósito activa pendiente
            now = datetime.utcnow()
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

        text = t("wallet_title", lang, balance=f"{balance:.4f}", min_dep=f"{settings.MIN_DEPOSIT_USDT:.2f}")
        await render_screen(client, callback, text, get_deposit_menu_keyboard(lang))

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
            lang = getattr(user, "language", "es") or "es"

            now = datetime.utcnow()
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

        text = t("wallet_title", lang, balance=f"{balance:.4f}", min_dep=f"{settings.MIN_DEPOSIT_USDT:.2f}")
        await render_screen(client, user_id, text, get_deposit_menu_keyboard(lang))

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
            tx_hash = message.text.strip()

            USER_STATES.pop(user_id, None)
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

                dup_stmt = select(Deposit).where(Deposit.tx_hash == tx_hash, Deposit.status == DepositStatus.CONFIRMED).with_for_update()
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
                deposit.confirmed_at = datetime.utcnow()
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
                        comm_rate = Decimal(str(settings.REFERRAL_COMMISSION_PERCENT)) / Decimal("100")
                        commission = credited_amount * comm_rate
                        referrer.balance += commission

                await session.commit()

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
