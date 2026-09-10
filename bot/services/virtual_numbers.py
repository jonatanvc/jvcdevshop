import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup
from pyrogram.enums import ParseMode
from sqlalchemy import select, update
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, VirtualNumberOrder
from bot.services.fivesim_client import fivesim_api
from bot.services.pricing import pricing_service
from bot.services.audit_logger import audit_logger
from bot.utils.emojis import PLATFORM_EMOJIS, parse_emojis, parse_keyboard, InlineKeyboardButton

# Catálogo oficial de las 13 plataformas más usadas del mundo con nombres formateados
CURATED_SERVICES: Dict[str, Dict[str, Any]] = {
    "whatsapp": {
        "name": "WhatsApp",
        "icon_id": PLATFORM_EMOJIS.get("whatsapp"),
        "code": "whatsapp"
    },
    "telegram": {
        "name": "Telegram",
        "icon_id": PLATFORM_EMOJIS.get("telegram"),
        "code": "telegram"
    },
    "apple": {
        "name": "Apple / iCloud",
        "icon_id": PLATFORM_EMOJIS.get("apple"),
        "code": "apple"
    },
    "openai": {
        "name": "ChatGPT (OpenAI)",
        "icon_id": PLATFORM_EMOJIS.get("openai"),
        "code": "openai"
    },
    "google": {
        "name": "Google / Gmail",
        "icon_id": PLATFORM_EMOJIS.get("google"),
        "code": "google"
    },
    "microsoft": {
        "name": "Microsoft / Outlook",
        "icon_id": PLATFORM_EMOJIS.get("microsoft"),
        "code": "microsoft"
    },
    "tiktok": {
        "name": "TikTok",
        "icon_id": PLATFORM_EMOJIS.get("tiktok"),
        "code": "tiktok"
    },
    "instagram": {
        "name": "Instagram / Meta",
        "icon_id": PLATFORM_EMOJIS.get("instagram"),
        "code": "instagram"
    },
    "discord": {
        "name": "Discord",
        "icon_id": PLATFORM_EMOJIS.get("discord"),
        "code": "discord"
    },
    "netflix": {
        "name": "Netflix",
        "icon_id": PLATFORM_EMOJIS.get("netflix"),
        "code": "netflix"
    },
    "steam": {
        "name": "Steam",
        "icon_id": PLATFORM_EMOJIS.get("steam"),
        "code": "steam"
    },
    "twitter": {
        "name": "X (Twitter)",
        "icon_id": PLATFORM_EMOJIS.get("twitter"),
        "code": "twitter"
    },
    "facebook": {
        "name": "Facebook",
        "icon_id": PLATFORM_EMOJIS.get("facebook"),
        "code": "facebook"
    }
}

# Mapeo de países de 5SIM con sus banderas oficiales en español
COUNTRY_NAMES: Dict[str, Tuple[str, str]] = {
    "usa": ("🇺🇸", "Estados Unidos"),
    "england": ("🇬🇧", "Reino Unido"),
    "canada": ("🇨🇦", "Canadá"),
    "colombia": ("🇨🇴", "Colombia"),
    "brazil": ("🇧🇷", "Brasil"),
    "argentina": ("🇦🇷", "Argentina"),
    "chile": ("🇨🇱", "Chile"),
    "spain": ("🇪🇸", "España"),
    "france": ("🇫🇷", "Francia"),
    "germany": ("🇩🇪", "Alemania"),
    "mexico": ("🇲🇽", "México"),
    "peru": ("🇵🇪", "Perú"),
    "netherlands": ("🇳🇱", "Países Bajos"),
    "indonesia": ("🇮🇩", "Indonesia"),
    "philippines": ("🇵🇭", "Filipinas"),
    "vietnam": ("🇻🇳", "Vietnam"),
    "thailand": ("🇹🇭", "Tailandia"),
    "malaysia": ("🇲🇾", "Malasia"),
    "turkey": ("🇹🇷", "Turquía"),
    "poland": ("🇵🇱", "Polonia"),
    "italy": ("🇮🇹", "Italia"),
    "portugal": ("🇵🇹", "Portugal"),
    "austria": ("🇦🇹", "Austria"),
    "belgium": ("🇧🇪", "Bélgica"),
    "sweden": ("🇸🇪", "Suecia"),
    "romania": ("🇷🇴", "Rumania"),
    "ukraine": ("🇺🇦", "Ucrania"),
    "kazakhstan": ("🇰🇿", "Kazajistán"),
    "southafrica": ("🇿🇦", "Sudáfrica"),
    "egypt": ("🇪🇬", "Egipto"),
    "india": ("🇮🇳", "India"),
    "bolivia": ("🇧🇴", "Bolivia"),
    "ecuador": ("🇪🇨", "Ecuador"),
    "dominicana": ("🇩🇴", "República Dominicana"),
    "guatemala": ("🇬🇹", "Guatemala"),
    "costarica": ("🇨🇷", "Costa Rica"),
    "panama": ("🇵🇦", "Panamá"),
    "uruguay": ("🇺🇾", "Uruguay"),
    "paraguay": ("🇵🇾", "Paraguay")
}

