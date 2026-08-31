from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, desc
from bot.database.session import async_session
from bot.database.models import Order
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter

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
            stmt = select(Order).where(Order.user_id == user_id).order_by(desc(Order.created_at))
            result = await session.execute(stmt)
            all_orders = result.scalars().all()

            if not all_orders:
                text = (
                    "💼 <b>MIS PEDIDOS</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Aún no has realizado ningún pedido.\n\n"
                    "<i>Explora nuestro catálogo y adquiere tus cuentas y licencias al mejor precio.</i>"
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛒 Ver Catálogo de Servicios", callback_data="catalog:disponibles:1")],
                    [InlineKeyboardButton("Volver", callback_data="account:view")]
                ])
                await render_screen(client, callback, text, keyboard)
                return

            total_orders = len(all_orders)
            total_pages = (total_orders + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE
            page = max(1, min(page, total_pages))

            start_idx = (page - 1) * ORDERS_PER_PAGE
            end_idx = start_idx + ORDERS_PER_PAGE
            orders_page = all_orders[start_idx:end_idx]

            text = f"💼 <b>MIS PEDIDOS ({total_orders} Total)</b>\n<i>Selecciona un pedido para ver los datos entregados:</i>\n"

            buttons = []
            for ord in orders_page:
                date_str = ord.created_at.strftime("%d/%m/%Y")
                btn_text = f"🛍️ #{ord.id} - {ord.product_name[:24]} (${float(ord.total_price):.2f}) [{date_str}]"
                buttons.append([
                    InlineKeyboardButton(btn_text, callback_data=f"order:view:{ord.id}:{page}")
                ])

            # Paginación
            if total_pages > 1:
                nav = []
                if page > 1:
                    nav.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"orders:page:{page - 1}"))
                nav.append(InlineKeyboardButton(f"Pág. {page}/{total_pages}", callback_data="noop"))
                if page < total_pages:
                    nav.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"orders:page:{page + 1}"))
                buttons.append(nav)

            buttons.append([
                InlineKeyboardButton("🛒 Ir al Catálogo", callback_data="catalog:disponibles:1"),
                InlineKeyboardButton("Volver", callback_data="account:view")
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
            stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
            res = await session.execute(stmt)
            order = res.scalar_one_or_none()

            if not order:
                await callback.answer("❌ Pedido no encontrado.", show_alert=True)
                return

            warranty_str = f"🛡️ {order.warranty_hours} horas" if order.warranty_hours > 0 else "Sin garantía"
            date_str = order.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")

            text = (
                f"🛍️ <b>DETALLES DEL PEDIDO #ORD_{order.id}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 <b>Producto:</b> <code>{order.product_name}</code> (x{order.quantity})\n"
                f"💰 <b>Precio Pagado:</b> <code>${float(order.total_price):.2f} USDT</code>\n"
                f"🛡️ <b>Garantía:</b> <code>{warranty_str}</code>\n"
                f"📅 <b>Fecha de Compra:</b> <code>{date_str}</code>\n"
                f"🆔 <b>ID Proveedor:</b> <code>{order.provider_order_id or 'N/A'}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔑 <b>DATOS / CREDENCIALES ENTREGADAS:</b>\n"
                f"<pre>{order.delivered_items}</pre>"
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Volver", callback_data=f"orders:page:{page}")],
                [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
            ])

            await render_screen(client, callback, text, keyboard)
