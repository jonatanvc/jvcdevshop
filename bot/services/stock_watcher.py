import asyncio
from datetime import datetime
from typing import Dict, Set
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from sqlalchemy import select
from bot.database.session import async_session
from bot.database.models import User, StockAlert
from bot.services.bunai_client import bunai_api
from bot.services.pricing import pricing_service
from bot.services.audit_logger import audit_logger
from bot.utils.i18n import t
from bot.utils.emojis import get_service_icon, parse_emojis, parse_keyboard

def get_product_icon_simple(name: str) -> str:
    """Asigna un icono representativo según el catálogo de servicios"""
    return get_service_icon(name, for_html=True)

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
        3. Notificar por mensaje privado a los clientes suscritos a alertas de restock en su idioma preferido.
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
                    name_lower = name.strip().lower()
                    if "test api" in name_lower or "test_api" in name_lower or str(pid).lower() in ("test", "test_api"):
                        continue

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

                        # Alerta al canal de logs del Owner
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
                            # Obtener idioma del usuario
                            u_stmt = select(User).where(User.telegram_id == alert.user_id)
                            u_res = await session.execute(u_stmt)
                            user = u_res.scalar_one_or_none()
                            lang = getattr(user, "language", "es") or "es"

                            dm_text = t(
                                "restock_alert_title",
                                lang,
                                product=name,
                                price=f"{user_price:.2f}",
                                stock=current_stock
                            )
                            dm_kb = parse_keyboard(InlineKeyboardMarkup([
                                [InlineKeyboardButton(t("btn_buy_now", lang), callback_data=f"product:view:{pid}:disponibles:1:0")],
                                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
                            ]))
                            try:
                                await client.send_message(
                                    chat_id=alert.user_id,
                                    text=parse_emojis(dm_text),
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
