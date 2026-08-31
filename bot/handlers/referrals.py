from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter

def register_referrals_handlers(app: Client):

    @app.on_callback_query(filters.regex("^referrals:view$"))
    async def cb_referrals_view(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer()
            return

        bot_info = await client.get_me()
        bot_username = bot_info.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

        async with async_session() as session:
            # Contar referidos directos
            count_stmt = select(func.count(User.telegram_id)).where(User.referred_by == user_id)
            count_res = await session.execute(count_stmt)
            total_referred = count_res.scalar() or 0

            # Usuario
            u_stmt = select(User).where(User.telegram_id == user_id)
            u_res = await session.execute(u_stmt)
            user = u_res.scalar_one_or_none()
            balance = float(user.balance) if user else 0.0

        comm_pct = settings.REFERRAL_COMMISSION_PERCENT

        text = (
            f"🔗 <b>PROGRAMA DE AFILIADOS & REFERIDOS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"¡Gana comisiones automáticas invitando amigos a utilizar el bot!\n\n"
            f"💰 <b>Tu Comisión:</b> <code>{comm_pct:.1f}%</code> de cada depósito que realicen tus referidos.\n"
            f"👥 <b>Amigos Invitados:</b> <code>{total_referred} usuarios</code>\n"
            f"💳 <b>Tu Saldo Actual:</b> <code>${balance:.4f} USDT</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Tu Enlace Personal de Invitación:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"<i>💡 Comparte este enlace. Cuando un usuario entre y recargue saldo, recibirás tu comisión directamente acreditada a tu cuenta para comprar servicios.</i>"
        )

        share_url = f"https://t.me/share/url?url={ref_link}&text=🚀%20Consigue%20cuentas%20de%20streaming,%20IA%20y%20licencias%20al%20mejor%20precio%20en%20este%20bot!"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Compartir mi Enlace", url=share_url)],
            [InlineKeyboardButton("🔙 Volver al Menú Principal", callback_data="menu_main")]
        ])

        await render_screen(client, callback, text, keyboard)
