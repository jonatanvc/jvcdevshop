from datetime import datetime
from typing import Optional, Any
from pyrogram import Client
from pyrogram.enums import ParseMode
from bot.config import settings

class AuditLogger:
    def __init__(self):
        self.log_group_id = settings.LOG_GROUP_ID

    async def _send_log(self, client: Client, text: str):
        """Envía un mensaje de auditoría al grupo privado configurado"""
        if not self.log_group_id or self.log_group_id == 0:
            return
        try:
            await client.send_message(
                chat_id=self.log_group_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"[AuditLogger Error] No se pudo enviar log a {self.log_group_id}: {e}")

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
    ):
        """Registra una nueva solicitud de depósito"""
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
        await self._send_log(client, msg)

    async def log_deposit_confirmed(
        self,
        client: Client,
        user_id: int,
        username: Optional[str],
        first_name: str,
        amount: float,
        tx_hash: str,
        new_balance: float
    ):
        """Registra un depósito confirmado en la blockchain"""
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
            f"⏰ <b>Fecha:</b> <code>{now}</code>"
        )
        await self._send_log(client, msg)

    async def log_system_alert(self, client: Client, title: str, details: str):
        """Envía una alerta del sistema (ej: saldo bajo en BunaiStore, error de stock)"""
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
