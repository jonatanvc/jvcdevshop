import asyncio
from datetime import datetime, timezone, timedelta
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, update
from bot.database.session import async_session
from bot.database.models import Deposit, DepositStatus, User
from bot.utils.i18n import t
from bot.utils.emojis import parse_emojis, parse_keyboard

async def check_and_send_deposit_reminders(app: Client):
    """
    Monitorea solicitudes de depósito USDT BEP-20 pendientes.
    Si el usuario generó la factura hace más de 15 minutos (y no ha expirado ni enviado hash),
    le envía un recordatorio amigable para maximizar la tasa de conversión.
    Se envía exactamente 1 sola vez por depósito gracias a reminder_sent = True.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    threshold_min = now - timedelta(minutes=15)
    threshold_max = now - timedelta(minutes=45)

    async with async_session() as session:
        stmt = select(Deposit).where(
            Deposit.status == DepositStatus.PENDING,
            Deposit.reminder_sent.is_(False),
            Deposit.created_at <= threshold_min,
            Deposit.created_at >= threshold_max,
            Deposit.expires_at > now
        )
        res = await session.execute(stmt)
        pending_deposits = res.scalars().all()

        if not pending_deposits:
            return

        for dep in pending_deposits:
            # Obtener datos del usuario
            u_stmt = select(User).where(User.telegram_id == dep.user_id)
            u_res = await session.execute(u_stmt)
            user = u_res.scalar_one_or_none()
            if not user:
                dep.reminder_sent = True
                continue

            lang = user.language or "es"
            name = user.first_name or "Usuario"
            amount_str = f"{float(dep.exact_amount):.4f}"

            if lang == "en":
                text = (
                    f"⏳ <b>Friendly Reminder: Pending Deposit</b>\n\n"
                    f"Hello <b>{name}</b>, we noticed you generated a top-up request for "
                    f"<code>{amount_str} USDT</code> a few minutes ago.\n\n"
                    f"• <b>Status:</b> Awaiting confirmation\n"
                    f"• <b>Network:</b> BNB Smart Chain (BEP-20)\n\n"
                    f"<i>If you already sent the transfer from Binance or your wallet, please tap 'Submit Hash' below so your balance is credited immediately!</i>"
                )
                btn_inv = "📄 View Invoice / QR"
                btn_hash = "⚡ Submit Hash / TxID"
                btn_cancel = "❌ Cancel Invoice"
            elif lang == "pt":
                text = (
                    f"⏳ <b>Lembrete Amigável: Depósito Pendente</b>\n\n"
                    f"Olá <b>{name}</b>, notamos que você gerou um pedido de recarga de "
                    f"<code>{amount_str} USDT</code> há alguns minutos.\n\n"
                    f"• <b>Status:</b> Aguardando confirmação\n"
                    f"• <b>Rede:</b> BNB Smart Chain (BEP-20)\n\n"
                    f"<i>Se você já realizou a transferência pela Binance ou sua carteira, toque em 'Enviar Hash' abaixo para creditar seu saldo agora mesmo!</i>"
                )
                btn_inv = "📄 Ver Fatura / QR"
                btn_hash = "⚡ Enviar Hash / TxID"
                btn_cancel = "❌ Cancelar Fatura"
            else:
                text = (
                    f"⏳ <b>Recordatorio Amigable: Depósito Pendiente</b>\n\n"
                    f"Hola <b>{name}</b>, notamos que generaste una solicitud de recarga por "
                    f"<code>{amount_str} USDT</code> hace unos minutos.\n\n"
                    f"• <b>Estado:</b> Esperando confirmación\n"
                    f"• <b>Red:</b> BNB Smart Chain (BEP-20)\n\n"
                    f"<i>Si ya realizaste la transferencia desde Binance o tu billetera, pulsa 'Enviar Hash' abajo para que tu saldo se acredite de inmediato.</i>"
                )
                btn_inv = "📄 Ver Factura / QR"
                btn_hash = "⚡ Enviar Hash / TxID"
                btn_cancel = "❌ Cancelar Factura"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(btn_inv, callback_data=f"deposit:view_inv:{dep.id}")],
                [InlineKeyboardButton(btn_hash, callback_data=f"deposit:submit_hash:{dep.id}")],
                [InlineKeyboardButton(btn_cancel, callback_data=f"deposit:cancel:{dep.id}")]
            ])

            try:
                await app.send_message(
                    chat_id=dep.user_id,
                    text=parse_emojis(text),
                    parse_mode=ParseMode.HTML,
                    reply_markup=parse_keyboard(keyboard)
                )
            except Exception as e:
                print(f"[DepositReminder] No se pudo enviar recordatorio a {dep.user_id}: {e}")

            dep.reminder_sent = True

        await session.commit()
