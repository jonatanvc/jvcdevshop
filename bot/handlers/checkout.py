from decimal import Decimal
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, update
from bot.database.session import async_session
from bot.database.models import User, Order, Setting
from bot.services.bunai_client import bunai_api
from bot.services.pricing import pricing_service
from bot.services.audit_logger import audit_logger
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter

def register_checkout_handlers(app: Client):

    @app.on_callback_query(filters.regex(r"^checkout:confirm:([a-zA-Z0-9_\-]+):(\d+)$"))
    async def cb_checkout_confirm(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer("⏳ Procesando...", show_alert=False)
            return

        product_id = callback.matches[0].group(1)
        qty = int(callback.matches[0].group(2))
        if qty <= 0:
            qty = 1

        async with async_session() as session:
            # 1. Comprobar modo mantenimiento
            m_stmt = select(Setting).where(Setting.key == "maintenance_mode")
            m_res = await session.execute(m_stmt)
            m_setting = m_res.scalar_one_or_none()
            if m_setting and m_setting.value == "true":
                await callback.answer("⚠️ El bot está en modo mantenimiento temporal. Compras pausadas.", show_alert=True)
                return

            # 2. Obtener producto y calcular precio total con posibles descuentos
            p_data = await bunai_api.get_product(product_id)
            if not p_data:
                await callback.answer("❌ El producto no se encuentra disponible.", show_alert=True)
                return

            base_price = float(p_data.get("price", 0.0))
            unit_price = await pricing_service.calculate_product_price(base_price, product_id, session)

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
            bunai_warranty = int(p_data.get("warranty_hours", 0))
            warranty_hours = pricing_service.calculate_adjusted_warranty(bunai_warranty)

            # 3. Transacción atómica de descuento de saldo (Anti Doble-Gasto)
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
                await callback.answer("❌ Saldo insuficiente para completar la compra.", show_alert=True)
                return

            await session.commit()

        # 4. Mensaje temporal de procesamiento
        await render_screen(
            client,
            callback,
            f"⏳ <b>Procesando tu orden de {qty}x {product_name}...</b>\n<i>Por favor espera unos segundos.</i>",
            None
        )

        # 5. Ejecutar compra en BunaiStore API
        order_res = await bunai_api.create_order(product_id, qty=qty)

        if not order_res.get("success"):
            # === ROLLBACK AUTOMÁTICO DE SALDO ===
            error_msg = order_res.get("error", "Error desconocido en el proveedor")
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
                "FALLO DE COMPRA & ROLLBACK APLICADO",
                f"👤 <b>Usuario:</b> <code>{user_id}</code>\n"
                f"📦 <b>Producto:</b> <code>{product_name}</code> (Cant: {qty})\n"
                f"💰 <b>Monto Reembolsado:</b> <code>${total_price:.2f} USDT</code>\n"
                f"❌ <b>Razón del Proveedor:</b> <code>{error_msg}</code>"
            )

            fail_text = (
                "❌ <b>NO SE PUDO COMPLETAR LA COMPRA</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"El proveedor rechazó la solicitud (posiblemente sin stock suficiente).\n\n"
                f"🛡️ <b>Tu saldo de ${total_price:.2f} USDT ha sido reembolsado intacto a tu cuenta.</b>"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Volver al Catálogo", callback_data="catalog:disponibles:1")],
                [InlineKeyboardButton("🔙 Menú Principal", callback_data="menu_main")]
            ])
            await render_screen(client, callback, fail_text, keyboard)
            return

        # 6. Compra exitosa: Procesar datos entregados
        order_data = order_res.get("data", {})
        provider_order_id = order_data.get("order_id")
        raw_items = order_data.get("items", [])
        after_note = order_data.get("after_note", "")

        delivered_text = ""
        if raw_items:
            delivered_text = "\n\n".join(raw_items)
        elif after_note:
            delivered_text = after_note
        else:
            delivered_text = "Orden registrada exitosamente para entrega manual."

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

        # 7. Notificar en el canal de auditoría del Owner
        await audit_logger.log_purchase(
            client=client,
            user_id=user_id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name or "Usuario",
            order_id=internal_order_id,
            product_name=f"{product_name} (x{qty})",
            paid_price=total_price,
            remaining_balance=float(remaining_balance),
            provider_order_id=provider_order_id,
            delivered_items=delivered_text
        )

        # 8. Pantalla de entrega al usuario
        warranty_note = f"\n🛡️ <b>Garantía:</b> <code>{warranty_hours} horas</code>" if warranty_hours > 0 else ""
        after_note_block = f"\n\n📌 <b>Instrucciones Post-Compra:</b>\n<i>{after_note}</i>" if after_note else ""

        success_text = (
            f"🎉 <b>¡COMPRA REALIZADA CON ÉXITO!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>Producto:</b> <code>{product_name}</code> (x{qty})\n"
            f"💰 <b>Total Pagado:</b> <code>${total_price:.2f} USDT</code>\n"
            f"🆔 <b>Orden #:</b> <code>ORD_{internal_order_id}</code>{warranty_note}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 <b>DATOS DE TU SERVICIO:</b>\n"
            f"<pre>{delivered_text}</pre>"
            f"{after_note_block}\n\n"
            f"<i>💡 Puedes consultar tus compras y garantías en cualquier momento desde 'Mis Pedidos'.</i>"
        )

        success_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💼 Ver en 'Mis Pedidos'", callback_data="orders:page:1")],
            [InlineKeyboardButton("🛒 Seguir Comprando", callback_data="catalog:disponibles:1")],
            [InlineKeyboardButton("🔙 Menú Principal", callback_data="menu_main")]
        ])

        await render_screen(client, callback, success_text, success_keyboard)
