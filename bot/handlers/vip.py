from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Set
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from sqlalchemy import select, update
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Order
from bot.services.audit_logger import audit_logger
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t
from bot.utils.emojis import parse_emojis, parse_keyboard
from bot.handlers.admin import is_admin, find_user_by_identifier

VIP_PRICE_USDT = Decimal(str(settings.VIP_MONTHLY_PRICE_USDT))

# Lock en memoria por usuario para prevenir llamadas simultáneas / race conditions de scripts
_ACTIVE_VIP_TRANSACTIONS: Set[int] = set()

def register_vip_handlers(app: Client):

    @app.on_callback_query(filters.regex(r"^account:vip$"))
    async def cb_account_vip(client: Client, callback: CallbackQuery):
        """Muestra la pantalla interactiva del Plan Revendedor VIP"""
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer()
            return

        try:
            await callback.answer()
        except Exception:
            pass

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                return

            lang = getattr(user, "language", "es") or "es"
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            is_active_vip = bool(user.is_vip and user.vip_expires_at and user.vip_expires_at > now)

            if is_active_vip:
                days_left = max(1, (user.vip_expires_at - now).days)
                exp_str = user.vip_expires_at.strftime("%Y-%m-%d %H:%M UTC")
                text = t("vip_active_title", lang, expires_at=exp_str, days_left=days_left)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_renew_vip", lang), callback_data="vip:confirm_screen")],
                    [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")],
                    [InlineKeyboardButton(t("btn_back", lang), callback_data="account:view")]
                ])
            else:
                text = t("vip_info_title", lang)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_activate_vip", lang), callback_data="vip:confirm_screen")],
                    [InlineKeyboardButton(t("btn_back", lang), callback_data="account:view")]
                ])

            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^vip:confirm_screen$"))
    async def cb_vip_confirm_screen(client: Client, callback: CallbackQuery):
        """Muestra la pantalla previa con TODOS los beneficios del Plan Revendedor VIP antes de procesar el pago"""
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer()
            return

        try:
            await callback.answer()
        except Exception:
            pass

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                return

            lang = getattr(user, "language", "es") or "es"
            balance_val = float(getattr(user, "balance", 0.0) or 0.0)
            has_sufficient = (user.balance or Decimal("0")) >= VIP_PRICE_USDT

            if has_sufficient:
                text = t("vip_confirm_title", lang, balance=f"{balance_val:.2f}")
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_confirm_pay_vip", lang), callback_data="vip:activate")],
                    [InlineKeyboardButton(t("btn_cancel", lang), callback_data="account:vip")]
                ])
            else:
                text = t("vip_insufficient_funds", lang, balance=f"{balance_val:.2f}")
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_deposit", lang), callback_data="wallet:deposit_menu")],
                    [InlineKeyboardButton(t("btn_back", lang), callback_data="account:vip")]
                ])

            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^vip:activate$"))
    async def cb_vip_activate(client: Client, callback: CallbackQuery):
        """
        Procesa el cobro seguro de 10 USDT de saldo del bot y activa/renueva la membresía VIP.
        Blindado con lock en memoria y transacción SQL atómica anti-race conditions y anti-doble-gasto.
        """
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer("⏳ ...")
            return

        if user_id in _ACTIVE_VIP_TRANSACTIONS:
            await callback.answer("⏳ Ya se está procesando tu solicitud...", show_alert=True)
            return

        _ACTIVE_VIP_TRANSACTIONS.add(user_id)
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            async with async_session() as session:
                # 1. Transacción SQL atómica: solo descuenta si balance >= VIP_PRICE_USDT
                deduct_stmt = (
                    update(User)
                    .where(User.telegram_id == user_id, User.balance >= VIP_PRICE_USDT)
                    .values(
                        balance=User.balance - VIP_PRICE_USDT,
                        total_spent=User.total_spent + VIP_PRICE_USDT
                    )
                    .returning(User.balance)
                )
                deduct_res = await session.execute(deduct_stmt)
                remaining_balance = deduct_res.scalar()

                if remaining_balance is None:
                    # Saldo insuficiente o gastado por una solicitud concurrente
                    user_res = await session.execute(select(User).where(User.telegram_id == user_id))
                    cur_user = user_res.scalar_one_or_none()
                    cur_bal = float(cur_user.balance) if cur_user else 0.0
                    lang = getattr(cur_user, "language", "es") or "es"
                    text = t("vip_insufficient_funds", lang, balance=f"{cur_bal:.2f}")
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(t("btn_deposit", lang), callback_data="wallet:deposit_menu")],
                        [InlineKeyboardButton(t("btn_back", lang), callback_data="account:vip")]
                    ])
                    await render_screen(client, callback, text, keyboard)
                    return

                # 2. Obtener usuario para actualizar su vigencia VIP
                user_stmt = select(User).where(User.telegram_id == user_id)
                u_res = await session.execute(user_stmt)
                user = u_res.scalar_one()

                lang = getattr(user, "language", "es") or "es"

                if user.is_vip and user.vip_expires_at and user.vip_expires_at > now:
                    # Si ya estaba activo, se le suman 30 días a su fecha existente
                    new_expiry = user.vip_expires_at + timedelta(days=settings.VIP_DURATION_DAYS)
                else:
                    new_expiry = now + timedelta(days=settings.VIP_DURATION_DAYS)

                user.is_vip = True
                user.vip_expires_at = new_expiry
                user.vip_warned_24h = False
                user.vip_warned_2h = False

                await session.commit()
                rem_bal = float(remaining_balance)

            # 3. Notificar en el canal de auditoría del Owner
            await audit_logger.log_system_alert(
                client=client,
                title="👑 NUEVA MEMBRESÍA VIP ACTIVADA",
                details=(
                    f"👤 <b>Usuario:</b> <code>{user_id}</code> (@{callback.from_user.username or 'N/A'})\n"
                    f"💵 <b>Cobro:</b> <code>${VIP_PRICE_USDT} USDT</code>\n"
                    f"💳 <b>Saldo Restante:</b> <code>${rem_bal:.2f} USDT</code>\n"
                    f"📅 <b>Válido Hasta:</b> <code>{new_expiry.strftime('%Y-%m-%d %H:%M UTC')}</code>"
                )
            )

            exp_str = new_expiry.strftime("%Y-%m-%d %H:%M UTC")
            success_text = t("vip_success_activated", lang, expires_at=exp_str)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")],
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
            ])

            try:
                await callback.answer("⭐ ¡Membresía VIP Activada!", show_alert=True)
            except Exception:
                pass

            await render_screen(client, callback, success_text, keyboard)

        finally:
            _ACTIVE_VIP_TRANSACTIONS.discard(user_id)

    @app.on_callback_query(filters.regex(r"^vip:copy_client:(\d+)$"))
    async def cb_vip_copy_client(client: Client, callback: CallbackQuery):
        """Genera y envía una plantilla limpia y neutral lista para reenviar a clientes de WhatsApp"""
        user_id = callback.from_user.id
        order_id = int(callback.matches[0].group(1))

        async with async_session() as session:
            stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
            res = await session.execute(stmt)
            order = res.scalar_one_or_none()

            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

        if not order:
            await callback.answer("❌ Pedido no encontrado.", show_alert=True)
            return

        warranty_line = f"\n🛡️ <b>Garantía:</b> <code>{order.warranty_hours} horas</code>" if order.warranty_hours > 0 else ""

        template_text = t(
            "vip_client_template",
            lang,
            product=order.product_name,
            items=order.delivered_items,
            warranty_text=warranty_line,
            after_note=""
        )

        try:
            # Enviar mensaje limpio separado para facilitar el copiado con 1 toque
            await client.send_message(
                chat_id=user_id,
                text=parse_emojis(template_text),
                parse_mode=ParseMode.HTML
            )
            await callback.answer("📋 Mensaje para cliente enviado abajo para fácil copiado.", show_alert=True)
        except Exception as e:
            await callback.answer(f"Error: {e}", show_alert=True)

    @app.on_message(filters.command(["vip"]) & filters.private)
    async def cmd_admin_vip(client: Client, message: Message):
        """
        Comando exclusivo de administrador para otorgar membresía VIP manual.
        Sintaxis: /vip <@usuario|user_id> <dias>
        Ejemplo: /vip @revendedor 15
        """
        if not message.from_user or not is_admin(message.from_user.id):
            return

        user_id = message.from_user.id

        try:
            await message.delete()
        except Exception:
            pass

        args = message.command[1:]
        if len(args) < 2:
            await client.send_message(
                chat_id=user_id,
                text=parse_emojis(
                    "❌ <b>Uso incorrecto del comando:</b>\n"
                    "Sintaxis: <code>/vip &lt;@usuario o ID&gt; &lt;dias&gt;</code>\n"
                    "Ejemplo: <code>/vip @revendedor 15</code>\n"
                    "Ejemplo: <code>/vip 123456789 30</code>"
                ),
                parse_mode=ParseMode.HTML
            )
            return

        target_str = args[0].strip()
        days_str = args[1].strip()

        if not days_str.isdigit() or not (1 <= int(days_str) <= 3650):
            await client.send_message(
                chat_id=user_id,
                text=parse_emojis("❌ <b>Los días deben ser un número entero entre 1 y 3650 (máximo 10 años).</b>"),
                parse_mode=ParseMode.HTML
            )
            return

        grant_days = int(days_str)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        async with async_session() as session:
            target_user = await find_user_by_identifier(session, target_str)

            if not target_user:
                await client.send_message(
                    chat_id=user_id,
                    text=parse_emojis(f"❌ No se encontró ningún usuario con: <code>{target_str}</code>."),
                    parse_mode=ParseMode.HTML
                )
                return

            target_user_id = target_user.telegram_id
            target_lang = getattr(target_user, "language", "es") or "es"

            # Sumar días si ya tenía activo o establecer desde now
            if target_user.is_vip and target_user.vip_expires_at and target_user.vip_expires_at > now:
                new_expiry = target_user.vip_expires_at + timedelta(days=grant_days)
            else:
                new_expiry = now + timedelta(days=grant_days)

            target_user.is_vip = True
            target_user.vip_expires_at = new_expiry
            target_user.vip_warned_24h = False
            target_user.vip_warned_2h = False

            await session.commit()

        # Notificar al administrador
        exp_fmt = new_expiry.strftime("%Y-%m-%d %H:%M UTC")
        await client.send_message(
            chat_id=user_id,
            text=parse_emojis(
                f"✅ <b>¡Membresía VIP Otorgada con Éxito!</b>\n\n"
                f"👤 <b>Usuario:</b> <code>{target_user_id}</code> (@{target_user.username or 'N/A'})\n"
                f"⏳ <b>Días Asignados:</b> <code>+{grant_days} días</code>\n"
                f"📅 <b>Nueva Fecha de Expiración:</b> <code>{exp_fmt}</code>"
            ),
            parse_mode=ParseMode.HTML
        )

        # Enviar DM al usuario avisándole del regalo/acceso VIP
        try:
            dm_text = t("vip_admin_granted_msg", target_lang, days=grant_days, expires_at=exp_fmt)
            dm_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_catalog", target_lang), callback_data="catalog:disponibles:1")],
                [InlineKeyboardButton(t("btn_main_menu", target_lang), callback_data="menu_main")]
            ])
            await client.send_message(
                chat_id=target_user_id,
                text=parse_emojis(dm_text),
                reply_markup=parse_keyboard(dm_kb),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

        # Registrar en el canal de auditoría del Owner
        await audit_logger.log_system_alert(
            client=client,
            title="👑 MEMBRESÍA VIP MANUAL OTORGADA POR ADMIN",
            details=(
                f"⚙️ <b>Admin:</b> <code>{user_id}</code>\n"
                f"👤 <b>Beneficiario:</b> <code>{target_user_id}</code> (@{target_user.username or 'N/A'})\n"
                f"⏳ <b>Días:</b> <code>{grant_days}</code>\n"
                f"📅 <b>Vence:</b> <code>{exp_fmt}</code>"
            )
        )
