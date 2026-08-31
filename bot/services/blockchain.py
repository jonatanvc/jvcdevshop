from decimal import Decimal
from typing import Dict, Any, List
from web3 import Web3
from bot.config import settings

class BSCValidator:
    def __init__(self):
        self.rpc_endpoints = settings.rpc_endpoints
        self.usdt_contract = settings.USDT_CONTRACT_ADDRESS.lower()
        self.admin_wallet = settings.ADMIN_WALLET_BSC.lower()
        self.min_confirmations = settings.MIN_BLOCK_CONFIRMATIONS
        # Transfer(address,address,uint256) topic
        self.transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

    def _get_web3_instances(self) -> List[Web3]:
        """Crea instancias de Web3 para todos los endpoints configurados (Multi-RPC Fallback)"""
        instances = []
        for rpc in self.rpc_endpoints:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 6}))
                instances.append(w3)
            except Exception:
                continue
        return instances

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

        w3_instances = self._get_web3_instances()
        if not w3_instances:
            return {
                "success": False,
                "error": "Error interno: No hay nodos RPC de BSC disponibles en este momento."
            }

        last_error = "No se pudo conectar a ningún nodo RPC de BSC."

        # Intentar con cada nodo RPC en orden hasta que uno responda exitosamente
        for w3 in w3_instances:
            try:
                # 1. Obtener recibo de la transacción
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                if not receipt:
                    return {
                        "success": False,
                        "error": "La transacción aún no se encuentra confirmada en la red BSC. Espera unos segundos e intenta nuevamente."
                    }

                # 2. Verificar estado de la transacción (1 = éxito, 0 = fallida)
                if receipt.get("status") != 1:
                    return {
                        "success": False,
                        "error": "La transacción fue revertida o falló en la blockchain."
                    }

                # 3. Validar confirmaciones de bloque (Anti-Reorg)
                tx_block = receipt.get("blockNumber")
                if tx_block:
                    current_block = w3.eth.block_number
                    confirmations = current_block - tx_block
                    if confirmations < self.min_confirmations:
                        return {
                            "success": False,
                            "error": f"La transacción tiene solo {confirmations} confirmaciones. Se requieren al menos {self.min_confirmations} confirmaciones de seguridad (~10 segundos). Intenta de nuevo en un instante."
                        }

                # 4. Buscar el evento Transfer en los logs
                found_usdt_transfer = False
                transferred_amount = Decimal("0")

                for log in receipt.get("logs", []):
                    contract_address = log.get("address", "").lower()
                    topics = log.get("topics", [])

                    if not topics:
                        continue

                    topic_0 = topics[0].hex() if hasattr(topics[0], "hex") else str(topics[0])

                    # Verificar contrato USDT oficial
                    if contract_address == self.usdt_contract and topic_0.lower() == self.transfer_topic.lower():
                        if len(topics) >= 3:
                            to_hex = topics[2].hex() if hasattr(topics[2], "hex") else str(topics[2])
                            recipient = "0x" + to_hex[-40:].lower()

                            if recipient == self.admin_wallet:
                                data_hex = log.get("data", "0x")
                                data_str = data_hex.hex() if hasattr(data_hex, "hex") else str(data_hex)
                                raw_value = int(data_str, 16)
                                transferred_amount = Decimal(raw_value) / Decimal(10**18)
                                found_usdt_transfer = True
                                break

                if not found_usdt_transfer:
                    return {
                        "success": False,
                        "error": "No se encontró una transferencia de USDT BEP-20 hacia la billetera del administrador en esta transacción."
                    }

                # 5. Validar monto transferido con tolerancia
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
                continue  # Intentar con el siguiente nodo RPC

        return {
            "success": False,
            "error": f"Error temporal al consultar los nodos RPC de BSC: {last_error}"
        }

bsc_validator = BSCValidator()
