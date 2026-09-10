import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from sqlalchemy import select, func, desc, update
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Coupon, CouponUsage, GiftCard
from bot.services.promos import promo_service
from bot.services.audit_logger import audit_logger
from bot.handlers.admin import is_admin
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.time_utils import format_dt
from bot.utils.emojis import parse_emojis, parse_keyboard

ADMIN_PROMO_STATES: Dict[int, Dict[str, Any]] = {}

COUPONS_PER_PAGE = 5
GIFTS_PER_PAGE = 6

def register_admin_promos_handlers(app: Client):

    # ==========================================
    # 🎟️ GESTIÓN DE CUPONES EN PANEL ADMIN
    # ==========================================

    @app.on_callback_query(filters.regex(r"^admin:coupons:page:(\d+)$"))
    async def cb_admin_coupons_list(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            await callback.answer("❌ Acceso denegado.", show_alert=True)
            return

        page = int(callback.matches[0].group(1))

        async with async_session() as session:
            stmt = select(Coupon).order_by(desc(Coupon.created_at))
            res = await session.execute(stmt)
            all_coupons = res.scalars().all()

            total_coupons = len(all_coupons)
            total_pages = max(1, math.ceil(total_coupons / COUPONS_PER_PAGE))
            page = max(1, min(page, total_pages))

            start_idx = (page - 1) * COUPONS_PER_PAGE
            coupons_page = all_coupons[start_idx:start_idx + COUPONS_PER_PAGE]

        text = (
            "🎟️ <b>PANEL DE CUPONES DE DESCUENTO</b>\n\n"
            f"Configura códigos promocionales porcentuales o de saldo fijo para tus usuarios.\n\n"
            f"• <b>Total de Cupones:</b> <code>{total_coupons}</code>\n"
            f"• <b>Página:</b> <code>{page}/{total_pages}</code>\n\n"
            "<i>Selecciona un cupón para ver detalles o pulsa 'Crear Nuevo':</i>"
        )

        buttons = []
        for c in coupons_page:
            status_icon = "🟢" if c.is_active else "🔴"
            val_str = f"{float(c.discount_value):.0f}%" if c.discount_type == "percent" else f"${float(c.discount_value):.2f} USDT"
            uses_str = f"{c.current_uses}/{c.max_uses if c.max_uses > 0 else '∞'}"
            btn_text = f"{status_icon} {c.code} (-{val_str}) [{uses_str}]"
            buttons.append([
                InlineKeyboardButton(btn_text, callback_data=f"admin:coupon:view:{c.id}:{page}")
            ])

        if total_pages > 1:
            nav = []
            if page > 1:
                nav.append(InlineKeyboardButton("◀️", callback_data=f"admin:coupons:page:{page - 1}"))
            else:
                nav.append(InlineKeyboardButton("🔵", callback_data="noop"))
            nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
            if page < total_pages:
                nav.append(InlineKeyboardButton("▶️", callback_data=f"admin:coupons:page:{page + 1}"))
            else:
                nav.append(InlineKeyboardButton("🔵", callback_data="noop"))
            buttons.append(nav)

        buttons.append([
            InlineKeyboardButton("➕ Crear Nuevo Cupón", callback_data="admin:coupon:create"),
            InlineKeyboardButton("🔙 Volver al Panel", callback_data="admin:menu")
        ])

        await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))

    @app.on_callback_query(filters.regex(r"^admin:coupon:view:(\d+):(\d+)$"))
    async def cb_admin_coupon_view(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        coupon_id = int(callback.matches[0].group(1))
        page = int(callback.matches[0].group(2))

        async with async_session() as session:
            stmt = select(Coupon).where(Coupon.id == coupon_id)
            res = await session.execute(stmt)
            coupon = res.scalar_one_or_none()

            if not coupon:
                await callback.answer("❌ Cupón no encontrado.", show_alert=True)
                return

            usage_stmt = select(func.count(CouponUsage.id), func.sum(CouponUsage.discount_amount)).where(CouponUsage.coupon_id == coupon.id)
            usage_res = await session.execute(usage_stmt)
            total_uses, total_discount = usage_res.first()
            total_discount = float(total_discount or 0.0)

        type_str = "Porcentual (%)" if coupon.discount_type == "percent" else "Monto Fijo (USDT)"
        val_str = f"{float(coupon.discount_value):.2f}%" if coupon.discount_type == "percent" else f"${float(coupon.discount_value):.2f} USDT"
        status_str = "🟢 ACTIVO" if coupon.is_active else "🔴 INACTIVO"
        exp_str = format_dt(coupon.expires_at, "%Y-%m-%d %H:%M") if coupon.expires_at else "Sin vencimiento"
        min_str = f"${float(coupon.min_purchase):.2f} USDT" if coupon.min_purchase > 0 else "Sin mínimo"
        max_str = f"{coupon.max_uses} usos" if coupon.max_uses > 0 else "Ilimitado"

        text = (
            f"🎟️ <b>DETALLE DEL CUPÓN:</b> <code>{coupon.code}</code>\n\n"
            f"• <b>Estado:</b> {status_str}\n"
            f"• <b>Tipo de Descuento:</b> <code>{type_str}</code>\n"
            f"• <b>Valor del Descuento:</b> <code>{val_str}</code>\n"
            f"• <b>Compra Mínima:</b> <code>{min_str}</code>\n"
            f"• <b>Límite Global de Usos:</b> <code>{max_str}</code>\n"
            f"• <b>Usos por Usuario:</b> <code>{coupon.user_limit} uso(s)</code>\n"
            f"• <b>Fecha de Expiración:</b> <code>{exp_str}</code>\n\n"
            f"📊 <b>ESTADÍSTICAS:</b>\n"
            f"• <b>Canjes Realizados:</b> <code>{total_uses or 0}</code>\n"
            f"• <b>Total Descontado:</b> <code>${total_discount:.2f} USDT</code>\n"
        )

        toggle_btn_text = "🔴 Desactivar Cupón" if coupon.is_active else "🟢 Activar Cupón"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_btn_text, callback_data=f"admin:coupon:toggle:{coupon.id}:{page}")],
            [InlineKeyboardButton("🗑️ Eliminar Cupón", callback_data=f"admin:coupon:delete:{coupon.id}:{page}")],
            [InlineKeyboardButton("◀️ Volver a Cupones", callback_data=f"admin:coupons:page:{page}")]
        ])

        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^admin:coupon:toggle:(\d+):(\d+)$"))
    async def cb_admin_coupon_toggle(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        coupon_id = int(callback.matches[0].group(1))
        page = int(callback.matches[0].group(2))

        async with async_session() as session:
            stmt = select(Coupon).where(Coupon.id == coupon_id)
            res = await session.execute(stmt)
            coupon = res.scalar_one_or_none()
            if coupon:
                coupon.is_active = not coupon.is_active
                await session.commit()
                status_txt = "activado" if coupon.is_active else "desactivado"
                await callback.answer(f"✅ Cupón {status_txt}.", show_alert=True)

        await cb_admin_coupon_view(client, callback)

    @app.on_callback_query(filters.regex(r"^admin:coupon:delete:(\d+):(\d+)$"))
    async def cb_admin_coupon_delete(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        coupon_id = int(callback.matches[0].group(1))
        page = int(callback.matches[0].group(2))

        async with async_session() as session:
            stmt = select(Coupon).where(Coupon.id == coupon_id)
            res = await session.execute(stmt)
            coupon = res.scalar_one_or_none()
            if coupon:
                await session.delete(coupon)
                await session.commit()
                await callback.answer("🗑️ Cupón eliminado exitosamente.", show_alert=True)

        callback.matches = [type("Match", (), {"group": lambda self, idx: str(page)})()]
        await cb_admin_coupons_list(client, callback)

    @app.on_callback_query(filters.regex("^admin:coupon:create$"))
    async def cb_admin_coupon_create_start(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        ADMIN_PROMO_STATES[user_id] = {
            "flow": "create_coupon",
            "step": "waiting_code",
            "data": {}
        }

        text = (
            "🎟️ <b>CREAR NUEVO CUPÓN (Paso 1 de 5)</b>\n\n"
            "Escribe en el chat el <b>Código</b> que tendrá el cupón.\n\n"
            "<i>Ejemplos: <code>PROMO10</code>, <code>BIENVENIDA</code>, <code>BLACKFRIDAY</code></i>\n\n"
            "• Debe tener al menos 3 caracteres.\n"
            "• Se convertirá automáticamente a mayúsculas."
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar", callback_data="admin:coupons:page:1")]
        ])

        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^admin:coupon:set_type:(percent|fixed)$"))
    async def cb_admin_coupon_set_type(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id) or user_id not in ADMIN_PROMO_STATES:
            return

        disc_type = callback.matches[0].group(1)
        state = ADMIN_PROMO_STATES[user_id]
        state["data"]["discount_type"] = disc_type
        state["step"] = "waiting_value"

        unit_str = "% (ej: 10 para 10% de descuento)" if disc_type == "percent" else "USDT (ej: 1.5 para 1.50 USDT de descuento)"

        text = (
            f"🎟️ <b>CREAR NUEVO CUPÓN (Paso 3 de 5)</b>\n\n"
            f"• <b>Código:</b> <code>{state['data']['code']}</code>\n"
            f"• <b>Tipo:</b> <code>{'Porcentual (%)' if disc_type == 'percent' else 'Monto Fijo (USDT)'}</code>\n\n"
            f"Escribe en el chat el <b>Valor del descuento</b> en {unit_str}:"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar", callback_data="admin:coupons:page:1")]
        ])

        await render_screen(client, callback, text, keyboard)

    # ==========================================
    # 🎁 GESTIÓN DE TARJETAS DE REGALO (GIFT CARDS)
    # ==========================================

    @app.on_callback_query(filters.regex(r"^admin:gifts:page:(\d+)(?::(all|avail))?$"))
    async def cb_admin_gifts_list(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            await callback.answer("❌ Acceso denegado.", show_alert=True)
            return

        page = int(callback.matches[0].group(1))
        filter_mode = callback.matches[0].group(2) or "all"

        async with async_session() as session:
            # Estadísticas globales
            total_cards_stmt = select(func.count(GiftCard.id))
            res_total = await session.execute(total_cards_stmt)
            total_cards = res_total.scalar() or 0

            redeemed_stmt = select(func.count(GiftCard.id), func.sum(GiftCard.amount)).where(GiftCard.is_redeemed.is_(True))
            res_redeemed = await session.execute(redeemed_stmt)
            total_redeemed, sum_redeemed = res_redeemed.first()
            sum_redeemed = float(sum_redeemed or 0.0)

            avail_stmt = select(func.count(GiftCard.id), func.sum(GiftCard.amount)).where(GiftCard.is_redeemed.is_(False))
            res_avail = await session.execute(avail_stmt)
            total_avail, sum_avail = res_avail.first()
            sum_avail = float(sum_avail or 0.0)

            # Consulta paginada
            query = select(GiftCard).order_by(desc(GiftCard.created_at))
            if filter_mode == "avail":
                query = query.where(GiftCard.is_redeemed.is_(False))

            res_cards = await session.execute(query)
            cards_list = res_cards.scalars().all()

            total_items = len(cards_list)
            total_pages = max(1, math.ceil(total_items / GIFTS_PER_PAGE))
            page = max(1, min(page, total_pages))

            start_idx = (page - 1) * GIFTS_PER_PAGE
            cards_page = cards_list[start_idx:start_idx + GIFTS_PER_PAGE]

        text = (
            "🎁 <b>PANEL DE TARJETAS DE REGALO (GIFT CARDS)</b>\n\n"
            "Crea códigos de saldo canjeable ideales para sorteos en canales, recompensas o fidelización.\n\n"
            f"📊 <b>ESTADÍSTICAS:</b>\n"
            f"• <b>Total Generadas:</b> <code>{total_cards}</code>\n"
            f"• <b>Disponibles:</b> <code>{total_avail or 0}</code> (${sum_avail:.2f} USDT)\n"
            f"• <b>Canjeadas:</b> <code>{total_redeemed or 0}</code> (${sum_redeemed:.2f} USDT)\n\n"
            f"<i>Mostrando: {'Sólo Disponibles' if filter_mode == 'avail' else 'Todas las tarjetas'} (Pág {page}/{total_pages})</i>"
        )

        buttons = []
        for g in cards_page:
            st_icon = "✅" if g.is_redeemed else "🎁"
            st_lbl = "Canjeada" if g.is_redeemed else "Disponible"
            btn_text = f"{st_icon} {g.code} (${float(g.amount):.2f}) - {st_lbl}"
            buttons.append([
                InlineKeyboardButton(btn_text, callback_data=f"admin:gift:view:{g.id}:{page}:{filter_mode}")
            ])

        if total_pages > 1:
            nav = []
            if page > 1:
                nav.append(InlineKeyboardButton("◀️", callback_data=f"admin:gifts:page:{page - 1}:{filter_mode}"))
            else:
                nav.append(InlineKeyboardButton("🔵", callback_data="noop"))
            nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
            if page < total_pages:
                nav.append(InlineKeyboardButton("▶️", callback_data=f"admin:gifts:page:{page + 1}:{filter_mode}"))
            else:
                nav.append(InlineKeyboardButton("🔵", callback_data="noop"))
            buttons.append(nav)

        toggle_filter_text = "👀 Ver Sólo Disponibles" if filter_mode == "all" else "📋 Ver Todas"
        next_filter = "avail" if filter_mode == "all" else "all"

        buttons.append([
            InlineKeyboardButton("➕ Generar Gift Cards", callback_data="admin:gift:create"),
            InlineKeyboardButton(toggle_filter_text, callback_data=f"admin:gifts:page:1:{next_filter}")
        ])
        buttons.append([
            InlineKeyboardButton("🔙 Volver al Panel", callback_data="admin:menu")
        ])

        await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))

    @app.on_callback_query(filters.regex(r"^admin:gift:view:(\d+):(\d+):([a-z]+)$"))
    async def cb_admin_gift_view(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        gift_id = int(callback.matches[0].group(1))
        page = int(callback.matches[0].group(2))
        filter_mode = callback.matches[0].group(3)

        async with async_session() as session:
            stmt = select(GiftCard).where(GiftCard.id == gift_id)
            res = await session.execute(stmt)
            card = res.scalar_one_or_none()

            if not card:
                await callback.answer("❌ Tarjeta no encontrada.", show_alert=True)
                return

            redeemed_user_name = "Nadie aún"
            if card.redeemed_by:
                u_stmt = select(User).where(User.telegram_id == card.redeemed_by)
                u_res = await session.execute(u_stmt)
                redeemed_user = u_res.scalar_one_or_none()
                if redeemed_user:
                    uname = f"@{redeemed_user.username}" if redeemed_user.username else f"{redeemed_user.first_name} ({redeemed_user.telegram_id})"
                    redeemed_user_name = uname

        created_str = format_dt(card.created_at, "%Y-%m-%d %H:%M:%S")
        redeemed_str = format_dt(card.redeemed_at, "%Y-%m-%d %H:%M:%S") if card.redeemed_at else "No canjeada"
        status_tag = "✅ CANJEADA" if card.is_redeemed else "🎁 DISPONIBLE PARA CANJE"

        text = (
            f"🎁 <b>TARJETA DE REGALO:</b> <code>{card.code}</code>\n\n"
            f"• <b>Monto:</b> <code>${float(card.amount):.2f} USDT</code>\n"
            f"• <b>Estado:</b> <b>{status_tag}</b>\n"
            f"• <b>Canjeada por:</b> <code>{redeemed_user_name}</code>\n"
            f"• <b>Fecha Canje:</b> <code>{redeemed_str}</code>\n"
            f"• <b>Fecha Creación:</b> <code>{created_str}</code>\n\n"
            f"<i>Código listo para copiar:</i>\n<code>{card.code}</code>"
        )

        buttons = []
        if not card.is_redeemed:
            buttons.append([
                InlineKeyboardButton("🗑️ Eliminar Tarjeta", callback_data=f"admin:gift:delete:{card.id}:{page}:{filter_mode}")
            ])
        buttons.append([
            InlineKeyboardButton("◀️ Volver a la Lista", callback_data=f"admin:gifts:page:{page}:{filter_mode}")
        ])

        await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))

    @app.on_callback_query(filters.regex(r"^admin:gift:delete:(\d+):(\d+):([a-z]+)$"))
    async def cb_admin_gift_delete(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        gift_id = int(callback.matches[0].group(1))
        page = int(callback.matches[0].group(2))
        filter_mode = callback.matches[0].group(3)

        async with async_session() as session:
            stmt = select(GiftCard).where(GiftCard.id == gift_id)
            res = await session.execute(stmt)
            card = res.scalar_one_or_none()
            if card and not card.is_redeemed:
                await session.delete(card)
                await session.commit()
                await callback.answer("🗑️ Tarjeta de regalo eliminada.", show_alert=True)

        callback.matches = [type("Match", (), {"group": lambda self, idx: str(page) if idx == 1 else filter_mode})()]
        await cb_admin_gifts_list(client, callback)

    @app.on_callback_query(filters.regex("^admin:gift:create$"))
    async def cb_admin_gift_create_start(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        text = (
            "🎁 <b>GENERADOR DE TARJETAS DE REGALO</b>\n\n"
            "Selecciona el monto en <b>USDT</b> que contendrá cada tarjeta de regalo, o pulsa 'Otro Monto' para escribirlo:"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💵 1 USDT", callback_data="admin:gift:set_amt:1"),
                InlineKeyboardButton("💵 2 USDT", callback_data="admin:gift:set_amt:2"),
                InlineKeyboardButton("💵 5 USDT", callback_data="admin:gift:set_amt:5")
            ],
            [
                InlineKeyboardButton("💵 10 USDT", callback_data="admin:gift:set_amt:10"),
                InlineKeyboardButton("💵 20 USDT", callback_data="admin:gift:set_amt:20"),
                InlineKeyboardButton("✏️ Otro Monto", callback_data="admin:gift:custom_amt")
            ],
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="admin:gifts:page:1")
            ]
        ])

        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^admin:gift:set_amt:(\d+(?:\.\d+)?)$"))
    async def cb_admin_gift_set_amount(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        amount = float(callback.matches[0].group(1))

        ADMIN_PROMO_STATES[user_id] = {
            "flow": "create_gift",
            "amount": amount
        }

        text = (
            f"🎁 <b>GENERAR TARJETAS DE ${amount:.2f} USDT</b>\n\n"
            f"¿Cuántas tarjetas de <b>${amount:.2f} USDT</b> deseas generar?\n\n"
            f"<i>Selecciona una cantidad rápida o escribe un número en el chat (máx 50):</i>"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎁 1 Código", callback_data="admin:gift:gen:1"),
                InlineKeyboardButton("🎁 3 Códigos", callback_data="admin:gift:gen:3"),
                InlineKeyboardButton("🎁 5 Códigos", callback_data="admin:gift:gen:5")
            ],
            [
                InlineKeyboardButton("🎁 10 Códigos", callback_data="admin:gift:gen:10"),
                InlineKeyboardButton("🎁 20 Códigos", callback_data="admin:gift:gen:20"),
                InlineKeyboardButton("❌ Cancelar", callback_data="admin:gifts:page:1")
            ]
        ])

        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^admin:gift:gen:(\d+)$"))
    async def cb_admin_gift_generate(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id) or user_id not in ADMIN_PROMO_STATES:
            await callback.answer("Error de sesión.", show_alert=True)
            return

        count = int(callback.matches[0].group(1))
        amount = ADMIN_PROMO_STATES[user_id].get("amount", 1.0)
        ADMIN_PROMO_STATES.pop(user_id, None)

        async with async_session() as session:
            cards = await promo_service.create_gift_cards(
                session=session,
                amount=amount,
                count=count,
                created_by=user_id
            )

        codes_text = "\n".join(f"<code>{c.code}</code> ({float(c.amount):.2f} USDT)" for c in cards)

        text = (
            f"🎉 <b>¡TARJETAS DE REGALO GENERADAS CON ÉXITO!</b>\n\n"
            f"• <b>Cantidad:</b> <code>{len(cards)}</code>\n"
            f"• <b>Monto por tarjeta:</b> <code>${amount:.2f} USDT</code>\n"
            f"• <b>Total en Saldo:</b> <code>${amount * len(cards):.2f} USDT</code>\n\n"
            f"📋 <b>Códigos listos para compartir / copiar:</b>\n"
            f"{codes_text}\n\n"
            f"<i>Los usuarios pueden canjearlos pulsando 'Canjear Tarjeta de Regalo' en su billetera o enviando /canjear CODIGO.</i>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎁 Ver Lista de Gift Cards", callback_data="admin:gifts:page:1")],
            [InlineKeyboardButton("🔙 Volver al Panel Admin", callback_data="admin:menu")]
        ])

        await render_screen(client, callback, text, keyboard)

    # ==========================================
    # 💬 MANEJO DE ENTRADAS DE TEXTO ADMIN
    # ==========================================

    @app.on_message(filters.private & ~filters.command(["start", "admin", "menu", "buscar", "search", "catalogo", "catalog", "pedidos", "orders", "depositar", "deposit", "saldo", "wallet", "soporte", "support", "ayuda", "help", "del", "dep", "vip"]), group=4)
    async def on_admin_promo_text(client: Client, message: Message):
        user_id = message.from_user.id
        if user_id not in ADMIN_PROMO_STATES:
            message.continue_propagation()
            return

        state = ADMIN_PROMO_STATES[user_id]
        flow = state.get("flow")
        txt = (message.text or "").strip()

        try:
            await message.delete()
        except Exception:
            pass

        # Flujo de creación de Cupón
        if flow == "create_coupon":
            step = state.get("step")

            if step == "waiting_code":
                code = txt.upper()
                if len(code) < 3 or len(code) > 25:
                    await client.send_message(user_id, "⚠️ El código debe tener entre 3 y 25 caracteres. Intenta de nuevo:")
                    return

                state["data"]["code"] = code
                state["step"] = "waiting_type"

                text = (
                    f"🎟️ <b>CREAR NUEVO CUPÓN (Paso 2 de 5)</b>\n\n"
                    f"• <b>Código:</b> <code>{code}</code>\n\n"
                    f"Selecciona el <b>tipo de descuento</b>:"
                )

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📊 Porcentual (%)", callback_data="admin:coupon:set_type:percent"),
                        InlineKeyboardButton("💵 Monto Fijo (USDT)", callback_data="admin:coupon:set_type:fixed")
                    ],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="admin:coupons:page:1")]
                ])
                await client.send_message(user_id, parse_emojis(text), parse_mode=ParseMode.HTML, reply_markup=parse_keyboard(keyboard))

            elif step == "waiting_value":
                try:
                    val = float(txt)
                    if val <= 0:
                        raise ValueError()
                except ValueError:
                    await client.send_message(user_id, "⚠️ Ingresa un número válido mayor a 0:")
                    return

                disc_type = state["data"]["discount_type"]
                if disc_type == "percent" and val > 90:
                    await client.send_message(user_id, "⚠️ El porcentaje no puede superar el 90%. Ingresa otro valor:")
                    return

                state["data"]["discount_value"] = val
                state["step"] = "waiting_max_uses"

                text = (
                    f"🎟️ <b>CREAR NUEVO CUPÓN (Paso 4 de 5)</b>\n\n"
                    f"• <b>Código:</b> <code>{state['data']['code']}</code>\n"
                    f"• <b>Descuento:</b> <code>{val:.2f}{'%' if disc_type == 'percent' else ' USDT'}</code>\n\n"
                    f"Ingresa el <b>límite de usos totales</b> (ej: <code>50</code> para 50 canjes globales, o <code>0</code> para ilimitado):"
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancelar", callback_data="admin:coupons:page:1")]
                ])
                await client.send_message(user_id, parse_emojis(text), parse_mode=ParseMode.HTML, reply_markup=parse_keyboard(keyboard))

            elif step == "waiting_max_uses":
                try:
                    max_u = int(txt)
                    if max_u < 0:
                        raise ValueError()
                except ValueError:
                    await client.send_message(user_id, "⚠️ Ingresa un número entero mayor o igual a 0:")
                    return

                state["data"]["max_uses"] = max_u
                state["step"] = "waiting_days"

                text = (
                    f"🎟️ <b>CREAR NUEVO CUPÓN (Paso 5 de 5)</b>\n\n"
                    f"• <b>Código:</b> <code>{state['data']['code']}</code>\n"
                    f"• <b>Límite de usos:</b> <code>{'Ilimitado' if max_u == 0 else f'{max_u} usos'}</code>\n\n"
                    f"Ingresa los <b>días de vigencia</b> del cupón (ej: <code>7</code> para 7 días, o <code>0</code> para que no expire nunca):"
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancelar", callback_data="admin:coupons:page:1")]
                ])
                await client.send_message(user_id, parse_emojis(text), parse_mode=ParseMode.HTML, reply_markup=parse_keyboard(keyboard))

            elif step == "waiting_days":
                try:
                    days = int(txt)
                    if days < 0:
                        raise ValueError()
                except ValueError:
                    await client.send_message(user_id, "⚠️ Ingresa un número entero mayor o igual a 0:")
                    return

                data = state["data"]
                ADMIN_PROMO_STATES.pop(user_id, None)

                async with async_session() as session:
                    ok, msg, coupon = await promo_service.create_coupon(
                        session=session,
                        code=data["code"],
                        discount_type=data["discount_type"],
                        discount_value=data["discount_value"],
                        max_uses=data["max_uses"],
                        duration_days=days
                    )

                if not ok:
                    await client.send_message(user_id, f"❌ Error: {msg}")
                    return

                val_tag = f"{float(coupon.discount_value):.2f}%" if coupon.discount_type == "percent" else f"${float(coupon.discount_value):.2f} USDT"
                exp_tag = f"{days} días" if days > 0 else "Sin fecha de expiración"

                final_text = (
                    f"🎉 <b>¡CUPÓN CREADO CON ÉXITO!</b>\n\n"
                    f"• <b>Código:</b> <code>{coupon.code}</code>\n"
                    f"• <b>Descuento:</b> <code>{val_tag}</code>\n"
                    f"• <b>Límite de Usos:</b> <code>{'Ilimitado' if coupon.max_uses == 0 else f'{coupon.max_uses} canjes'}</code>\n"
                    f"• <b>Vigencia:</b> <code>{exp_tag}</code>\n\n"
                    f"<i>Los usuarios pueden aplicar este cupón al realizar una compra en el bot.</i>"
                )

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎟️ Ver Lista de Cupones", callback_data="admin:coupons:page:1")],
                    [InlineKeyboardButton("🔙 Volver al Panel Admin", callback_data="admin:menu")]
                ])
                await client.send_message(user_id, parse_emojis(final_text), parse_mode=ParseMode.HTML, reply_markup=parse_keyboard(keyboard))

        # Flujo de Gift Card personalizada
        elif flow == "create_gift":
            if state.get("step") == "waiting_custom_amount":
                try:
                    amt = float(txt)
                    if amt <= 0.1 or amt > 1000:
                        raise ValueError()
                except ValueError:
                    await client.send_message(user_id, "⚠️ Ingresa un monto válido entre 0.1 y 1000 USDT:")
                    return

                state["amount"] = amt
                state["step"] = None

                text = (
                    f"🎁 <b>GENERAR TARJETAS DE ${amt:.2f} USDT</b>\n\n"
                    f"¿Cuántas tarjetas de <b>${amt:.2f} USDT</b> deseas generar?\n\n"
                    f"<i>Selecciona una cantidad rápida o escribe un número en el chat (máx 50):</i>"
                )

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("1 Código", callback_data="admin:gift:gen:1"),
                        InlineKeyboardButton("3 Códigos", callback_data="admin:gift:gen:3"),
                        InlineKeyboardButton("5 Códigos", callback_data="admin:gift:gen:5")
                    ],
                    [
                        InlineKeyboardButton("10 Códigos", callback_data="admin:gift:gen:10"),
                        InlineKeyboardButton("20 Códigos", callback_data="admin:gift:gen:20"),
                        InlineKeyboardButton("❌ Cancelar", callback_data="admin:gifts:page:1")
                    ]
                ])
                await client.send_message(user_id, parse_emojis(text), parse_mode=ParseMode.HTML, reply_markup=parse_keyboard(keyboard))

    @app.on_callback_query(filters.regex("^admin:gift:custom_amt$"))
    async def cb_admin_gift_custom_amt(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        ADMIN_PROMO_STATES[user_id] = {
            "flow": "create_gift",
            "step": "waiting_custom_amount"
        }

        text = (
            "🎁 <b>MONTO PERSONALIZADO PARA GIFT CARDS</b>\n\n"
            "Escribe en el chat la cantidad de <b>USDT</b> que contendrá cada tarjeta (ejemplo: <code>3.5</code> o <code>15</code>):"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar", callback_data="admin:gifts:page:1")]
        ])
        await render_screen(client, callback, text, keyboard)

