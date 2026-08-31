import time
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import select
from bot.config import settings
from bot.database.models import Setting, CustomPricing
from bot.services.bunai_client import bunai_api

PAGE_SIZE = 8

class PricingService:
    def __init__(self):
        self._cached_catalog: List[Dict[str, Any]] = []
        self._last_fetch_time: float = 0.0
        self._cache_ttl: float = 30.0  # 30 segundos de caché

    async def get_global_margin(self, session) -> float:
        """Obtiene el margen global configurado en la base de datos"""
        stmt = select(Setting).where(Setting.key == "global_margin_percent")
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        if setting:
            try:
                return float(setting.value)
            except ValueError:
                pass
        return settings.DEFAULT_MARGIN_PERCENT

    async def set_global_margin(self, session, new_margin: float) -> None:
        """Actualiza el margen global de ganancia"""
        stmt = select(Setting).where(Setting.key == "global_margin_percent")
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        if not setting:
            setting = Setting(key="global_margin_percent", value=str(new_margin))
            session.add(setting)
        else:
            setting.value = str(new_margin)
        await session.commit()
        self.invalidate_cache()

    async def calculate_product_price(self, base_price: float, product_id: str, session) -> float:
        """
        Calcula el precio de venta final aplicando la Estrategia Escalonada Progresiva:
        1. Prioridad: Precios o márgenes personalizados en la BD (CustomPricing).
        2. Tramo 1 (Costo < $0.50): Multiplicador x7.0 (+600% margen).
        3. Tramo 2 (Costo $0.50 a $0.99): Multiplicador x4.0 (+300% margen).
        4. Tramo 3 (Costo $1.00 a $2.99): Multiplicador x2.5 (+150% margen).
        5. Tramo 4 (Costo >= $3.00): Multiplicador x2.0 (+100% margen / el doble).
        """
        stmt = select(CustomPricing).where(CustomPricing.product_id == product_id)
        result = await session.execute(stmt)
        custom = result.scalar_one_or_none()

        if custom:
            if custom.custom_price is not None:
                return round(float(custom.custom_price), 2)
            if custom.custom_margin is not None:
                margin = float(custom.custom_margin)
                return round(base_price * (1.0 + margin / 100.0), 2)

        # Regla Escalonada Progresiva Suave
        if base_price < 0.50:
            final_price = base_price * 7.0
        elif base_price < 1.00:
            final_price = base_price * 4.0
        elif base_price < 3.00:
            final_price = base_price * 2.5
        else:
            final_price = base_price * 2.0

        return round(final_price, 2)

    def calculate_adjusted_warranty(self, bunai_warranty_hours: int) -> int:
        """
        Ajusta la garantía al 50% de lo que ofrece BunaiStore
        para mantener un margen de seguridad de respaldo del 100% con el proveedor.
        """
        if not bunai_warranty_hours or bunai_warranty_hours <= 0:
            return 0
        return max(1, bunai_warranty_hours // 2)

    async def get_processed_catalog(
        self,
        session,
        filter_mode: str = "disponibles",
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Obtiene y procesa el catálogo de BunaiStore con los precios y garantías ajustadas
        """
        now = time.time()
        if force_refresh or (now - self._last_fetch_time > self._cache_ttl) or not self._cached_catalog:
            raw_products = await bunai_api.get_products(force_refresh=force_refresh)

            # Cargar configuraciones de precios personalizados
            stmt = select(CustomPricing)
            res = await session.execute(stmt)
            custom_map = {cp.product_id: cp for cp in res.scalars().all()}

            processed = []
            for p in raw_products:
                pid = p.get("id") or p.get("product_id")
                if not pid:
                    continue

                custom = custom_map.get(pid)
                if custom and custom.is_hidden:
                    continue

                base_price = float(p.get("price", 0.0))
                user_price = await self.calculate_product_price(base_price, pid, session)

                stock_count = int(p.get("stock_count", 0))
                infinite_stock = bool(p.get("infinite_stock", False))
                has_stock = infinite_stock or stock_count > 0
                has_promo = bool(p.get("has_promo", False))
                bunai_warranty = int(p.get("warranty_hours", 0))
                adjusted_warranty = self.calculate_adjusted_warranty(bunai_warranty)

                processed.append({
                    "product_id": pid,
                    "name": p.get("display_name") or p.get("name") or "Servicio Digital",
                    "base_price": base_price,
                    "user_price": user_price,
                    "stock_count": stock_count,
                    "infinite_stock": infinite_stock,
                    "has_stock": has_stock,
                    "has_promo": has_promo,
                    "warranty_hours": adjusted_warranty,
                    "bunai_warranty_hours": bunai_warranty,
                    "note": p.get("note", ""),
                    "promo_tiers": p.get("promo_tiers"),
                    "stock_type": p.get("stock_type", "auto")
                })

            self._cached_catalog = processed
            self._last_fetch_time = now

        # Aplicar filtros (disponibles, agotados, ofertas, todos)
        if filter_mode == "disponibles":
            return [p for p in self._cached_catalog if p["has_stock"]]
        elif filter_mode == "agotados":
            return [p for p in self._cached_catalog if not p["has_stock"]]
        elif filter_mode == "ofertas":
            return [p for p in self._cached_catalog if p["has_promo"]]
        elif filter_mode == "todos":
            return self._cached_catalog
        return [p for p in self._cached_catalog if p["has_stock"]]

    def paginate(
        self,
        items: List[Dict[str, Any]],
        page: int = 1,
        page_size: int = PAGE_SIZE
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """Pagina la lista de productos"""
        total_items = len(items)
        if total_items == 0:
            return [], 1, 1

        total_pages = (total_items + page_size - 1) // page_size
        current_page = max(1, min(page, total_pages))

        start = (current_page - 1) * page_size
        end = start + page_size

        return items[start:end], total_pages, current_page

    def invalidate_cache(self):
        self._cached_catalog = []
        self._last_fetch_time = 0.0

pricing_service = PricingService()
