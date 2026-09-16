import time
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import select
from bot.config import settings
from bot.database.models import Setting, CustomPricing
from bot.services.bunai_client import bunai_api
from bot.utils.formatters import adjust_warranty_in_name

PAGE_SIZE = 8

class PricingService:
    def __init__(self):
        self._cached_catalog: List[Dict[str, Any]] = []
        self._last_fetch_time: float = 0.0
        self._cache_ttl: float = 10.0  # 10 segundos de TTL para sincronización en tiempo real

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

    def calculate_price_from_custom(self, base_price: float, custom: Optional[CustomPricing] = None) -> float:
        """
        Calcula el precio de venta final aplicando la Estrategia Escalonada Progresiva Optimizada:
        1. Prioridad: Precios o márgenes personalizados en la BD (CustomPricing).
        2. Tramo Micro (Costo < $0.50): Multiplicador x3.5 (+250% margen). Piso mínimo: $0.35 USDT.
        3. Tramo Bajo (Costo $0.50 a $0.99): Multiplicador x2.4 (+140% margen).
        4. Tramo Medio (Costo $1.00 a $2.99): Multiplicador x1.75 (+75% margen).
        5. Tramo Estándar (Costo $3.00 a $7.99): Multiplicador x1.50 (+50% margen).
        6. Tramo Alto (Costo >= $8.00): Multiplicador x1.38 (+38% margen).

        Garantía VIP: Con el 20% de descuento del Plan Revendedor VIP (factor 0.80),
        todos los tramos garantizan margen de ganancia neto positivo para el Owner:
        - Micro: +180% neto
        - Bajo: +92% neto
        - Medio: +40% neto
        - Estándar: +20% neto
        - Alto: +10.4% neto
        """
        if custom:
            if custom.custom_price is not None:
                return round(float(custom.custom_price), 2)
            if custom.custom_margin is not None:
                margin = float(custom.custom_margin)
                return round(base_price * (1.0 + margin / 100.0), 2)

        # Regla Escalonada Progresiva Optimizada y Competitiva
        if base_price < 0.50:
            final_price = max(0.35, base_price * 3.5)
        elif base_price < 1.00:
            final_price = base_price * 2.4
        elif base_price < 3.00:
            final_price = base_price * 1.75
        elif base_price < 8.00:
            final_price = base_price * 1.50
        else:
            final_price = base_price * 1.38

        return round(final_price, 2)

    def calculate_vip_price(self, price: float) -> float:
        """Calcula el precio de venta VIP aplicando el descuento de revendedor configurado (ej: 20% OFF)"""
        discount_factor = 1.0 - (settings.VIP_DISCOUNT_PERCENT / 100.0)
        return round(price * discount_factor, 2)

    def calculate_virtual_number_price(self, cost_usd: float, is_vip: bool = False, is_owner: bool = False) -> float:
        """
        Calcula el precio de venta en USDT para números virtuales 5SIM:
        - Si es Owner: tarifa de costo neto de la API (0% margen).
        - Si es usuario regular: aplica la regla escalonada progresiva optimizada.
        - Piso mínimo de seguridad: $0.35 USDT (excepto owner).
        Si el usuario tiene membresía VIP activa, aplica 20% de descuento adicional.
        """
        if is_owner:
            return round(cost_usd, 2)

        if cost_usd < 0.50:
            price = max(0.35, cost_usd * 3.5)
        elif cost_usd < 1.00:
            price = cost_usd * 2.4
        elif cost_usd < 3.00:
            price = cost_usd * 1.75
        elif cost_usd < 8.00:
            price = cost_usd * 1.50
        else:
            price = cost_usd * 1.38

        final_price = round(price, 2)
        if is_vip:
            return self.calculate_vip_price(final_price)
        return final_price

    async def get_virtual_number_pricing(self, country: str, service_name: str) -> Optional[Dict[str, float]]:
        """
        Obtiene el costo real de 5SIM y calcula el precio de venta en USDT con el margen de ganancia.
        """
        from bot.services.fivesim_client import fivesim_api
        offers = await fivesim_api.get_service_offers(service_name)
        matched = next((o for o in offers if o["country"].lower() == country.lower()), None)
        if not matched:
            raw = await fivesim_api.get_raw_prices(country=country, product=service_name)
            cost = 0.0
            if isinstance(raw, dict):
                c_data = raw.get(country, raw).get(service_name, raw.get(country, raw))
                if isinstance(c_data, dict):
                    for op, info in c_data.items():
                        if isinstance(info, dict) and int(info.get("count", 0)) > 0:
                            c = float(info.get("cost", 0.0))
                            if cost == 0.0 or c < cost:
                                cost = c
            if cost <= 0.0:
                return None
            cost_usd = cost
        else:
            cost_usd = matched["cost_usd"]

        retail_price_usdt = self.calculate_virtual_number_price(cost_usd, is_vip=False, is_owner=False)
        vip_price_usdt = self.calculate_virtual_number_price(cost_usd, is_vip=True, is_owner=False)

        return {
            "fivesim_cost_usd": cost_usd,
            "retail_price_usdt": retail_price_usdt,
            "vip_price_usdt": vip_price_usdt,
        }

    async def calculate_product_price(
        self,
        base_price: float,
        product_id: str,
        session,
        custom: Optional[CustomPricing] = None,
        is_vip: bool = False
    ) -> float:
        """Consulta CustomPricing en BD si no se proporcionó y calcula el precio final (con soporte VIP)"""
        if custom is None and session is not None:
            stmt = select(CustomPricing).where(CustomPricing.product_id == product_id)
            result = await session.execute(stmt)
            custom = result.scalar_one_or_none()
        price = self.calculate_price_from_custom(base_price, custom)
        if is_vip:
            return self.calculate_vip_price(price)
        return price

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
        Obtiene y procesa el catálogo de BunaiStore con precios y filtros estrictos.
        - disponibles: Productos con stock > 0 o infinitos.
        - agotados: Productos con stock == 0 y no infinitos.
        - ofertas: Productos con promo/descuento que además tengan stock.
        - todos: Todos los productos activos.
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
                pid = str(p.get("product_id") or p.get("variant_id") or p.get("id") or "").strip()
                if not pid:
                    continue

                name = adjust_warranty_in_name(p.get("display_name") or p.get("name") or "Servicio Digital")
                name_lower = name.strip().lower()
                # Excluir productos de prueba del proveedor
                if "test api" in name_lower or "test_api" in name_lower or str(pid).lower() in ("test", "test_api"):
                    continue

                custom = custom_map.get(pid)
                if custom and custom.is_hidden:
                    continue

                base_price = float(p.get("price", 0.0))
                user_price = self.calculate_price_from_custom(base_price, custom)

                stock_raw = p.get("stock_count", 0)
                try:
                    stock_count = int(stock_raw)
                except (ValueError, TypeError):
                    stock_count = 0

                infinite_stock = bool(p.get("infinite_stock", False))
                # Tiene stock estrictamente si infinite_stock es True o stock_count > 0
                has_stock = infinite_stock or (stock_count > 0)
                has_promo = bool(p.get("has_promo", False))
                bunai_warranty = int(p.get("warranty_hours", 0))
                adjusted_warranty = self.calculate_adjusted_warranty(bunai_warranty)

                processed.append({
                    "product_id": pid,
                    "name": name,
                    "price": base_price,
                    "base_price": base_price,
                    "user_price": user_price,
                    "vip_price": self.calculate_vip_price(user_price),
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

        # Aplicar filtros estrictos
        if filter_mode == "disponibles":
            return [p for p in self._cached_catalog if p["has_stock"] is True]
        elif filter_mode == "agotados":
            return [p for p in self._cached_catalog if p["has_stock"] is False]
        elif filter_mode == "ofertas":
            return [p for p in self._cached_catalog if p["has_promo"] is True and p["has_stock"] is True]
        elif filter_mode == "todos":
            return self._cached_catalog
        return [p for p in self._cached_catalog if p["has_stock"] is True]

    async def get_category_counts(self, session) -> Dict[str, int]:
        """Obtiene el conteo exacto de productos en cada categoría"""
        all_prods = await self.get_processed_catalog(session, filter_mode="todos", force_refresh=False)
        disp_count = sum(1 for p in all_prods if p["has_stock"] is True)
        agot_count = sum(1 for p in all_prods if p["has_stock"] is False)
        ofer_count = sum(1 for p in all_prods if p["has_promo"] is True and p["has_stock"] is True)
        return {
            "disponibles": disp_count,
            "agotados": agot_count,
            "ofertas": ofer_count,
            "todos": len(all_prods)
        }

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
