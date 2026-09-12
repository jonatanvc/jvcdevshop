import math
import unicodedata
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from sqlalchemy import select
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, VirtualNumberOrder
from bot.services.fivesim_client import fivesim_api
from bot.services.pricing import pricing_service
from bot.services.virtual_numbers import (
    virtual_numbers_service, CURATED_SERVICES, get_country_display
)
from bot.services.vouchers import voucher_service
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.emojis import (
    InlineKeyboardButton, parse_emojis, parse_keyboard,
    EMOJI_PHONE, EMOJI_REFRESH, EMOJI_CROSS, EMOJI_CHECK, EMOJI_PARTY,
    EMOJI_KEY, EMOJI_HOURGLASS, EMOJI_WALLET, EMOJI_WARN, EMOJI_CROWN
)

COUNTRIES_PER_PAGE = 6
VNUM_SEARCH_STATES: Dict[int, str] = {}
VNUM_LAST_SEARCH: Dict[int, Tuple[str, str]] = {}

def normalize_text(text: str) -> str:
    """Normaliza texto removiendo acentos y convirtiendo a minúsculas para búsquedas flexibles"""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower()

def get_services_catalog_keyboard() -> InlineKeyboardMarkup:
    """Genera la botonera con las 13 plataformas más populares del mundo en 2 columnas"""
    buttons = []
    items = list(CURATED_SERVICES.items())

    for i in range(0, len(items), 2):
        row = []
        # Primer servicio de la fila
        code1, data1 = items[i]
        btn1 = InlineKeyboardButton(
            data1["name"],
            callback_data=f"vnum:select_service:{code1}:1",
            icon_custom_emoji_id=data1["icon_id"]
        )
        row.append(btn1)

        # Segundo servicio de la fila (si existe)
        if i + 1 < len(items):
            code2, data2 = items[i + 1]
            btn2 = InlineKeyboardButton(
                data2["name"],
                callback_data=f"vnum:select_service:{code2}:1",
                icon_custom_emoji_id=data2["icon_id"]
            )
            row.append(btn2)

        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")
    ])
    return InlineKeyboardMarkup(buttons)

async def render_countries_screen(client: Client, target: Any, user_id: int, service_code: str, page: int):
    """Renderiza la lista paginada de países con botones limpios, buscador y botón actualizar"""
    service_info = CURATED_SERVICES.get(service_code)
    if not service_info:
        return

    offers = await fivesim_api.get_service_offers(service_code)

    is_owner = settings.is_owner(user_id)
    async with async_session() as session:
        u_stmt = select(User).where(User.telegram_id == user_id)
        u_res = await session.execute(u_stmt)
        user = u_res.scalar_one_or_none()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        is_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now)

    if not offers:
        text = (
            f"📲 <b>{service_info['name']} — Países no disponibles</b>\n\n"
            f"En este momento no hay números en stock para <b>{service_info['name']}</b> en los proveedores de 5SIM.\n\n"
            f"<i>Por favor intenta más tarde o prueba con otra plataforma.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Reintentar", callback_data=f"vnum:select_service:{service_code}:1")],
            [InlineKeyboardButton("🔙 Volver a Servicios", callback_data="vnum:catalog")]
        ])
        await render_screen(client, target, text, keyboard)
        return

    total_offers = len(offers)
    total_pages = max(1, math.ceil(total_offers / COUNTRIES_PER_PAGE))
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * COUNTRIES_PER_PAGE
    page_offers = offers[start_idx:start_idx + COUNTRIES_PER_PAGE]

    price_label = "USD" if is_owner else "USDT"
    owner_note = "\n👑 <i>(Modo Owner: Precios de costo neto de API 5SIM)</i>\n" if is_owner else ""
    vip_note = "\n👑 <i>(Beneficio VIP: 20% OFF aplicado)</i>\n" if (is_vip and not is_owner) else ""

    text = (
        f"📲 <b>NÚMEROS VIRTUALES PARA {service_info['name'].upper()}</b>\n{owner_note}{vip_note}\n"
        f"Elige el país de tu preferencia para recibir el código de verificación:\n\n"
        f"• <b>Países con Stock:</b> <code>{total_offers}</code>\n"
        f"• <b>Página:</b> <code>{page}/{total_pages}</code>\n\n"
        f"<i>Precios en {price_label} con entrega instantánea:</i>"
    )

    buttons = []
    for off in page_offers:
        c_code = off["country"]
        cost_usd = off["cost_usd"]
        flag, name = get_country_display(c_code)

        # Calcular precio en USDT con margen Bunai y VIP (o al costo si es Owner)
        price_usdt = pricing_service.calculate_virtual_number_price(cost_usd, is_vip=is_vip, is_owner=is_owner)

        # Botón limpio: solo bandera, nombre del país y precio
        btn_label = f"{flag} {name} — ${price_usdt:.2f} {price_label}"
        buttons.append([
            InlineKeyboardButton(
                btn_label,
                callback_data=f"vnum:confirm:{service_code}:{c_code}"
            )
        ])

    # Navegación paginada
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("◀️", callback_data=f"vnum:select_service:{service_code}:{page - 1}"))
        else:
            nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))

        nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))

        if page < total_pages:
            nav_row.append(InlineKeyboardButton("▶️", callback_data=f"vnum:select_service:{service_code}:{page + 1}"))
        else:
            nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))

        buttons.append(nav_row)

    # Fila de Controles: Actualizar y Buscar País (idéntico al catálogo de productos)
    buttons.append([
        InlineKeyboardButton("🔄 Actualizar", callback_data=f"vnum:refresh:{service_code}:{page}"),
        InlineKeyboardButton("🔍 Buscar País", callback_data=f"vnum:search_prompt:{service_code}")
    ])

    buttons.append([
        InlineKeyboardButton("🔙 Volver a Plataformas", callback_data="vnum:catalog")
    ])

    await render_screen(client, target, text, InlineKeyboardMarkup(buttons))

