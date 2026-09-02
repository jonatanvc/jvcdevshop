from typing import Optional
from pyrogram import Client
from pyrogram.enums import ParseMode
from bot.config import settings
from bot.utils.time_utils import get_now_str
from bot.utils.emojis import (
    EMOJI_SHOPPING, EMOJI_USER, EMOJI_BOX, EMOJI_MONEY, EMOJI_CARD,
    EMOJI_KEY, EMOJI_TARGET, EMOJI_HOURGLASS, EMOJI_CLOCK, EMOJI_CROSS,
    EMOJI_CHECK, EMOJI_LINK, EMOJI_BROADCAST, EMOJI_SPARKLES, EMOJI_WARN,
    EMOJI_INBOX, EMOJI_BAR_CHART, EMOJI_NAME_TAG, parse_emojis
)

class AuditLogger:
    def __init__(self):
        self.log_group_id = settings.LOG_GROUP_ID

    async def _send_log(self, client: Client, text: str) -> Optional[int]:
        """Envía un mensaje de auditoría al grupo privado configurado y devuelve su ID"""
        if not self.log_group_id or self.log_group_id == 0:
            return None
        try:
            if text:
                text = parse_emojis(text)
            msg = await client.send_message(
                chat_id=self.log_group_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            return msg.id
        except Exception as e:
            print(f"[AuditLogger Error] No se pudo enviar log a {self.log_group_id}: {e}")
            return None

    async def log_purchase(
        self,
        client: Client,
        user_id: int,
        username: Optional[str],
        first_name: str,
        order_id: int,
        product_name: str,
        paid_price: float,
        remaining_balance: float,
        provider_order_id: Optional[str],
        delivered_items: str
    ):
        """Registra una compra exitosa en el canal de auditoría con la hora local exacta"""
        user_mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        now = get_now_str("%Y-%m-%d %H:%M:%S")

        msg = (
            f"{EMOJI_SHOPPING} <b>NUEVA COMPRA REALIZADA #ORD_{order_id}</b>\n\n"
            f"{EMOJI_USER} <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"{EMOJI_NAME_TAG} <b>Nombre:</b> {first_name}\n"
            f"{EMOJI_BOX} <b>Producto:</b> <code>{product_name}</code>\n"
            f"{EMOJI_MONEY} <b>Precio Pagado:</b> <code>${paid_price:.2f} USDT</code>\n"
            f"{EMOJI_BAR_CHART} <b>Saldo Restante Usuario:</b> <code>${remaining_balance:.2f} USDT</code>\n"
            f"🆔 <b>ID Orden Proveedor:</b> <code>{provider_order_id or 'N/A'}</code>\n"
            f"{EMOJI_CLOCK} <b>Fecha:</b> <code>{now}</code>\n\n"
            f"{EMOJI_KEY} <b>DATOS / CUENTAS ENTREGADAS:</b>\n"
            f"<pre>{delivered_items}</pre>"
        )
        await self._send_log(client, msg)

    async def log_deposit_request(
        self,
        client: Client,
        user_id: int,
        username: Optional[str],
        first_name: str,
        base_amount: float,
        exact_amount: float
    ) -> Optional[int]:
        """Registra una nueva solicitud de depósito y retorna el ID del mensaje para editarlo si cambia de estado"""
        user_mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        now = get_now_str("%Y-%m-%d %H:%M:%S")

        msg = (
            f"{EMOJI_INBOX} <b>NUEVA SOLICITUD DE DEPÓSITO</b>\n\n"
            f"{EMOJI_USER} <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"💵 <b>Monto Base Solicitado:</b> <code>${base_amount:.2f} USDT</code>\n"
            f"{EMOJI_TARGET} <b>Monto Exacto Asignado:</b> <code>{exact_amount:.4f} USDT</code>\n"
            f"{EMOJI_HOURGLASS} <b>Vigencia:</b> 30 minutos\n"
            f"{EMOJI_CLOCK} <b>Fecha:</b> <code>{now}</code>"
        )
        return await self._send_log(client, msg)

    async def log_deposit_cancelled(
        self,
        client: Client,
        user_id: int,
        username: Optional[str],
        first_name: str,
        amount_cancelled: float,
        deposit_id: int,
        log_message_id: Optional[int] = None
    ):
        """Edita el mismo mensaje original de la solicitud de depósito en el canal de logs indicando que fue cancelada"""
        user_mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        now = get_now_str("%Y-%m-%d %H:%M:%S")

        msg = (
            f"{EMOJI_CROSS} <b>SOLICITUD DE DEPÓSITO CANCELADA</b>\n\n"
            f"{EMOJI_USER} <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"{EMOJI_MONEY} <b>Monto Cancelado:</b> <code>${amount_cancelled:.4f} USDT</code>\n"
            f"🆔 <b>ID Depósito:</b> <code>DEP_{deposit_id}</code>\n"
            f"{EMOJI_CLOCK} <b>Cancelado:</b> <code>{now}</code>"
        )

        if not self.log_group_id or self.log_group_id == 0:
            return

        if log_message_id:
            try:
                await client.edit_message_text(
                    chat_id=self.log_group_id,
                    message_id=log_message_id,
                    text=msg,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                return
            except Exception as e:
                print(f"[AuditLogger edit cancelled error]: {e}")

        # Fallback si no se pudo editar el mensaje previo
        await self._send_log(client, msg)

    async def log_deposit_confirmed(
        self,
        client: Client,
        user_id: int,
        username: Optional[str],
        first_name: str,
        amount: float,
        tx_hash: str,
        new_balance: float,
        deposit_id: Optional[int] = None,
        log_message_id: Optional[int] = None
    ):
        """Edita el mismo mensaje original de la solicitud en el canal de logs indicando confirmación en blockchain"""
        user_mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        bsc_link = f"https://bscscan.com/tx/{tx_hash}"
        now = get_now_str("%Y-%m-%d %H:%M:%S")

        msg = (
            f"{EMOJI_CHECK} <b>DEPÓSITO CONFIRMADO EN BLOCKCHAIN</b>\n\n"
            f"{EMOJI_USER} <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"{EMOJI_MONEY} <b>Monto Acreditado:</b> <code>+${amount:.4f} USDT</code>\n"
            f"{EMOJI_CARD} <b>Nuevo Saldo Usuario:</b> <code>${new_balance:.4f} USDT</code>\n"
            f"{EMOJI_LINK} <b>Hash / TxID:</b> <a href='{bsc_link}'>{tx_hash[:10]}...{tx_hash[-8:]}</a>\n"
            f"🆔 <b>ID Depósito:</b> <code>DEP_{deposit_id or 'N/A'}</code>\n"
            f"{EMOJI_CLOCK} <b>Confirmado:</b> <code>{now}</code>"
        )

        if not self.log_group_id or self.log_group_id == 0:
            return

        if log_message_id:
            try:
                await client.edit_message_text(
                    chat_id=self.log_group_id,
                    message_id=log_message_id,
                    text=msg,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                return
            except Exception as e:
                print(f"[AuditLogger edit confirmed error]: {e}")

        # Fallback
        await self._send_log(client, msg)

    async def log_restock_alert(
        self,
        client: Client,
        product_name: str,
        icon: str,
        added_stock: int,
        total_stock: int,
        cost_price: float,
        user_price: float
    ):
        """Envía alerta al canal de logs cuando el proveedor añade stock"""
        msg = (
            f"{EMOJI_BROADCAST} <b>¡{added_stock} stock añadido a {product_name}!</b>\n\n"
            f"{icon} <b>{product_name}</b> - <code>{user_price:.2f} USDT</code> (Stock: {total_stock})\n"
            f"{EMOJI_MONEY} <b>Costo Proveedor:</b> <code>${cost_price:.2f} USD</code>"
        )
        await self._send_log(client, msg)

    async def log_new_product_alert(
        self,
        client: Client,
        product_name: str,
        icon: str,
        initial_stock: str,
        cost_price: float,
        user_price: float,
        product_id: str
    ):
        """Envía alerta al canal de logs cuando el proveedor agrega un producto nuevo"""
        msg = (
            f"{EMOJI_SPARKLES} <b>¡NUEVO PRODUCTO AÑADIDO POR PROVEEDOR!</b>\n\n"
            f"{icon} <b>{product_name}</b> - <code>{user_price:.2f} USDT</code> (Stock: {initial_stock})\n"
            f"{EMOJI_MONEY} <b>Costo en Bunai:</b> <code>${cost_price:.2f} USD</code>\n"
            f"🆔 <b>ID:</b> <code>{product_id}</code>"
        )
        await self._send_log(client, msg)

    async def log_system_alert(self, client: Client, title: str, details: str):
        """Envía una alerta del sistema con hora local exacta"""
        now = get_now_str("%Y-%m-%d %H:%M:%S")
        msg = (
            f"{EMOJI_WARN} <b>ALERTA DEL SISTEMA: {title}</b>\n\n"
            f"{details}\n\n"
            f"{EMOJI_CLOCK} <b>Fecha:</b> <code>{now}</code>"
        )
        await self._send_log(client, msg)

    async def log_new_user(self, client: Client, user_id: int, username: Optional[str], first_name: str):
        """Registra un nuevo usuario en el bot con fecha y hora local"""
        user_mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        now = get_now_str("%Y-%m-%d %H:%M:%S")
        msg = (
            f"{EMOJI_USER} <b>NUEVO USUARIO REGISTRADO</b>\n\n"
            f"• <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"{EMOJI_NAME_TAG} <b>Nombre:</b> {first_name}\n"
            f"• <b>Fecha:</b> <code>{now}</code>"
        )
        await self._send_log(client, msg)

audit_logger = AuditLogger()
