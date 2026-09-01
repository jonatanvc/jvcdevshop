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
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter

USER_STATES: Dict[int, Dict[str, Any]] = {}

def get_deposit_menu_keyboard() -> InlineKeyboardMarkup:
    """Botonera con montos rápidos de recarga (mínimo 2 USDT)"""
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
            InlineKeyboardButton("✍️ Ingresar Otro Monto", callback_data="deposit:custom")
        ],
        [
            InlineKeyboardButton("Volver", callback_data="menu_main")
        ]
    ])

def get_invoice_keyboard(deposit_id: int) -> InlineKeyboardMarkup:
    """Botonera de la pantalla de pago con botón para ver QR y enviar TxID"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Ver Código QR", callback_data=f"deposit:show_qr:{deposit_id}")
        ],
        [
            InlineKeyboardButton("🔗 Ingresar Hash / TxID", callback_data=f"deposit:submit_hash:{deposit_id}")
        ],
        [
            InlineKeyboardButton("🔄 Verificar Pago", callback_data=f"deposit:submit_hash:{deposit_id}")
        ],
        [
            InlineKeyboardButton("❌ Cancelar Solicitud", callback_data=f"deposit:cancel:{deposit_id}"),
            InlineKeyboardButton("Volver", callback_data="menu_main")
        ]
    ])

async def create_deposit_invoice(client: Client, user_id: int, username: str, first_name: str, base_amount: float, target) -> None:
    """Crea la solicitud de depósito con fracción decimal única y renderiza la pantalla de pago"""
    async with async_session() as session:
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=30)

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

        new_deposit = Deposit(
            user_id=user_id,
            base_amount=Decimal(str(base_amount)),
            exact_amount=exact_dec,
            status=DepositStatus.PENDING,
            expires_at=expires_at,
            created_at=now
        )
        session.add(new_deposit)
        await session.commit()
        await session.refresh(new_deposit)
        deposit_id = new_deposit.id

    # Notificar solicitud en canal de auditoría
    await audit_logger.log_deposit_request(
        client=client,
        user_id=user_id,
        username=username,
        first_name=first_name,
        base_amount=base_amount,
        exact_amount=float(exact_dec)
    )

    # Renderizar pantalla de pago
    invoice_text = (
        f"💳 <b>SOLICITUD DE RECARGA USDT (BEP-20)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>IMPORTANTE:</b> Envía <b>EXACTAMENTE</b> la cantidad indicada a continuación para que la acreditación sea automática.\n\n"
        f"🎯 <b>Monto Exacto a Enviar:</b>\n"
        f"<code>{exact_val:.4f}</code> USDT\n\n"
        f"📬 <b>Dirección de Billetera (BNB Smart Chain / BEP-20):</b>\n"
        f"<code>{settings.ADMIN_WALLET_BSC}</code>\n\n"
        f"⏳ <b>Tiempo Límite:</b> <code>30 minutos</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Pulsa '📱 Ver Código QR' para escanear desde tu app o realiza la transferencia y luego pulsa 'Ingresar Hash / TxID'.</i>"
    )

    await render_screen(client, target, invoice_text, get_invoice_keyboard(deposit_id))

def register_wallet_handlers(app: Client):

    @app.on_callback_query(filters.regex("^wallet:deposit_menu$"))
    async def cb_deposit_menu(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer()
            return

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            balance = float(user.balance) if user else 0.0

        text = (
            f"💳 <b>BILLETERA & DEPÓSITOS USDT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Saldo Actual:</b> <code>${balance:.4f} USDT</code>\n"
            f"🌐 <b>Red Aceptada:</b> <code>BNB Smart Chain (BEP-20)</code>\n"
            f"🔒 <b>Depósito Mínimo:</b> <code>${settings.MIN_DEPOSIT_USDT:.2f} USDT</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Selecciona el monto que deseas recargar o pulsa 'Ingresar Otro Monto':</i>"
        )
        await render_screen(client, callback, text, get_deposit_menu_keyboard())

    @app.on_callback_query(filters.regex(r"^deposit:amount:(\d+)$"))
    async def cb_deposit_fixed(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        amount = float(callback.matches[0].group(1))
        await create_deposit_invoice(
            client=client,
            user_id=user_id,
            username=callback.from_user.username or "",
            first_name=callback.from_user.first_name or "Usuario",
            base_amount=amount,
            target=callback
        )

    @app.on_callback_query(filters.regex("^deposit:custom$"))
    async def cb_deposit_custom(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        USER_STATES[user_id] = {"action": "waiting_amount"}

        text = (
            f"✍️ <b>INGRESA EL MONTO A DEPOSITAR</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Escribe la cantidad de USDT que deseas recargar en tu cuenta.\n\n"
            f"⚠️ <b>Monto Mínimo:</b> <code>{settings.MIN_DEPOSIT_USDT:.2f} USDT</code>\n\n"
            f"<i>Ejemplo: Envía un mensaje escribiendo <code>15</code> o <code>25.5</code></i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Volver", callback_data="wallet:deposit_menu")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^deposit:show_qr:(\d+)$"))
    async def cb_show_qr(client: Client, callback: CallbackQuery):
        """Envía la imagen QR oficial de la billetera o el código generado"""
        user_id = callback.from_user.id
        deposit_id = int(callback.matches[0].group(1))

        async with async_session() as session:
            stmt = select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id)
            res = await session.execute(stmt)
            deposit = res.scalar_one_or_none()

            if not deposit:
                await callback.answer("❌ Solicitud no encontrada.", show_alert=True)
                return

            exact_val = float(deposit.exact_amount)

        qr_media = get_wallet_qr_media()

        caption = (
            f"📱 <b>CÓDIGO QR DE PAGO BSC (BEP-20)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Monto a transferir:</b> <code>{exact_val:.4f}</code> USDT\n"
            f"📬 <b>Billetera:</b> <code>{settings.ADMIN_WALLET_BSC}</code>\n\n"
            f"<i>Escanea este código directamente desde Trust Wallet, Binance o MetaMask.</i>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Ingresar Hash / TxID", callback_data=f"deposit:submit_hash:{deposit_id}")],
            [InlineKeyboardButton("🔙 Volver a la Solicitud", callback_data=f"deposit:view_inv:{deposit_id}")]
        ])

        try:
            await client.send_photo(
                chat_id=callback.message.chat.id,
                photo=qr_media,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            await callback.answer("✅ Código QR abierto.")
        except Exception as e:
            await callback.answer(f"Error al cargar QR: {e}", show_alert=True)

    @app.on_callback_query(filters.regex(r"^deposit:view_inv:(\d+)$"))
    async def cb_view_invoice(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        deposit_id = int(callback.matches[0].group(1))

        async with async_session() as session:
            stmt = select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id)
            res = await session.execute(stmt)
            deposit = res.scalar_one_or_none()

            if not deposit or deposit.status != DepositStatus.PENDING:
                await cb_deposit_menu(client, callback)
                return

            exact_val = float(deposit.exact_amount)

        invoice_text = (
            f"💳 <b>SOLICITUD DE RECARGA USDT (BEP-20)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <b>IMPORTANTE:</b> Envía <b>EXACTAMENTE</b> la cantidad indicada a continuación para que la acreditación sea automática.\n\n"
            f"🎯 <b>Monto Exacto a Enviar:</b>\n"
            f"<code>{exact_val:.4f}</code> USDT\n\n"
            f"📬 <b>Dirección de Billetera (BNB Smart Chain / BEP-20):</b>\n"
            f"<code>{settings.ADMIN_WALLET_BSC}</code>\n\n"
            f"⏳ <b>Tiempo Límite:</b> <code>30 minutos</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Pulsa '📱 Ver Código QR' para escanear desde tu app o realiza la transferencia y luego pulsa 'Ingresar Hash / TxID'.</i>"
        )

        await render_screen(client, callback, invoice_text, get_invoice_keyboard(deposit_id))

    @app.on_callback_query(filters.regex(r"^deposit:submit_hash:(\d+)$"))
    async def cb_submit_hash(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        deposit_id = int(callback.matches[0].group(1))

        USER_STATES[user_id] = {
            "action": "waiting_hash",
            "deposit_id": deposit_id
        }

        text = (
            f"🔗 <b>ENVÍA EL HASH / TXID DE LA TRANSACCIÓN</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Pega a continuación el Hash (TxID) de la transferencia realizada desde tu billetera (Trust Wallet, Binance, MetaMask, etc).\n\n"
            f"<i>Ejemplo: <code>0x4a8c9b...</code></i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Volver", callback_data=f"deposit:view_inv:{deposit_id}")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^deposit:cancel:(\d+)$"))
    async def cb_deposit_cancel(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        deposit_id = int(callback.matches[0].group(1))
        USER_STATES.pop(user_id, None)

        async with async_session() as session:
            stmt = select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id)
            res = await session.execute(stmt)
            dep = res.scalar_one_or_none()
            if dep and dep.status == DepositStatus.PENDING:
                dep.status = DepositStatus.EXPIRED
                await session.commit()

        await callback.answer("Solicitud cancelada.")
        await cb_deposit_menu(client, callback)

    @app.on_message(filters.private & filters.text & ~filters.command(["start", "admin", "buscar"]))
    async def handle_text_inputs(client: Client, message: Message):
        user_id = message.from_user.id
        state = USER_STATES.get(user_id)
        if not state:
            return

        # Borrar el mensaje de texto del usuario para mantener la pantalla única limpia
        try:
            await message.delete()
        except Exception:
            pass

        action = state.get("action")

        # 1. Esperando monto personalizado
        if action == "waiting_amount":
            text_val = message.text.strip().replace(",", ".")
            try:
                amount = float(text_val)
            except ValueError:
                err_text = (
                    "❌ Por favor ingresa un número válido (ejemplo: <code>5</code> o <code>12.5</code>).\n\n"
                    f"⚠️ <b>Monto Mínimo:</b> <code>{settings.MIN_DEPOSIT_USDT:.2f} USDT</code>"
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("Volver", callback_data="wallet:deposit_menu")]])
                await render_screen(client, user_id, err_text, kb)
                return

            if amount < settings.MIN_DEPOSIT_USDT:
                err_text = (
                    f"⚠️ El monto mínimo de recarga es de <b>${settings.MIN_DEPOSIT_USDT:.2f} USDT</b>.\n"
                    "Por favor ingresa un monto mayor:"
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("Volver", callback_data="wallet:deposit_menu")]])
                await render_screen(client, user_id, err_text, kb)
                return

            USER_STATES.pop(user_id, None)
            await create_deposit_invoice(
                client=client,
                user_id=user_id,
                username=message.from_user.username or "",
                first_name=message.from_user.first_name or "Usuario",
                base_amount=amount,
                target=user_id
            )

        # 2. Esperando TxHash
        elif action == "waiting_hash":
            deposit_id = state.get("deposit_id")
            tx_hash = message.text.strip()

            USER_STATES.pop(user_id, None)
            await render_screen(
                client,
                user_id,
                "⏳ <b>Verificando transacción en la blockchain BSC...</b>\n<i>Consultando nodos de red y confirmaciones.</i>",
                None
            )

            async with async_session() as session:
                # Bloqueo atómico a nivel de fila (Anti Race-Condition)
                stmt = select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id).with_for_update()
                res = await session.execute(stmt)
                deposit = res.scalar_one_or_none()

                if not deposit or deposit.status != DepositStatus.PENDING:
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Volver", callback_data="wallet:deposit_menu")]])
                    await render_screen(client, user_id, "❌ Esta solicitud de depósito ya expiró o fue procesada.", kb)
                    return

                if datetime.utcnow() > deposit.expires_at:
                    deposit.status = DepositStatus.EXPIRED
                    await session.commit()
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Volver", callback_data="wallet:deposit_menu")]])
                    await render_screen(client, user_id, "❌ El tiempo límite de 30 minutos para este depósito ha expirado. Genera una nueva solicitud.", kb)
                    return

                # Comprobar si el hash ya fue usado antes (Anti-Replay Attack)
                dup_stmt = select(Deposit).where(Deposit.tx_hash == tx_hash, Deposit.status == DepositStatus.CONFIRMED).with_for_update()
                dup_res = await session.execute(dup_stmt)
                if dup_res.scalar_one_or_none():
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Volver", callback_data="wallet:deposit_menu")]])
                    await render_screen(client, user_id, "❌ <b>Este Hash de transacción ya fue reclamado y acreditado previamente.</b>", kb)
                    return

                # Validar On-Chain con Multi-RPC y Confirmaciones
                val_res = await bsc_validator.verify_deposit(tx_hash, float(deposit.exact_amount))

                if not val_res.get("success"):
                    err_msg = val_res.get("error", "Transacción inválida")
                    retry_kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Reintentar Ingresar Hash", callback_data=f"deposit:submit_hash:{deposit_id}")],
                        [InlineKeyboardButton("Volver", callback_data="menu_main")]
                    ])
                    await render_screen(client, user_id, f"❌ <b>Verificación Fallida:</b>\n{err_msg}", retry_kb)
                    return

                # Acreditación Exitosa
                credited_amount = Decimal(str(val_res["amount"]))
                deposit.status = DepositStatus.CONFIRMED
                deposit.tx_hash = tx_hash
                deposit.confirmed_at = datetime.utcnow()

                user_stmt = select(User).where(User.telegram_id == user_id).with_for_update()
                u_res = await session.execute(user_stmt)
                user = u_res.scalar_one_or_none()
                user.balance += credited_amount
                new_balance = float(user.balance)

                # Comisión de referidos
                if user.referred_by:
                    ref_stmt = select(User).where(User.telegram_id == user.referred_by).with_for_update()
                    ref_res = await session.execute(ref_stmt)
                    referrer = ref_res.scalar_one_or_none()
                    if referrer:
                        comm_rate = Decimal(str(settings.REFERRAL_COMMISSION_PERCENT)) / Decimal("100")
                        commission = credited_amount * comm_rate
                        referrer.balance += commission

                await session.commit()

            # Notificar al canal de auditoría
            await audit_logger.log_deposit_confirmed(
                client=client,
                user_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name or "Usuario",
                amount=float(credited_amount),
                tx_hash=tx_hash,
                new_balance=new_balance
            )

            # Notificar al usuario editando la pantalla única
            success_text = (
                f"🎉 <b>¡DEPÓSITO ACREDITADO CON ÉXITO!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>Monto Acreditado:</b> <code>+${float(credited_amount):.4f} USDT</code>\n"
                f"💳 <b>Nuevo Saldo Total:</b> <code>${new_balance:.4f} USDT</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>Ya puedes explorar el catálogo y comprar cualquier servicio digital.</i>"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Ir al Catálogo de Servicios", callback_data="catalog:disponibles:1")],
                [InlineKeyboardButton("Volver", callback_data="menu_main")]
            ])
            await render_screen(client, user_id, success_text, keyboard)
