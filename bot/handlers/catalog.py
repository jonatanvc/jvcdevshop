from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, update
from bot.database.session import async_session
from bot.database.models import User, StockAlert
from bot.services.pricing import pricing_service, PAGE_SIZE
from bot.services.bunai_client import bunai_api
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter

SEARCH_STATES = {}

FILTER_NAMES = {
    "disponibles": "Disponibles",
    "agotados": "Agotados",
    "ofertas": "Ofertas",
    "todos": "Todos"
}

FILTER_ROTATION = ["disponibles", "ofertas", "agotados", "todos"]

def get_product_icon(name: str) -> str:
    """Asigna un icono representativo según el nombre del servicio"""
    name_lower = name.lower()
    if "gemini" in name_lower or "google" in name_lower:
        return "1️⃣"
    elif "office" in name_lower or "microsoft" in name_lower or "onedrive" in name_lower:
        return "🪟"
    elif "capcut" in name_lower:
        return "✂️"
    elif "chatgpt" in name_lower or "openai" in name_lower:
        return "🤖"
    elif "claude" in name_lower or "anthropic" in name_lower:
        return "💥"
    elif "netflix" in name_lower:
        return "🎬"
    elif "surfshark" in name_lower or "nord" in name_lower or "vpn" in name_lower:
        return "🛡️"
    elif "youtube" in name_lower:
        return "📺"
    elif "canva" in name_lower:
        return "🎨"
    elif "figma" in name_lower:
        return "📐"
    elif "grammarly" in name_lower:
        return "✍️"
    elif "linkedin" in name_lower:
        return "👔"
    elif "spotify" in name_lower:
        return "🎧"
    elif "leonardo" in name_lower or "veo" in name_lower or "kling" in name_lower:
        return "🎨"
    elif "windows" in name_lower:
        return "💻"
    elif "test" in name_lower:
        return "🧪"
    return "🏷️"

def build_catalog_keyboard(items: list, page: int, total_pages: int, filter_mode: str) -> InlineKeyboardMarkup:
    """Construye la botonera inline del catálogo con paginación máxima de 8 productos y buscador"""
    buttons = []

    # 1. Botones de cada producto
    for p in items:
        icon = get_product_icon(p["name"])
        stock_str = "∞" if p["infinite_stock"] else (str(p["stock_count"]) if p["stock_count"] > 0 else "Agotado")
        price_str = f"{p['user_price']:.2f}".rstrip("0").rstrip(".") if p["user_price"] % 1 != 0 else f"{int(p['user_price'])}"
        
        btn_text = f"{icon} {p['name']} - {price_str} USDT (Stock: {stock_str})"
        buttons.append([
            InlineKeyboardButton(btn_text, callback_data=f"product:view:{p['product_id']}:{filter_mode}:{page}:0")
        ])

    # 2. Fila de paginación (si hay más de 1 página)
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"catalog:{filter_mode}:{page - 1}"))
        else:
            nav_row.append(InlineKeyboardButton("⏺️", callback_data="noop"))

        nav_row.append(InlineKeyboardButton(f"Pág. {page}/{total_pages}", callback_data="noop"))

        if page < total_pages:
            nav_row.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"catalog:{filter_mode}:{page + 1}"))
        else:
            nav_row.append(InlineKeyboardButton("⏺️", callback_data="noop"))
        
        buttons.append(nav_row)

    # 3. Fila de controles (Actualizar y Cambiar Filtro)
    current_idx = FILTER_ROTATION.index(filter_mode) if filter_mode in FILTER_ROTATION else 0
    next_filter = FILTER_ROTATION[(current_idx + 1) % len(FILTER_ROTATION)]
    next_filter_name = FILTER_NAMES[next_filter]

    buttons.append([
        InlineKeyboardButton("🔄 Actualizar", callback_data=f"catalog_refresh:{filter_mode}:{page}"),
        InlineKeyboardButton(f"Cambiar a: {next_filter_name}", callback_data=f"catalog:{next_filter}:1")
    ])

    # 4. Buscador y Volver
    buttons.append([
        InlineKeyboardButton("🔍 Buscar Servicio", callback_data="catalog:search_prompt"),
        InlineKeyboardButton("Volver", callback_data="menu_main")
    ])

    return InlineKeyboardMarkup(buttons)

