from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, desc
from bot.database.session import async_session
from bot.database.models import User, Order
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.time_utils import format_dt

ORDERS_PER_PAGE = 6

def register_orders_handlers(app: Client):

    @app.on_callback_query(filters.regex(r"^orders:page:(\d+)$"))
    async def cb_orders_list(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer()
            return

        page = int(callback.matches[0].group(1))

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = user.language if user else "es"

            stmt = select(Order).where(Order.user_id == user_id).order_by(desc(Order.created_at))
            result = await session.execute(stmt)
            all_orders = result.scalars().all()

            if not all_orders:
                text = t("orders_empty", lang)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")],
                    [InlineKeyboardButton(t("btn_back", lang), callback_data="account:view")]
                ])
                await render_screen(client, callback, text, keyboard)
                return

            total_orders = len(all_orders)
            total_pages = (total_orders + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE
            page = max(1, min(page, total_pages))

            start_idx = (page - 1) * ORDERS_PER_PAGE
            end_idx = start_idx + ORDERS_PER_PAGE
            orders_page = all_orders[start_idx:end_idx]

            text = t("orders_title", lang, count=total_orders)

            buttons = []
            for ord in orders_page:
                date_str = format_dt(ord.created_at, "%d/%m/%Y")
                btn_text = f"🛍️ #{ord.id} - {ord.product_name[:24]} (${float(ord.total_price):.2f}) [{date_str}]"
                buttons.append([
                    InlineKeyboardButton(btn_text, callback_data=f"order:view:{ord.id}:{page}")
                ])

            if total_pages > 1:
                nav = []
                if page > 1:
                    nav.append(InlineKeyboardButton("◀️", callback_data=f"orders:page:{page - 1}"))
                nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
                if page < total_pages:
                    nav.append(InlineKeyboardButton("▶️", callback_data=f"orders:page:{page + 1}"))
                buttons.append(nav)

            buttons.append([
                InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1"),
                InlineKeyboardButton(t("btn_back", lang), callback_data="account:view")
            ])

            await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))

    @app.on_callback_query(filters.regex(r"^order:view:(\d+):(\d+)$"))
    async def cb_order_detail(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer()
            return

        order_id = int(callback.matches[0].group(1))
        page = int(callback.matches[0].group(2))

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = user.language if user else "es"

            stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
            res = await session.execute(stmt)
            order = res.scalar_one_or_none()

            if not order:
                await callback.answer("❌ Error", show_alert=True)
                return

            if order.warranty_hours == 0:
                warranty_str = t("no_warranty", lang)
            elif order.warranty_hours >= 24 and order.warranty_hours % 24 == 0:
                warranty_str = t("warranty_days", lang, days=order.warranty_hours // 24)
            else:
                warranty_str = t("warranty_hours", lang, hours=order.warranty_hours)

            date_str = format_dt(order.created_at, "%Y-%m-%d %H:%M:%S")

            text = t(
                "order_detail_title",
                lang,
                order_id=order.id,
                product=order.product_name,
                qty=order.quantity,
                total=f"{float(order.total_price):.2f}",
                warranty=warranty_str,
                date=date_str,
                prov_id=order.provider_order_id or "N/A",
                items=order.delivered_items
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_back", lang), callback_data=f"orders:page:{page}")],
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
            ])

            await render_screen(client, callback, text, keyboard)
