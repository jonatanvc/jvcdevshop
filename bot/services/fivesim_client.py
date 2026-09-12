import time
import asyncio
from typing import Dict, Any, Optional, List
import httpx
from bot.config import settings

class FiveSimClient:
    """
    Cliente asíncrono para la API de 5SIM.net (v1).
    Proporciona métodos para consultar saldo, precios, comprar números temporales
    para activación por SMS OTP, verificar recepción de código y cancelar órdenes.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._prices_cache: Dict[str, Any] = {}
        self._prices_cache_ts: float = 0.0
        self._cache_ttl: float = 30.0  # 30 segundos de caché para precios y stock

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Accept": "application/json"}
            if settings.FIVESIM_API_KEY and settings.FIVESIM_API_KEY.strip():
                headers["Authorization"] = f"Bearer {settings.FIVESIM_API_KEY.strip()}"

            base_url = settings.FIVESIM_BASE_URL.replace("/v1", "").rstrip("/") or "https://5sim.net"
            self._client = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(15.0, connect=8.0),
                headers=headers
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def is_configured(self) -> bool:
        """Verifica si la API Key de 5SIM está configurada"""
        return bool(settings.FIVESIM_API_KEY and settings.FIVESIM_API_KEY.strip())

    async def get_profile(self) -> Dict[str, Any]:
        """
        Consulta el perfil y saldo disponible en la cuenta de 5SIM.
        Endpoint: GET /v1/user/profile
        Retorna: {"id": 1, "email": "...", "balance": 15.50, "rating": 96}
        """
        if not self.is_configured():
            return {"error": "API Key de 5SIM no configurada.", "balance": 0.0}

        client = self._get_client()
        try:
            resp = await client.get("/v1/user/profile")
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}: {resp.text}", "balance": 0.0}
        except Exception as e:
            return {"error": str(e), "balance": 0.0}

    async def get_raw_prices(self, country: Optional[str] = None, product: Optional[str] = None) -> Dict[str, Any]:
        """
        Consulta precios y cantidad de números en stock.
        Endpoint: GET /v1/guest/prices?country={country}&product={product}
        """
        now = time.time()
        cache_key = f"{country or 'all'}:{product or 'all'}"
        if cache_key in self._prices_cache and (now - self._prices_cache_ts) < self._cache_ttl:
            return self._prices_cache[cache_key]

        client = self._get_client()
        params = {}
        if country:
            params["country"] = country
        if product:
            params["product"] = product

        try:
            resp = await client.get("/v1/guest/prices", params=params)
            if resp.status_code == 200:
                data = resp.json()
                self._prices_cache[cache_key] = data
                self._prices_cache_ts = now
                return data
            return {}
        except Exception as e:
            print(f"[FiveSimClient.get_raw_prices Error]: {e}")
            return self._prices_cache.get(cache_key, {})

    async def get_service_offers(self, product: str) -> List[Dict[str, Any]]:
        """
        Obtiene las mejores ofertas disponibles por país para un servicio específico (ej: whatsapp).
        Calcula el costo más bajo y el stock disponible para cada país.
        Retorna lista ordenada por disponibilidad y precio.
        """
        prices_data = await self.get_raw_prices(product=product)
        offers = []

        if not isinstance(prices_data, dict):
            return offers

        # 5SIM puede devolver {"whatsapp": {"country": {"operator": {...}}}}
        # o {"country": {"whatsapp": {"operator": {...}}}}
        # o {"country": {"operator": {...}}}
        countries_dict = prices_data.get(product, prices_data)
        if not isinstance(countries_dict, dict):
            countries_dict = prices_data

        for country_key, country_data in countries_dict.items():
            if not isinstance(country_data, dict):
                continue

            # Si country_data contiene el producto como subclave
            if product in country_data and isinstance(country_data[product], dict):
                ops_dict = country_data[product]
            else:
                ops_dict = country_data

            best_operator = "any"
            min_cost = float("inf")
            total_stock = 0

            for op_name, op_info in ops_dict.items():
                if not isinstance(op_info, dict):
                    continue
                count = int(op_info.get("count", 0))
                cost = float(op_info.get("cost", 0.0))
                total_stock += count

                if count > 0 and cost < min_cost:
                    min_cost = cost
                    best_operator = op_name

            if total_stock > 0 and min_cost < float("inf"):
                offers.append({
                    "country": country_key,
                    "operator": best_operator,
                    "product": product,
                    "cost_usd": min_cost,
                    "stock": total_stock
                })

        # Ordenar: primero países con menor precio y más stock
        offers.sort(key=lambda x: (x["cost_usd"], -x["stock"]))
        return offers

    async def buy_activation(self, country: str, operator: str, product: str) -> Dict[str, Any]:
        """
        Compra un número temporal para recibir SMS de activación.
        Endpoint: GET /v1/user/buy/activation/{country}/{operator}/{product}
        Retorna:
            Success: {"id": 1234, "phone": "+123...", "operator": "...", "status": "PENDING", ...}
            Error: {"error": "no free phones" o mensaje de error}
        """
        if not self.is_configured():
            return {"error": "La API Key de 5SIM no está configurada en el bot."}

        client = self._get_client()
        url = f"/v1/user/buy/activation/{country}/{operator}/{product}"

        try:
            resp = await client.get(url)
            text_body = resp.text.strip()

            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception:
                    # En algunos casos 5sim responde con texto plano de error
                    return {"error": text_body}

            if "no free phones" in text_body.lower():
                return {"error": "Sin números disponibles en este momento para este país y operador. Intenta con otro país."}
            elif "not enough user balance" in text_body.lower():
                return {"error": "Saldo insuficiente en el proveedor 5SIM. Contacta al administrador."}
            elif "bad country" in text_body.lower() or "bad service" in text_body.lower():
                return {"error": f"Servicio o país inválido: {text_body}"}
            else:
                return {"error": f"Error del proveedor 5SIM: {text_body or resp.status_code}"}

        except httpx.TimeoutException:
            return {"error": "El servidor de 5SIM tardó demasiado en responder. Intenta de nuevo."}
        except Exception as e:
            return {"error": f"Error de conexión con 5SIM: {str(e)}"}

    async def check_order(self, order_id: int) -> Dict[str, Any]:
        """
        Consulta el estado de una orden y los SMS recibidos.
        Endpoint: GET /v1/user/check/{order_id}
        """
        if not self.is_configured():
            return {"error": "API Key no configurada."}

        client = self._get_client()
        try:
            resp = await client.get(f"/v1/user/check/{order_id}")
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"error": str(e)}

    async def finish_order(self, order_id: int) -> Dict[str, Any]:
        """
        Finaliza una orden completada con éxito tras recibir el SMS.
        Endpoint: GET /v1/user/finish/{order_id}
        """
        if not self.is_configured():
            return {"error": "API Key no configurada."}

        client = self._get_client()
        try:
            resp = await client.get(f"/v1/user/finish/{order_id}")
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception:
                    return {"status": "FINISHED"}
            return {"error": resp.text}
        except Exception as e:
            return {"error": str(e)}

    async def cancel_order(self, order_id: int) -> Dict[str, Any]:
        """
        Cancela una orden si el SMS no ha llegado aún y libera el saldo.
        Endpoint: GET /v1/user/cancel/{order_id}
        """
        if not self.is_configured():
            return {"error": "API Key no configurada."}

        client = self._get_client()
        try:
            resp = await client.get(f"/v1/user/cancel/{order_id}")
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception:
                    return {"status": "CANCELED"}
            return {"error": resp.text}
        except Exception as e:
            return {"error": str(e)}

    async def ban_order(self, order_id: int) -> Dict[str, Any]:
        """
        Reporta un número como inválido o ya registrado para solicitar otro.
        Endpoint: GET /v1/user/ban/{order_id}
        """
        if not self.is_configured():
            return {"error": "API Key no configurada."}

        client = self._get_client()
        try:
            resp = await client.get(f"/v1/user/ban/{order_id}")
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception:
                    return {"status": "BANNED"}
            return {"error": resp.text}
        except Exception as e:
            return {"error": str(e)}

# Instancia global singleton reutilizable
fivesim_api = FiveSimClient()
