from datetime import datetime, timezone
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

        bot_username = getattr(client.me, "username", "") or (await client.get_me()).username
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

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        is_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now_utc)
        comm_pct = settings.VIP_REFERRAL_COMMISSION_PERCENT if is_vip else settings.REFERRAL_COMMISSION_PERCENT

        vip_banner = "👑 <i>(⭐ Beneficio VIP: Comisión de 20% en cada recarga activa)</i>\n\n" if is_vip else ""
        text = vip_banner + t(
            "referrals_title",
            lang,
            percent=f"{comm_pct:.1f}",
            count=total_referred,
            earnings=f"{total_earnings:.2f}",
            ref_link=ref_link
        )

        share_url = f"https://t.me/share/url?url={ref_link}&text=🚀%20Get%20AI,%20streaming%20and%20software%20licenses%20at%20the%20best%20price!"

        btn_my_refs = "👥 Mis Referidos" if lang == "es" else ("👥 My Referrals" if lang == "en" else "👥 Meus Indicados")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{btn_my_refs} ({total_referred})", callback_data="referrals:list:1")],
            [InlineKeyboardButton(t("btn_share_ref", lang), url=share_url)],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="menu_main")]
        ])

        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^referrals:list:(\d+)$"))
    async def cb_referrals_list(client: Client, callback: CallbackQuery):
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

            # Total de referidos
            count_stmt = select(func.count(User.telegram_id)).where(User.referred_by == user_id)
            count_res = await session.execute(count_stmt)
            total_refs = count_res.scalar() or 0

            if total_refs == 0:
                empty_text = (
                    f"👥 <b>MIS REFERIDOS</b>\n\n"
                    f"Aún no tienes usuarios registrados con tu enlace de invitación.\n\n"
                    f"<i>¡Comparte tu enlace personal para comenzar a ganar comisiones automáticas de cada recarga!</i>"
                )
                if lang == "en":
                    empty_text = (
                        f"👥 <b>MY REFERRALS</b>\n\n"
                        f"You don't have any referred users registered yet.\n\n"
                        f"<i>Share your personal link to start earning automatic commissions on every deposit!</i>"
                    )
                elif lang == "pt":
                    empty_text = (
                        f"👥 <b>MEUS INDICADOS</b>\n\n"
                        f"Você ainda não tem usuários cadastrados com seu link de convite.\n\n"
                        f"<i>Compartilhe seu link pessoal para começar a ganhar comissões automáticas em cada recarga!</i>"
                    )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_back", lang), callback_data="referrals:view")]
                ])
                await render_screen(client, callback, empty_text, keyboard)
                return

            total_pages = max(1, (total_refs + page_size - 1) // page_size)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * page_size

            refs_stmt = (
                select(User)
                .where(User.referred_by == user_id)
                .order_by(User.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            refs_res = await session.execute(refs_stmt)
            referrals = refs_res.scalars().all()

            # Consultar depósitos de esta página de usuarios
            ref_ids = [r.telegram_id for r in referrals]
            deps_stmt = (
                select(Deposit.user_id, func.sum(Deposit.base_amount))
                .where(Deposit.user_id.in_(ref_ids), Deposit.status == DepositStatus.CONFIRMED)
                .group_by(Deposit.user_id)
            )
            deps_res = await session.execute(deps_stmt)
            deposits_map = {uid: float(amt or 0.0) for uid, amt in deps_res.all()}

        header = (
            f"👥 <b>MIS USUARIOS REFERIDOS ({total_refs})</b>\n\n"
            f"Página: <code>{page}/{total_pages}</code>\n\n"
        )
        if lang == "en":
            header = f"👥 <b>MY REFERRED USERS ({total_refs})</b>\n\nPaging: <code>{page}/{total_pages}</code>\n\n"
        elif lang == "pt":
            header = f"👥 <b>MEUS USUÁRIOS INDICADOS ({total_refs})</b>\n\nPágina: <code>{page}/{total_pages}</code>\n\n"

        lines = []
        for i, ref in enumerate(referrals, start=offset + 1):
            tag = f"@{ref.username}" if ref.username else f"ID: <code>{ref.telegram_id}</code>"
            reg_date = ref.created_at.strftime("%Y-%m-%d") if ref.created_at else "N/A"
            deposited = deposits_map.get(ref.telegram_id, 0.0)
            vip_mark = " 👑" if ref.is_vip else ""
            lines.append(
                f"<b>{i}.</b> {tag}{vip_mark}\n"
                f"   📅 <i>Registro:</i> <code>{reg_date}</code> | 💳 <i>Recargas:</i> <code>${deposited:.2f} USDT</code>"
            )

        text = header + "\n\n".join(lines)

        buttons = []
        if total_pages > 1:
            nav_row = []
            if page > 1:
                nav_row.append(InlineKeyboardButton("◀️", callback_data=f"referrals:list:{page - 1}"))
            else:
                nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))

            nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))

            if page < total_pages:
                nav_row.append(InlineKeyboardButton("▶️", callback_data=f"referrals:list:{page + 1}"))
            else:
                nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))
            buttons.append(nav_row)

        buttons.append([InlineKeyboardButton(t("btn_back", lang), callback_data="referrals:view")])
        await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))
