from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Deposit, DepositStatus
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t

def register_referrals_handlers(app: Client):

    @app.on_callback_query(filters.regex("^referrals:view$"))
    async def cb_referrals_view(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        bot_username = client.me.username if client.me else ""
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

            # 1. Cantidad de usuarios referidos
            count_stmt = select(func.count(User.telegram_id)).where(User.referred_by == user_id)
            count_res = await session.execute(count_stmt)
            total_referred = count_res.scalar() or 0

            # 2. Ganancias reales por comisiones de depósitos confirmados
            total_earnings = 0.0
            ref_users_stmt = select(User.telegram_id).where(User.referred_by == user_id)
            ref_users_res = await session.execute(ref_users_stmt)
            ref_user_ids = [uid for uid in ref_users_res.scalars().all()]

            if ref_user_ids:
                earnings_stmt = select(func.sum(Deposit.base_amount)).where(
                    Deposit.user_id.in_(ref_user_ids),
                    Deposit.status == DepositStatus.CONFIRMED
                )
                earnings_res = await session.execute(earnings_stmt)
                total_dep_base = float(earnings_res.scalar() or 0.0)
                comm_rate = float(settings.REFERRAL_COMMISSION_PERCENT) / 100.0
                total_earnings = total_dep_base * comm_rate

        comm_pct = settings.REFERRAL_COMMISSION_PERCENT

        text = t(
            "referrals_title",
            lang,
            percent=f"{comm_pct:.1f}",
            count=total_referred,
            earnings=f"{total_earnings:.2f}",
            ref_link=ref_link
        )

        share_url = f"https://t.me/share/url?url={ref_link}&text=🚀%20Get%20AI,%20streaming%20and%20software%20licenses%20at%20the%20best%20price!"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_share_ref", lang), url=share_url)],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="menu_main")]
        ])

        await render_screen(client, callback, text, keyboard)
