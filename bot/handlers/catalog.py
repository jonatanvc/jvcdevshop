import asyncio
from typing import Union
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, StockAlert
from bot.services.pricing import pricing_service, PAGE_SIZE
from bot.services.bunai_client import bunai_api
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.translator import translate_text
from bot.utils.emojis import (
    get_service_icon, get_service_custom_emoji_id, EMOJI_TAG, EMOJI_DICE, EMOJI_MONEY,
    EMOJI_WALLET, EMOJI_CALC, EMOJI_STAR, EMOJI_PROVIDER, EMOJI_WARN, EMOJI_BELL
)

SEARCH_STATES = {}
CUSTOM_QTY_STATES = {}

def get_product_icon(name: str, for_html: bool = False) -> str:
    """Asigna un icono representativo según el catálogo de servicios"""
    return get_service_icon(name, for_html=for_html)

def build_catalog_keyboard(items: list, page: int, total_pages: int, filter_mode: str, lang: str = "es", is_vip: bool = False) -> InlineKeyboardMarkup:
    """Construye la botonera inline del catálogo ultra limpia con botón de categorías dedicado y precios VIP"""
    buttons = []

    # 1. Botones de cada producto
    for p in items:
        if is_vip:
            vip_price = p.get("vip_price") or round(p["user_price"] * 0.80, 2)
            btn_title = f"{p['name']} (${vip_price:.2f} ⭐)"
        else:
            btn_title = p["name"]
        btn = InlineKeyboardButton(btn_title, callback_data=f"product:view:{p['product_id']}:{filter_mode}:{page}:1")
        btn.icon_custom_emoji_id = get_service_custom_emoji_id(p["name"])
        buttons.append([btn])

    # 2. Fila de paginación (si hay más de 1 página)
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("◀️", callback_data=f"catalog:{filter_mode}:{page - 1}"))
        else:
            nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))

        nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))

        if page < total_pages:
            nav_row.append(InlineKeyboardButton("▶️", callback_data=f"catalog:{filter_mode}:{page + 1}"))
        else:
            nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))
        
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
    has_note: bool = False,
    lang: str = "es",
    is_owner: bool = False,
    api_balance: float = 0.0,
    user_balance: float = 0.0,
    stock_count: int = 0,
    infinite_stock: bool = False
) -> InlineKeyboardMarkup:
    """Construye la botonera interactiva y limpia para seleccionar cantidad y comprar"""
    buttons = []

    # Si el producto NO tiene stock disponible:
    if not has_stock:
        # Fila principal destacada: Botón de Alerta de Stock
        if is_alert_active:
            buttons.append([
                InlineKeyboardButton(t("btn_cancel_stock_alert", lang), callback_data=f"stock_alert:unsub:{product_id}:{filter_mode}:{page}:{qty}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(t("btn_notify_stock", lang), callback_data=f"stock_alert:sub:{product_id}:{filter_mode}:{page}:{qty}")
            ])

        # Ver Nota si existe
        if has_note:
            buttons.append([
                InlineKeyboardButton(t("btn_view_note", lang), callback_data=f"pnote:{product_id}:{filter_mode}:{page}:{qty}")
            ])

        # Botón Volver
        buttons.append([
            InlineKeyboardButton(t("btn_back", lang), callback_data=f"catalog:{filter_mode}:{page}")
        ])
        return InlineKeyboardMarkup(buttons)

    # Si el producto TIENE stock disponible:
    calc_qty = max(1, qty)
    prev_qty = max(1, qty - 1)
    next_qty = min(stock_count, qty + 1) if not infinite_stock else qty + 1

    # Fila 1: Stepper interactivo (+ / -) y cantidad actual (sin poder superar el stock disponible)
    buttons.append([
        InlineKeyboardButton("➖ 1", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{prev_qty}"),
        InlineKeyboardButton(f"🧮 Cant: {calc_qty}", callback_data="noop"),
        InlineKeyboardButton("➕ 1", callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{next_qty}")
    ])

    # Fila 2: Presets de cantidades comunes que no excedan el stock disponible
    preset_options = [1, 5, 10, 25, 50]
    preset_vals = [p for p in preset_options if infinite_stock or p <= stock_count]
    if not infinite_stock and stock_count > 1 and stock_count not in preset_vals:
        preset_vals.append(stock_count)

    if preset_vals:
        preset_row = []
        for p in preset_vals:
            lbl = f"{p}" if (infinite_stock or p != stock_count or p in preset_options) else f"Máx ({p})"
            preset_row.append(InlineKeyboardButton(lbl, callback_data=f"pqty:{product_id}:{filter_mode}:{page}:{p}"))
        buttons.append(preset_row)

    # Fila 3: Botón para ingresar cualquier cantidad personalizada
    buttons.append([
        InlineKeyboardButton("📝 Ingresar Cantidad Personalizada", callback_data=f"pqty_custom:{product_id}:{filter_mode}:{page}:{calc_qty}")
    ])

    # Fila 4: Botones de acción principal (compra)
    if is_owner:
        can_buy_api = (api_balance >= total_price)
        can_buy_bot = (user_balance >= total_price)

        if can_buy_api:
            buttons.append([
                InlineKeyboardButton(
                    f"👑 Comprar {calc_qty} con Saldo API (${total_price:.2f} USD)",
                    callback_data=f"checkout:confirm:{product_id}:{calc_qty}:api"
                )
            ])

        if can_buy_bot:
            buttons.append([
                InlineKeyboardButton(
                    f"🛍️ Comprar {calc_qty} con Saldo Bot (${total_price:.2f} USD)",
                    callback_data=f"checkout:confirm:{product_id}:{calc_qty}:bot"
                )
            ])

        if not can_buy_api and not can_buy_bot:
            buttons.append([
                InlineKeyboardButton(t("btn_recharge_balance", lang), callback_data="wallet_main")
            ])
    else:
        if can_buy:
            buttons.append([
                InlineKeyboardButton(
                    f"🛍️ Comprar {calc_qty} por ${total_price:.2f} USD",
                    callback_data=f"checkout:confirm:{product_id}:{calc_qty}:bot"
                )
            ])
        else:
            buttons.append([
                InlineKeyboardButton(t("btn_recharge_balance", lang), callback_data="wallet_main")
            ])

    # Fila 5: Ver Nota (solo si el producto tiene nota configurada)
    if has_note:
        buttons.append([
            InlineKeyboardButton(t("btn_view_note", lang), callback_data=f"pnote:{product_id}:{filter_mode}:{page}:{calc_qty}")
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

            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            is_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now_utc)

            vip_banner = "👑 <i>(Modo Revendedor VIP: 20% OFF aplicado en todo el catálogo)</i>\n\n" if is_vip else ""
            header_key = f"catalog_header_{filter_mode}"
            header_text = f"{vip_banner}{t(header_key, lang, count=len(products))}\n\n"

            if not items_page:
                header_text += f"<i>{t('catalog_empty', lang)}</i>\n"

            keyboard = build_catalog_keyboard(items_page, current_page, total_pages, filter_mode, lang, is_vip=is_vip)
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

            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            is_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now_utc)

            vip_banner = "👑 <i>(Modo Revendedor VIP: 20% OFF aplicado en todo el catálogo)</i>\n\n" if is_vip else ""
            header_key = f"catalog_header_{filter_mode}"
            header_text = f"{vip_banner}{t(header_key, lang, count=len(products))}\n\n"

            if not items_page:
                header_text += f"<i>{t('catalog_empty', lang)}</i>\n"

            keyboard = build_catalog_keyboard(items_page, current_page, total_pages, filter_mode, lang, is_vip=is_vip)
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

    @app.on_message(filters.command(["catalogo", "catalog"]) & filters.private)
    async def cmd_catalog(client: Client, message: Message):
        user_id = message.from_user.id
        try:
            await message.delete()
        except Exception:
            pass

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

            products = await pricing_service.get_processed_catalog(session, filter_mode="disponibles", force_refresh=False)
            items_page, total_pages, current_page = pricing_service.paginate(products, page=1, page_size=PAGE_SIZE)

            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            is_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now_utc)

            vip_banner = "👑 <i>(Modo Revendedor VIP: 20% OFF aplicado en todo el catálogo)</i>\n\n" if is_vip else ""
            header_text = f"{vip_banner}{t('catalog_header_disponibles', lang, count=len(products))}\n\n"
            if not items_page:
                header_text += f"<i>{t('catalog_empty', lang)}</i>\n"

            keyboard = build_catalog_keyboard(items_page, current_page, total_pages, "disponibles", lang, is_vip=is_vip)
            await render_screen(client, user_id, header_text, keyboard)

    @app.on_message(filters.command(["buscar", "search"]) & filters.private)
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

    @app.on_message(filters.private & filters.text & ~filters.command(["start", "admin", "buscar", "search", "catalogo", "catalog", "pedidos", "orders", "depositar", "deposit", "saldo", "wallet", "soporte", "support", "ayuda", "help", "del", "dep"]), group=1)
    async def handle_catalog_text_inputs(client: Client, message: Message):
        user_id = message.from_user.id

        # 1. Cantidad personalizada ingresada por el usuario
        if user_id in CUSTOM_QTY_STATES:
            state = CUSTOM_QTY_STATES.pop(user_id)
            try:
                await message.delete()
            except Exception:
                pass

            raw_txt = message.text.strip()
            if not raw_txt.isdigit() or int(raw_txt) <= 0:
                CUSTOM_QTY_STATES[user_id] = state
                err_msg = await client.send_message(
                    chat_id=user_id,
                    text="⚠️ <i>Por favor, escribe un número entero positivo válido (ej: 5, 20, 50, 150).</i>"
                )
                await asyncio.sleep(3)
                try:
                    await err_msg.delete()
                except Exception:
                    pass
                return

            input_val = int(raw_txt)
            stock_count = state.get("stock_count", 0)
            infinite_stock = state.get("infinite_stock", False)

            if not infinite_stock and stock_count > 0 and input_val > stock_count:
                new_val = stock_count
                warn_msg = await client.send_message(
                    chat_id=user_id,
                    text=f"⚠️ <i>Has solicitado {input_val} unidades, pero solo hay <b>{stock_count}</b> disponibles en stock. Se ha ajustado la cantidad al máximo disponible ({stock_count}).</i>"
                )

                async def _del_warn(m):
                    await asyncio.sleep(3.5)
                    try:
                        await m.delete()
                    except Exception:
                        pass
                asyncio.create_task(_del_warn(warn_msg))
            else:
                new_val = input_val

            await render_product_screen(
                client=client,
                target=user_id,
                product_id=state["product_id"],
                filter_mode=state["filter_mode"],
                page=state["page"],
                qty=new_val
            )
            return

        # 2. Búsqueda por texto en catálogo
        if SEARCH_STATES.get(user_id):
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
            return

        message.continue_propagation()

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

            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            is_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now_utc)

            items_page, total_pages, current_page = pricing_service.paginate(results, page=1, page_size=PAGE_SIZE)
            vip_banner = "👑 <i>(Modo Revendedor VIP: 20% OFF aplicado)</i>\n\n" if is_vip else ""
            text = f"{vip_banner}" + t("search_results_title", lang, query=query, count=len(results)) + "\n"
            keyboard = build_catalog_keyboard(items_page, current_page, total_pages, "todos", lang, is_vip=is_vip)
            await render_screen(client, user_id, text, keyboard)

    async def render_product_screen(
        client: Client,
        target: Union[CallbackQuery, int],
        product_id: str,
        filter_mode: str,
        page: int,
        qty: int
    ):
        """Renderiza la pantalla completa de detalle del producto y calculadora interactiva"""
        user_id = target.from_user.id if isinstance(target, CallbackQuery) else int(target)
        if qty <= 0:
            qty = 1

        async with async_session() as session:
            p_data = await bunai_api.get_product(product_id)
            if not p_data:
                # Buscar en el catálogo en caché local como respaldo
                cached_items = pricing_service._cached_catalog or []
                p_data = next((item for item in cached_items if item.get("product_id") == product_id), None)

            if not p_data:
                if isinstance(target, CallbackQuery):
                    try:
                        await target.answer("❌ No disponible / Not available", show_alert=True)
                    except Exception:
                        pass
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

            name = p_data.get("display_name") or p_data.get("name") or "Servicio Digital"
            icon = get_product_icon(name, for_html=True)
            stock_count = int(p_data.get("stock_count", 0))
            infinite_stock = bool(p_data.get("infinite_stock", False))
            bunai_warranty = int(p_data.get("warranty_hours", 0))
            adjusted_warranty = pricing_service.calculate_adjusted_warranty(bunai_warranty)
            has_promo = bool(p_data.get("has_promo", False))
            has_stock = infinite_stock or stock_count > 0

            # Si no hay stock disponible, la cantidad es 0.
            # Si hay stock, la cantidad seleccionada NO puede superar el stock disponible
            if not has_stock:
                qty = 0
            elif not infinite_stock and stock_count > 0:
                qty = max(1, min(qty, stock_count))
            else:
                qty = max(1, qty)

            stock_display = t("stock_unlimited", lang) if infinite_stock else (f"{stock_count}" if stock_count > 0 else f"0 ({t('stock_out', lang)})")

            if adjusted_warranty == 0:
                warranty_display = t("no_warranty", lang)
            elif adjusted_warranty >= 24 and adjusted_warranty % 24 == 0:
                warranty_display = t("warranty_days", lang, days=adjusted_warranty // 24)
            else:
                warranty_display = t("warranty_hours", lang, hours=adjusted_warranty)

            is_owner = settings.is_owner(user_id)
            base_price = float(p_data.get("price", 0.0))
            api_balance = 0.0

            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            is_active_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now_utc)

            if not has_stock:
                total_price = 0.0
                can_buy = False
                unit_price = base_price if is_owner else (await pricing_service.calculate_product_price(base_price, product_id, session))
                if is_active_vip and not is_owner:
                    vip_unit_price = pricing_service.calculate_vip_price(unit_price)
                    price_line = f"{EMOJI_TAG} <b>Precio Normal:</b> <s>{unit_price:.2f} USDT</s> ➡️ <b>VIP (-20%):</b> <code>{vip_unit_price:.2f} USDT</code> ⭐"
                else:
                    price_line = f"{EMOJI_TAG} <b>{t('base_price_label', lang)}:</b> {unit_price:.2f} USDT"
                total_line = f"{EMOJI_WARN} <b>Estado:</b> <code>Agotado / Sin Stock</code>"
                balance_line = f"{EMOJI_WALLET} <b>{t('your_balance', lang)}:</b> {user_balance:.2f} USDT"
                offer_line = ""
            elif is_owner:
                unit_price = base_price
                api_balance = await bunai_api.get_balance()
                effective_balance = api_balance
                offer_line = ""
                calc_qty = max(1, qty)
                total_price = round(calc_qty * unit_price, 2)
                can_buy = (api_balance >= total_price or user_balance >= total_price) and (infinite_stock or stock_count >= calc_qty)

                price_line = f"{EMOJI_TAG} <b>Precio Costo Proveedor:</b> <code>${unit_price:.2f} USD</code> 👑"
                total_line = f"{EMOJI_MONEY} <b>Total a Pagar (Costo):</b> <code>${total_price:.2f} USD</code> 👑"
                balance_line = (
                    f"{EMOJI_PROVIDER} <b>Saldo API BunaiStore:</b> <code>${api_balance:.2f} USD</code> 👑\n"
                    f"{EMOJI_WALLET} <b>Saldo en el Bot:</b> <code>${user_balance:.2f} USDT</code>"
                )
            else:
                unit_price = await pricing_service.calculate_product_price(base_price, product_id, session)
                effective_balance = user_balance
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

                if is_active_vip:
                    vip_unit_price = pricing_service.calculate_vip_price(unit_price)
                    price_line = f"{EMOJI_TAG} <b>Precio Normal:</b> <s>{unit_price:.2f} USDT</s> ➡️ <b>VIP (-20%):</b> <code>{vip_unit_price:.2f} USDT</code> ⭐"
                    unit_price = vip_unit_price
                else:
                    price_line = f"{EMOJI_TAG} <b>{t('base_price_label', lang)}:</b> {unit_price:.2f} USDT"

                calc_qty = max(1, qty)
                subtotal = calc_qty * unit_price
                if discount_pct > 0:
                    subtotal = subtotal * (1.0 - (discount_pct / 100.0))
                total_price = round(subtotal, 2)
                can_buy = (effective_balance >= total_price) and (infinite_stock or stock_count >= qty)

                vip_tag = " <i>(⭐ Tarifa VIP 20% OFF)</i>" if is_active_vip else ""
                total_line = f"{EMOJI_MONEY} <b>{t('total_amount', lang)}:</b> {total_price:.2f} USDT{vip_tag}"
                balance_line = f"{EMOJI_WALLET} <b>{t('your_balance', lang)}:</b> {effective_balance:.2f} USDT"

            if not has_stock:
                text = (
                    f"{icon} <b>{t('product_label', lang)}:</b> {name}\n"
                    f"{price_line}\n"
                    f"{EMOJI_DICE} <b>{t('available_stock_label', lang)}:</b> {stock_display}\n"
                    f"{EMOJI_STAR} <b>{t('warranty_label', lang)}:</b> {warranty_display}\n\n"
                    f"{total_line}\n"
                    f"{balance_line}\n\n"
                    f"<i>{EMOJI_BELL} Toca el botón de abajo para que el bot te notifique de inmediato cuando este servicio tenga stock disponible.</i>"
                )
            else:
                text = (
                    f"{icon} <b>{t('product_label', lang)}:</b> {name}\n"
                    f"{price_line}\n"
                    f"{EMOJI_DICE} <b>{t('available_stock_label', lang)}:</b> {stock_display}\n"
                    f"{EMOJI_STAR} <b>{t('warranty_label', lang)}:</b> {warranty_display}"
                    f"{offer_line}\n\n"
                    f"{EMOJI_CALC} <b>{t('selected_qty', lang)}:</b> {qty}\n"
                    f"{total_line}\n"
                    f"{balance_line}"
                )

            raw_note = p_data.get("note", "")
            has_note = bool(raw_note and str(raw_note).strip())

            bot_username = getattr(client.me, "username", "") or (await client.get_me()).username

            keyboard = build_product_calculator_keyboard(
                product_id=product_id,
                filter_mode=filter_mode,
                page=page,
                qty=qty,
                can_buy=can_buy,
                has_stock=has_stock,
                is_alert_active=is_alert_active,
                total_price=total_price,
                bot_username=bot_username,
                has_note=has_note,
                lang=lang,
                is_owner=is_owner,
                api_balance=api_balance,
                user_balance=user_balance,
                stock_count=stock_count,
                infinite_stock=infinite_stock
            )

            await render_screen(client, target, text, keyboard)

    @app.on_callback_query(filters.regex(r"^product:view:([a-zA-Z0-9_\-]+):([a-z_]+):(\d+):(\d+)$"))
    async def cb_product_view(client: Client, callback: CallbackQuery):
        """Muestra la vista del producto con calculadora interactiva"""
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        CUSTOM_QTY_STATES.pop(user_id, None)

        product_id = callback.matches[0].group(1)
        filter_mode = callback.matches[0].group(2)
        page = int(callback.matches[0].group(3))
        qty = int(callback.matches[0].group(4))

        await render_product_screen(client, callback, product_id, filter_mode, page, qty)

    @app.on_callback_query(filters.regex(r"^pqty:([a-zA-Z0-9_\-]+):([a-z_]+):(\d+):(\d+)$"))
    async def cb_pqty(client: Client, callback: CallbackQuery):
        """Maneja el ajuste interactivo de cantidad (+1, -1, o presets)"""
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        CUSTOM_QTY_STATES.pop(user_id, None)

        product_id = callback.matches[0].group(1)
        filter_mode = callback.matches[0].group(2)
        page = int(callback.matches[0].group(3))
        qty = int(callback.matches[0].group(4))

        await render_product_screen(client, callback, product_id, filter_mode, page, qty)

    @app.on_callback_query(filters.regex(r"^pqty_custom:([a-zA-Z0-9_\-]+):([a-z_]+):(\d+):(\d+)$"))
    async def cb_custom_qty_prompt(client: Client, callback: CallbackQuery):
        """Pide al usuario ingresar una cantidad personalizada por texto"""
        try:
            await callback.answer()
        except Exception:
            pass

        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        product_id = callback.matches[0].group(1)
        filter_mode = callback.matches[0].group(2)
        page = int(callback.matches[0].group(3))
        qty = int(callback.matches[0].group(4))

        p_data = await bunai_api.get_product(product_id)
        if not p_data:
            cached_items = pricing_service._cached_catalog or []
            p_data = next((item for item in cached_items if item.get("product_id") == product_id), None)

        stock_count = int(p_data.get("stock_count", 0)) if p_data else 0
        infinite_stock = bool(p_data.get("infinite_stock", False)) if p_data else False

        CUSTOM_QTY_STATES[user_id] = {
            "product_id": product_id,
            "filter_mode": filter_mode,
            "page": page,
            "qty": qty,
            "stock_count": stock_count,
            "infinite_stock": infinite_stock
        }

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        if not infinite_stock and stock_count > 0:
            prompt_hint = f"entre <code>1</code> y <code>{stock_count}</code> unidades (máximo disponible: <b>{stock_count}</b>)"
        else:
            prompt_hint = "la cantidad que deseas comprar (ej: <code>5</code>, <code>25</code>, <code>100</code>)"

        text = (
            "📝 <b>Ingresar Cantidad Personalizada</b>\n\n"
            f"Por favor, escribe en este chat {prompt_hint}:"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_cancel", lang), callback_data=f"product:view:{product_id}:{filter_mode}:{page}:{qty}")]
        ])
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

        await render_product_screen(client, callback, product_id, filter_mode, page, qty)

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
        raw_note = p_data.get("note") if p_data else ""
        if raw_note and raw_note.strip():
            note = await translate_text(raw_note, lang)
        else:
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
