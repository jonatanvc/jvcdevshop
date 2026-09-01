from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, update
from bot.database.session import async_session
from bot.database.models import User, StockAlert
from bot.services.pricing import pricing_service, PAGE_SIZE
from bot.services.bunai_client import bunai_api
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t

SEARCH_STATES = {}

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
    return "🏷️"

def build_catalog_keyboard(items: list, page: int, total_pages: int, filter_mode: str, lang: str = "es") -> InlineKeyboardMarkup:
    """Construye la botonera inline del catálogo ultra limpia con botón de categorías dedicado"""
    buttons = []

    # 1. Botones de cada producto
    for p in items:
        icon = get_product_icon(p["name"])
        stock_str = t("stock_unlimited", lang) if p["infinite_stock"] else (str(p["stock_count"]) if p["stock_count"] > 0 else t("stock_out", lang))
        price_str = f"{p['user_price']:.2f}".rstrip("0").rstrip(".") if p["user_price"] % 1 != 0 else f"{int(p['user_price'])}"
        
        btn_text = f"{icon} {p['name']} - {price_str} USDT (Stock: {stock_str})"
        buttons.append([
            InlineKeyboardButton(btn_text, callback_data=f"product:view:{p['product_id']}:{filter_mode}:{page}:0")
        ])

    # 2. Fila de paginación (si hay más de 1 página)
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("◀️", callback_data=f"catalog:{filter_mode}:{page - 1}"))
        else:
            nav_row.append(InlineKeyboardButton("⏺️", callback_data="noop"))

        nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))

        if page < total_pages:
            nav_row.append(InlineKeyboardButton("▶️", callback_data=f"catalog:{filter_mode}:{page + 1}"))
        else:
            nav_row.append(InlineKeyboardButton("⏺️", callback_data="noop"))
        
        buttons.append(nav_row)

    # 3. Fila de Controles: Actualizar y Selector Directo de Categorías
    buttons.append([
        InlineKeyboardButton(t("btn_refresh", lang), callback_data=f"catalog_refresh:{filter_mode}:{page}"),
        InlineKeyboardButton(t("btn_categories", lang), callback_data=f"catalog:picker:{filter_mode}:{page}")
    ])

    # 4. Buscador y Volver al Menú Principal
    buttons.append([
        InlineKeyboardButton(t("btn_search_service", lang), callback_data="catalog:search_prompt"),
        InlineKeyboardButton(t("btn_back", lang), callback_data="menu_main")
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
    bot_username: str,
    lang: str = "es"
) -> InlineKeyboardMarkup:
    """Construye el teclado numérico interactivo traducido"""
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
                InlineKeyboardButton(t("btn_buy_qty", lang, qty=qty, total=f"{total_price:.2f}"), callback_data=f"checkout:confirm:{product_id}:{qty}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(t("btn_recharge_balance", lang), callback_data="wallet:deposit_menu")
            ])
    else:
        if is_alert_active:
            buttons.append([
                InlineKeyboardButton(t("btn_cancel_stock_alert", lang), callback_data=f"stock_alert:unsub:{product_id}:{filter_mode}:{page}:{qty}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(t("btn_notify_stock", lang), callback_data=f"stock_alert:sub:{product_id}:{filter_mode}:{page}:{qty}")
            ])

    # Fila 5: Compartir Enlace y Ver Nota
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}&text=Check%20out%20this%20service!"
    buttons.append([
        InlineKeyboardButton(t("btn_share_link", lang), url=share_url),
        InlineKeyboardButton(t("btn_view_note", lang), callback_data=f"pnote:{product_id}:{filter_mode}:{page}:{qty}")
    ])

    # Fila 6: Botón Volver
    buttons.append([
        InlineKeyboardButton(t("btn_back", lang), callback_data=f"catalog:{filter_mode}:{page}")
    ])

    return InlineKeyboardMarkup(buttons)