async def execute_vnum_search(client: Client, user_id: int, service_code: str, query: str, page: int = 1, callback: Optional[CallbackQuery] = None):
    """Ejecuta la búsqueda de países filtrando por código y nombre en español"""
    VNUM_LAST_SEARCH[user_id] = (service_code, query)
    service_info = CURATED_SERVICES.get(service_code, {"name": service_code.capitalize()})
    offers = await fivesim_api.get_service_offers(service_code)

    norm_query = normalize_text(query)

    matched_offers = []
    for off in offers:
        c_code = off["country"].lower()
        flag, name = get_country_display(c_code)
        norm_name = normalize_text(name)
        if norm_query in c_code or norm_query in norm_name:
            matched_offers.append(off)

    is_owner = settings.is_owner(user_id)
    async with async_session() as session:
        u_stmt = select(User).where(User.telegram_id == user_id)
        u_res = await session.execute(u_stmt)
        user = u_res.scalar_one_or_none()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        is_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now)

    price_label = "USD" if is_owner else "USDT"
    target = callback if callback else user_id

    if not matched_offers:
        text = (
            f"🔍 <b>BUSCADOR DE PAÍSES ({service_info['name'].upper()})</b>\n\n"
            f"❌ No se encontraron países con stock disponibles que coincidan con <b>\"{query}\"</b>.\n\n"
            f"<i>Puedes intentar con otro término o ver el catálogo completo de países.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Otra Búsqueda", callback_data=f"vnum:search_prompt:{service_code}")],
            [InlineKeyboardButton("🔙 Ver Todos los Países", callback_data=f"vnum:select_service:{service_code}:1")]
        ])
        await render_screen(client, target, text, keyboard)
        return

    total_matches = len(matched_offers)
    total_pages = max(1, math.ceil(total_matches / COUNTRIES_PER_PAGE))
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * COUNTRIES_PER_PAGE
    page_offers = matched_offers[start_idx:start_idx + COUNTRIES_PER_PAGE]

    text = (
        f"🔍 <b>RESULTADOS PARA \"{query.upper()}\" ({service_info['name'].upper()})</b>\n\n"
        f"• <b>Coincidencias encontradas:</b> <code>{total_matches} país(es)</code>\n"
        f"• <b>Página:</b> <code>{page}/{total_pages}</code>\n\n"
        f"<i>Toca un país para adquirir tu número:</i>"
    )

    buttons = []
    for off in page_offers:
        c_code = off["country"]
        cost_usd = off["cost_usd"]
        flag, name = get_country_display(c_code)
        price_usdt = pricing_service.calculate_virtual_number_price(cost_usd, is_vip=is_vip, is_owner=is_owner)
        btn_label = f"{flag} {name} — ${price_usdt:.2f} {price_label}"
        buttons.append([
            InlineKeyboardButton(
                btn_label,
                callback_data=f"vnum:confirm:{service_code}:{c_code}"
            )
        ])

    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("◀️", callback_data=f"vnum:spage:{page - 1}"))
        else:
            nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))

        nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))

        if page < total_pages:
            nav_row.append(InlineKeyboardButton("▶️", callback_data=f"vnum:spage:{page + 1}"))
        else:
            nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))

        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton("🔍 Otra Búsqueda", callback_data=f"vnum:search_prompt:{service_code}"),
        InlineKeyboardButton("🔙 Ver Todos los Países", callback_data=f"vnum:select_service:{service_code}:1")
    ])

    await render_screen(client, target, text, InlineKeyboardMarkup(buttons))

