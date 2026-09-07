from decimal import Decimal
from datetime import datetime, timedelta, timezone
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

VIP_PRICE_USDT = Decimal(str(settings.VIP_MONTHLY_PRICE_USDT))

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
                    [InlineKeyboardButton(t("btn_renew_vip", lang), callback_data="vip:activate")],
                    [InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")],
                    [InlineKeyboardButton(t("btn_back", lang), callback_data="account:view")]
                ])
            else:
                text = t("vip_info_title", lang)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_activate_vip", lang), callback_data="vip:activate")],
                    [InlineKeyboardButton(t("btn_back", lang), callback_data="account:view")]
                ])

            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^vip:activate$"))
    async def cb_vip_activate(client: Client, callback: CallbackQuery):
        """Procesa el cobro de 10 USDT de saldo del bot y activa/renueva la membresía VIP"""
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer("⏳ ...")
            return

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id).with_for_update()
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                return

            lang = getattr(user, "language", "es") or "es"

            # 1. Comprobar si el usuario tiene saldo suficiente (10 USDT)
            if user.balance < VIP_PRICE_USDT:
                text = t("vip_insufficient_funds", lang, balance=f"{float(user.balance):.2f}")
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_deposit", lang), callback_data="wallet:deposit_menu")],
                    [InlineKeyboardButton(t("btn_back", lang), callback_data="account:vip")]
                ])
                await render_screen(client, callback, text, keyboard)
                return

            # 2. Descontar 10 USDT y calcular nueva fecha de expiración
            user.balance -= VIP_PRICE_USDT
            user.total_spent += VIP_PRICE_USDT

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
            rem_bal = float(user.balance)

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
        user_id = message.from_user.id
        if not settings.is_owner(user_id) and user_id not in settings.admin_ids:
            return

        try:
            await message.delete()
        except Exception:
            pass

        args = message.command[1:]
        if len(args) < 2:
            await message.reply_text(
                "❌ <b>Uso incorrecto del comando:</b>\n"
                "Sintaxis: <code>/vip &lt;@usuario o ID&gt; &lt;dias&gt;</code>\n"
                "Ejemplo: <code>/vip @revendedor 15</code>\n"
                "Ejemplo: <code>/vip 123456789 30</code>",
                parse_mode=ParseMode.HTML
            )
            return

        target_str = args[0].strip()
        days_str = args[1].strip()

        if not days_str.isdigit() or int(days_str) <= 0:
            await message.reply_text("❌ Los días deben ser un número entero mayor a 0.", parse_mode=ParseMode.HTML)
            return

        grant_days = int(days_str)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        async with async_session() as session:
            # Buscar usuario por ID o por username
            if target_str.isdigit():
                stmt = select(User).where(User.telegram_id == int(target_str))
            else:
                uname = target_str.lstrip("@").lower()
                stmt = select(User).where(User.username.ilike(uname))

            res = await session.execute(stmt)
            target_user = res.scalar_one_or_none()

            if not target_user:
                await message.reply_text(f"❌ No se encontró ningún usuario con: <code>{target_str}</code>.", parse_mode=ParseMode.HTML)
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
        await message.reply_text(
            f"✅ <b>¡Membresía VIP Otorgada con Éxito!</b>\n\n"
            f"👤 <b>Usuario:</b> <code>{target_user_id}</code> (@{target_user.username or 'N/A'})\n"
            f"⏳ <b>Días Asignados:</b> <code>+{grant_days} días</code>\n"
            f"📅 <b>Nueva Fecha de Expiración:</b> <code>{exp_fmt}</code>",
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