def register_catalog_handlers(app: Client):

    @app.on_callback_query(filters.regex(r"^catalog:picker:([a-z_]+):(\d+)$"))
    async def cb_catalog_picker(client: Client, callback: CallbackQuery):
        """Muestra el menú selector directo de categorías con conteo en tiempo real"""
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer()
            return

        current_filter = callback.matches[0].group(1)
        current_page = int(callback.matches[0].group(2))

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

            counts = await pricing_service.get_category_counts(session)

            text = t("cat_picker_title", lang)
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(t("cat_opt_disponibles", lang, count=counts["disponibles"]), callback_data="catalog:disponibles:1"),
                    InlineKeyboardButton(t("cat_opt_ofertas", lang, count=counts["ofertas"]), callback_data="catalog:ofertas:1")
                ],
                [
                    InlineKeyboardButton(t("cat_opt_agotados", lang, count=counts["agotados"]), callback_data="catalog:agotados:1"),
                    InlineKeyboardButton(t("cat_opt_todos", lang, count=counts["todos"]), callback_data="catalog:todos:1")
                ],
                [
                    InlineKeyboardButton(t("btn_back", lang), callback_data=f"catalog:{current_filter}:{current_page}")
                ]
            ])
            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^catalog:([a-z_]+):(\d+)$"))
    async def cb_catalog(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer()
            return

        filter_mode = callback.matches[0].group(1)
        page = int(callback.matches[0].group(2))

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

            products = await pricing_service.get_processed_catalog(session, filter_mode=filter_mode, force_refresh=False)
            items_page, total_pages, current_page = pricing_service.paginate(products, page=page, page_size=PAGE_SIZE)

            header_key = f"catalog_header_{filter_mode}"
            header_text = f"{t(header_key, lang, count=len(products))}\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"

            if not items_page:
                header_text += f"<i>{t('catalog_empty', lang)}</i>\n"

            keyboard = build_catalog_keyboard(items_page, current_page, total_pages, filter_mode, lang)
            await render_screen(client, callback, header_text, keyboard)

    @app.on_callback_query(filters.regex(r"^catalog_refresh:([a-z_]+):(\d+)$"))
    async def cb_catalog_refresh(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer("⏳ ...")
            return

        await callback.answer("🔄 Sincronizando...")
        filter_mode = callback.matches[0].group(1)
        page = int(callback.matches[0].group(2))

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

            products = await pricing_service.get_processed_catalog(session, filter_mode=filter_mode, force_refresh=True)
            items_page, total_pages, current_page = pricing_service.paginate(products, page=page, page_size=PAGE_SIZE)

            header_key = f"catalog_header_{filter_mode}"
            header_text = f"{t(header_key, lang, count=len(products))}\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"

            if not items_page:
                header_text += f"<i>{t('catalog_empty', lang)}</i>\n"

            keyboard = build_catalog_keyboard(items_page, current_page, total_pages, filter_mode, lang)
            await render_screen(client, callback, header_text, keyboard)

    @app.on_callback_query(filters.regex("^catalog:search_prompt$"))
    async def cb_search_prompt(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        SEARCH_STATES[user_id] = True

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        text = t("search_prompt_title", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_back", lang), callback_data="catalog:disponibles:1")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_message(filters.command("buscar") & filters.private)
    async def cmd_search(client: Client, message: Message):
        user_id = message.from_user.id
        try:
            await message.delete()
        except Exception:
            pass

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        if len(message.command) < 2:
            text = t("search_prompt_title", lang)
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_back", lang), callback_data="catalog:disponibles:1")]])
            await render_screen(client, user_id, text, keyboard)
            return

        query = " ".join(message.command[1:]).lower()
        await execute_search(client, user_id, query, lang)

    @app.on_message(filters.private & filters.text & ~filters.command(["start", "admin", "buscar"]), group=1)
    async def handle_search_text(client: Client, message: Message):
        user_id = message.from_user.id
        if not SEARCH_STATES.get(user_id):
            message.continue_propagation()
            return

        SEARCH_STATES.pop(user_id, None)
        try:
            await message.delete()
        except Exception:
            pass
        query = message.text.strip().lower()

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        await execute_search(client, user_id, query, lang)

    async def execute_search(client: Client, user_id: int, query: str, lang: str):
        async with async_session() as session:
            products = await pricing_service.get_processed_catalog(session, filter_mode="todos", force_refresh=False)
            results = [p for p in products if query in p["name"].lower() or query in p["product_id"].lower()]

            if not results:
                text = t("search_no_results", lang, query=query)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")],
                    [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
                ])
                await render_screen(client, user_id, text, keyboard)
                return

            items_page, total_pages, current_page = pricing_service.paginate(results, page=1, page_size=PAGE_SIZE)
            text = t("search_results_title", lang, query=query, count=len(results)) + "\n"
            keyboard = build_catalog_keyboard(items_page, current_page, total_pages, "todos", lang)
            await render_screen(client, user_id, text, keyboard)

    @app.on_callback_query(filters.regex(r"^product:view:([a-zA-Z0-9_\-]+):([a-z_]+):(\d+):(\d+)$"))
    async def cb_product_view(client: Client, callback: CallbackQuery):
        """Muestra la vista del producto con calculadora interactiva y garantías traducidas"""
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
                await callback.answer("❌ No disponible / Not available", show_alert=True)
                return

            user_stmt = select(User).where(User.telegram_id == user_id)
            u_res = await session.execute(user_stmt)
            user = u_res.scalar_one_or_none()
            user_balance = float(user.balance) if user else 0.0
            lang = getattr(user, "language", "es") or "es"

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

            stock_display = t("stock_unlimited", lang) if infinite_stock else (f"{stock_count}" if stock_count > 0 else f"0 ({t('stock_out', lang)})")
            
            if adjusted_warranty == 0:
                warranty_display = t("no_warranty", lang)
            elif adjusted_warranty >= 24 and adjusted_warranty % 24 == 0:
                warranty_display = t("warranty_days", lang, days=adjusted_warranty // 24)
            else:
                warranty_display = t("warranty_hours", lang, hours=adjusted_warranty)

            offer_line = ""
            discount_pct = 0.0
            if has_promo:
                promo_tiers = p_data.get("promo_tiers")
                if isinstance(promo_tiers, list) and len(promo_tiers) > 0:
                    tier = promo_tiers[0]
                    offer_line = f"\n\n{t('promo_offer_text', lang, qty=tier.get('qty', 100), discount=tier.get('discount', 5.0))}"
                    if qty >= tier.get("qty", 100):
                        discount_pct = float(tier.get("discount", 5.0))
                elif isinstance(promo_tiers, dict) and len(promo_tiers) > 0:
                    first_min = next(iter(promo_tiers))
                    offer_line = f"\n\n{t('promo_offer_text', lang, qty=first_min, discount=promo_tiers[first_min])}"

            calc_qty = max(1, qty) if qty > 0 else 0
            subtotal = calc_qty * unit_price
            if discount_pct > 0:
                subtotal = subtotal * (1.0 - (discount_pct / 100.0))
            total_price = subtotal if qty > 0 else unit_price

            can_buy = (user_balance >= total_price) and (infinite_stock or stock_count >= qty)

            text = (
                f"{icon} <b>{t('product_label', lang)}:</b> {name}\n"
                f"🏷️ <b>{t('base_price_label', lang)}:</b> {unit_price:.2f} USDT\n"
                f"🎲 <b>{t('available_stock_label', lang)}:</b> {stock_display}\n"
                f"⭐ <b>{t('warranty_label', lang)}:</b> {warranty_display}"
                f"{offer_line}\n\n"
                f"🧮 <b>{t('selected_qty', lang)}:</b> {qty}\n"
                f"👛 <b>{t('total_amount', lang)}:</b> {total_price:.2f} USDT\n"
                f"👛 <b>{t('your_balance', lang)}:</b> {user_balance:.2f} USDT"
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
                bot_username=bot_info.username,
                lang=lang
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
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

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
                await callback.answer(t("alert_activated", lang), show_alert=True)
            else:
                if existing:
                    existing.is_active = False
                    await session.commit()
                await callback.answer(t("alert_cancelled", lang), show_alert=True)

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
                await callback.answer("❌ No disponible", show_alert=True)
                return

            user_stmt = select(User).where(User.telegram_id == callback.from_user.id)
            u_res = await session.execute(user_stmt)
            user = u_res.scalar_one_or_none()
            user_balance = float(user.balance) if user else 0.0
            lang = getattr(user, "language", "es") or "es"

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

            stock_display = t("stock_unlimited", lang) if infinite_stock else (f"{stock_count}" if stock_count > 0 else f"0 ({t('stock_out', lang)})")
            
            if adjusted_warranty == 0:
                warranty_display = t("no_warranty", lang)
            elif adjusted_warranty >= 24 and adjusted_warranty % 24 == 0:
                warranty_display = t("warranty_days", lang, days=adjusted_warranty // 24)
            else:
                warranty_display = t("warranty_hours", lang, hours=adjusted_warranty)

            offer_line = ""
            discount_pct = 0.0
            if has_promo:
                promo_tiers = p_data.get("promo_tiers")
                if isinstance(promo_tiers, list) and len(promo_tiers) > 0:
                    tier = promo_tiers[0]
                    offer_line = f"\n\n{t('promo_offer_text', lang, qty=tier.get('qty', 100), discount=tier.get('discount', 5.0))}"
                    if new_qty >= tier.get("qty", 100):
                        discount_pct = float(tier.get("discount", 5.0))
                elif isinstance(promo_tiers, dict) and len(promo_tiers) > 0:
                    first_min = next(iter(promo_tiers))
                    offer_line = f"\n\n{t('promo_offer_text', lang, qty=first_min, discount=promo_tiers[first_min])}"

            calc_qty = max(1, new_qty) if new_qty > 0 else 0
            subtotal = calc_qty * unit_price
            if discount_pct > 0:
                subtotal = subtotal * (1.0 - (discount_pct / 100.0))
            total_price = subtotal if new_qty > 0 else unit_price

            can_buy = (user_balance >= total_price) and (infinite_stock or stock_count >= new_qty)

            text = (
                f"{icon} <b>{t('product_label', lang)}:</b> {name}\n"
                f"🏷️ <b>{t('base_price_label', lang)}:</b> {unit_price:.2f} USDT\n"
                f"🎲 <b>{t('available_stock_label', lang)}:</b> {stock_display}\n"
                f"⭐ <b>{t('warranty_label', lang)}:</b> {warranty_display}"
                f"{offer_line}\n\n"
                f"🧮 <b>{t('selected_qty', lang)}:</b> {new_qty}\n"
                f"👛 <b>{t('total_amount', lang)}:</b> {total_price:.2f} USDT\n"
                f"👛 <b>{t('your_balance', lang)}:</b> {user_balance:.2f} USDT"
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
                bot_username=bot_info.username,
                lang=lang
            )

            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^pnote:([a-zA-Z0-9_\-]+):([a-z_]+):(\d+):(\d+)$"))
    async def cb_product_note(client: Client, callback: CallbackQuery):
        """Muestra la Nota del Admin traducida"""
        product_id = callback.matches[0].group(1)
        filter_mode = callback.matches[0].group(2)
        page = int(callback.matches[0].group(3))
        qty = int(callback.matches[0].group(4))
        user_id = callback.from_user.id

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        p_data = await bunai_api.get_product(product_id)
        note = p_data.get("note") if p_data else ""
        if not note:
            note = t("no_admin_note", lang)

        text = (
            f"{t('admin_note_title', lang)}\n\n"
            f"<blockquote>{note}</blockquote>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_back", lang), callback_data=f"product:view:{product_id}:{filter_mode}:{page}:{qty}")]
        ])

        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex("^noop$"))
    async def cb_noop(client: Client, callback: CallbackQuery):
        await callback.answer()
