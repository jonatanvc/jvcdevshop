from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, desc
from bot.database.session import async_session
from bot.database.models import User, Order, VirtualNumberOrder
from bot.services.virtual_numbers import CURATED_SERVICES, get_country_display
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.time_utils import format_dt
from bot.utils.formatters import adjust_warranty_in_name, format_delivered_credentials

ORDERS_PER_PAGE = 6

def register_orders_handlers(app: Client):

    @app.on_message(filters.command(["pedidos", "orders"]) & filters.private)
    async def cmd_orders(client: Client, message: Message):
        user_id = message.from_user.id
        try:
            await message.delete()
        except Exception:
            pass

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = user.language if user else "es"

            stmt = select(Order).where(Order.user_id == user_id).order_by(desc(Order.created_at))
            result = await session.execute(stmt)
            all_orders = result.scalars().all()

            # Pestañas superiores
            tab_buttons = [
                InlineKeyboardButton("🛒 Cuentas •", callback_data="orders:page:1:main"),
                InlineKeyboardButton("📲 Números Virtuales", callback_data="vnum_orders:page:1:main")
            ]

            if not all_orders:
                text = t("orders_empty", lang)
                keyboard = InlineKeyboardMarkup([
                    tab_buttons,
                    [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")],
                    [InlineKeyboardButton(t("btn_back", lang), callback_data="menu_main")]
                ])
                await render_screen(client, user_id, text, keyboard)
                return

            total_orders = len(all_orders)
            total_pages = (total_orders + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE
            page = 1

            start_idx = 0
            end_idx = ORDERS_PER_PAGE
            orders_page = all_orders[start_idx:end_idx]

            text = t("orders_title", lang, count=total_orders)

            buttons = [tab_buttons]
            for ord in orders_page:
                date_str = format_dt(ord.created_at, "%d/%m/%Y")
                ord_pname = adjust_warranty_in_name(ord.product_name)
                btn_text = f"🛍️ #{ord.id} - {ord_pname[:22]} (${float(ord.total_price):.2f}) [{date_str}]"
                buttons.append([
                    InlineKeyboardButton(btn_text, callback_data=f"order:view:{ord.id}:{page}:main")
                ])

            if total_pages > 1:
                nav = [InlineKeyboardButton("🔵", callback_data="noop"), InlineKeyboardButton(f"1/{total_pages}", callback_data="noop")]
                if total_pages > 1:
                    nav.append(InlineKeyboardButton("▶️", callback_data="orders:page:2:main"))
                buttons.append(nav)

            buttons.append([
                InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1"),
                InlineKeyboardButton(t("btn_back", lang), callback_data="menu_main")
            ])

            await render_screen(client, user_id, text, InlineKeyboardMarkup(buttons))

    @app.on_callback_query(filters.regex(r"^orders:page:(\d+)(?::([a-z_]+))?$"))
    async def cb_orders_list(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        page = int(callback.matches[0].group(1))
        src = callback.matches[0].group(2) or "main"
        back_target = "menu_main" if src == "main" else "account:view"

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = user.language if user else "es"

            stmt = select(Order).where(Order.user_id == user_id).order_by(desc(Order.created_at))
            result = await session.execute(stmt)
            all_orders = result.scalars().all()

            tab_buttons = [
                InlineKeyboardButton("🛒 Cuentas •", callback_data=f"orders:page:1:{src}"),
                InlineKeyboardButton("📲 Números Virtuales", callback_data=f"vnum_orders:page:1:{src}")
            ]

            if not all_orders:
                text = t("orders_empty", lang)
                keyboard = InlineKeyboardMarkup([
                    tab_buttons,
                    [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")],
                    [InlineKeyboardButton(t("btn_back", lang), callback_data=back_target)]
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

            buttons = [tab_buttons]
            for ord in orders_page:
                date_str = format_dt(ord.created_at, "%d/%m/%Y")
                ord_pname = adjust_warranty_in_name(ord.product_name)
                btn_text = f"🛍️ #{ord.id} - {ord_pname[:22]} (${float(ord.total_price):.2f}) [{date_str}]"
                buttons.append([
                    InlineKeyboardButton(btn_text, callback_data=f"order:view:{ord.id}:{page}:{src}")
                ])

            if total_pages > 1:
                nav = []
                if page > 1:
                    nav.append(InlineKeyboardButton("◀️", callback_data=f"orders:page:{page - 1}:{src}"))
                else:
                    nav.append(InlineKeyboardButton("🔵", callback_data="noop"))
                nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
                if page < total_pages:
                    nav.append(InlineKeyboardButton("▶️", callback_data=f"orders:page:{page + 1}:{src}"))
                else:
                    nav.append(InlineKeyboardButton("🔵", callback_data="noop"))
                buttons.append(nav)

            buttons.append([
                InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1"),
                InlineKeyboardButton(t("btn_back", lang), callback_data=back_target)
            ])

            await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))

    @app.on_callback_query(filters.regex(r"^order:view:(\d+):(\d+)(?::([a-z_]+))?$"))
    async def cb_order_detail(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        order_id = int(callback.matches[0].group(1))
        page = int(callback.matches[0].group(2))
        src = callback.matches[0].group(3) or "main"

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
                product=adjust_warranty_in_name(order.product_name),
                qty=order.quantity,
                total=f"{float(order.total_price):.2f}",
                warranty=warranty_str,
                date=date_str,
                prov_id=order.provider_order_id or "N/A",
                items=format_delivered_credentials(order.delivered_items)
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_back", lang), callback_data=f"orders:page:{page}:{src}")],
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
            ])

            await render_screen(client, callback, text, keyboard)

    # ========================================================
    # 📲 HISTORIAL DE NÚMEROS VIRTUALES (PESTAÑA SECUNDARIA)
    # ========================================================

    @app.on_callback_query(filters.regex(r"^vnum_orders:page:(\d+)(?::([a-z_]+))?$"))
    async def cb_vnum_orders_list(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        page = int(callback.matches[0].group(1))
        src = callback.matches[0].group(2) or "main"
        back_target = "menu_main" if src == "main" else "account:view"

        async with async_session() as session:
            stmt = (
                select(VirtualNumberOrder)
                .where(VirtualNumberOrder.user_id == user_id)
                .order_by(desc(VirtualNumberOrder.created_at))
            )
            res = await session.execute(stmt)
            all_vorders = res.scalars().all()

        tab_buttons = [
            InlineKeyboardButton("🛒 Cuentas", callback_data=f"orders:page:1:{src}"),
            InlineKeyboardButton("📲 Números Virtuales •", callback_data=f"vnum_orders:page:1:{src}")
        ]

        if not all_vorders:
            text = (
                "📲 <b>HISTORIAL DE NÚMEROS VIRTUALES</b>\n\n"
                "<i>Aún no has solicitado números virtuales temporales.</i>\n\n"
                "💡 <i>Puedes activar cuentas de WhatsApp, Telegram, Google, Discord y muchas más en segundos.</i>"
            )
            keyboard = InlineKeyboardMarkup([
                tab_buttons,
                [InlineKeyboardButton("📲 Comprar Número Virtual", callback_data="vnum:catalog")],
                [InlineKeyboardButton("🔙 Volver", callback_data=back_target)]
            ])
            await render_screen(client, callback, text, keyboard)
            return

        total_orders = len(all_vorders)
        total_pages = (total_orders + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * ORDERS_PER_PAGE
        end_idx = start_idx + ORDERS_PER_PAGE
        vorders_page = all_vorders[start_idx:end_idx]

        text = (
            f"📲 <b>HISTORIAL DE NÚMEROS VIRTUALES ({total_orders})</b>\n\n"
            "<i>Selecciona un número para ver su código OTP recibido, mensaje SMS o reordenar:</i>"
        )

        buttons = [tab_buttons]
        for vord in vorders_page:
            st = vord.status
            if st in ["RECEIVED", "FINISHED"]:
                badge = "✅"
            elif st == "PENDING":
                badge = "⏳"
            elif st == "CANCELLED":
                badge = "❌"
            elif st == "TIMEOUT":
                badge = "⏰"
            else:
                badge = "📱"

            flag, _ = get_country_display(vord.country)
            srv_name = vord.service_name.upper()
            date_str = format_dt(vord.created_at, "%d/%m")
            btn_text = f"{badge} #{vord.id} - {srv_name} {flag} (${float(vord.price_usdt):.2f}) [{date_str}]"
            buttons.append([
                InlineKeyboardButton(btn_text, callback_data=f"vnum_order:view:{vord.id}:{page}:{src}")
            ])

        if total_pages > 1:
            nav = []
            if page > 1:
                nav.append(InlineKeyboardButton("◀️", callback_data=f"vnum_orders:page:{page - 1}:{src}"))
            else:
                nav.append(InlineKeyboardButton("🔵", callback_data="noop"))
            nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
            if page < total_pages:
                nav.append(InlineKeyboardButton("▶️", callback_data=f"vnum_orders:page:{page + 1}:{src}"))
            else:
                nav.append(InlineKeyboardButton("🔵", callback_data="noop"))
            buttons.append(nav)

        buttons.append([
            InlineKeyboardButton("📲 Comprar Número Virtual", callback_data="vnum:catalog"),
            InlineKeyboardButton("🔙 Volver", callback_data=back_target)
        ])

        await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))

    @app.on_callback_query(filters.regex(r"^vnum_order:view:(\d+):(\d+)(?::([a-z_]+))?$"))
    async def cb_vnum_order_detail(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        order_id = int(callback.matches[0].group(1))
        page = int(callback.matches[0].group(2))
        src = callback.matches[0].group(3) or "main"

        async with async_session() as session:
            stmt = select(VirtualNumberOrder).where(
                VirtualNumberOrder.id == order_id,
                VirtualNumberOrder.user_id == user_id
            )
            res = await session.execute(stmt)
            order = res.scalar_one_or_none()

        if not order:
            await callback.answer("❌ Orden no encontrada.", show_alert=True)
            return

        service_info = CURATED_SERVICES.get(order.service_name.lower(), {"name": order.service_name.upper()})
        flag, country_name = get_country_display(order.country)
        date_str = format_dt(order.created_at, "%Y-%m-%d %H:%M:%S")

        st = order.status
        if st in ["RECEIVED", "FINISHED"]:
            status_desc = "✅ <b>Completado con éxito (OTP recibido)</b>"
        elif st == "PENDING":
            status_desc = "⏳ <b>Esperando código SMS...</b>"
        elif st == "CANCELLED":
            status_desc = "❌ <b>Cancelado por el usuario (Saldo reembolsado)</b>"
        elif st == "TIMEOUT":
            status_desc = "⏰ <b>Tiempo agotado sin SMS (Saldo reembolsado)</b>"
        else:
            status_desc = f"ℹ️ <b>{st}</b>"

        otp_block = f"<code>{order.sms_code}</code>" if order.sms_code else "<i>No se recibió código</i>"
        sms_text_block = f"<pre>{order.sms_full_text}</pre>" if order.sms_full_text else "<i>Sin mensaje SMS</i>"

        text = (
            f"📲 <b>DETALLES DE NÚMERO VIRTUAL #{order.id}</b>\n\n"
            f"• <b>Plataforma:</b> {service_info['name']}\n"
            f"• <b>País:</b> {flag} {country_name}\n"
            f"• <b>Número Telefónico (Toca para copiar):</b>\n"
            f"<code>{order.phone}</code>\n\n"
            f"• <b>Estado:</b> {status_desc}\n"
            f"• <b>Precio:</b> <code>${float(order.price_usdt):.2f} USDT</code>\n"
            f"• <b>Fecha:</b> <code>{date_str}</code>\n\n"
            f"🔑 <b>Código OTP Recibido:</b>\n"
            f"{otp_block}\n\n"
            f"💬 <b>SMS Completo:</b>\n"
            f"{sms_text_block}"
        )

        buttons = []
        if order.status in ["RECEIVED", "FINISHED"]:
            buttons.append([
                InlineKeyboardButton("⚡ Pedir Otro Número (Mismo País)", callback_data=f"vnum:reorder:{order.service_name}:{order.country}")
            ])
        elif order.status == "PENDING":
            buttons.append([
                InlineKeyboardButton("🔄 Comprobar SMS", callback_data=f"vnum:check_sms:{order.id}"),
                InlineKeyboardButton("❌ Cancelar y Reembolsar", callback_data=f"vnum:cancel:{order.id}")
            ])

        buttons.extend([
            [InlineKeyboardButton("🔙 Volver al Historial", callback_data=f"vnum_orders:page:{page}:{src}")],
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
        ])

        await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))
