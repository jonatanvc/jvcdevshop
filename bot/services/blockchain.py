from decimal import Decimal
from typing import Dict, Any, Optional
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


def parse_incoming_usdt_transfer(log: Dict[str, Any], usdt_contract: str, admin_wallet: str) -> Optional[Dict[str, Any]]:
    topics = log.get("topics", [])
    if clean_hex(log.get("address")) != clean_hex(usdt_contract):
        return None
    if len(topics) < 3 or clean_hex(topics[0]) != "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
        return None

    recipient = clean_hex(topics[2])
    wallet = clean_hex(admin_wallet)
    if len(recipient) != 64 or recipient[-40:] != wallet:
        return None

    data_hex = clean_hex(log.get("data", ""))
    tx_hash = str(log.get("transactionHash") or "").lower()
    raw_block = log.get("blockNumber")
    if not data_hex or not tx_hash or raw_block is None:
        return None

    return {
        "tx_hash": tx_hash if tx_hash.startswith("0x") else f"0x{tx_hash}",
        "block_number": int(clean_hex(raw_block), 16),
        "log_index": int(clean_hex(log.get("logIndex", "0")), 16),
        "amount": Decimal(int(data_hex, 16)) / Decimal(10**18),
    }

class BSCValidator:
    def __init__(self):
        self.rpc_endpoints = settings.rpc_endpoints
        self.usdt_contract = clean_hex(settings.USDT_CONTRACT_ADDRESS)
        self.admin_wallet = clean_hex(settings.ADMIN_WALLET_BSC)
        self.min_confirmations = settings.MIN_BLOCK_CONFIRMATIONS
        # Transfer(address,address,uint256) topic sin 0x
        self.transfer_topic = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

    def _sum_admin_usdt_transfers(self, logs: list) -> tuple[bool, Decimal]:
        found_transfer = False
        total_amount = Decimal("0")
        for log in logs:
            if clean_hex(log.get("address", "")) != self.usdt_contract:
                continue
            topics = log.get("topics", [])
            if len(topics) < 3 or clean_hex(topics[0]) != self.transfer_topic:
                continue
            recipient_topic = clean_hex(topics[2])
            if len(recipient_topic) != 64 or recipient_topic[-40:] != self.admin_wallet:
                continue
            data_hex = clean_hex(log.get("data", "0"))
            total_amount += Decimal(int(data_hex, 16) if data_hex else 0) / Decimal(10**18)
            found_transfer = True
        return found_transfer, total_amount

    @staticmethod
    async def _rpc_call(rpc_url: str, client: httpx.AsyncClient, method: str, params: list) -> Any:
        response = await client.post(
            rpc_url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(payload["error"].get("message", "BSC RPC request failed"))
        return payload.get("result")

    async def _scan_rpc_range(
        self,
        rpc_url: str,
        client: httpx.AsyncClient,
        start_block: int
    ) -> tuple[int, list[Dict[str, Any]]]:
        raw_head = await self._rpc_call(rpc_url, client, "eth_blockNumber", [])
        latest_block = int(clean_hex(raw_head), 16)
        confirmed_block = latest_block - self.min_confirmations + 1
        if confirmed_block < start_block:
            return confirmed_block, []

        events = []
        cursor = start_block
        recipient_topic = "0x" + ("0" * 24) + self.admin_wallet
        while cursor <= confirmed_block:
            range_end = min(confirmed_block, cursor + 499)
            logs = await self._rpc_call(
                rpc_url,
                client,
                "eth_getLogs",
                [{
                    "address": "0x" + self.usdt_contract,
                    "fromBlock": hex(cursor),
                    "toBlock": hex(range_end),
                    "topics": ["0x" + self.transfer_topic, None, recipient_topic],
                }]
            )
            for log in logs or []:
                event = parse_incoming_usdt_transfer(log, self.usdt_contract, self.admin_wallet)
                if event:
                    events.append(event)
            cursor = range_end + 1

        block_numbers = sorted({event["block_number"] for event in events})
        timestamps = {}
        for block_number in block_numbers:
            block = await self._rpc_call(
                rpc_url, client, "eth_getBlockByNumber", [hex(block_number), False]
            )
            if not block or not block.get("timestamp"):
                raise RuntimeError(f"No se pudo obtener el timestamp del bloque {block_number}")
            timestamps[block_number] = int(clean_hex(block["timestamp"]), 16)

        for event in events:
            event["timestamp"] = timestamps[event["block_number"]]
        events.sort(key=lambda event: (event["block_number"], event["log_index"]))
        return confirmed_block, events

    async def get_confirmed_block_number(self) -> int:
        """Returns the highest BSC block with the configured confirmation count."""
        last_error = "No se pudo consultar ningún nodo RPC de BSC."
        async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": "JVCDevStoreBot/1.0"}) as client:
            for rpc_url in self.rpc_endpoints:
                try:
                    raw_head = await self._rpc_call(rpc_url, client, "eth_blockNumber", [])
                    return int(clean_hex(raw_head), 16) - self.min_confirmations + 1
                except Exception as exc:
                    last_error = str(exc)
        raise RuntimeError(f"No se pudo determinar el bloque confirmado de BSC: {last_error}")

    async def scan_incoming_transfers(self, start_block: int) -> tuple[int, list[Dict[str, Any]]]:
        """Lee eventos USDT entrantes hasta el último bloque con confirmaciones suficientes."""
        last_error = "No se pudo consultar ningún nodo RPC de BSC."
        async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": "JVCDevStoreBot/1.0"}) as client:
            for rpc_url in self.rpc_endpoints:
                try:
                    return await self._scan_rpc_range(rpc_url, client, start_block)
                except Exception as exc:
                    last_error = str(exc)
        raise RuntimeError(f"Error al escanear transferencias USDT en BSC: {last_error}")

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
                    if tx_block <= 0:
                        last_error = "El recibo no contiene un bloque válido."
                        continue

                    current_block = await self._get_current_block_httpx(rpc, client)
                    if current_block <= 0 or current_block < tx_block:
                        last_error = "No se pudo verificar el bloque actual en este nodo RPC."
                        continue

                    confirmations = current_block - tx_block + 1
                    if confirmations < self.min_confirmations:
                        return {
                            "success": False,
                            "error": f"La transacción tiene solo {confirmations} confirmaciones. Se requieren al menos {self.min_confirmations}. Intenta de nuevo en un instante."
                        }

                    # 4. Buscar el evento Transfer en los logs de la transacción
                    found_usdt_transfer, transferred_amount = self._sum_admin_usdt_transfers(
                        receipt.get("logs", [])
                    )

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
