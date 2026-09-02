from decimal import Decimal
from typing import Dict, Any, List, Optional
import httpx
from bot.config import settings

def clean_hex(val: Any) -> str:
    """Normaliza cualquier valor (bytes, HexBytes, int, str) a una cadena hexadecimal limpia sin prefijo 0x y en minúsculas."""
    if val is None:
        return ""
    if isinstance(val, (bytes, bytearray)):
        h = val.hex()
    elif hasattr(val, "hex") and callable(val.hex):
        try:
            h = val.hex()
        except TypeError:
            h = str(val)
    else:
        h = str(val)
    h = h.lower().strip()
    if h.startswith("0x"):
        h = h[2:]
    return h

class BSCValidator:
    def __init__(self):
        self.rpc_endpoints = settings.rpc_endpoints
        self.usdt_contract = clean_hex(settings.USDT_CONTRACT_ADDRESS)
        self.admin_wallet = clean_hex(settings.ADMIN_WALLET_BSC)
        self.min_confirmations = settings.MIN_BLOCK_CONFIRMATIONS
        # Transfer(address,address,uint256) topic sin 0x
        self.transfer_topic = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

    async def _query_rpc_httpx(self, rpc_url: str, client: httpx.AsyncClient, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Consulta el recibo de la transacción mediante JSON-RPC HTTP asíncrono directo."""
        try:
            resp = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_getTransactionReceipt",
                    "params": [tx_hash]
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result")
        except Exception:
            pass
        return None

    async def _get_current_block_httpx(self, rpc_url: str, client: httpx.AsyncClient) -> int:
        """Obtiene el número de bloque más reciente de la red BSC."""
        try:
            resp = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_blockNumber",
                    "params": []
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                res = data.get("result")
                if res:
                    return int(clean_hex(res), 16)
        except Exception:
            pass
        return 0

    async def verify_deposit(self, tx_hash: str, expected_amount: float) -> Dict[str, Any]:
        """
        Verifica on-chain con tolerancia a fallos (Multi-RPC Fallback) que:
        1. La transacción exista y sea exitosa (status = 1).
        2. Tenga al menos N confirmaciones de bloque (Anti-Reorganización de Red).
        3. El contrato sea USDT oficial en BSC (0x55d398326f99059fF775485246999027B3197955).
        4. El receptor sea exactamente la billetera del Administrador.
        5. El monto sea mayor o igual al monto exacto requerido.
        """
        tx_hash = tx_hash.strip()
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash

        if len(tx_hash) != 66:
            return {
                "success": False,
                "error": "El formato del Hash/TxID es inválido (debe tener 66 caracteres comenzando con 0x)."
            }

        last_error = "No se pudo conectar a ningún nodo RPC de BSC."

        async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            for rpc in self.rpc_endpoints:
                try:
                    # 1. Obtener recibo de la transacción
                    receipt = await self._query_rpc_httpx(rpc, client, tx_hash)
                    if not receipt:
                        continue

                    # 2. Verificar estado de la transacción (1 = éxito, 0 = fallida)
                    raw_status = receipt.get("status")
                    clean_status = clean_hex(raw_status)
                    if clean_status not in ("1", "01") and raw_status != 1:
                        return {
                            "success": False,
                            "error": "La transacción fue revertida o falló en la blockchain."
                        }

                    # 3. Validar confirmaciones de bloque
                    raw_block = receipt.get("blockNumber")
                    tx_block = int(clean_hex(raw_block), 16) if raw_block else 0
                    if tx_block > 0:
                        current_block = await self._get_current_block_httpx(rpc, client)
                        if current_block > 0:
                            confirmations = current_block - tx_block
                            if confirmations < self.min_confirmations:
                                return {
                                    "success": False,
                                    "error": f"La transacción tiene solo {confirmations} confirmaciones. Se requieren al menos {self.min_confirmations} confirmaciones de seguridad (~10 segundos). Intenta de nuevo en un instante."
                                }

                    # 4. Buscar el evento Transfer en los logs de la transacción
                    found_usdt_transfer = False
                    transferred_amount = Decimal("0")

                    logs = receipt.get("logs", [])
                    for log in logs:
                        contract_address = clean_hex(log.get("address", ""))
                        topics = log.get("topics", [])
                        if not topics:
                            continue

                        topic_0 = clean_hex(topics[0])

                        # Validar si corresponde al contrato oficial de USDT y evento Transfer
                        if contract_address == self.usdt_contract and topic_0 == self.transfer_topic:
                            if len(topics) >= 3:
                                # topic_2 contiene la dirección de destino con padding de 32 bytes (64 hex chars)
                                to_hex = clean_hex(topics[2])
                                recipient = to_hex[-40:]  # Extraer los últimos 20 bytes (40 hex chars)

                                if recipient == self.admin_wallet:
                                    data_hex = clean_hex(log.get("data", "0"))
                                    raw_value = int(data_hex, 16) if data_hex else 0
                                    # USDT en BSC (BEP-20) tiene 18 decimales
                                    transferred_amount = Decimal(raw_value) / Decimal(10**18)
                                    found_usdt_transfer = True
                                    break

                    if not found_usdt_transfer:
                        return {
                            "success": False,
                            "error": "No se encontró una transferencia de USDT BEP-20 hacia la billetera del administrador en esta transacción."
                        }

                    # 5. Validar monto transferido con tolerancia a redondeo
                    exp_dec = Decimal(str(expected_amount))
                    if transferred_amount < (exp_dec - Decimal("0.0001")):
                        return {
                            "success": False,
                            "error": f"El monto transferido ({transferred_amount:.4f} USDT) es menor al monto requerido ({exp_dec:.4f} USDT)."
                        }

                    return {
                        "success": True,
                        "amount": float(transferred_amount),
                        "tx_hash": tx_hash,
                        "block_number": tx_block
                    }

                except Exception as e:
                    last_error = str(e)
                    continue

        return {
            "success": False,
            "error": f"Error temporal al consultar los nodos RPC de BSC: {last_error}"
        }

bsc_validator = BSCValidator()
