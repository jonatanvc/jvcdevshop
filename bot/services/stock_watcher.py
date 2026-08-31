import asyncio
from datetime import datetime
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from sqlalchemy import select, update
from bot.database.session import async_session
from bot.database.models import StockAlert
from bot.services.bunai_client import bunai_api
from bot.services.pricing import pricing_service
from bot.services.audit_logger import audit_logger

class StockWatcher:
    async def check_and_notify_restocks(self, client: Client):
        """Revisa productos agotados con alertas activas y notifica a los usuarios si fueron reabastecidos"""
        try:
            async with async_session() as session:
                # 1. Obtener lista única de productos con alertas pendientes
                stmt = select(StockAlert.product_id).where(StockAlert.is_active == True).distinct()
                res = await session.execute(stmt)
                pending_product_ids = res.scalars().all()

                if not pending_product_ids:
                    return

            for product_id in pending_product_ids:
                p_data = await bunai_api.get_product(product_id)
                if not p_data:
                    continue

                stock_count = int(p_data.get("stock_count", 0))
                infinite_stock = bool(p_data.get("infinite_stock", False))

                # Si el producto ahora tiene stock disponible
                if infinite_stock or stock_count > 0:
                    stock_display = "Ilimitado (∞)" if infinite_stock else f"{stock_count} unidades"
                    product_name = p_data.get("display_name") or p_data.get("name") or "Servicio Digital"
                    base_price = float(p_data.get("price", 0.0))

                    async with async_session() as session:
                        user_price = await pricing_service.calculate_product_price(base_price, product_id, session)

                        # Obtener todos los usuarios suscritos a este producto
                        alert_stmt = select(StockAlert).where(
                            StockAlert.product_id == product_id,
                            StockAlert.is_active == True
                        )
                        alert_res = await session.execute(alert_stmt)
                        alerts_to_notify = alert_res.scalars().all()

                        notified_count = 0

                        for alert in alerts_to_notify:
                            user_id = alert.user_id
                            text = (
                                f"🔔 <b>¡PRODUCTO RESTABLECIDO EN STOCK!</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"📦 <b>Producto:</b> <code>{product_name}</code>\n"
                                f"💰 <b>Precio:</b> <code>${user_price:.2f} USDT</code>\n"
                                f"🎲 <b>Stock Disponible:</b> <code>{stock_display}</code>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"<i>El servicio que estabas esperando ya está disponible para compra inmediata. ¡Aprovecha antes de que se agote!</i>"
                            )

                            keyboard = InlineKeyboardMarkup([
                                [InlineKeyboardButton("🛒 Ver y Comprar Ahora", callback_data=f"product:view:{product_id}:disponibles:1:0")],
                                [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
                            ])

                            try:
                                await client.send_message(
                                    chat_id=user_id,
                                    text=text,
                                    reply_markup=keyboard,
                                    parse_mode=ParseMode.HTML
                                )
                                notified_count += 1
                                await asyncio.sleep(0.05)
                            except Exception:
                                pass

                            alert.is_active = False
                            alert.notified_at = datetime.utcnow()

                        await session.commit()

                    if notified_count > 0:
                        await audit_logger.log_system_alert(
                            client=client,
                            title="NOTIFICACIÓN DE RESTOCK ENVIADA",
                            details=(
                                f"📦 <b>Producto:</b> <code>{product_name}</code> ({product_id})\n"
                                f"🎲 <b>Stock Restablecido:</b> <code>{stock_display}</code>\n"
                                f"👥 <b>Usuarios Notificados:</b> <code>{notified_count}</code>"
                            )
                        )

        except Exception as e:
            print(f"[StockWatcher Error] {e}")

stock_watcher = StockWatcher()