def register_virtual_numbers_handlers(app: Client):

    # ==========================================
    # 📱 1. CATÁLOGO DE PLATAFORMAS PRINCIPALES
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:(catalog|menu)$"))
    async def cb_vnum_catalog(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        VNUM_SEARCH_STATES.pop(user_id, None)
        if rate_limiter.is_rate_limited(user_id):
            return

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            balance_val = float(user.balance) if user else 0.0

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            is_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now)

        vip_badge = f"\n👑 <b>Beneficio VIP Activo:</b> <code>20% OFF aplicado en todos los números</code>\n" if is_vip else ""

        text = (
            f"📲 <b>NÚMEROS VIRTUALES (SMS OTP)</b>\n\n"
            f"Adquiere números telefónicos temporales para recibir códigos de verificación al instante.\n\n"
            f"💳 <b>Tu Saldo Actual:</b> <code>${balance_val:.2f} USDT</code>\n"
            f"{vip_badge}\n"
            f"🛡️ <b>Garantía Cero Riesgo:</b>\n"
            f"<i>Solo se debita tu saldo si el SMS llega con éxito. Si el código no llega en 15 minutos o decides cancelar, tus USDT se reembolsan automáticamente al 100%.</i>\n\n"
            f"<b>Selecciona la plataforma que deseas verificar:</b>"
        )

        await render_screen(client, callback, text, get_services_catalog_keyboard())

    # ==========================================
    # 🌍 2. SELECTOR DE PAÍSES Y PRECIOS
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:select_service:([a-z0-9_]+):(\d+)$"))
    async def cb_vnum_select_service(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        VNUM_SEARCH_STATES.pop(user_id, None)
        if rate_limiter.is_rate_limited(user_id):
            return

        service_code = callback.matches[0].group(1)
        page = int(callback.matches[0].group(2))

        service_info = CURATED_SERVICES.get(service_code)
        if not service_info:
            await callback.answer("❌ Plataforma no disponible.", show_alert=True)
            return

        await callback.answer("⏳ Consultando países disponibles en 5SIM...")
        await render_countries_screen(client, callback, user_id, service_code, page)

    # ==========================================
    # 🔄 2.1. ACTUALIZAR PAÍSES EN TIEMPO REAL
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:refresh:([a-z0-9_]+):(\d+)$"))
    async def cb_vnum_refresh(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        service_code = callback.matches[0].group(1)
        page = int(callback.matches[0].group(2))

        # Invalidar caché local de 5SIM para datos frescos
        fivesim_api._prices_cache.clear()
        fivesim_api._prices_cache_ts = 0.0

        await callback.answer("🔄 Actualizando lista y stock...")
        await render_countries_screen(client, callback, user_id, service_code, page)

    # ==========================================
    # 🔍 2.2. BUSCADOR DE PAÍS POR TEXTO
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:search_prompt:([a-z0-9_]+)$"))
    async def cb_vnum_search_prompt(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        service_code = callback.matches[0].group(1)
        service_info = CURATED_SERVICES.get(service_code, {"name": service_code.capitalize()})
        VNUM_SEARCH_STATES[user_id] = service_code

        text = (
            f"🔍 <b>BUSCADOR DE PAÍSES ({service_info['name'].upper()})</b>\n\n"
            f"Escribe el nombre o código del país que buscas (ejemplo: <code>Colombia</code>, <code>España</code>, <code>Estados Unidos</code>, <code>Argentina</code>).\n\n"
            f"<i>O pulsa el botón volver para regresar a la lista de países.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Volver a la Lista", callback_data=f"vnum:select_service:{service_code}:1")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^vnum:spage:(\d+)$"))
    async def cb_vnum_search_page(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        page = int(callback.matches[0].group(1))
        cached = VNUM_LAST_SEARCH.get(user_id)
        if not cached:
            await callback.answer("⚠️ Búsqueda expirada. Selecciona la plataforma.", show_alert=True)
            await cb_vnum_catalog(client, callback)
            return

        service_code, query = cached
        await execute_vnum_search(client, user_id, service_code, query, page=page, callback=callback)

    @app.on_message(filters.private & filters.text & ~filters.command(["start", "admin", "buscar", "search", "catalogo", "catalog", "pedidos", "orders", "depositar", "deposit", "saldo", "wallet", "soporte", "support", "ayuda", "help", "del", "dep"]), group=5)
    async def handle_vnum_search_text(client: Client, message: Message):
        user_id = message.from_user.id
        if user_id in VNUM_SEARCH_STATES:
            service_code = VNUM_SEARCH_STATES.pop(user_id)
            try:
                await message.delete()
            except Exception:
                pass
            query = message.text.strip()
            await execute_vnum_search(client, user_id, service_code, query, page=1)
            return
        message.continue_propagation()

    # ==========================================
    # 💳 3. PANTALLA DE CONFIRMACIÓN DE COMPRA
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:confirm:([a-z0-9_]+):([a-z0-9_]+)$"))
    async def cb_vnum_confirm(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        service_code = callback.matches[0].group(1)
        country_code = callback.matches[0].group(2)

        service_info = CURATED_SERVICES.get(service_code)
        if not service_info:
            return

        flag, country_name = get_country_display(country_code)

        # Consultar precio y stock actual
        offers = await fivesim_api.get_service_offers(service_code)
        matched_offer = next((o for o in offers if o["country"] == country_code), None)

        if not matched_offer:
            await callback.answer("⚠️ Este país se quedó sin stock. Elige otro.", show_alert=True)
            await cb_vnum_select_service(client, callback)
            return

        cost_usd = matched_offer["cost_usd"]
        stock_available = matched_offer.get("stock", 0)

        is_owner = settings.is_owner(user_id)
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            balance_val = float(user.balance) if user else 0.0

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            is_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now)

        regular_price = pricing_service.calculate_virtual_number_price(cost_usd, is_vip=False)
        final_price = pricing_service.calculate_virtual_number_price(cost_usd, is_vip=is_vip, is_owner=is_owner)

        fivesim_bal = 0.0
        if is_owner:
            try:
                prof = await fivesim_api.get_profile()
                fivesim_bal = float(prof.get("balance", 0.0))
            except Exception:
                fivesim_bal = 0.0

        if is_owner:
            price_text = f"👑 <b>Tarifa Owner (Precio Costo API):</b> <code>${final_price:.2f} USD</code>\n"
            balance_section = (
                f"💳 <b>Tus Saldos Disponibles:</b>\n"
                f"• 📱 <b>Saldo API 5SIM.net:</b> <code>${fivesim_bal:.2f} USD</code> 👑\n"
                f"• 👛 <b>Saldo Billetera Bot:</b> <code>${balance_val:.2f} USDT</code>\n\n"
            )
        elif is_vip:
            price_text = f"👑 <b>Tarifa Revendedor VIP:</b> <s>${regular_price:.2f}</s> <b>${final_price:.2f} USDT</b> (20% OFF)\n"
            balance_section = f"💳 <b>Tu Saldo Actual:</b> <code>${balance_val:.2f} USDT</code>\n\n"
        else:
            price_text = f"💵 <b>Precio Total:</b> <code>${final_price:.2f} USDT</code>\n"
            balance_section = f"💳 <b>Tu Saldo Actual:</b> <code>${balance_val:.2f} USDT</code>\n\n"

        text = (
            f"📲 <b>CONFIRMAR NÚMERO VIRTUAL</b>\n\n"
            f"• <b>Plataforma:</b> {service_info['name']}\n"
            f"• <b>País:</b> {flag} {country_name}\n"
            f"• <b>Stock Disponible:</b> <code>{stock_available} números</code>\n"
            f"{price_text}"
            f"{balance_section}"
            f"🛡️ <b>Garantía Cero Riesgo:</b>\n"
            f"<i>El saldo solo se cobra si el SMS llega con éxito. Si el código no entra o cancelas la solicitud en los próximos 15 minutos, se te reembolsa el 100% automáticamente.</i>"
        )

        if is_owner:
            buttons = []
            if fivesim_bal >= final_price:
                buttons.append([InlineKeyboardButton(
                    f"👑 Comprar con Saldo API 5SIM (${final_price:.2f} USD)",
                    callback_data=f"vnum:execute:{service_code}:{country_code}:api"
                )])
            if balance_val >= final_price:
                buttons.append([InlineKeyboardButton(
                    f"🛍️ Comprar con Saldo Bot (${final_price:.2f} USDT)",
                    callback_data=f"vnum:execute:{service_code}:{country_code}:bot"
                )])

            if not buttons:
                diff_api = final_price - fivesim_bal
                text += f"\n\n⚠️ <i>Saldo insuficiente en 5SIM (faltan ${diff_api:.2f} USD) y en el bot (faltan ${final_price - balance_val:.2f} USDT).</i>"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("👛 Recargar Mi Billetera", callback_data="wallet:deposit_menu")],
                    [InlineKeyboardButton("🔙 Elegir Otro País", callback_data=f"vnum:select_service:{service_code}:1")]
                ])
            else:
                buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data=f"vnum:select_service:{service_code}:1")])
                keyboard = InlineKeyboardMarkup(buttons)
        else:
            has_sufficient = balance_val >= final_price
            if has_sufficient:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"✅ Confirmar Compra (${final_price:.2f} USDT)", callback_data=f"vnum:execute:{service_code}:{country_code}:bot")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data=f"vnum:select_service:{service_code}:1")]
                ])
            else:
                diff = final_price - balance_val
                text += f"\n\n⚠️ <i>Te faltan <b>${diff:.2f} USDT</b> para completar esta compra.</i>"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("👛 Recargar Mi Billetera", callback_data="wallet:deposit_menu")],
                    [InlineKeyboardButton("🔙 Elegir Otro País", callback_data=f"vnum:select_service:{service_code}:1")]
                ])

        await render_screen(client, callback, text, keyboard)

    # ==========================================
    # 🚀 4. EJECUCIÓN DE COMPRA Y ASIGNACIÓN
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:execute:([a-z0-9_]+):([a-z0-9_]+)(?::([a-z]+))?$"))
    async def cb_vnum_execute(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        service_code = callback.matches[0].group(1)
        country_code = callback.matches[0].group(2)
        raw_method = callback.matches[0].group(3)

        await callback.answer("⏳ Solicitando número en 5SIM...")

        is_owner = settings.is_owner(user_id)
        pay_with_api = bool(is_owner and (raw_method == "api" or raw_method is None))

        result = await virtual_numbers_service.purchase_number(
            user_id=user_id,
            service_code=service_code,
            country=country_code,
            is_owner=is_owner,
            pay_with_api=pay_with_api
        )

        if "error" in result:
            err_text = result["error"]
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Intentar con Otro País", callback_data=f"vnum:select_service:{service_code}:1")],
                [InlineKeyboardButton("🔙 Menú Principal", callback_data="menu_main")]
            ])
            await render_screen(client, callback, f"❌ <b>No se pudo asignar el número:</b>\n\n{err_text}", keyboard)
            return

        order = result.get("order") or {}
        order_id = order.get("id") or result.get("order_id")

        # Mostrar pantalla activa de espera
        await show_live_order_screen(client, callback, order_id, user_id)

    # ==========================================
    # ⏳ 5. PANTALLA ACTIVA DE ESPERA DE SMS
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:view_order:(\d+)$"))
    async def cb_vnum_view_order(client: Client, callback: CallbackQuery):
        order_id = int(callback.matches[0].group(1))
        user_id = callback.from_user.id
        await show_live_order_screen(client, callback, order_id, user_id)

    # ==========================================
    # 🔄 6. ACTUALIZAR / CONSULTAR SMS MANUAL
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:check_sms:(\d+)$"))
    async def cb_vnum_check_sms(client: Client, callback: CallbackQuery):
        order_id = int(callback.matches[0].group(1))
        user_id = callback.from_user.id

        await callback.answer("🔄 Verificando buzón de SMS...")

        check_res = await virtual_numbers_service.check_single_order(order_id)

        if check_res.get("status") == "RECEIVED":
            # Código recibido con éxito - Publicar comprobante en canal público si no se ha publicado
            async with async_session() as session:
                res_o = await session.execute(select(VirtualNumberOrder).where(VirtualNumberOrder.id == order_id))
                v_ord = res_o.scalar_one_or_none()
                if v_ord and not v_ord.voucher_message_id:
                    v_id = await voucher_service.publish_virtual_number_voucher(
                        client=client,
                        order_id=v_ord.id,
                        service_name=v_ord.service_name,
                        country_code=v_ord.country,
                        phone=v_ord.phone,
                        price_usdt=float(v_ord.price_usdt),
                        user_id=v_ord.user_id,
                        username=callback.from_user.username,
                        first_name=callback.from_user.first_name
                    )
                    if v_id:
                        v_ord.voucher_message_id = v_id
                        v_ord.rating = 5
                        await session.commit()

            await show_success_screen(client, callback, check_res, order_id)
            return

        if check_res.get("status") in ["CANCELLED", "TIMEOUT"]:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Nuevo Número", callback_data="vnum:catalog")],
                [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
            ])
            await render_screen(
                client,
                callback,
                "⚠️ <b>La orden ha finalizado o expirado.</b>\n\n<i>Cualquier saldo retenido fue reembolsado automáticamente a tu billetera.</i>",
                keyboard
            )
            return

        await show_live_order_screen(client, callback, order_id, user_id)

    # ==========================================
    # ❌ 7. CANCELAR NÚMERO Y REEMBOLSAR
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:cancel:(\d+)$"))
    async def cb_vnum_cancel(client: Client, callback: CallbackQuery):
        order_id = int(callback.matches[0].group(1))
        user_id = callback.from_user.id

        await callback.answer("⏳ Cancelando número y reembolsando saldo...")

        res = await virtual_numbers_service.cancel_and_refund_order(order_id, user_id, client=client)

        if "error" in res:
            await callback.answer(f"❌ {res['error']}", show_alert=True)
            await show_live_order_screen(client, callback, order_id, user_id)
            return

        refunded = res.get("refunded_amount", 0.0)
        c_service = res.get("service_name", "")
        c_country = res.get("country", "")
        is_api_pay = (res.get("payment_method") == "api")

        if is_api_pay:
            refund_info = (
                f"💰 <b>Saldo Reembolsado:</b> <code>+${refunded:.2f} USD</code>\n"
                f"<i>Los fondos fueron devueltos directamente a tu cuenta de 5SIM.net.</i>"
            )
        else:
            refund_info = (
                f"💰 <b>Saldo Reembolsado:</b> <code>+${refunded:.2f} USDT</code>\n"
                f"<i>Los fondos ya se encuentran disponibles en tu billetera del bot.</i>"
            )

        text = (
            f"✅ <b>NÚMERO CANCELADO EXITOSAMENTE</b>\n\n"
            f"La orden fue liberada en 5SIM y no se generó ningún cargo.\n\n"
            f"{refund_info}"
        )
        buttons_cancel = []
        if c_service and c_country:
            buttons_cancel.append([InlineKeyboardButton("⚡ Probar Otro Número (Mismo País)", callback_data=f"vnum:reorder:{c_service}:{c_country}")])
        buttons_cancel.extend([
            [InlineKeyboardButton("📱 Probar con Otro Número", callback_data="vnum:catalog")],
            [InlineKeyboardButton("👛 Ver Mi Billetera", callback_data="wallet:deposit_menu")],
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
        ])
        keyboard = InlineKeyboardMarkup(buttons_cancel)

        await render_screen(client, callback, text, keyboard)

    # ==========================================
    # ⚡ 8. REORDENAR INMEDIATO (1 SOLO CLIC)
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:reorder:([a-z0-9_]+):([a-z0-9_]+)$"))
    async def cb_vnum_reorder(client: Client, callback: CallbackQuery):
        service_name = callback.matches[0].group(1)
        country = callback.matches[0].group(2)
        user_id = callback.from_user.id

        if rate_limiter.is_rate_limited(user_id):
            await callback.answer("⏳ Por favor espera un momento...", show_alert=False)
            return

        is_owner = settings.is_owner(user_id)
        await callback.answer("⚡ Solicitando nuevo número...", show_alert=False)

        # 1. Comprobar disponibilidad y precio actual
        price_info = await pricing_service.get_virtual_number_pricing(country, service_name)
        if not price_info:
            await callback.answer("❌ El servicio no está disponible actualmente para este país.", show_alert=True)
            return

        req_price = price_info.get("fivesim_cost_usd", 0.0) if is_owner else price_info.get("retail_price_usdt", 0.0)

        # 2. Comprobar saldo disponible
        pay_with_api = False
        if is_owner:
            try:
                prof = await fivesim_api.get_profile()
                fivesim_bal = float(prof.get("balance", 0.0))
            except Exception:
                fivesim_bal = 0.0

            if fivesim_bal >= req_price:
                pay_with_api = True
            else:
                async with async_session() as session:
                    user_res = await session.execute(select(User).where(User.telegram_id == user_id))
                    user = user_res.scalar_one_or_none()
                    current_bal = float(user.balance) if user else 0.0

                if current_bal < req_price:
                    await callback.answer(f"❌ Saldo insuficiente en 5SIM (${fivesim_bal:.2f}) y en el bot (${current_bal:.2f})", show_alert=True)
                    return
        else:
            async with async_session() as session:
                user_res = await session.execute(select(User).where(User.telegram_id == user_id))
                user = user_res.scalar_one_or_none()
                current_bal = float(user.balance) if user else 0.0

            if current_bal < req_price:
                diff = req_price - current_bal
                await callback.answer(f"❌ Saldo insuficiente (${current_bal:.2f} < ${req_price:.2f} USDT)", show_alert=True)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Recargar Saldo", callback_data="wallet:deposit_menu")],
                    [InlineKeyboardButton("📱 Volver al Catálogo", callback_data="vnum:catalog")]
                ])
                await render_screen(
                    client,
                    callback,
                    f"❌ <b>SALDO INSUFICIENTE</b>\n\n"
                    f"• <b>Saldo actual:</b> <code>${current_bal:.2f} USDT</code>\n"
                    f"• <b>Precio del número:</b> <code>${req_price:.2f} USDT</code>\n"
                    f"• <b>Faltante:</b> <code>${diff:.2f} USDT</code>\n\n"
                    f"<i>Recarga tu billetera para adquirir este número al instante.</i>",
                    keyboard
                )
                return

        # 3. Pantalla de carga inmediata
        await render_screen(
            client,
            callback,
            "⚡ <b>Asignando nuevo número virtual en 5SIM...</b>\n<i>Por favor espera unos segundos.</i>",
            None
        )

        # 4. Ejecutar compra directa en 5SIM
        purchase_res = await virtual_numbers_service.purchase_number(
            user_id=user_id,
            service_code=service_name,
            country=country,
            operator="any",
            is_owner=is_owner,
            pay_with_api=pay_with_api
        )

        if "error" in purchase_res:
            err = purchase_res["error"]
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Reintentar", callback_data=f"vnum:reorder:{service_name}:{country}")],
                [InlineKeyboardButton("📱 Ver Otros Países", callback_data=f"vnum:select_service:{service_name}:1")],
                [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
            ])
            await render_screen(
                client,
                callback,
                f"❌ <b>NO SE PUDO ASIGNAR EL NÚMERO</b>\n\n<code>{err}</code>\n\n<i>No se ha descontado saldo de tu billetera.</i>",
                keyboard
            )
            return

        new_order_id = purchase_res.get("order_id") or purchase_res.get("order", {}).get("id")
        await show_live_order_screen(client, callback, new_order_id, user_id)

    # ==========================================
    # ⭐ 9. CALIFICACIÓN DE NÚMERO VIRTUAL
    # ==========================================

    @app.on_callback_query(filters.regex(r"^rate:vnum:(\d+):([1-5])$"))
    async def cb_rate_vnum_order(client: Client, callback: CallbackQuery):
        order_id = int(callback.matches[0].group(1))
        stars = int(callback.matches[0].group(2))
        user_id = callback.from_user.id

        async with async_session() as session:
            res = await session.execute(select(VirtualNumberOrder).where(VirtualNumberOrder.id == order_id))
            order = res.scalar_one_or_none()
            if not order or order.user_id != user_id:
                await callback.answer("❌ Orden no encontrada.", show_alert=True)
                return

            order.rating = stars
            voucher_msg_id = order.voucher_message_id
            service_name = order.service_name
            country = order.country
            phone = order.phone
            price_usdt = float(order.price_usdt)
            await session.commit()

        if voucher_msg_id:
            await voucher_service.update_virtual_number_voucher_rating(
                client=client,
                voucher_msg_id=voucher_msg_id,
                order_id=order_id,
                service_name=service_name,
                country_code=country,
                phone=phone,
                price_usdt=price_usdt,
                user_id=user_id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                stars=stars
            )

        await callback.answer(f"¡Muchas gracias! Calificación de {stars} ⭐ registrada.", show_alert=False)

        # Refrescar mensaje eliminando los botones de estrellas y dejando un badge limpio
        if callback.message:
            try:
                old_kb = callback.message.reply_markup.inline_keyboard if callback.message.reply_markup else []
                new_kb = []
                for row in old_kb:
                    # Si es la fila con estrellas
                    if any("rate:vnum:" in (btn.callback_data or "") for btn in row):
                        new_kb.append([
                            InlineKeyboardButton(f"✅ Calificaste con {'⭐' * stars} ({stars}/5)", callback_data="noop")
                        ])
                    else:
                        new_kb.append(row)
                await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_kb))
            except Exception:
                pass

