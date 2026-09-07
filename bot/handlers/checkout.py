from decimal import Decimal
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, update
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Order, Setting
from bot.services.bunai_client import bunai_api
from bot.services.pricing import pricing_service
from bot.services.audit_logger import audit_logger
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.translator import translate_text
from bot.utils.emojis import EMOJI_STAR, EMOJI_PIN

def register_checkout_handlers(app: Client):

    @app.on_callback_query(filters.regex(r"^checkout:confirm:([a-zA-Z0-9_\-]+):(\d+)(?::([a-z]+))?$"))
    async def cb_checkout_confirm(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer("⏳ ...", show_alert=False)
            return

        is_owner = settings.is_owner(user_id)

        product_id = callback.matches[0].group(1)
        qty = int(callback.matches[0].group(2))
        if qty <= 0:
            qty = 1

        raw_method = callback.matches[0].group(3)
        pay_method = raw_method if raw_method else ("api" if is_owner else "bot")
        pay_with_api = is_owner and (pay_method == "api")

        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = user.language if user else "es"

            # 1. Comprobar modo mantenimiento (Owner tiene bypass)
            m_stmt = select(Setting).where(Setting.key == "maintenance_mode")
            m_res = await session.execute(m_stmt)
            m_setting = m_res.scalar_one_or_none()
            if m_setting and m_setting.value == "true" and not is_owner:
                await callback.answer("⚠️ Maintenance Mode Active / Modo Mantenimiento", show_alert=True)
                return

            # 2. Obtener producto y calcular precio total
            p_data = await bunai_api.get_product(product_id)
            if not p_data:
                await callback.answer("❌ Error / Not available", show_alert=True)
                return

            base_price = float(p_data.get("price", 0.0))

            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            is_active_vip = bool(user and user.is_vip and user.vip_expires_at and user.vip_expires_at > now_utc)

            if is_owner:
                # El owner siempre paga el precio de costo exacto del proveedor (0% margen)
                unit_price = base_price
                discount_pct = 0.0
            else:
                unit_price = await pricing_service.calculate_product_price(base_price, product_id, session)
                if is_active_vip:
                    unit_price = pricing_service.calculate_vip_price(unit_price)
                discount_pct = 0.0
                has_promo = bool(p_data.get("has_promo", False))
                if has_promo:
                    promo_tiers = p_data.get("promo_tiers")
                    if isinstance(promo_tiers, list) and len(promo_tiers) > 0:
                        tier = promo_tiers[0]
                        if qty >= tier.get("qty", 100):
                            discount_pct = float(tier.get("discount", 5.0))
                    elif isinstance(promo_tiers, dict) and len(promo_tiers) > 0:
                        first_min = next(iter(promo_tiers))
                        if qty >= int(first_min):
                            discount_pct = float(promo_tiers[first_min])

            subtotal = qty * unit_price
            if discount_pct > 0:
                subtotal = subtotal * (1.0 - (discount_pct / 100.0))
            total_price = round(subtotal, 2)
            total_price_dec = Decimal(str(total_price))

            product_name = p_data.get("display_name") or p_data.get("name") or "Servicio Digital"
            stock_count = int(p_data.get("stock_count", 0))
            infinite_stock = bool(p_data.get("infinite_stock", False))
            if not infinite_stock and stock_count < qty:
                await callback.answer("❌ Stock insuficiente en el proveedor", show_alert=True)
                return

            bunai_warranty = int(p_data.get("warranty_hours", 0))
            warranty_hours = pricing_service.calculate_adjusted_warranty(bunai_warranty)

            # 3. Verificación y descuento de saldo
            if pay_with_api:
                # El owner paga directamente con su saldo en la API de BunaiStore
                api_balance = await bunai_api.get_balance(force_refresh=True)
                if api_balance < total_price:
                    await callback.answer(f"❌ Saldo API insuficiente (${api_balance:.2f} < ${total_price:.2f} USD)", show_alert=True)
                    return
                # No se descuenta nada de user.balance en la base de datos local
                remaining_balance = Decimal(str(round(api_balance - total_price, 2)))
            else:
                # Transacción atómica de descuento de saldo (Anti Doble-Gasto)
                deduct_stmt = (
                    update(User)
                    .where(User.telegram_id == user_id, User.balance >= total_price_dec)
                    .values(
                        balance=User.balance - total_price_dec,
                        total_spent=User.total_spent + total_price_dec
                    )
                    .returning(User.balance)
                )
                deduct_res = await session.execute(deduct_stmt)
                remaining_balance = deduct_res.scalar()

                if remaining_balance is None:
                    await callback.answer("❌ Saldo insuficiente en el bot", show_alert=True)
                    return

                await session.commit()

        # 4. Mensaje temporal de procesamiento traducido
        proc_text = t("processing_order", lang, qty=qty, product=product_name)
        if pay_with_api:
            proc_text += "\n👑 <i>(Procesando compra directa con saldo API)</i>"
        elif is_owner:
            proc_text += "\n👑 <i>(Procesando compra Owner a precio de costo con saldo Bot)</i>"
        await render_screen(client, callback, proc_text, None)

        # 5. Ejecutar compra en BunaiStore API
        order_res = await bunai_api.create_order(product_id, qty=qty)

        if not order_res.get("success"):
            error_msg = order_res.get("error", "Error desconocido")
            if not pay_with_api:
                # Rollback automático de saldo del bot
                async with async_session() as session:
                    rollback_stmt = (
                        update(User)
                        .where(User.telegram_id == user_id)
                        .values(
                            balance=User.balance + total_price_dec,
                            total_spent=User.total_spent - total_price_dec
                        )
                    )
                    await session.execute(rollback_stmt)
                    await session.commit()

            await audit_logger.log_system_alert(
                client,
                "FALLO DE COMPRA OWNER (API)" if is_owner else "FALLO DE COMPRA & ROLLBACK APLICADO",
                f"👤 <b>Usuario:</b> <code>{user_id}</code> {'👑 (Owner)' if is_owner else ''}\n"
                f"📦 <b>Producto:</b> <code>{product_name}</code> (Cant: {qty})\n"
                f"💰 <b>Monto:</b> <code>${total_price:.2f} {'USD (API)' if is_owner else 'USDT'}</code>\n"
                f"❌ <b>Razón:</b> <code>{error_msg}</code>"
            )

            if is_owner:
                fail_text = (
                    f"❌ <b>NO SE PUDO COMPLETAR LA COMPRA OWNER</b>\n\n"
                    f"El proveedor rechazó la orden:\n<code>{error_msg}</code>\n\n"
                    f"<i>Tu saldo del bot no fue afectado. Verifica tu cuenta en BunaiStore.</i>"
                )
            else:
                fail_text = t("purchase_fail_title", lang, total=total_price)

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")],
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
            ])
            await render_screen(client, callback, fail_text, keyboard)
            return

        # 6. Compra exitosa
        order_data = order_res.get("data", {})
        provider_order_id = order_data.get("order_id")
        
        raw_items_data = order_data.get("items", [])
        if isinstance(raw_items_data, str):
            raw_items = [raw_items_data]
        elif isinstance(raw_items_data, list):
            raw_items = [str(x.get("content", x)) if isinstance(x, dict) else str(x) for x in raw_items_data]
        else:
            raw_items = []

        raw_after_note = order_data.get("after_note", "")
        if raw_after_note and raw_after_note.strip():
            after_note = await translate_text(raw_after_note, lang)
        else:
            after_note = ""

        delivered_text = ""
        if raw_items:
            delivered_text = "\n\n".join(raw_items)
        elif raw_after_note:
            delivered_text = raw_after_note
        else:
            delivered_text = "OK"

        # Guardar en Base de Datos
        async with async_session() as session:
            new_order = Order(
                user_id=user_id,
                product_id=product_id,
                product_name=product_name,
                quantity=qty,
                unit_price=Decimal(str(unit_price)),
                total_price=total_price_dec,
                provider_order_id=provider_order_id,
                delivered_items=delivered_text,
                warranty_hours=warranty_hours
            )
            session.add(new_order)
            await session.commit()
            await session.refresh(new_order)
            internal_order_id = new_order.id

        # Notificar en el canal de auditoría del Owner
        if pay_with_api:
            new_api_bal = await bunai_api.get_balance(force_refresh=True)
            audit_rem_bal = new_api_bal
            owner_payment_mode = " [👑 COMPRA OWNER - SALDO API]"
        else:
            audit_rem_bal = float(remaining_balance)
            owner_payment_mode = " [👑 COMPRA OWNER - SALDO BOT]" if is_owner else ""

        await audit_logger.log_purchase(
            client=client,
            user_id=user_id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name or "Usuario",
            order_id=internal_order_id,
            product_name=f"{product_name} (x{qty}){owner_payment_mode}",
            paid_price=total_price,
            remaining_balance=audit_rem_bal,
            provider_order_id=provider_order_id,
            delivered_items=delivered_text,
            is_owner=is_owner
        )

        # Pantalla de entrega traducida
        warranty_text = f"\n{EMOJI_STAR} <b>{t('warranty_label', lang)}:</b> <code>{warranty_hours}h</code>" if warranty_hours > 0 else ""
        after_note_block = f"\n\n{EMOJI_PIN} <b>Info:</b>\n<i>{after_note}</i>" if after_note else ""

        if is_owner:
            currency_tag = "USD (API)" if pay_with_api else "USDT (Bot)"
            balance_tag = f"💳 <b>Saldo Restante API:</b> <code>${audit_rem_bal:.2f} USD</code>" if pay_with_api else f"💳 <b>Saldo Restante Bot:</b> <code>${audit_rem_bal:.2f} USDT</code>"
            footer_note = "<i>👑 Compra procesada a precio de costo con tu saldo directo de BunaiStore.</i>" if pay_with_api else "<i>👑 Compra procesada a precio de costo con tu saldo en el bot.</i>"
            success_text = (
                f"👑 <b>¡COMPRA OWNER REALIZADA CON ÉXITO!</b>\n\n"
                f"📦 <b>Producto:</b> <code>{product_name}</code> (x{qty})\n"
                f"💵 <b>Costo Pagado:</b> <code>${total_price:.2f} {currency_tag}</code>\n"
                f"{balance_tag}\n"
                f"🆔 <b>Orden #:</b> <code>ORD_{internal_order_id}</code>{warranty_text}\n"
                f"🌐 <b>ID Proveedor:</b> <code>{provider_order_id or 'N/A'}</code>\n\n"
                f"🔑 <b>DATOS DE TU SERVICIO:</b>\n<pre>{delivered_text}</pre>{after_note_block}\n\n"
                f"{footer_note}"
            )
        else:
            success_text = t(
                "purchase_success_title",
                lang,
                product=product_name,
                qty=qty,
                total=f"{total_price:.2f}",
                order_id=internal_order_id,
                warranty_text=warranty_text,
                items=delivered_text,
                after_note=after_note_block
            )

        buttons_success = []
        if is_active_vip or is_owner:
            buttons_success.append([InlineKeyboardButton(t("btn_copy_client", lang), callback_data=f"vip:copy_client:{internal_order_id}")])

        buttons_success.extend([
            [InlineKeyboardButton(t("btn_view_in_orders", lang), callback_data="orders:page:1:main")],
            [InlineKeyboardButton(t("btn_continue_shopping", lang), callback_data="catalog:disponibles:1")],
            [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
        ])

        success_keyboard = InlineKeyboardMarkup(buttons_success)
        await render_screen(client, callback, success_text, success_keyboard)

    @app.on_callback_query(filters.regex(r"^pbuy_(?:owner_api|flow):([a-zA-Z0-9_\-]+):([a-z_]+):(\d+):(\d+)$"))
    async def cb_pbuy_alias(client: Client, callback: CallbackQuery):
        """Compatibilidad retroactiva con callbacks de compra directa"""
        import re
        is_owner_api = callback.data.startswith("pbuy_owner_api:")
        product_id = callback.matches[0].group(1)
        qty = int(callback.matches[0].group(4))
        method = "api" if is_owner_api else "bot"
        m = re.match(r"^([a-zA-Z0-9_\-]+):(\d+):([a-z]+)$", f"{product_id}:{qty}:{method}")
        callback.matches = [m]
        await cb_checkout_confirm(client, callback)
