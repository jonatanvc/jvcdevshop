from datetime import datetime, timezone, timedelta
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from bot.database.session import async_session
from bot.config import settings
from bot.database.models import Deposit, DepositStatus, User
from bot.utils.navigation import USER_LAST_MESSAGES, USER_LAST_MESSAGES_IS_MEDIA, render_screen

async def check_and_send_deposit_reminders(app: Client):
    """
    Monitorea solicitudes de depósito USDT BEP-20 pendientes.
    Si el usuario generó la factura hace más de 15 minutos (y no ha expirado ni enviado hash),
    le envía un recordatorio amigable para maximizar la tasa de conversión.
    Se envía exactamente 1 sola vez por depósito gracias a reminder_sent = True.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    reminder_after_minutes = max(1, min(15, settings.DEPOSIT_EXPIRY_MINUTES // 2))
    threshold_min = now - timedelta(minutes=reminder_after_minutes)

    async with async_session() as session:
        stmt = select(Deposit).where(
            Deposit.status == DepositStatus.PENDING,
            Deposit.reminder_sent.is_(False),
            Deposit.created_at <= threshold_min,
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
            amount_str = f"{float(dep.exact_amount):.6f}"

            if lang == "en":
                text = (
                    f"⏳ <b>Friendly Reminder: Pending Deposit</b>\n\n"
                    f"Hello <b>{name}</b>, we noticed you generated a top-up request for "
                    f"<code>{amount_str} USDT</code> a few minutes ago.\n\n"
                    f"• <b>Status:</b> Awaiting confirmation\n"
                    f"• <b>Network:</b> BNB Smart Chain (BEP-20)\n\n"
                    f"<i>Send the exact amount before the invoice expires. The bot will detect your transfer automatically.</i>"
                )
                btn_inv = "📄 View Invoice / QR"
                btn_cancel = "❌ Cancel Invoice"
            elif lang == "pt":
                text = (
                    f"⏳ <b>Lembrete Amigável: Depósito Pendente</b>\n\n"
                    f"Olá <b>{name}</b>, notamos que você gerou um pedido de recarga de "
                    f"<code>{amount_str} USDT</code> há alguns minutos.\n\n"
                    f"• <b>Status:</b> Aguardando confirmação\n"
                    f"• <b>Rede:</b> BNB Smart Chain (BEP-20)\n\n"
                    f"<i>Envie o valor exato antes do vencimento. O bot detectará sua transferência automaticamente.</i>"
                )
                btn_inv = "📄 Ver Fatura / QR"
                btn_cancel = "❌ Cancelar Fatura"
            else:
                text = (
                    f"⏳ <b>Recordatorio Amigable: Depósito Pendiente</b>\n\n"
                    f"Hola <b>{name}</b>, notamos que generaste una solicitud de recarga por "
                    f"<code>{amount_str} USDT</code> hace unos minutos.\n\n"
                    f"• <b>Estado:</b> Esperando confirmación\n"
                    f"• <b>Red:</b> BNB Smart Chain (BEP-20)\n\n"
                    f"<i>Envía el importe exacto antes del vencimiento. El bot detectará la transferencia automáticamente.</i>"
                )
                btn_inv = "📄 Ver Factura / QR"
                btn_cancel = "❌ Cancelar Factura"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(btn_inv, callback_data=f"deposit:view_inv:{dep.id}")],
                [InlineKeyboardButton(btn_cancel, callback_data=f"deposit:cancel:{dep.id}")]
            ])

            if dep.user_message_id:
                if dep.user_message_is_media:
                    try:
                        await app.delete_messages(dep.user_id, dep.user_message_id)
                    except Exception:
                        pass
                    USER_LAST_MESSAGES.pop(dep.user_id, None)
                    USER_LAST_MESSAGES_IS_MEDIA.pop(dep.user_id, None)
                else:
                    USER_LAST_MESSAGES[dep.user_id] = dep.user_message_id
                    USER_LAST_MESSAGES_IS_MEDIA[dep.user_id] = False
            try:
                reminder_message = await render_screen(app, dep.user_id, text, keyboard)
                if reminder_message:
                    dep.user_message_id = reminder_message.id
                    dep.user_message_is_media = False
            except Exception as e:
                print(f"[DepositReminder] No se pudo actualizar factura de {dep.user_id}: {e}")

            dep.reminder_sent = True

        await session.commit()
