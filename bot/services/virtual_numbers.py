import asyncio
import logging
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
from bot.services.vouchers import voucher_service
from bot.utils.emojis import PLATFORM_EMOJIS, parse_emojis, parse_keyboard, InlineKeyboardButton

logger = logging.getLogger(__name__)

def parse_5sim_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parsea de forma precisa la fecha ISO devuelta por la API de 5SIM (ej: '2026-09-12T15:10:18.627863Z')
    convirtiéndola siempre a un datetime UTC naive para sincronización exacta en base de datos.
    """
    if not date_str:
        return None
    try:
        clean = str(date_str).strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(str(date_str).strip(), fmt)
                if dt.tzinfo is not None:
                    return dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt
            except Exception:
                continue
        return None

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

# Mapeo completo de todos los 155 países de 5SIM con sus banderas oficiales en español
COUNTRY_NAMES: Dict[str, Tuple[str, str]] = {
    # América Latina y Caribe
    "colombia": ("🇨🇴", "Colombia"),
    "brazil": ("🇧🇷", "Brasil"),
    "argentina": ("🇦🇷", "Argentina"),
    "chile": ("🇨🇱", "Chile"),
    "mexico": ("🇲🇽", "México"),
    "peru": ("🇵🇪", "Perú"),
    "venezuela": ("🇻🇪", "Venezuela"),
    "bolivia": ("🇧🇴", "Bolivia"),
    "ecuador": ("🇪🇨", "Ecuador"),
    "dominicana": ("🇩🇴", "Rep. Dominicana"),
    "guatemala": ("🇬🇹", "Guatemala"),
    "costarica": ("🇨🇷", "Costa Rica"),
    "panama": ("🇵🇦", "Panamá"),
    "uruguay": ("🇺🇾", "Uruguay"),
    "paraguay": ("🇵🇾", "Paraguay"),
    "salvador": ("🇸🇻", "El Salvador"),
    "honduras": ("🇭🇳", "Honduras"),
    "nicaragua": ("🇳🇮", "Nicaragua"),
    "cuba": ("🇨🇺", "Cuba"),
    "puertorico": ("🇵🇷", "Puerto Rico"),
    "haiti": ("🇭🇹", "Haití"),
    "jamaica": ("🇯🇲", "Jamaica"),
    "guyana": ("🇬🇾", "Guyana"),
    "suriname": ("🇸🇷", "Surinam"),
    "antiguaandbarbuda": ("🇦🇬", "Antigua y Barbuda"),
    "aruba": ("🇦🇼", "Aruba"),
    "bahamas": ("🇧🇸", "Bahamas"),
    "barbados": ("🇧🇧", "Barbados"),
    "belize": ("🇧🇿", "Belice"),
    "frenchguiana": ("🇬🇫", "Guayana Francesa"),
    "guadeloupe": ("🇬🇵", "Guadalupe"),
    "saintkittsandnevis": ("🇰🇳", "San Cristóbal y Nieves"),
    "saintlucia": ("🇱🇨", "Santa Lucía"),
    "saintvincentandgrenadines": ("🇻🇨", "San Vicente y las Granadinas"),
    "tit": ("🇹🇹", "Trinidad y Tobago"),

    # Norteamérica y Europa
    "usa": ("🇺🇸", "Estados Unidos"),
    "canada": ("🇨🇦", "Canadá"),
    "england": ("🇬🇧", "Reino Unido"),
    "spain": ("🇪🇸", "España"),
    "france": ("🇫🇷", "Francia"),
    "germany": ("🇩🇪", "Alemania"),
    "italy": ("🇮🇹", "Italia"),
    "portugal": ("🇵🇹", "Portugal"),
    "netherlands": ("🇳🇱", "Países Bajos"),
    "poland": ("🇵🇱", "Polonia"),
    "sweden": ("🇸🇪", "Suecia"),
    "switzerland": ("🇨🇭", "Suiza"),
    "norway": ("🇳🇴", "Noruega"),
    "denmark": ("🇩🇰", "Dinamarca"),
    "finland": ("🇫🇮", "Finlandia"),
    "austria": ("🇦🇹", "Austria"),
    "belgium": ("🇧🇪", "Bélgica"),
    "romania": ("🇷🇴", "Rumania"),
    "ukraine": ("🇺🇦", "Ucrania"),
    "russia": ("🇷🇺", "Rusia"),
    "czech": ("🇨🇿", "República Checa"),
    "hungary": ("🇭🇺", "Hungría"),
    "greece": ("🇬🇷", "Grecia"),
    "ireland": ("🇮🇪", "Irlanda"),
    "croatia": ("🇭🇷", "Croacia"),
    "serbia": ("🇷🇸", "Serbia"),
    "slovakia": ("🇸🇰", "Eslovaquia"),
    "slovenia": ("🇸🇮", "Eslovenia"),
    "bulgaria": ("🇧🇬", "Bulgaria"),
    "bih": ("🇧🇦", "Bosnia"),
    "albania": ("🇦🇱", "Albania"),
    "estonia": ("🇪🇪", "Estonia"),
    "latvia": ("🇱🇻", "Letonia"),
    "lithuania": ("🇱🇹", "Lituania"),
    "belarus": ("🇧🇾", "Bielorrusia"),
    "moldova": ("🇲🇩", "Moldavia"),
    "cyprus": ("🇨🇾", "Chipre"),
    "georgia": ("🇬🇪", "Georgia"),
    "armenia": ("🇦🇲", "Armenia"),
    "azerbaijan": ("🇦🇿", "Azerbaiyán"),
    "luxembourg": ("🇱🇺", "Luxemburgo"),
    "montenegro": ("🇲🇪", "Montenegro"),
    "northmacedonia": ("🇲🇰", "Macedonia del Norte"),

    # Asia y Oceanía
    "china": ("🇨🇳", "China"),
    "japan": ("🇯🇵", "Japón"),
    "southkorea": ("🇰🇷", "Corea del Sur"),
    "taiwan": ("🇹🇼", "Taiwán"),
    "hongkong": ("🇭🇰", "Hong Kong"),
    "india": ("🇮🇳", "India"),
    "indonesia": ("🇮🇩", "Indonesia"),
    "philippines": ("🇵🇭", "Filipinas"),
    "vietnam": ("🇻🇳", "Vietnam"),
    "thailand": ("🇹🇭", "Tailandia"),
    "malaysia": ("🇲🇾", "Malasia"),
    "singapore": ("🇸🇬", "Singapur"),
    "australia": ("🇦🇺", "Australia"),
    "newzealand": ("🇳🇿", "Nueva Zelanda"),
    "pakistan": ("🇵🇰", "Pakistán"),
    "bangladesh": ("🇧🇩", "Bangladés"),
    "cambodia": ("🇰🇭", "Camboya"),
    "laos": ("🇱🇦", "Laos"),
    "nepal": ("🇳🇵", "Nepal"),
    "srilanka": ("🇱🇰", "Sri Lanka"),
    "kazakhstan": ("🇰🇿", "Kazajistán"),
    "uzbekistan": ("🇺🇿", "Uzbekistán"),
    "tajikistan": ("🇹🇯", "Tayikistán"),
    "turkmenistan": ("🇹🇲", "Turkmenistán"),
    "afghanistan": ("🇦🇫", "Afganistán"),
    "mongolia": ("🇲🇳", "Mongolia"),
    "easttimor": ("🇹🇱", "Timor Oriental"),
    "bhutane": ("🇧🇹", "Bután"),
    "macau": ("🇲🇴", "Macao"),
    "maldives": ("🇲🇻", "Maldivas"),
    "kyrgyzstan": ("🇰🇬", "Kirguistán"),
    "newcaledonia": ("🇳🇨", "Nueva Caledonia"),
    "papuanewguinea": ("🇵🇬", "Papúa Nueva Guinea"),
    "samoa": ("🇼🇸", "Samoa"),
    "solomonislands": ("🇸🇧", "Islas Salomón"),

    # Medio Oriente y África
    "turkey": ("🇹🇷", "Turquía"),
    "israel": ("🇮🇱", "Israel"),
    "uae": ("🇦🇪", "Emiratos Árabes"),
    "saudiarabia": ("🇸🇦", "Arabia Saudita"),
    "egypt": ("🇪🇬", "Egipto"),
    "morocco": ("🇲🇦", "Marruecos"),
    "southafrica": ("🇿🇦", "Sudáfrica"),
    "nigeria": ("🇳🇬", "Nigeria"),
    "kenya": ("🇰🇪", "Kenia"),
    "ghana": ("🇬🇭", "Ghana"),
    "algeria": ("🇩🇿", "Argelia"),
    "tunisia": ("🇹🇳", "Túnez"),
    "angola": ("🇦🇴", "Angola"),
    "cameroon": ("🇨🇲", "Camerún"),
    "senegal": ("🇸🇳", "Senegal"),
    "uganda": ("🇺🇬", "Uganda"),
    "zambia": ("🇿🇲", "Zambia"),
    "zimbabwe": ("🇿🇼", "Zimbabue"),
    "tanzania": ("🇹🇿", "Tanzania"),
    "ethiopia": ("🇪🇹", "Etiopía"),
    "ivorycoast": ("🇨🇮", "Costa de Marfil"),
    "mozambique": ("🇲🇿", "Mozambique"),
    "madagascar": ("🇲🇬", "Madagascar"),
    "congo": ("🇨🇩", "Congo"),
    "benin": ("🇧🇯", "Benín"),
    "burkinafaso": ("🇧🇫", "Burkina Faso"),
    "burundi": ("🇧🇮", "Burundi"),
    "gabon": ("🇬🇦", "Gabón"),
    "gambia": ("🇬🇲", "Gambia"),
    "guinea": ("🇬🇳", "Guinea"),
    "liberia": ("🇱🇷", "Liberia"),
    "malawi": ("🇲🇼", "Malaui"),
    "rwanda": ("🇷🇼", "Ruanda"),
    "sierraleone": ("🇸🇱", "Sierra Leona"),
    "togo": ("🇹🇬", "Togo"),
    "bahrain": ("🇧🇭", "Baréin"),
    "botswana": ("🇧🇼", "Botsuana"),
    "capeverde": ("🇨🇻", "Cabo Verde"),
    "chad": ("🇹🇩", "Chad"),
    "comoros": ("🇰🇲", "Comoras"),
    "djibouti": ("🇩🇯", "Yibuti"),
    "equatorialguinea": ("🇬🇶", "Guinea Ecuatorial"),
    "guineabissau": ("🇬🇼", "Guinea-Bisáu"),
    "jordan": ("🇯🇴", "Jordania"),
    "kuwait": ("🇰🇼", "Kuwait"),
    "lesotho": ("🇱🇸", "Lesoto"),
    "mauritania": ("🇲🇷", "Mauritania"),
    "mauritius": ("🇲🇺", "Mauricio"),
    "namibia": ("🇳🇦", "Namibia"),
    "oman": ("🇴🇲", "Omán"),
    "reunion": ("🇷🇪", "Reunión"),
    "seychelles": ("🇸🇨", "Seychelles"),
    "swaziland": ("🇸🇿", "Suazilandia")
}

def get_country_display(country_code: str) -> Tuple[str, str]:
    """Retorna (bandera, nombre_en_espanol) para cualquier código de 5SIM (sin bolita del mundo)"""
    code_clean = country_code.lower().strip()
    if code_clean in COUNTRY_NAMES:
        return COUNTRY_NAMES[code_clean]
    # En caso imprevisto de país no listado, bandera neutral (nunca globo terráqueo)
    return ("🏳️", country_code.capitalize())

class VirtualNumbersService:

    async def purchase_number(
        self,
        user_id: int,
        service_code: Optional[str] = None,
        country: Optional[str] = None,
        operator: str = "any",
        is_owner: bool = False,
        pay_with_api: bool = False,
        service_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Adquiere un número temporal en 5SIM, debita el saldo atómicamente en PostgreSQL
        con el margen de Bunai (+20% OFF si VIP, o costo neto 0% si Owner) y crea el registro de orden.
        Si pay_with_api=True (Owner), no debita el saldo de la billetera del bot y usa directamente
        el saldo de la API de 5SIM.
        """
        if not fivesim_api.is_configured():
            return {"error": "La API de 5SIM no está configurada por el administrador."}

        # Resolver alias de parámetros
        code = service_code or service_name
        if not code or not country:
            return {"error": "Faltan datos de la plataforma o el país seleccionado."}

        # 1. Si es pago directo con la API, verificar que sea owner y consultar saldo 5SIM
        if pay_with_api:
            if not is_owner:
                return {"error": "Solo el administrador/owner puede pagar con saldo directo de la API."}
            try:
                prof_5sim = await fivesim_api.get_profile()
                fivesim_bal = float(prof_5sim.get("balance", 0.0))
                if fivesim_bal < 0.05:
                    pay_with_api = False  # Fallback a débito de saldo del bot a precio de costo
            except Exception:
                pay_with_api = False

        # 2. Verificar usuario en base de datos (auto-crearlo si no existe para evitar error de clave foránea)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        is_vip = False
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                user = User(
                    telegram_id=user_id,
                    username="",
                    first_name="Owner" if is_owner else "Usuario",
                    balance=Decimal("0.0000"),
                    total_spent=Decimal("0.0000"),
                    language="es"
                )
                session.add(user)
                await session.commit()
            else:
                if getattr(user, "is_banned", False):
                    return {"error": "Tu cuenta se encuentra suspendida por la administración. Contacta a soporte."}
                is_vip = bool(user.is_vip and user.vip_expires_at and user.vip_expires_at > now)
                if not pay_with_api and float(user.balance) <= 0.0 and not is_owner:
                    return {"error": "No tienes saldo suficiente en tu cuenta para comprar números virtuales."}

        # 3. Llamar a 5SIM para adquirir el número
        res_5sim = await fivesim_api.buy_activation(country, operator, code)
        if "error" in res_5sim or not res_5sim.get("phone"):
            err_msg = res_5sim.get("error", "Error desconocido al comprar número en 5SIM.")
            return {"error": err_msg}

        fivesim_id = res_5sim.get("id")
        phone = res_5sim.get("phone")
        cost_usd = float(res_5sim.get("price", 0.0))
        op_used = res_5sim.get("operator", operator)

        # 4. Calcular precio de venta al usuario con margen Bunai y VIP (o precio costo si Owner o pago API)
        if pay_with_api:
            price_usdt = cost_usd
        else:
            price_usdt = pricing_service.calculate_virtual_number_price(cost_usd, is_vip=is_vip, is_owner=is_owner)

        # 5. Transacción atómica: debitar saldo (si no fue por API) y registrar orden en base de datos
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id).with_for_update()
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                user = User(
                    telegram_id=user_id,
                    username="",
                    first_name="Owner" if is_owner else "Usuario",
                    balance=Decimal("0.0000"),
                    total_spent=Decimal("0.0000"),
                    language="es"
                )
                session.add(user)
                await session.commit()
                res = await session.execute(stmt)
                user = res.scalar_one()

            if not pay_with_api:
                if float(user.balance) < price_usdt:
                    # Si no tiene saldo suficiente en el bot, cancelar de inmediato en 5SIM para no perder dinero
                    asyncio.create_task(fivesim_api.cancel_order(fivesim_id))
                    return {
                        "error": f"Saldo insuficiente. Este número cuesta <b>${price_usdt:.2f} USDT</b> y tienes <b>${float(user.balance):.2f} USDT</b>."
                    }

                # Debitar saldo en bot
                user.balance -= Decimal(str(price_usdt))
                user.total_spent += Decimal(str(price_usdt))

            # Tiempo exacto de expiración asignado por 5SIM (generalmente 15 a 20 minutos según operador)
            fivesim_expires = parse_5sim_datetime(res_5sim.get("expires"))
            expires_at = fivesim_expires or (now + timedelta(minutes=20))

            new_order = VirtualNumberOrder(
                user_id=user_id,
                fivesim_order_id=fivesim_id,
                phone=phone,
                service_name=code,
                country=country,
                operator=op_used,
                cost_usd=Decimal(str(cost_usd)),
                price_usdt=Decimal(str(price_usdt)),
                payment_method="api" if pay_with_api else "bot",
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
                "service": code,
                "country": country,
                "price_usdt": price_usdt,
                "payment_method": "api" if pay_with_api else "bot",
                "expires_at": expires_at,
                "status": "PENDING"
            }

        return {"order": order_data, "order_id": new_order.id}

    async def cancel_and_refund_order(self, order_id: int, user_id: int, client: Optional[Client] = None) -> Dict[str, Any]:
        """
        Cancela una orden activa en 5SIM y gestiona el reembolso:
        - Si pagó con bot: reembolsa el 100% de los USDT al balance del usuario en el bot.
        - Si pagó con API 5SIM: 5SIM devuelve el saldo a la cuenta 5SIM, no toca el balance del bot.
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
            await fivesim_api.cancel_order(order.fivesim_order_id)

            # 2. Reembolsar en el bot solo si pagó con saldo del bot
            is_api_pay = (getattr(order, "payment_method", "bot") == "api")
            refund_amt = order.price_usdt

            if not is_api_pay:
                u_stmt = select(User).where(User.telegram_id == user_id).with_for_update()
                u_res = await session.execute(u_stmt)
                user = u_res.scalar_one_or_none()
                if user:
                    user.balance += refund_amt

            order.status = "CANCELLED"
            order.is_refunded = True

            await session.commit()

        # Log en canal de auditoría si client está disponible
        if client:
            try:
                pay_desc = f"API 5SIM (${float(order.cost_usd):.2f} USD devueltos a la cuenta)" if is_api_pay else f"+${float(refund_amt):.2f} USDT a Billetera Bot"
                await audit_logger.log_system_alert(
                    client=client,
                    title="NÚMERO VIRTUAL CANCELADO Y REEMBOLSADO",
                    details=(
                        f"👤 <b>Usuario:</b> <code>{user_id}</code>\n"
                        f"📱 <b>Teléfono:</b> <code>{order.phone}</code>\n"
                        f"📲 <b>Servicio:</b> {order.service_name.upper()} ({order.country.upper()})\n"
                        f"💵 <b>Reembolso:</b> <code>{pay_desc}</code>\n"
                        f"🆔 <b>5SIM Order:</b> <code>{order.fivesim_order_id}</code>"
                    )
                )
            except Exception:
                pass

        return {
            "success": True,
            "refunded_amount": float(refund_amt),
            "payment_method": "api" if is_api_pay else "bot",
            "service_name": order.service_name,
            "country": order.country
        }

    async def ban_and_refund_order(self, order_id: int, user_id: int, client: Optional[Client] = None) -> Dict[str, Any]:
        """
        Reporta un número como inválido o ya registrado/bloqueado en 5SIM (ban_order) y gestiona el reembolso inmediato:
        - Si pagó con bot: reembolsa el 100% de los USDT al balance del usuario en el bot.
        - Si pagó con API 5SIM: 5SIM devuelve el saldo a la cuenta 5SIM.
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

            if order.status not in ["PENDING", "RECEIVED"]:
                return {"error": f"La orden ya no puede ser reportada (Estado: {order.status})."}

            if order.is_refunded:
                return {"error": "Esta orden ya fue reembolsada previamente."}

            # 1. Reportar y banear en la API de 5SIM
            await fivesim_api.ban_order(order.fivesim_order_id)

            # 2. Reembolsar en el bot
            is_api_pay = (getattr(order, "payment_method", "bot") == "api")
            refund_amt = order.price_usdt

            if not is_api_pay:
                u_stmt = select(User).where(User.telegram_id == user_id).with_for_update()
                u_res = await session.execute(u_stmt)
                user = u_res.scalar_one_or_none()
                if user:
                    user.balance += refund_amt

            order.status = "CANCELLED"
            order.is_refunded = True

            await session.commit()

        # Log en canal de auditoría
        if client:
            try:
                pay_desc = f"API 5SIM (${float(order.cost_usd):.2f} USD devueltos)" if is_api_pay else f"+${float(refund_amt):.2f} USDT a Billetera"
                await audit_logger.log_system_alert(
                    client=client,
                    title="NÚMERO VIRTUAL REPORTADO (BLOQUEADO / EN USO)",
                    details=(
                        f"👤 <b>Usuario:</b> <code>{user_id}</code>\n"
                        f"📱 <b>Teléfono:</b> <code>{order.phone}</code>\n"
                        f"📲 <b>Servicio:</b> {order.service_name.upper()} ({order.country.upper()})\n"
                        f"💵 <b>Reembolso:</b> <code>{pay_desc}</code>\n"
                        f"🆔 <b>5SIM Order:</b> <code>{order.fivesim_order_id}</code>"
                    )
                )
            except Exception:
                pass

        return {
            "success": True,
            "refunded_amount": float(refund_amt),
            "payment_method": "api" if is_api_pay else "bot",
            "service_name": order.service_name,
            "country": order.country
        }

    async def finish_and_close_order(self, order_id: int) -> Dict[str, Any]:
        """Finaliza formalmente la orden en 5SIM una vez que el cliente concluye su uso"""
        async with async_session() as session:
            stmt = select(VirtualNumberOrder).where(VirtualNumberOrder.id == order_id)
            res = await session.execute(stmt)
            order = res.scalar_one_or_none()
            if order:
                order.status = "FINISHED"
                await session.commit()
                asyncio.create_task(fivesim_api.finish_order(order.fivesim_order_id))
                return {"success": True}
        return {"error": "Orden no encontrada"}

    async def check_single_order(self, order_id: int) -> Dict[str, Any]:
        """
        Consulta si ya entró el SMS (o nuevos SMS) para una orden específica:
        - Sincroniza el tiempo real de expiración según el reloj oficial de 5SIM.
        - Si el SMS llegó o hay uno nuevo, marca RECEIVED y retorna el código OTP más reciente.
        - Permite recibir múltiples SMS (Re-SMS) durante el tiempo que dure la orden.
        - Si 5SIM marca TIMEOUT o CANCELED, procesa el reembolso correspondiente.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        async with async_session() as session:
            stmt = select(VirtualNumberOrder).where(VirtualNumberOrder.id == order_id).with_for_update()
            res = await session.execute(stmt)
            order = res.scalar_one_or_none()

            if not order:
                return {"status": "NOT_FOUND"}

            if order.status in ["FINISHED", "CANCELLED", "TIMEOUT"]:
                return {"status": order.status, "is_refunded": order.is_refunded}

            # Consultar estado oficial en 5SIM
            res_5sim = await fivesim_api.check_order(order.fivesim_order_id)
            status_5sim = res_5sim.get("status", "").upper()
            sms_list = res_5sim.get("sms", [])

            # Sincronizar expires_at con la fecha oficial del proveedor 5SIM
            fivesim_expires = parse_5sim_datetime(res_5sim.get("expires"))
            if fivesim_expires and fivesim_expires != order.expires_at:
                order.expires_at = fivesim_expires
                await session.commit()

            # 1. SMS OTP Recibido (último código recibido)
            if sms_list and len(sms_list) > 0:
                latest_sms = sms_list[-1]
                sms_code = str(latest_sms.get("code") or "").strip()
                sms_text = str(latest_sms.get("text") or "").strip()

                order.status = "RECEIVED"
                order.sms_code = sms_code
                order.sms_full_text = sms_text
                await session.commit()

                return {
                    "status": "RECEIVED",
                    "code": sms_code,
                    "text": sms_text,
                    "phone": order.phone,
                    "service_name": order.service_name,
                    "country": order.country,
                    "price_usdt": float(order.price_usdt),
                    "sms_count": len(sms_list)
                }

            # 2. Expiración o cancelación detectada directamente por 5SIM
            if status_5sim in ["CANCELED", "TIMEOUT", "BANNED"]:
                if not order.is_refunded:
                    if getattr(order, "payment_method", "bot") != "api":
                        u_stmt = select(User).where(User.telegram_id == order.user_id).with_for_update()
                        u_res = await session.execute(u_stmt)
                        user = u_res.scalar_one_or_none()
                        if user:
                            user.balance += order.price_usdt
                    order.is_refunded = True
                order.status = "TIMEOUT" if status_5sim == "TIMEOUT" else "CANCELLED"
                await session.commit()
                return {"status": order.status, "is_refunded": True}

            # 3. Si 5SIM sigue PENDING: verificar si ya pasó el tiempo total de expiración + ventana de gracia
            grace_period = timedelta(seconds=60)
            if now >= (order.expires_at + grace_period):
                # El tiempo de 5SIM ha concluido por completo y se superó el margen de gracia
                if not order.is_refunded:
                    if getattr(order, "payment_method", "bot") != "api":
                        u_stmt = select(User).where(User.telegram_id == order.user_id).with_for_update()
                        u_res = await session.execute(u_stmt)
                        user = u_res.scalar_one_or_none()
                        if user:
                            user.balance += order.price_usdt
                    order.is_refunded = True
                order.status = "TIMEOUT"
                await session.commit()
                asyncio.create_task(fivesim_api.cancel_order(order.fivesim_order_id))
                return {"status": "TIMEOUT", "is_refunded": True}

            return {
                "status": "PENDING",
                "phone": order.phone,
                "expires_at": order.expires_at
            }

virtual_numbers_service = VirtualNumbersService()

async def check_and_notify_pending_virtual_orders(app: Client):
    """
    Monitor periódico que revisa las órdenes de números virtuales pendientes:
    - Respeta estrictamente el tiempo de expiración asignado por 5SIM (nunca cancela antes de tiempo).
    - Si el SMS llegó: guarda el código, finaliza en 5SIM y notifica al usuario con su OTP y comprobante.
    - Si expiró en 5SIM: procesa el reembolso y notifica al usuario que el tiempo concluyó.
    """
    async with async_session() as session:
        stmt = select(VirtualNumberOrder).where(
            VirtualNumberOrder.status == "PENDING"
        )
        res = await session.execute(stmt)
        pending_orders = res.scalars().all()

    for order in pending_orders:
        try:
            # Consultar estado real en 5SIM (sincroniza y respeta la expiración oficial)
            check_res = await virtual_numbers_service.check_single_order(order.id)
            st = check_res.get("status")

            # 1. Código OTP Recibido
            if st == "RECEIVED":
                code = check_res.get("code", "")
                text_msg = check_res.get("text", "")

                # Publicar comprobante automático en el canal público y en auditoría
                if not order.voucher_message_id:
                    v_msg_id = await voucher_service.publish_virtual_number_voucher(
                        client=app,
                        order_id=order.id,
                        service_name=order.service_name,
                        country_code=order.country,
                        phone=order.phone,
                        price_usdt=float(order.price_usdt),
                        user_id=order.user_id,
                        stars=5
                    )
                    if v_msg_id:
                        async with async_session() as s2:
                            await s2.execute(
                                update(VirtualNumberOrder)
                                .where(VirtualNumberOrder.id == order.id)
                                .values(voucher_message_id=v_msg_id, rating=5)
                            )
                            await s2.commit()

                    # Registrar activación en el canal de auditoría del Owner
                    try:
                        ord_username = None
                        ord_first_name = "Usuario"
                        async with async_session() as s_u:
                            res_u = await s_u.execute(select(User).where(User.telegram_id == order.user_id))
                            u_obj = res_u.scalar_one_or_none()
                            if u_obj:
                                ord_username = u_obj.username
                                ord_first_name = u_obj.first_name or "Usuario"

                        await audit_logger.log_virtual_number_activation(
                            client=app,
                            user_id=order.user_id,
                            username=ord_username,
                            first_name=ord_first_name,
                            order_id=order.id,
                            service_name=order.service_name,
                            country_code=order.country,
                            phone=order.phone,
                            code=code,
                            price_usdt=float(order.price_usdt),
                            fivesim_order_id=order.fivesim_order_id,
                            is_owner=settings.is_owner(order.user_id)
                        )
                    except Exception as e_audit:
                        logger.warning(f"[VirtualNumberOrder Polling] Error enviando auditoría: {e_audit}")

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
                        [
                            InlineKeyboardButton("⭐ 1", callback_data=f"rate:vnum:{order.id}:1"),
                            InlineKeyboardButton("⭐ 2", callback_data=f"rate:vnum:{order.id}:2"),
                            InlineKeyboardButton("⭐ 3", callback_data=f"rate:vnum:{order.id}:3"),
                            InlineKeyboardButton("⭐ 4", callback_data=f"rate:vnum:{order.id}:4"),
                            InlineKeyboardButton("⭐ 5", callback_data=f"rate:vnum:{order.id}:5"),
                        ],
                        [InlineKeyboardButton("⚡ Pedir Otro Número (Mismo País)", callback_data=f"vnum:reorder:{order.service_name}:{order.country}")],
                        [InlineKeyboardButton("📱 Comprar Otro Número", callback_data="vnum:catalog")],
                        [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
                    ])
                    await app.send_message(order.user_id, parse_emojis(success_text), parse_mode=ParseMode.HTML, reply_markup=parse_keyboard(kb))
                except Exception:
                    pass
                continue

            # 2. Orden Expirada o Cancelada por 5SIM
            if st in ["TIMEOUT", "CANCELLED"]:
                try:
                    if getattr(order, "payment_method", "bot") == "api":
                        refund_info = (
                            f"💰 <b>Reembolso:</b> <code>${float(order.cost_usd):.2f} USD</code> devueltos a tu cuenta de la API 5SIM.\n"
                        )
                    else:
                        refund_info = (
                            f"💰 <b>Reembolso Acreditado:</b> <code>+${float(order.price_usdt):.2f} USDT</code>\n"
                            f"<i>Tus fondos han sido devueltos automáticamente a tu billetera del bot.</i>\n"
                        )

                    service_info = CURATED_SERVICES.get(order.service_name, {"name": order.service_name.upper()})
                    service_display = service_info.get("name", order.service_name.upper())

                    alert_text = (
                        f"⏰ <b>TIEMPO AGOTADO - NÚMERO VIRTUAL</b>\n\n"
                        f"El tiempo de espera para el número <code>{order.phone}</code> ({service_display}) ha expirado sin recibir ningún SMS.\n\n"
                        f"{refund_info}"
                    )
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("⚡ Probar Otro Número (Mismo País)", callback_data=f"vnum:reorder:{order.service_name}:{order.country}")],
                        [InlineKeyboardButton("📱 Probar con Otro País", callback_data=f"vnum:select_service:{order.service_name}:1")],
                        [InlineKeyboardButton("👛 Ver Billetera", callback_data="wallet:deposit_menu")]
                    ])
                    await app.send_message(order.user_id, parse_emojis(alert_text), parse_mode=ParseMode.HTML, reply_markup=parse_keyboard(kb))
                except Exception:
                    pass
                continue

            # 3. Si sigue PENDING: no hacer nada, seguir esperando el tiempo asignado por 5SIM
        except Exception as e:
            print(f"[VirtualOrdersWorker Error on order {order.id}]: {e}")