def get_country_display(country_code: str) -> Tuple[str, str]:
    """Retorna (bandera, nombre_en_espanol) para cualquier código de 5SIM"""
    code_clean = country_code.lower().strip()
    if code_clean in COUNTRY_NAMES:
        return COUNTRY_NAMES[code_clean]
    return ("🌐", country_code.capitalize())

class VirtualNumbersService:

    async def purchase_number(
        self,
        user_id: int,
        service_code: str,
        country: str,
        operator: str = "any"
    ) -> Dict[str, Any]:
        """
        Adquiere un número temporal en 5SIM, debita el saldo atómicamente en PostgreSQL
        con el margen de Bunai (+20% OFF si VIP) y crea el registro de orden.
        Si 5SIM falla, revierte sin cobrar al usuario.
        """
        if not fivesim_api.is_configured():
            return {"error": "La API de 5SIM no está configurada por el administrador."}

        # 1. Verificar usuario y saldo en base de datos
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                return {"error": "Usuario no registrado en el bot."}

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            is_vip = bool(user.is_vip and user.vip_expires_at and user.vip_expires_at > now)
            current_balance = float(user.balance)

        # 2. Llamar a 5SIM para adquirir el número
        res_5sim = await fivesim_api.buy_activation(country, operator, service_code)
        if "error" in res_5sim or not res_5sim.get("phone"):
            err_msg = res_5sim.get("error", "Error desconocido al comprar número en 5SIM.")
            return {"error": err_msg}

        fivesim_id = res_5sim.get("id")
        phone = res_5sim.get("phone")
        cost_usd = float(res_5sim.get("price", 0.0))
        op_used = res_5sim.get("operator", operator)

        # 3. Calcular precio de venta al usuario con margen Bunai y VIP
        price_usdt = pricing_service.calculate_virtual_number_price(cost_usd, is_vip=is_vip)

        # 4. Transacción atómica: debitar saldo y crear orden en base de datos
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id).with_for_update()
            res = await session.execute(stmt)
            user = res.scalar_one()

            if float(user.balance) < price_usdt:
                # Si no tiene saldo suficiente, cancelar de inmediato en 5SIM para no perder dinero
                asyncio.create_task(fivesim_api.cancel_order(fivesim_id))
                return {
                    "error": f"Saldo insuficiente. Este número cuesta <b>${price_usdt:.2f} USDT</b> y tienes <b>${float(user.balance):.2f} USDT</b>."
                }

            # Debitar saldo
            user.balance -= Decimal(str(price_usdt))

            # Tiempo de expiración (generalmente 15 minutos en 5sim)
            expires_at = now + timedelta(minutes=15)
            if res_5sim.get("expires"):
                try:
                    exp_clean = res_5sim["expires"].replace("Z", "+00:00")
                    expires_at = datetime.fromisoformat(exp_clean).astimezone(timezone.utc).replace(tzinfo=None)
                except Exception:
                    expires_at = now + timedelta(minutes=15)

            new_order = VirtualNumberOrder(
                user_id=user_id,
                fivesim_order_id=fivesim_id,
                phone=phone,
                service_name=service_code,
                country=country,
                operator=op_used,
                cost_usd=Decimal(str(cost_usd)),
                price_usdt=Decimal(str(price_usdt)),
                status="PENDING",
                is_refunded=False,
                expires_at=expires_at,
                created_at=now
            )
            session.add(new_order)
            await session.commit()
            await session.refresh(new_order)

            order_data = {
                "id": new_order.id,
                "fivesim_id": fivesim_id,
                "phone": phone,
                "service": service_code,
                "country": country,
                "price_usdt": price_usdt,
                "expires_at": expires_at,
                "status": "PENDING"
            }

        return {"order": order_data}

    async def cancel_and_refund_order(self, order_id: int, user_id: int, client: Optional[Client] = None) -> Dict[str, Any]:
        """
        Cancela una orden activa en 5SIM y reembolsa el 100% de los USDT al balance del usuario.
        Garantía Cero Riesgo: Seguro, atómico y libre de pérdidas.
        """
        async with async_session() as session:
            stmt = select(VirtualNumberOrder).where(
                VirtualNumberOrder.id == order_id,
                VirtualNumberOrder.user_id == user_id
            ).with_for_update()
            res = await session.execute(stmt)
            order = res.scalar_one_or_none()

            if not order:
                return {"error": "Orden no encontrada."}

            if order.status not in ["PENDING", "TIMEOUT"]:
                return {"error": f"La orden ya no puede ser cancelada (Estado: {order.status})."}

            if order.is_refunded:
                return {"error": "Esta orden ya fue reembolsada previamente."}

            # 1. Cancelar en la API de 5SIM
            cancel_res = await fivesim_api.cancel_order(order.fivesim_order_id)

            # 2. Reembolsar en el bot
            u_stmt = select(User).where(User.telegram_id == user_id).with_for_update()
            u_res = await session.execute(u_stmt)
            user = u_res.scalar_one()

            refund_amt = order.price_usdt
            user.balance += refund_amt
            order.status = "CANCELLED"
            order.is_refunded = True

            await session.commit()

        # Log en canal de auditoría si client está disponible
        if client:
            try:
                await audit_logger.log_system_alert(
                    client=client,
                    title="NÚMERO VIRTUAL CANCELADO Y REEMBOLSADO",
                    details=(
                        f"👤 <b>Usuario:</b> <code>{user_id}</code>\n"
                        f"📱 <b>Teléfono:</b> <code>{order.phone}</code>\n"
                        f"🌐 <b>Servicio:</b> {order.service_name.upper()} ({order.country.upper()})\n"
                        f"💵 <b>Monto Reembolsado:</b> <code>+${float(refund_amt):.2f} USDT</code>\n"
                        f"🆔 <b>5SIM Order:</b> <code>{order.fivesim_order_id}</code>"
                    )
                )
            except Exception:
                pass

        return {"success": True, "refunded_amount": float(refund_amt)}

    async def check_single_order(self, order_id: int) -> Dict[str, Any]:
        """
        Consulta si ya entró el SMS para una orden específica.
        Si entró el código: lo guarda en la BD, finaliza la orden en 5SIM y retorna el código.
        """
        async with async_session() as session:
            stmt = select(VirtualNumberOrder).where(VirtualNumberOrder.id == order_id)
            res = await session.execute(stmt)
            order = res.scalar_one_or_none()

            if not order:
                return {"error": "Orden no encontrada."}

            if order.status == "RECEIVED":
                return {
                    "status": "RECEIVED",
                    "code": order.sms_code,
                    "text": order.sms_full_text,
                    "phone": order.phone
                }

            if order.status in ["CANCELLED", "TIMEOUT"]:
                return {"status": order.status, "is_refunded": order.is_refunded}

            # Consultar estado en 5SIM
            res_5sim = await fivesim_api.check_order(order.fivesim_order_id)
            status_5sim = res_5sim.get("status", "").upper()
            sms_list = res_5sim.get("sms", [])

            if sms_list and len(sms_list) > 0:
                first_sms = sms_list[0]
                sms_code = str(first_sms.get("code") or "").strip()
                sms_text = str(first_sms.get("text") or "").strip()

                # Guardar en BD
                order.status = "RECEIVED"
                order.sms_code = sms_code
                order.sms_full_text = sms_text
                await session.commit()

                # Finalizar orden en 5SIM
                asyncio.create_task(fivesim_api.finish_order(order.fivesim_order_id))

                return {
                    "status": "RECEIVED",
                    "code": sms_code,
                    "text": sms_text,
                    "phone": order.phone
                }

            if status_5sim in ["CANCELED", "TIMEOUT", "BANNED"]:
                # Si 5sim canceló o expiró, reembolsar
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                if not order.is_refunded:
                    u_stmt = select(User).where(User.telegram_id == order.user_id).with_for_update()
                    u_res = await session.execute(u_stmt)
                    user = u_res.scalar_one()
                    user.balance += order.price_usdt
                    order.is_refunded = True
                order.status = "TIMEOUT" if status_5sim == "TIMEOUT" else "CANCELLED"
                await session.commit()
                return {"status": order.status, "is_refunded": True}

            return {
                "status": "PENDING",
                "phone": order.phone,
                "expires_at": order.expires_at
            }