def build_product_calculator_keyboard(
    product_id: str,
    filter_mode: str,
    page: int,
    qty: int,
    can_buy: bool,
    has_stock: bool,
    is_alert_active: bool,
    total_price: float,
    bot_username: str
) -> InlineKeyboardMarkup:
    """Construye el teclado numérico interactivo con soporte para alerta de restock"""
    buttons = []

    # Fila 1: Cantidad actual y botón Del
    buttons.append([
        InlineKeyboardButton(f"Cant: {qty}", callback_data="noop"),
        InlineKeyboardButton("Del", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:del")
    ])

    # Fila 2: Dígitos 1 a 5
    buttons.append([
        InlineKeyboardButton("1", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:1"),
        InlineKeyboardButton("2", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:2"),
        InlineKeyboardButton("3", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:3"),
        InlineKeyboardButton("4", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:4"),
        InlineKeyboardButton("5", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:5"),
    ])

    # Fila 3: Dígitos 6 a 0
    buttons.append([
        InlineKeyboardButton("6", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:6"),
        InlineKeyboardButton("7", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:7"),
        InlineKeyboardButton("8", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:8"),
        InlineKeyboardButton("9", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:9"),
        InlineKeyboardButton("0", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{qty}:0"),
    ])

    # Fila 4: Botón de acción principal
    if has_stock:
        if qty > 0 and can_buy:
            buttons.append([
                InlineKeyboardButton(f"🛒 Comprar {qty} (${total_price:.2f} USDT)", callback_data=f"checkout:confirm:{product_id}:{qty}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton("⊞ Recargar Saldo", callback_data="wallet:deposit_menu")
            ])
    else:
        # Si está agotado: Opción de activar/desactivar alerta automática de restock
        if is_alert_active:
            buttons.append([
                InlineKeyboardButton("🔕 Alerta Activa (Toca para Cancelar)", callback_data=f"stock_alert:unsub:{product_id}:{filter_mode}:{page}:{qty}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton("🔔 Avisarme cuando haya stock", callback_data=f"stock_alert:sub:{product_id}:{filter_mode}:{page}:{qty}")
            ])

    # Fila 5: Compartir Enlace y Ver Nota
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}&text=Mira%20este%20servicio%20disponible!"
    buttons.append([
        InlineKeyboardButton("🔗 Compartir Enlace 📋", url=share_url),
        InlineKeyboardButton("📝 Ver Nota", callback_data=f"pnote:{product_id}:{filter_mode}:{page}:{qty}")
    ])

    # Fila 6: Botón Volver
    buttons.append([
        InlineKeyboardButton("Volver", callback_data=f"catalog:{filter_mode}:{page}")
    ])

    return InlineKeyboardMarkup(buttons)

def register_catalog_handlers(app: Client):

    @app.on_callback_query(filters.regex(r"^catalog:([a-z_]+):(\d+)$"))
    async def cb_catalog(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer()
            return

        filter_mode = callback.matches[0].group(1)
        page = int(callback.matches[0].group(2))

        async with async_session() as session:
            products = await pricing_service.get_processed_catalog(session, filter_mode=filter_mode, force_refresh=False)
            items_page, total_pages, current_page = pricing_service.paginate(products, page=page, page_size=PAGE_SIZE)

            filter_title = FILTER_NAMES.get(filter_mode, "Disponibles")
            header_text = f"<b>Productos {filter_title}:</b>\n"

            if not items_page:
                header_text += "\n<i>No hay productos en esta categoría por el momento.</i>"

            keyboard = build_catalog_keyboard(items_page, current_page, total_pages, filter_mode)
            await render_screen(client, callback, header_text, keyboard)

    @app.on_callback_query(filters.regex(r"^catalog_refresh:([a-z_]+):(\d+)$"))
    async def cb_catalog_refresh(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer("⏳ Actualizando...")
            return

        await callback.answer("🔄 Sincronizando catálogo en tiempo real...")
        filter_mode = callback.matches[0].group(1)
        page = int(callback.matches[0].group(2))

        async with async_session() as session:
            products = await pricing_service.get_processed_catalog(session, filter_mode=filter_mode, force_refresh=True)
            items_page, total_pages, current_page = pricing_service.paginate(products, page=page, page_size=PAGE_SIZE)

            filter_title = FILTER_NAMES.get(filter_mode, "Disponibles")
            header_text = f"<b>Productos {filter_title}:</b>\n"

            if not items_page:
                header_text += "\n<i>No hay productos en esta categoría por el momento.</i>"

            keyboard = build_catalog_keyboard(items_page, current_page, total_pages, filter_mode)
            await render_screen(client, callback, header_text, keyboard)

    @app.on_callback_query(filters.regex("^catalog:search_prompt$"))
    async def cb_search_prompt(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        SEARCH_STATES[user_id] = True

        text = (
            "🔍 <b>BUSCADOR DE SERVICIOS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Escribe el nombre del servicio que buscas (ejemplo: <code>Gemini</code>, <code>Netflix</code>, <code>Office</code>, <code>ChatGPT</code>).\n\n"
            "<i>O escribe <code>/buscar nombre</code> en cualquier momento.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Volver", callback_data="catalog:disponibles:1")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_message(filters.command("buscar") & filters.private)
    async def cmd_search(client: Client, message: Message):
        user_id = message.from_user.id
        try:
            await message.delete()
        except Exception:
            pass

        if len(message.command) < 2:
            text = "🔍 Por favor escribe el nombre a buscar (ej: <code>/buscar netflix</code> o <code>/buscar gemini</code>)."
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Volver", callback_data="catalog:disponibles:1")]])
            await render_screen(client, user_id, text, keyboard)
            return

        query = " ".join(message.command[1:]).lower()
        await execute_search(client, user_id, query)

    @app.on_message(filters.private & filters.text & ~filters.command(["start", "admin", "buscar"]))
    async def handle_search_text(client: Client, message: Message):
        user_id = message.from_user.id
        if SEARCH_STATES.pop(user_id, None):
            try:
                await message.delete()
            except Exception:
                pass
            query = message.text.strip().lower()
            await execute_search(client, user_id, query)

    async def execute_search(client: Client, user_id: int, query: str):
        async with async_session() as session:
            products = await pricing_service.get_processed_catalog(session, filter_mode="todos", force_refresh=False)
            results = [p for p in products if query in p["name"].lower() or query in p["product_id"].lower()]

            if not results:
                text = (
                    f"🔍 <b>Resultados de búsqueda para:</b> <i>'{query}'</i>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "❌ No se encontraron productos con ese nombre."
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛒 Volver al Catálogo", callback_data="catalog:disponibles:1")],
                    [InlineKeyboardButton("Volver", callback_data="menu_main")]
                ])
                await render_screen(client, user_id, text, keyboard)
                return

            items_page, total_pages, current_page = pricing_service.paginate(results, page=1, page_size=PAGE_SIZE)
            text = f"🔍 <b>Resultados para:</b> <i>'{query}'</i> ({len(results)} encontrados):\n"
            keyboard = build_catalog_keyboard(items_page, current_page, total_pages, "todos")
            await render_screen(client, user_id, text, keyboard)

    @app.on_callback_query(filters.regex(r"^product:view:([a-zA-Z0-9_\-]+):([a-z_]+):(\d+):(\d+)$"))
    async def cb_product_view(client: Client, callback: CallbackQuery):
        """Muestra la vista del producto con calculadora interactiva y garantías al 50%"""
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer()
            return

        product_id = callback.matches[0].group(1)
        filter_mode = callback.matches[0].group(2)
        page = int(callback.matches[0].group(3))
        qty = int(callback.matches[0].group(4))

        bot_info = await client.get_me()

        async with async_session() as session:
            p_data = await bunai_api.get_product(product_id)
            if not p_data:
                await callback.answer("❌ El producto no se encuentra disponible.", show_alert=True)
                return

            user_stmt = select(User).where(User.telegram_id == user_id)
            u_res = await session.execute(user_stmt)
            user = u_res.scalar_one_or_none()
            user_balance = float(user.balance) if user else 0.0

            # Verificar si el usuario tiene alerta activa
            alert_stmt = select(StockAlert).where(
                StockAlert.user_id == user_id,
                StockAlert.product_id == product_id,
                StockAlert.is_active == True
            )
            alert_res = await session.execute(alert_stmt)
            is_alert_active = alert_res.scalar_one_or_none() is not None

            base_price = float(p_data.get("price", 0.0))
            unit_price = await pricing_service.calculate_product_price(base_price, product_id, session)

            name = p_data.get("display_name") or p_data.get("name") or "Servicio Digital"
            icon = get_product_icon(name)
            stock_count = int(p_data.get("stock_count", 0))
            infinite_stock = bool(p_data.get("infinite_stock", False))
            bunai_warranty = int(p_data.get("warranty_hours", 0))
            adjusted_warranty = pricing_service.calculate_adjusted_warranty(bunai_warranty)
            has_promo = bool(p_data.get("has_promo", False))
            has_stock = infinite_stock or stock_count > 0

            stock_display = "Ilimitado (∞)" if infinite_stock else (f"{stock_count}" if stock_count > 0 else "0 (Agotado)")
            warranty_display = "Sin Garantía" if adjusted_warranty == 0 else (f"{adjusted_warranty // 24} Días" if adjusted_warranty >= 24 and adjusted_warranty % 24 == 0 else f"{adjusted_warranty} Horas")

            offer_line = ""
            discount_pct = 0.0
            if has_promo:
                promo_tiers = p_data.get("promo_tiers")
                if isinstance(promo_tiers, list) and len(promo_tiers) > 0:
                    tier = promo_tiers[0]
                    offer_line = f"\n\n🎁 <b>Oferta: Compra {tier.get('qty', 100)}+ ➔ -{tier.get('discount', 5.0)}% Desc</b>"
                    if qty >= tier.get("qty", 100):
                        discount_pct = float(tier.get("discount", 5.0))
                elif isinstance(promo_tiers, dict) and len(promo_tiers) > 0:
                    first_min = next(iter(promo_tiers))
                    offer_line = f"\n\n🎁 <b>Oferta: Compra {first_min}+ ➔ -{promo_tiers[first_min]}% Desc</b>"

            calc_qty = max(1, qty) if qty > 0 else 0
            subtotal = calc_qty * unit_price
            if discount_pct > 0:
                subtotal = subtotal * (1.0 - (discount_pct / 100.0))
            total_price = subtotal if qty > 0 else unit_price

            can_buy = (user_balance >= total_price) and (infinite_stock or stock_count >= qty)

            text = (
                f"{icon} <b>Producto:</b> {name}\n"
                f"🏷️ <b>Precio Base:</b> {unit_price:.2f} USDT\n"
                f"🎲 <b>Stock Disponible:</b> {stock_display}\n"
                f"⭐ <b>Garantía:</b> {warranty_display}"
                f"{offer_line}\n\n"
                f"🧮 <b>Cant. Seleccionada:</b> {qty}\n"
                f"👛 <b>Monto Total:</b> {total_price:.2f} USDT\n"
                f"👛 <b>Saldo:</b> {user_balance:.2f} USDT"
            )

            keyboard = build_product_calculator_keyboard(
                product_id=product_id,
                filter_mode=filter_mode,
                page=page,
                qty=qty,
                can_buy=can_buy,
                has_stock=has_stock,
                is_alert_active=is_alert_active,
                total_price=total_price,
                bot_username=bot_info.username
            )

            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^stock_alert:(sub|unsub):([a-zA-Z0-9_\-]+):([a-z_]+):(\d+):(\d+)$"))
    async def cb_stock_alert_toggle(client: Client, callback: CallbackQuery):
        """Maneja la suscripción / cancelación de alertas de stock para un producto"""
        action = callback.matches[0].group(1)
        product_id = callback.matches[0].group(2)
        filter_mode = callback.matches[0].group(3)
        page = int(callback.matches[0].group(4))
        qty = int(callback.matches[0].group(5))
        user_id = callback.from_user.id

        p_data = await bunai_api.get_product(product_id)
        product_name = p_data.get("display_name") or p_data.get("name") or "Servicio Digital" if p_data else "Servicio Digital"

        async with async_session() as session:
            stmt = select(StockAlert).where(
                StockAlert.user_id == user_id,
                StockAlert.product_id == product_id,
                StockAlert.is_active == True
            )
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()

            if action == "sub":
                if not existing:
                    new_alert = StockAlert(
                        user_id=user_id,
                        product_id=product_id,
                        product_name=product_name,
                        is_active=True
                    )
                    session.add(new_alert)
                    await session.commit()
                await callback.answer("🔔 ¡Alerta activada! Te enviaremos un mensaje privado automático cuando haya stock.", show_alert=True)
            else:
                if existing:
                    existing.is_active = False
                    await session.commit()
                await callback.answer("🔕 Alerta de stock cancelada.", show_alert=True)

        # Re-renderizar vista de producto
        await cb_product_view(client, callback)

    @app.on_callback_query(filters.regex(r"^pqty:([a-zA-Z0-9_\-]+):([a-z_]+):(\d+):(\d+):([0-9]|del)$"))
    async def cb_keypad_press(client: Client, callback: CallbackQuery):
        """Maneja los toques en el teclado numérico (1-0 y Del)"""
        product_id = callback.matches[0].group(1)
        filter_mode = callback.matches[0].group(2)
        page = int(callback.matches[0].group(3))
        current_qty = int(callback.matches[0].group(4))
        action = callback.matches[0].group(5)

        if action == "del":
            qty_str = str(current_qty)
            new_qty_str = qty_str[:-1] if len(qty_str) > 1 else "0"
            new_qty = int(new_qty_str)
        else:
            digit = action
            if current_qty == 0:
                new_qty = int(digit)
            else:
                new_qty_str = f"{current_qty}{digit}"
                new_qty = min(999, int(new_qty_str))

        bot_info = await client.get_me()

        async with async_session() as session:
            p_data = await bunai_api.get_product(product_id)
            if not p_data:
                await callback.answer("❌ El producto no se encuentra disponible.", show_alert=True)
                return

            user_stmt = select(User).where(User.telegram_id == callback.from_user.id)
            u_res = await session.execute(user_stmt)
            user = u_res.scalar_one_or_none()
            user_balance = float(user.balance) if user else 0.0

            alert_stmt = select(StockAlert).where(
                StockAlert.user_id == callback.from_user.id,
                StockAlert.product_id == product_id,
                StockAlert.is_active == True
            )
            alert_res = await session.execute(alert_stmt)
            is_alert_active = alert_res.scalar_one_or_none() is not None

            base_price = float(p_data.get("price", 0.0))
            unit_price = await pricing_service.calculate_product_price(base_price, product_id, session)

            name = p_data.get("display_name") or p_data.get("name") or "Servicio Digital"
            icon = get_product_icon(name)
            stock_count = int(p_data.get("stock_count", 0))
            infinite_stock = bool(p_data.get("infinite_stock", False))
            bunai_warranty = int(p_data.get("warranty_hours", 0))
            adjusted_warranty = pricing_service.calculate_adjusted_warranty(bunai_warranty)
            has_promo = bool(p_data.get("has_promo", False))
            has_stock = infinite_stock or stock_count > 0

            stock_display = "Ilimitado (∞)" if infinite_stock else (f"{stock_count}" if stock_count > 0 else "0 (Agotado)")
            warranty_display = "Sin Garantía" if adjusted_warranty == 0 else (f"{adjusted_warranty // 24} Días" if adjusted_warranty >= 24 and adjusted_warranty % 24 == 0 else f"{adjusted_warranty} Horas")

            offer_line = ""
            discount_pct = 0.0
            if has_promo:
                promo_tiers = p_data.get("promo_tiers")
                if isinstance(promo_tiers, list) and len(promo_tiers) > 0:
                    tier = promo_tiers[0]
                    offer_line = f"\n\n🎁 <b>Oferta: Compra {tier.get('qty', 100)}+ ➔ -{tier.get('discount', 5.0)}% Desc</b>"
                    if new_qty >= tier.get("qty", 100):
                        discount_pct = float(tier.get("discount", 5.0))
                elif isinstance(promo_tiers, dict) and len(promo_tiers) > 0:
                    first_min = next(iter(promo_tiers))
                    offer_line = f"\n\n🎁 <b>Oferta: Compra {first_min}+ ➔ -{promo_tiers[first_min]}% Desc</b>"

            calc_qty = max(1, new_qty) if new_qty > 0 else 0
            subtotal = calc_qty * unit_price
            if discount_pct > 0:
                subtotal = subtotal * (1.0 - (discount_pct / 100.0))
            total_price = subtotal if new_qty > 0 else unit_price

            can_buy = (user_balance >= total_price) and (infinite_stock or stock_count >= new_qty)

            text = (
                f"{icon} <b>Producto:</b> {name}\n"
                f"🏷️ <b>Precio Base:</b> {unit_price:.2f} USDT\n"
                f"🎲 <b>Stock Disponible:</b> {stock_display}\n"
                f"⭐ <b>Garantía:</b> {warranty_display}"
                f"{offer_line}\n\n"
                f"🧮 <b>Cant. Seleccionada:</b> {new_qty}\n"
                f"👛 <b>Monto Total:</b> {total_price:.2f} USDT\n"
                f"👛 <b>Saldo:</b> {user_balance:.2f} USDT"
            )

            keyboard = build_product_calculator_keyboard(
                product_id=product_id,
                filter_mode=filter_mode,
                page=page,
                qty=new_qty,
                can_buy=can_buy,
                has_stock=has_stock,
                is_alert_active=is_alert_active,
                total_price=total_price,
                bot_username=bot_info.username
            )

            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^pnote:([a-zA-Z0-9_\-]+):([a-z_]+):(\d+):(\d+)$"))
    async def cb_product_note(client: Client, callback: CallbackQuery):
        """Muestra la Nota del Admin (Foto 3) con bloque blockquote y botón Atrás"""
        product_id = callback.matches[0].group(1)
        filter_mode = callback.matches[0].group(2)
        page = int(callback.matches[0].group(3))
        qty = int(callback.matches[0].group(4))

        p_data = await bunai_api.get_product(product_id)
        note = p_data.get("note") if p_data else ""
        if not note:
            note = "No hay notas o términos adicionales configurados para este producto."

        text = (
            f"📝 <b>Nota del Admin:</b>\n\n"
            f"<blockquote>{note}</blockquote>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Atrás", callback_data=f"product:view:{product_id}:{filter_mode}:{page}:{qty}")]
        ])

        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex("^noop$"))
    async def cb_noop(client: Client, callback: CallbackQuery):
        await callback.answer()