async def show_live_order_screen(client: Client, target: Any, order_id: int, user_id: int):
    """Renderiza la pantalla de espera en vivo con temporizador y número copiable"""
    async with async_session() as session:
        stmt = select(VirtualNumberOrder).where(
            VirtualNumberOrder.id == order_id,
            VirtualNumberOrder.user_id == user_id
        )
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()

        if not order:
            return

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        remaining_seconds = max(0, int((order.expires_at - now).total_seconds()))

    # Si ya expiró, chequear en 5sim
    if remaining_seconds <= 0:
        await virtual_numbers_service.check_single_order(order_id)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Nuevo Número", callback_data="vnum:catalog")],
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
        ])
        if getattr(order, "payment_method", "bot") == "api":
            exp_text = "⏰ <b>Tiempo agotado sin recibir el código SMS.</b>\n\n<i>La orden fue cancelada y tu saldo fue reintegrado a tu cuenta de la API 5SIM.</i>"
        else:
            exp_text = "⏰ <b>Tiempo agotado sin recibir el código SMS.</b>\n\n<i>La orden fue cancelada y tu saldo fue reembolsado al 100% en tu billetera.</i>"
        await render_screen(
            client,
            target,
            exp_text,
            keyboard
        )
        return

    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60

    service_info = CURATED_SERVICES.get(order.service_name, {"name": order.service_name.capitalize()})
    flag, country_name = get_country_display(order.country)

    text = (
        f"📲 <b>NÚMERO VIRTUAL ASIGNADO</b>\n\n"
        f"• <b>Plataforma:</b> {service_info['name']}\n"
        f"• <b>País:</b> {flag} {country_name}\n\n"
        f"📞 <b>Número Telefónico (Toca para copiar):</b>\n"
        f"<code>{order.phone}</code>\n\n"
        f"⏳ <b>Tiempo Restante:</b> <code>{minutes:02d}:{seconds:02d} min</code>\n"
        f"📡 <b>Estado:</b> <i>Esperando código SMS...</i>\n\n"
        f"<i>Ingresa el número en {service_info['name']} para solicitar el código. En cuanto llegue, la pantalla se actualizará automáticamente o puedes pulsar 'Comprobar SMS'.</i>\n\n"
        f"🛡️ <i>Si el código no llega o quieres otro número, pulsa 'Cancelar' para recuperar tus fondos al instante.</i>"
    )

    cancel_btn_text = "❌ Cancelar Orden" if getattr(order, "payment_method", "bot") == "api" else "❌ Cancelar y Reembolsar"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Comprobar SMS", callback_data=f"vnum:check_sms:{order_id}"),
            InlineKeyboardButton(cancel_btn_text, callback_data=f"vnum:cancel:{order_id}")
        ],
        [
            InlineKeyboardButton("🏠 Volver al Menú", callback_data="menu_main")
        ]
    ])

    await render_screen(client, target, text, keyboard)

