from datetime import datetime
from typing import Optional, Any
from pyrogram import Client
from pyrogram.enums import ParseMode
from bot.config import settings

class AuditLogger:
    def __init__(self):
        self.log_group_id = settings.LOG_GROUP_ID

    async def _send_log(self, client: Client, text: str) -> Optional[int]:
        """Envía un mensaje de auditoría al grupo privado configurado y devuelve su ID"""
        if not self.log_group_id or self.log_group_id == 0:
            return None
        try:
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
        """Registra una compra exitosa en el canal de auditoría"""
        user_mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = (
            f"🛍️ <b>NUEVA COMPRA REALIZADA #ORD_{order_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"📛 <b>Nombre:</b> {first_name}\n"
            f"📦 <b>Producto:</b> <code>{product_name}</code>\n"
            f"💰 <b>Precio Pagado:</b> <code>${paid_price:.2f} USDT</code>\n"
            f"📊 <b>Saldo Restante Usuario:</b> <code>${remaining_balance:.2f} USDT</code>\n"
            f"🆔 <b>ID Orden Proveedor:</b> <code>{provider_order_id or 'N/A'}</code>\n"
            f"⏰ <b>Fecha:</b> <code>{now}</code>\n\n"
            f"🔑 <b>DATOS / CUENTAS ENTREGADAS:</b>\n"
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
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = (
            f"📥 <b>NUEVA SOLICITUD DE DEPÓSITO</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"💵 <b>Monto Base Solicitado:</b> <code>${base_amount:.2f} USDT</code>\n"
            f"🎯 <b>Monto Exacto Asignado:</b> <code>{exact_amount:.4f} USDT</code>\n"
            f"⏳ <b>Vigencia:</b> 30 minutos\n"
            f"⏰ <b>Fecha:</b> <code>{now}</code>"
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
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = (
            f"❌ <b>SOLICITUD DE DEPÓSITO CANCELADA</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"💰 <b>Monto Cancelado:</b> <code>${amount_cancelled:.4f} USDT</code>\n"
            f"🆔 <b>ID Depósito:</b> <code>DEP_{deposit_id}</code>\n"
            f"⏰ <b>Cancelado:</b> <code>{now}</code>"
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
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = (
            f"✅ <b>DEPÓSITO CONFIRMADO EN BLOCKCHAIN</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"💰 <b>Monto Acreditado:</b> <code>+${amount:.4f} USDT</code>\n"
            f"💳 <b>Nuevo Saldo Usuario:</b> <code>${new_balance:.4f} USDT</code>\n"
            f"🔗 <b>Hash / TxID:</b> <a href='{bsc_link}'>{tx_hash[:10]}...{tx_hash[-8:]}</a>\n"
            f"🆔 <b>ID Depósito:</b> <code>DEP_{deposit_id or 'N/A'}</code>\n"
            f"⏰ <b>Confirmado:</b> <code>{now}</code>"
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
            f"📢 <b>¡{added_stock} stock añadido a {product_name}!</b>\n\n"
            f"{icon} <b>{product_name}</b> - <code>{user_price:.2f} USDT</code> (Stock: {total_stock})\n"
            f"💰 <b>Costo Proveedor:</b> <code>${cost_price:.2f} USD</code>"
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
            f"✨ <b>¡NUEVO PRODUCTO AÑADIDO POR PROVEEDOR!</b>\n\n"
            f"{icon} <b>{product_name}</b> - <code>{user_price:.2f} USDT</code> (Stock: {initial_stock})\n"
            f"💰 <b>Costo en Bunai:</b> <code>${cost_price:.2f} USD</code>\n"
            f"🆔 <b>ID:</b> <code>{product_id}</code>"
        )
        await self._send_log(client, msg)

    async def log_system_alert(self, client: Client, title: str, details: str):
        """Envía una alerta del sistema"""
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = (
            f"⚠️ <b>ALERTA DEL SISTEMA: {title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{details}\n\n"
            f"⏰ <b>Fecha:</b> <code>{now}</code>"
        )
        await self._send_log(client, msg)

    async def log_new_user(self, client: Client, user_id: int, username: Optional[str], first_name: str):
        """Registra un nuevo usuario en el bot"""
        user_mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = (
            f"👤 <b>NUEVO USUARIO REGISTRADO</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Usuario:</b> {user_mention} (<code>{user_id}</code>)\n"
            f"• <b>Nombre:</b> {first_name}\n"
            f"• <b>Fecha:</b> <code>{now}</code>"
        )
        await self._send_log(client, msg)

audit_logger = AuditLogger()