virtual_numbers_service = VirtualNumbersService()

async def check_and_notify_pending_virtual_orders(app: Client):
    """
    Monitor periódico que revisa las órdenes de números virtuales
    que están en estado PENDING:
    - Si el SMS llegó: guarda el código, finaliza en 5SIM y le envía un DM de felicitación al usuario.
    - Si expiró (15 min): cancela en 5SIM, reembolsa el saldo en PostgreSQL y le notifica al usuario.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session() as session:
        stmt = select(VirtualNumberOrder).where(
            VirtualNumberOrder.status == "PENDING"
        )
        res = await session.execute(stmt)
        pending_orders = res.scalars().all()

    for order in pending_orders:
        try:
            # 1. Comprobar si ya expiró el tiempo sin recibir SMS
            if order.expires_at <= now:
                await virtual_numbers_service.cancel_and_refund_order(order.id, order.user_id, client=app)
                try:
                    alert_text = (
                        f"⏰ <b>TIEMPO AGOTADO - NÚMERO VIRTUAL</b>\n\n"
                        f"El tiempo de 15 minutos para el número <code>{order.phone}</code> ({order.service_name.upper()}) expiró sin recibir ningún SMS.\n\n"
                        f"💰 <b>Reembolso Acreditado:</b> <code>+${float(order.price_usdt):.2f} USDT</code>\n"
                        f"<i>Tus fondos han sido devueltos automáticamente a tu billetera.</i>"
                    )
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📱 Probar con Otro País", callback_data=f"vnum:select_service:{order.service_name}:1")],
                        [InlineKeyboardButton("👛 Ver Billetera", callback_data="wallet:deposit_menu")]
                    ])
                    await app.send_message(order.user_id, parse_emojis(alert_text), parse_mode=ParseMode.HTML, reply_markup=parse_keyboard(kb))
                except Exception:
                    pass
                continue

            # 2. Consultar si entró el SMS en 5SIM
            check_res = await virtual_numbers_service.check_single_order(order.id)
            if check_res.get("status") == "RECEIVED":
                code = check_res.get("code", "")
                text_msg = check_res.get("text", "")
                try:
                    success_text = (
                        f"🎉 <b>¡CÓDIGO DE VERIFICACIÓN RECIBIDO!</b>\n\n"
                        f"• <b>Plataforma:</b> {order.service_name.upper()}\n"
                        f"• <b>Número:</b> <code>{order.phone}</code>\n\n"
                        f"🔑 <b>Tu Código OTP (Toca para copiar):</b>\n"
                        f"<code>{code}</code>\n\n"
                        f"💬 <b>SMS Completo:</b>\n"
                        f"<i>\"{text_msg}\"</i>\n\n"
                        f"✅ <i>¡Activación completada con éxito!</i>"
                    )
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📱 Comprar Otro Número", callback_data="vnum:catalog")],
                        [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
                    ])
                    await app.send_message(order.user_id, parse_emojis(success_text), parse_mode=ParseMode.HTML, reply_markup=parse_keyboard(kb))
                except Exception:
                    pass

        except Exception as e:
            print(f"[VirtualOrdersWorker Error on order {order.id}]: {e}")