async def show_success_screen(client: Client, target: Any, check_res: Dict[str, Any], order_id: int):
    """Muestra la pantalla de código OTP recibido con éxito"""
    code = check_res.get("code", "")
    full_text = check_res.get("text", "")
    phone = check_res.get("phone", "")
    service = check_res.get("service_name", "")
    country = check_res.get("country", "")

    current_rating = None
    async with async_session() as session:
        r = await session.execute(select(VirtualNumberOrder).where(VirtualNumberOrder.id == order_id))
        o = r.scalar_one_or_none()
        if o:
            service = service or o.service_name
            country = country or o.country
            current_rating = o.rating

    text = (
        f"🎉 <b>¡CÓDIGO DE VERIFICACIÓN RECIBIDO!</b>\n\n"
        f"📞 <b>Número:</b> <code>{phone}</code>\n\n"
        f"🔑 <b>Tu Código OTP (Toca para copiar):</b>\n"
        f"<code>{code}</code>\n\n"
        f"💬 <b>Mensaje Completo:</b>\n"
        f"<i>\"{full_text}\"</i>\n\n"
        f"✅ <i>¡Activación completada con éxito!</i>"
    )

    buttons = []
    # Fila de estrellas integrada sin repetir mensajes
    if current_rating:
        buttons.append([
            InlineKeyboardButton(f"✅ Calificaste con {'⭐' * current_rating} ({current_rating}/5)", callback_data="noop")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("⭐ 1", callback_data=f"rate:vnum:{order_id}:1"),
            InlineKeyboardButton("⭐ 2", callback_data=f"rate:vnum:{order_id}:2"),
            InlineKeyboardButton("⭐ 3", callback_data=f"rate:vnum:{order_id}:3"),
            InlineKeyboardButton("⭐ 4", callback_data=f"rate:vnum:{order_id}:4"),
            InlineKeyboardButton("⭐ 5", callback_data=f"rate:vnum:{order_id}:5"),
        ])

    if service and country:
        buttons.append([InlineKeyboardButton("⚡ Pedir Otro Número (Mismo País)", callback_data=f"vnum:reorder:{service}:{country}")])

    buttons.extend([
        [InlineKeyboardButton("📱 Comprar Otro Número", callback_data="vnum:catalog")],
        [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
    ])

    keyboard = InlineKeyboardMarkup(buttons)
    await render_screen(client, target, text, keyboard)
