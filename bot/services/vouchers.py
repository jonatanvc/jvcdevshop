import logging
from typing import Optional, Tuple
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import settings
from bot.utils.time_utils import get_now_str
from bot.utils.formatters import adjust_warranty_in_name
from bot.utils.emojis import parse_emojis

logger = logging.getLogger(__name__)

class VoucherService:
    def __init__(self):
        self.channel_id = settings.VOUCHERS_CHANNEL_ID
        self._cached_bot_username: Optional[str] = None

    async def _get_bot_username(self, client: Client) -> str:
        if not self._cached_bot_username:
            try:
                me = await client.get_me()
                self._cached_bot_username = me.username or ""
            except Exception:
                self._cached_bot_username = ""
        return self._cached_bot_username

    def _mask_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> str:
        """Ofusca el usuario para proteger su privacidad en canales públicos"""
        if username:
            clean_u = username.strip().lstrip("@")
            if len(clean_u) <= 2:
                return f"@{clean_u}***"
            return f"@{clean_u[:2]}***"
        if first_name:
            clean_fn = first_name.strip()
            if len(clean_fn) <= 2:
                return f"{clean_fn}***"
            return f"{clean_fn[:2]}*** (ID: ...{str(user_id)[-4:]})"
        return f"Usuario ...{str(user_id)[-4:]}"

    def _mask_phone(self, phone: str) -> str:
        """Ofusca parcialmente el número de teléfono"""
        p = phone.strip()
        if len(p) >= 8:
            return f"{p[:6]} *** {p[-4:]}"
        elif len(p) >= 5:
            return f"{p[:3]} *** {p[-2:]}"
        return f"{p[:2]}***"

    def _format_product_voucher_text(
        self,
        order_id: int,
        product_name: str,
        qty: int,
        total_price: float,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        stars: int = 5,
        now_str: Optional[str] = None
    ) -> str:
        masked_user = self._mask_user(user_id, username, first_name)
        clean_name = adjust_warranty_in_name(product_name)
        now = now_str or get_now_str("%Y-%m-%d %H:%M:%S")
        stars_clamped = max(1, min(5, stars))
        stars_bar = "⭐" * stars_clamped

        return (
            f"⭐ <b>COMPROBANTE DE COMPRA EXITOSA</b>\n\n"
            f"👤 <b>Cliente:</b> {masked_user}\n"
            f"📦 <b>Producto:</b> <code>{clean_name}</code> (x{qty})\n"
            f"💵 <b>Total Pagado:</b> <code>${total_price:.2f} USDT</code>\n"
            f"🆔 <b>Comprobante #:</b> <code>#ORD_{order_id}</code>\n"
            f"🌟 <b>Calificación:</b> {stars_bar} ({stars_clamped}/5)\n"
            f"📅 <b>Fecha:</b> <code>{now}</code>\n\n"
            f"🛡️ <i>Servicio entregado de forma automática y 100% garantizada.</i>"
        )

    async def publish_product_voucher(
        self,
        client: Client,
        order_id: int,
        product_name: str,
        qty: int,
        total_price: float,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        stars: int = 5
    ) -> Optional[int]:
        """Publica el comprobante de compra digital en el canal público"""
        if not self.channel_id or self.channel_id == 0:
            return None

        try:
            bot_username = await self._get_bot_username(client)
            text = self._format_product_voucher_text(
                order_id=order_id,
                product_name=product_name,
                qty=qty,
                total_price=total_price,
                user_id=user_id,
                username=username,
                first_name=first_name,
                stars=stars
            )

            buttons = []
            if bot_username:
                buttons.append([InlineKeyboardButton("🛒 Ir a la Tienda", url=f"https://t.me/{bot_username}")])
            keyboard = InlineKeyboardMarkup(buttons) if buttons else None

            msg = await client.send_message(
                chat_id=self.channel_id,
                text=parse_emojis(text),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            return msg.id
        except Exception as e:
            logger.warning(f"[VoucherService] No se pudo publicar comprobante de producto #{order_id}: {e}")
            return None

    async def update_product_voucher_rating(
        self,
        client: Client,
        voucher_msg_id: int,
        order_id: int,
        product_name: str,
        qty: int,
        total_price: float,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        stars: int = 5
    ) -> bool:
        """Actualiza la calificación por estrellas en el comprobante del canal público"""
        if not self.channel_id or self.channel_id == 0 or not voucher_msg_id:
            return False

        try:
            bot_username = await self._get_bot_username(client)
            text = self._format_product_voucher_text(
                order_id=order_id,
                product_name=product_name,
                qty=qty,
                total_price=total_price,
                user_id=user_id,
                username=username,
                first_name=first_name,
                stars=stars
            )

            buttons = []
            if bot_username:
                buttons.append([InlineKeyboardButton("🛒 Ir a la Tienda", url=f"https://t.me/{bot_username}")])
            keyboard = InlineKeyboardMarkup(buttons) if buttons else None

            await client.edit_message_text(
                chat_id=self.channel_id,
                message_id=voucher_msg_id,
                text=parse_emojis(text),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            return True
        except Exception as e:
            logger.warning(f"[VoucherService] No se pudo actualizar calificación en voucher {voucher_msg_id}: {e}")
            return False

    def _format_virtual_number_voucher_text(
        self,
        order_id: int,
        service_name: str,
        country_code: str,
        phone: str,
        price_usdt: float,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        stars: int = 5,
        now_str: Optional[str] = None
    ) -> str:
        from bot.services.virtual_numbers import CURATED_SERVICES, get_country_display

        masked_user = self._mask_user(user_id, username, first_name)
        masked_phone = self._mask_phone(phone)
        flag, country_name = get_country_display(country_code)
        service_display = CURATED_SERVICES.get(service_name.lower(), {}).get("name", service_name.upper())
        now = now_str or get_now_str("%Y-%m-%d %H:%M:%S")
        stars_clamped = max(1, min(5, stars))
        stars_bar = "⭐" * stars_clamped

        return (
            f"📲 <b>ACTIVACIÓN DE NÚMERO VIRTUAL</b>\n\n"
            f"👤 <b>Cliente:</b> {masked_user}\n"
            f"🌐 <b>Plataforma:</b> <b>{service_display}</b>\n"
            f"📍 <b>País:</b> {flag} {country_name}\n"
            f"📞 <b>Número:</b> <code>{masked_phone}</code>\n"
            f"💵 <b>Precio:</b> <code>${price_usdt:.2f} USDT</code>\n"
            f"🆔 <b>Comprobante #:</b> <code>#VNUM_{order_id}</code>\n"
            f"🌟 <b>Calificación:</b> {stars_bar} ({stars_clamped}/5)\n"
            f"✅ <b>Estado:</b> <code>SMS OTP Recibido</code>\n"
            f"📅 <b>Fecha:</b> <code>{now}</code>\n\n"
            f"🛡️ <i>Activación instantánea y 100% verificada.</i>"
        )

    async def publish_virtual_number_voucher(
        self,
        client: Client,
        order_id: int,
        service_name: str,
        country_code: str,
        phone: str,
        price_usdt: float,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        stars: int = 5
    ) -> Optional[int]:
        """
        Publica el comprobante de activación de número virtual en el canal público.
        """
        if not self.channel_id or self.channel_id == 0:
            return None

        try:
            text = self._format_virtual_number_voucher_text(
                order_id=order_id,
                service_name=service_name,
                country_code=country_code,
                phone=phone,
                price_usdt=price_usdt,
                user_id=user_id,
                username=username,
                first_name=first_name,
                stars=stars
            )

            bot_username = await self._get_bot_username(client)
            buttons = []
            if bot_username:
                buttons.append([InlineKeyboardButton("📲 Conseguir Número Virtual", url=f"https://t.me/{bot_username}")])
            keyboard = InlineKeyboardMarkup(buttons) if buttons else None

            msg = await client.send_message(
                chat_id=self.channel_id,
                text=parse_emojis(text),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            return msg.id
        except Exception as e:
            logger.warning(f"[VoucherService] No se pudo publicar comprobante de número virtual #{order_id}: {e}")
            return None

    async def update_virtual_number_voucher_rating(
        self,
        client: Client,
        voucher_msg_id: int,
        order_id: int,
        service_name: str,
        country_code: str,
        phone: str,
        price_usdt: float,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        stars: int = 5
    ) -> bool:
        """Actualiza la calificación por estrellas en el comprobante de número virtual del canal público"""
        if not self.channel_id or self.channel_id == 0 or not voucher_msg_id:
            return False

        try:
            bot_username = await self._get_bot_username(client)
            text = self._format_virtual_number_voucher_text(
                order_id=order_id,
                service_name=service_name,
                country_code=country_code,
                phone=phone,
                price_usdt=price_usdt,
                user_id=user_id,
                username=username,
                first_name=first_name,
                stars=stars
            )

            buttons = []
            if bot_username:
                buttons.append([InlineKeyboardButton("📲 Conseguir Número Virtual", url=f"https://t.me/{bot_username}")])
            keyboard = InlineKeyboardMarkup(buttons) if buttons else None

            await client.edit_message_text(
                chat_id=self.channel_id,
                message_id=voucher_msg_id,
                text=parse_emojis(text),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            return True
        except Exception as e:
            logger.warning(f"[VoucherService] No se pudo actualizar calificación en voucher vnum {voucher_msg_id}: {e}")
            return False

voucher_service = VoucherService()
