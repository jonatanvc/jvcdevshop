import time
import httpx
from typing import Dict, Any, List, Optional
from bot.config import settings

class BunaiAPIClient:
    def __init__(self):
        self.base_url = settings.BUNAI_BASE_URL.rstrip("/")
        self.api_key = settings.BUNAI_API_KEY
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        # Caché en memoria para evitar saturar el rate limit de BunaiStore (60 req/min)
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 30  # 30 segundos de TTL
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=10.0,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
            )
        return self._client

    def _get_from_cache(self, key: str) -> Optional[Any]:
        if key in self._cache:
            data, expire_at = self._cache[key]
            if time.time() < expire_at:
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any, ttl: Optional[int] = None):
        ttl_val = ttl if ttl is not None else self._cache_ttl
        self._cache[key] = (data, time.time() + ttl_val)

    def invalidate_cache(self):
        """Limpia la caché en memoria cuando se solicita actualización forzada"""
        self._cache.clear()

    async def get_me(self) -> Dict[str, Any]:
        """Consulta el saldo real del desarrollador/owner en BunaiStore"""
        cached = self._get_from_cache("bunai_me")
        if cached is not None:
            return cached

        client = self._get_client()
        # 1. Probar endpoint /developer/me
        try:
            res_dev = await client.get(f"{self.base_url}/developer/me")
            if res_dev.status_code == 200:
                data = res_dev.json()
                self._set_cache("bunai_me", data, ttl=15)
                return data
        except Exception:
            pass

        # 2. Fallback a endpoint /me
        try:
            res = await client.get(f"{self.base_url}/me")
            if res.status_code == 200:
                data = res.json()
                self._set_cache("bunai_me", data, ttl=15)
                return data
        except Exception:
            pass

        return {"balance": 0.0, "api_spent": 0.0}

    async def get_products(self, view: str = "variants", limit: int = 100, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Obtiene la lista de productos/variantes disponibles"""
        cache_key = f"products_{view}_{limit}"
        if not force_refresh:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached

        url = f"{self.base_url}/products?view={view}&limit={limit}"
        try:
            client = self._get_client()
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                self._set_cache(cache_key, data)
                return data
            return []
        except Exception as e:
            print(f"[BunaiAPIClient Error] get_products: {e}")
            return []

    async def get_product_groups(self, include_variants: bool = True, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Obtiene las colecciones/grupos de productos con sus variantes"""
        cache_key = f"groups_{include_variants}"
        if not force_refresh:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached

        url = f"{self.base_url}/product-groups?include_variants={'true' if include_variants else 'false'}&limit=100"
        try:
            client = self._get_client()
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                self._set_cache(cache_key, data)
                return data
            return []
        except Exception as e:
            print(f"[BunaiAPIClient Error] get_product_groups: {e}")
            return []

    async def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el detalle completo de un producto específico"""
        cache_key = f"product_detail_{product_id}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{self.base_url}/products/{product_id}"
        try:
            client = self._get_client()
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                self._set_cache(cache_key, data, ttl=20)
                return data
            return None
        except Exception as e:
            print(f"[BunaiAPIClient Error] get_product: {e}")
            return None

    async def create_order(self, product_id: str, qty: int = 1) -> Dict[str, Any]:
        """Ejecuta la compra inmediata de un producto en BunaiStore"""
        url = f"{self.base_url}/orders"
        payload = {
            "product_id": product_id,
            "qty": qty,
            "include_after_note": True
        }
        try:
            client = self._get_client()
            res = await client.post(url, json=payload)
            data = res.json()
            if res.status_code in (200, 201):
                # Invalidar caché de saldo para reflejar el nuevo saldo tras la compra
                self._cache.pop("bunai_me", None)
                return {
                    "success": True,
                    "data": data.get("order", data),
                    "status_code": res.status_code
                }
            return {
                "success": False,
                "error": data.get("detail", data.get("message", "Error al procesar orden en proveedor")),
                "status_code": res.status_code
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error de conexión con el proveedor: {str(e)}",
                "status_code": 500
            }

bunai_api = BunaiAPIClient()
