import asyncio
from datetime import datetime
from typing import Dict, Set, Optional
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from sqlalchemy import select
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import StockAlert
from bot.services.bunai_client import bunai_api
from bot.services.pricing import pricing_service
from bot.services.audit_logger import audit_logger

def get_product_icon_simple(name: str) -> str:
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

class StockWatcher:
    def __init__(self):
        # Mapeos en memoria para detectar cambios de stock y productos nuevos
        self._previous_stock: Dict[str, int] = {}
        self._known_product_ids: Set[str] = set()
        self._is_initialized: bool = False

    async def initialize_baseline(self):
        """Carga el estado inicial de productos para no enviar alertas repetidas al arrancar"""
        try:
            products = await bunai_api.get_products(force_refresh=True)
            for p in products:
                pid = p.get("id") or p.get("product_id")
                if pid:
                    self._known_product_ids.add(pid)
                    self._previous_stock[pid] = int(p.get("stock_count", 0))
            self._is_initialized = True
        except Exception as e:
            print(f"[StockWatcher Init Error]: {e}")

    async def check_and_notify_restocks(self, client: Client):
        """
        Escanea el catálogo de BunaiStore en tiempo real para:
        1. Detectar si el proveedor agregó stock a un producto existente y avisar en el canal de logs.
        2. Detectar si el proveedor agregó un producto completamente nuevo y avisar en el canal de logs.
        3. Notificar por mensaje privado a los clientes suscritos a alertas de restock.
        """
        try:
            if not self._is_initialized:
                await self.initialize_baseline()
                return

            products = await bunai_api.get_products(force_refresh=True)
            if not products:
                return

            async with async_session() as session:
                for p in products:
                    pid = p.get("id") or p.get("product_id")
                    if not pid:
                        continue

                    name = p.get("display_name") or p.get("name") or "Servicio Digital"
                    icon = get_product_icon_simple(name)
                    base_price = float(p.get("price", 0.0))
                    current_stock = int(p.get("stock_count", 0))
                    infinite_stock = bool(p.get("infinite_stock", False))
                    user_price = await pricing_service.calculate_product_price(base_price, pid, session)

                    # ==========================================================
                    # CASO 1: PRODUCTO TOTALMENTE NUEVO AÑADIDO POR EL PROVEEDOR
                    # ==========================================================
                    if pid not in self._known_product_ids:
                        self._known_product_ids.add(pid)
                        self._previous_stock[pid] = current_stock
                        stock_text = "Ilimitado (∞)" if infinite_stock else str(current_stock)

                        # Alerta al canal de logs del Owner (sin botones)
                        await audit_logger.log_new_product_alert(
                            client=client,
                            product_name=name,
                            icon=icon,
                            initial_stock=stock_text,
                            cost_price=base_price,
                            user_price=user_price,
                            product_id=pid
                        )
                        continue

                    # ==========================================================
                    # CASO 2: STOCK AÑADIDO A UN PRODUCTO EXISTENTE
                    # ==========================================================
                    prev_stock = self._previous_stock.get(pid, 0)

                    if current_stock > prev_stock and not infinite_stock:
                        added_stock = current_stock - prev_stock
                        self._previous_stock[pid] = current_stock

                        # Alerta al canal de logs del Owner idéntica al formato de aviso (sin botones)
                        await audit_logger.log_restock_alert(
                            client=client,
                            product_name=name,
                            icon=icon,
                            added_stock=added_stock,
                            total_stock=current_stock,
                            cost_price=base_price,
                            user_price=user_price
                        )

                        # Notificar a usuarios de Telegram que tenían la alerta activa
                        alert_stmt = select(StockAlert).where(
                            StockAlert.product_id == pid,
                            StockAlert.is_active == True
                        )
                        alert_res = await session.execute(alert_stmt)
                        alerts_to_notify = alert_res.scalars().all()

                        for alert in alerts_to_notify:
                            dm_text = (
                                f"🔔 <b>¡PRODUCTO RESTABLECIDO EN STOCK!</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"📦 <b>Producto:</b> <code>{name}</code>\n"
                                f"💰 <b>Precio:</b> <code>${user_price:.2f} USDT</code>\n"
                                f"🎲 <b>Stock Disponible:</b> <code>{current_stock} unidades</code>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"<i>El servicio que estabas esperando ya tiene stock disponible. ¡Aprovecha antes de que se agote!</i>"
                            )
                            dm_kb = InlineKeyboardMarkup([
                                [InlineKeyboardButton("🛒 Ver y Comprar Ahora", callback_data=f"product:view:{pid}:disponibles:1:0")],
                                [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
                            ])
                            try:
                                await client.send_message(
                                    chat_id=alert.user_id,
                                    text=dm_text,
                                    reply_markup=dm_kb,
                                    parse_mode=ParseMode.HTML
                                )
                                await asyncio.sleep(0.05)
                            except Exception:
                                pass

                            alert.is_active = False
                            alert.notified_at = datetime.utcnow()

                        await session.commit()

                    else:
                        # Actualizar estado para seguimiento
                        self._previous_stock[pid] = current_stock

        except Exception as e:
            print(f"[StockWatcher Error] {e}")

stock_watcher = StockWatcher()
