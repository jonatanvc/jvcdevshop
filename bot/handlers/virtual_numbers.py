import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional
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
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.emojis import (
    InlineKeyboardButton, parse_emojis, parse_keyboard,
    EMOJI_PHONE, EMOJI_REFRESH, EMOJI_CROSS, EMOJI_CHECK, EMOJI_PARTY,
    EMOJI_KEY, EMOJI_HOURGLASS, EMOJI_WALLET, EMOJI_WARN, EMOJI_CROWN
)

COUNTRIES_PER_PAGE = 6

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

def register_virtual_numbers_handlers(app: Client):

    # ==========================================
    # 📱 1. CATÁLOGO DE PLATAFORMAS PRINCIPALES
    # ==========================================

    @app.on_callback_query(filters.regex(r"^vnum:(catalog|menu)$"))
    async def cb_vnum_catalog(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
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
        if rate_limiter.is_rate_limited(user_id):
            return

        service_code = callback.matches[0].group(1)
        page = int(callback.matches[0].group(2))

        service_info = CURATED_SERVICES.get(service_code)
        if not service_info:
            await callback.answer("❌ Plataforma no disponible.", show_alert=True)
            return

        await callback.answer("⏳ Consultando países disponibles en 5SIM...")

        # Consultar ofertas disponibles en tiempo real en 5SIM
        offers = await fivesim_api.get_service_offers(service_code)

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
            await render_screen(client, callback, text, keyboard)
            return

        total_offers = len(offers)
        total_pages = max(1, math.ceil(total_offers / COUNTRIES_PER_PAGE))
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * COUNTRIES_PER_PAGE
        page_offers = offers[start_idx:start_idx + COUNTRIES_PER_PAGE]

        text = (
            f"📲 <b>NÚMEROS VIRTUALES PARA {service_info['name'].upper()}</b>\n\n"
            f"Elige el país de tu preferencia para recibir el código de verificación:\n\n"
            f"• <b>Países con Stock:</b> <code>{total_offers}</code>\n"
            f"• <b>Página:</b> <code>{page}/{total_pages}</code>\n\n"
            f"<i>Precios en USDT con entrega instantánea:</i>"
        )

        buttons = []
        for off in page_offers:
            c_code = off["country"]
            cost_usd = off["cost_usd"]
            stock = off["stock"]
            flag, name = get_country_display(c_code)

            # Calcular precio en USDT con margen Bunai y VIP
            price_usdt = pricing_service.calculate_virtual_number_price(cost_usd, is_vip=is_vip)

            btn_label = f"{flag} {name} — ${price_usdt:.2f} USDT ({stock} disp.)"
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

        buttons.append([
            InlineKeyboardButton("🔙 Volver a Plataformas", callback_data="vnum:catalog")
        ])

        await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))

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

        # Consultar precio actual
        offers = await fivesim_api.get_service_offers(service_code)
        matched_offer = next((o for o in offers if o["country"] == country_code), None)

        if not matched_offer:
            await callback.answer("⚠️ Este país se quedó sin stock. Elige otro.", show_alert=True)
            await cb_vnum_select_service(client, callback)
            return

        cost_usd = matched_offer["cost_usd"]

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            balance_val = float(user.balance) if user else 0.0

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            is_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now)

        regular_price = pricing_service.calculate_virtual_number_price(cost_usd, is_vip=False)
        final_price = pricing_service.calculate_virtual_number_price(cost_usd, is_vip=is_vip)

        vip_text = ""
        if is_vip:
            vip_text = f"👑 <b>Tarifa Revendedor VIP:</b> <s>${regular_price:.2f}</s> <b>${final_price:.2f} USDT</b> (20% OFF)\n"
        else:
            vip_text = f"💵 <b>Precio Total:</b> <code>${final_price:.2f} USDT</code>\n"

        has_sufficient = balance_val >= final_price

        text = (
            f"📲 <b>CONFIRMAR NÚMERO VIRTUAL</b>\n\n"
            f"• <b>Plataforma:</b> {service_info['name']}\n"
            f"• <b>País:</b> {flag} {country_name}\n"
            f"{vip_text}"
            f"💳 <b>Tu Saldo Actual:</b> <code>${balance_val:.2f} USDT</code>\n\n"
            f"🛡️ <b>Garantía Cero Riesgo:</b>\n"
            f"<i>El saldo solo se cobra si el SMS llega con éxito. Si el código no entra o cancelas la solicitud en los próximos 15 minutos, se te reembolsa el 100% automáticamente.</i>"
        )

        if has_sufficient:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ Confirmar Compra (${final_price:.2f} USDT)", callback_data=f"vnum:execute:{service_code}:{country_code}")],
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

    @app.on_callback_query(filters.regex(r"^vnum:execute:([a-z0-9_]+):([a-z0-9_]+)$"))
    async def cb_vnum_execute(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        service_code = callback.matches[0].group(1)
        country_code = callback.matches[0].group(2)

        await callback.answer("⏳ Solicitando número en 5SIM...")

        result = await virtual_numbers_service.purchase_number(user_id, service_code, country_code)

        if "error" in result:
            err_text = result["error"]
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Intentar con Otro País", callback_data=f"vnum:select_service:{service_code}:1")],
                [InlineKeyboardButton("🔙 Menú Principal", callback_data="menu_main")]
            ])
            await render_screen(client, callback, f"❌ <b>No se pudo asignar el número:</b>\n\n{err_text}", keyboard)
            return

        order = result["order"]
        order_id = order["id"]

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
            # Código recibido con éxito
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

        text = (
            f"✅ <b>NÚMERO CANCELADO EXITOSAMENTE</b>\n\n"
            f"La orden fue liberada en 5SIM y no se generó ningún cargo.\n\n"
            f"💰 <b>Saldo Reembolsado:</b> <code>+${refunded:.2f} USDT</code>\n"
            f"<i>Los fondos ya se encuentran disponibles en tu billetera.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Probar con Otro Número", callback_data="vnum:catalog")],
            [InlineKeyboardButton("👛 Ver Mi Billetera", callback_data="wallet:deposit_menu")],
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
        ])

        await render_screen(client, callback, text, keyboard)

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
        await render_screen(
            client,
            target,
            "⏰ <b>Tiempo agotado sin recibir el código SMS.</b>\n\n<i>La orden fue cancelada y tu saldo fue reembolsado al 100% en tu billetera.</i>",
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
        f"🛡️ <i>Si el código no llega o quieres otro número, pulsa 'Cancelar y Reembolsar' para recuperar tus fondos al instante.</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Comprobar SMS", callback_data=f"vnum:check_sms:{order_id}"),
            InlineKeyboardButton("❌ Cancelar y Reembolsar", callback_data=f"vnum:cancel:{order_id}")
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

    text = (
        f"🎉 <b>¡CÓDIGO DE VERIFICACIÓN RECIBIDO!</b>\n\n"
        f"📞 <b>Número:</b> <code>{phone}</code>\n\n"
        f"🔑 <b>Tu Código OTP (Toca para copiar):</b>\n"
        f"<code>{code}</code>\n\n"
        f"💬 <b>Mensaje Completo:</b>\n"
        f"<i>\"{full_text}\"</i>\n\n"
        f"✅ <i>¡Activación completada con éxito!</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Comprar Otro Número", callback_data="vnum:catalog")],
        [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
    ])

    await render_screen(client, target, text, keyboard)
