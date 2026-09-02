import asyncio
from decimal import Decimal
from typing import Dict, Any, Optional
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Order, Deposit, DepositStatus, Setting
from bot.services.bunai_client import bunai_api
from bot.services.pricing import pricing_service
from bot.services.backup_service import backup_service
from bot.services.audit_logger import audit_logger
from bot.utils.navigation import render_screen

ADMIN_STATES: Dict[int, Dict[str, Any]] = {}

def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids

async def find_user_by_identifier(session, identifier: str) -> Optional[User]:
    """Busca un usuario por @username (case-insensitive) o por telegram_id numérico."""
    clean_id = identifier.strip()
    if clean_id.startswith("@"):
        uname = clean_id[1:].strip().lower()
        stmt = select(User).where(func.lower(User.username) == uname)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()
    elif clean_id.isdigit():
        tid = int(clean_id)
        stmt = select(User).where(User.telegram_id == tid)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()
    else:
        stmt = select(User).where(func.lower(User.username) == clean_id.lower())
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

async def show_admin_panel(client: Client, target: Any, user_id: int):
    async with async_session() as session:
        users_res = await session.execute(select(func.count(User.telegram_id)))
        total_users = users_res.scalar() or 0

        orders_res = await session.execute(select(func.count(Order.id), func.sum(Order.total_price)))
        total_orders, total_sales = orders_res.first()
        total_sales = float(total_sales or 0.0)

        dep_res = await session.execute(
            select(func.sum(Deposit.exact_amount)).where(Deposit.status == DepositStatus.CONFIRMED)
        )
        total_deposited = float(dep_res.scalar() or 0.0)

        m_res = await session.execute(select(Setting).where(Setting.key == "maintenance_mode"))
        m_setting = m_res.scalar_one_or_none()
        maintenance_active = m_setting.value == "true" if m_setting else False

    bunai_profile = await bunai_api.get_me()
    bunai_balance = float(bunai_profile.get("balance", 0.0))
    bunai_spent = float(bunai_profile.get("api_spent", 0.0))

    balance_alert = " ⚠️ <i>¡Recarga recomendada!</i>" if bunai_balance < 10.0 else " ✅"

    text = (
        f"⚙️ <b>PANEL DE ADMINISTRACIÓN & MÉTRICAS</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 <b>Usuarios Totales:</b> <code>{total_users}</code>\n"
        f"💳 <b>Total Depositado (USDT):</b> <code>${total_deposited:.2f}</code>\n"
        f"🛍️ <b>Ventas Realizadas:</b> <code>{total_orders} pedidos</code> (${total_sales:.2f} USDT)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏢 <b>Saldo en BunaiStore:</b> <code>${bunai_balance:.2f} USD</code>{balance_alert}\n"
        f"📉 <b>Gasto Total en Proveedor:</b> <code>${bunai_spent:.2f} USD</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 <b>ESTRATEGIA DE PRECIOS ACTIVA:</b>\n"
        f"• <b>Costo &lt; $0.50:</b> <code>x7.0 (+600%)</code>\n"
        f"• <b>Costo $0.50 - $0.99:</b> <code>x4.0 (+300%)</code>\n"
        f"• <b>Costo $1.00 - $2.99:</b> <code>x2.5 (+150%)</code>\n"
        f"• <b>Costo &ge; $3.00:</b> <code>x2.0 (+100%)</code>\n"
        f"🛡️ <b>Garantías:</b> <code>50% de BunaiStore</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🛠️ <b>Modo Mantenimiento:</b> <code>{'🔴 ACTIVADO' if maintenance_active else '🟢 DESACTIVADO'}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>Selecciona una acción administrativa:</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🛠️ {'Desactivar' if maintenance_active else 'Activar'} Mantenimiento", callback_data="admin:toggle_maintenance"),
            InlineKeyboardButton("🔄 Sincronizar Catálogo", callback_data="admin:clear_cache")
        ],
        [
            InlineKeyboardButton("📢 Enviar Difusión (Broadcast)", callback_data="admin:broadcast"),
            InlineKeyboardButton("💾 Backup BD", callback_data="admin:download_backup")
        ],
        [
            InlineKeyboardButton("Volver", callback_data="menu_main")
        ]
    ])

    await render_screen(client, target, text, keyboard)

def register_admin_handlers(app: Client):

    @app.on_message(filters.command("del") & filters.private)
    async def cmd_del_balance(client: Client, message: Message):
        user_id = message.from_user.id
        if not is_admin(user_id):
            return

        try:
            await message.delete()
        except Exception:
            pass

        if len(message.command) < 2:
            help_text = (
                "⚠️ <b>Uso correcto del comando:</b>\n"
                "<code>/del @usuario</code> o <code>/del 123456789</code>\n\n"
                "<i>Este comando restablece el saldo del usuario a 0.00 USDT.</i>"
            )
            await client.send_message(chat_id=user_id, text=help_text)
            return

        target_ident = message.command[1].strip()
        async with async_session() as session:
            user = await find_user_by_identifier(session, target_ident)
            if not user:
                await client.send_message(
                    chat_id=user_id,
                    text=f"❌ <b>Usuario no encontrado:</b> No se encontró a ningún usuario con el identificador <code>{target_ident}</code> en la base de datos."
                )
                return

            old_balance = float(user.balance)
            user.balance = Decimal("0.0000")
            target_uid = user.telegram_id
            target_uname = user.username or "N/A"
            lang = user.language or "es"
            await session.commit()

        # Notificar al Administrador
        conf_text = (
            "🗑️ <b>SALDO RESTABLECIDO A CERO</b>\n"
            "━━━━━━━━━━━━━━━\n"
            f"👤 <b>Usuario:</b> <code>{target_uid}</code> (@{target_uname})\n"
            f"💰 <b>Saldo Anterior:</b> <code>${old_balance:.2f} USDT</code>\n"
            f"👛 <b>Saldo Actual:</b> <code>$0.00 USDT</code>"
        )
        await client.send_message(chat_id=user_id, text=conf_text)

        # Notificar por DM al usuario
        try:
            user_dm_text = (
                "⚠️ <b>Aviso de Billetera:</b>\n"
                "━━━━━━━━━━━━━━━\n"
                "Tu saldo ha sido restablecido a <code>0.00 USDT</code> por la administración."
            )
            if lang == "en":
                user_dm_text = (
                    "⚠️ <b>Wallet Notice:</b>\n"
                    "━━━━━━━━━━━━━━━\n"
                    "Your balance has been reset to <code>0.00 USDT</code> by administration."
                )
            elif lang == "pt":
                user_dm_text = (
                    "⚠️ <b>Aviso de Carteira:</b>\n"
                    "━━━━━━━━━━━━━━━\n"
                    "Seu saldo foi redefinido para <code>0.00 USDT</code> pela administração."
                )
            await client.send_message(chat_id=target_uid, text=user_dm_text)
        except Exception:
            pass

        # Canal de auditoría
        await audit_logger.log_system_alert(
            client=client,
            title="SALDO DE USUARIO RESTABLECIDO A CERO",
            details=(
                f"👮‍♂️ <b>Admin:</b> <code>{user_id}</code>\n"
                f"👤 <b>Usuario:</b> <code>{target_uid}</code> (@{target_uname})\n"
                f"💰 <b>Saldo Removido:</b> <code>${old_balance:.2f} USDT</code>\n"
                f"👛 <b>Saldo Actual:</b> <code>$0.00 USDT</code>"
            )
        )

    @app.on_message(filters.command("dep") & filters.private)
    async def cmd_dep_balance(client: Client, message: Message):
        user_id = message.from_user.id
        if not is_admin(user_id):
            return

        try:
            await message.delete()
        except Exception:
            pass

        if len(message.command) < 3:
            help_text = (
                "⚠️ <b>Uso correcto del comando:</b>\n"
                "<code>/dep 5.50 @usuario</code> o <code>/dep 5.50 123456789</code>\n\n"
                "<i>Añade saldo en USDT directamente a la billetera del usuario.</i>"
            )
            await client.send_message(chat_id=user_id, text=help_text)
            return

        arg1 = message.command[1].strip()
        arg2 = message.command[2].strip()

        # Permitir tanto /dep 5.50 @user como /dep @user 5.50
        amount = None
        target_ident = None

        try:
            amount = float(arg1.replace(",", "."))
            target_ident = arg2
        except ValueError:
            try:
                amount = float(arg2.replace(",", "."))
                target_ident = arg1
            except ValueError:
                pass

        if amount is None or amount <= 0 or not target_ident:
            await client.send_message(
                chat_id=user_id,
                text="❌ <b>Monto inválido:</b> Asegúrate de indicar un monto numérico mayor a 0.\nEjemplo: <code>/dep 5.50 @usuario</code>"
            )
            return

        amount_dec = Decimal(f"{amount:.4f}")

        async with async_session() as session:
            user = await find_user_by_identifier(session, target_ident)
            if not user:
                await client.send_message(
                    chat_id=user_id,
                    text=f"❌ <b>Usuario no encontrado:</b> No se encontró a ningún usuario con el identificador <code>{target_ident}</code> en la base de datos."
                )
                return

            old_balance = float(user.balance)
            user.balance += amount_dec
            new_balance = float(user.balance)
            target_uid = user.telegram_id
            target_uname = user.username or "N/A"
            lang = user.language or "es"
            await session.commit()

        # Confirmación al Admin
        conf_text = (
            "✅ <b>SALDO AGREGADO EXITOSAMENTE</b>\n"
            "━━━━━━━━━━━━━━━\n"
            f"👤 <b>Usuario:</b> <code>{target_uid}</code> (@{target_uname})\n"
            f"➕ <b>Monto Añadido:</b> <code>+${amount:.2f} USDT</code>\n"
            f"💰 <b>Saldo Anterior:</b> <code>${old_balance:.2f} USDT</code>\n"
            f"👛 <b>Nuevo Saldo:</b> <code>${new_balance:.2f} USDT</code>"
        )
        await client.send_message(chat_id=user_id, text=conf_text)

        # Notificación por DM al Usuario
        try:
            user_dm_text = (
                "🎉 <b>¡Saldo Acreditado!</b>\n"
                "━━━━━━━━━━━━━━━\n"
                f"Se han añadido <b>+${amount:.2f} USDT</b> a tu saldo por la administración.\n"
                f"👛 <b>Tu Saldo Actual:</b> <code>${new_balance:.2f} USDT</code>"
            )
            if lang == "en":
                user_dm_text = (
                    "🎉 <b>Balance Credited!</b>\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"<b>+${amount:.2f} USDT</b> has been added to your balance by administration.\n"
                    f"👛 <b>Current Balance:</b> <code>${new_balance:.2f} USDT</code>"
                )
            elif lang == "pt":
                user_dm_text = (
                    "🎉 <b>Saldo Creditado!</b>\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"Foram adicionados <b>+${amount:.2f} USDT</b> ao seu saldo pela administração.\n"
                    f"👛 <b>Saldo Atual:</b> <code>${new_balance:.2f} USDT</code>"
                )
            await client.send_message(chat_id=target_uid, text=user_dm_text)
        except Exception:
            pass

        # Canal de Auditoría
        await audit_logger.log_system_alert(
            client=client,
            title="SALDO MANUAL AÑADIDO POR ADMIN",
            details=(
                f"👮‍♂️ <b>Admin:</b> <code>{user_id}</code>\n"
                f"👤 <b>Usuario:</b> <code>{target_uid}</code> (@{target_uname})\n"
                f"➕ <b>Monto Añadido:</b> <code>+${amount:.2f} USDT</code>\n"
                f"💰 <b>Saldo Anterior:</b> <code>${old_balance:.2f} USDT</code>\n"
                f"👛 <b>Nuevo Saldo:</b> <code>${new_balance:.2f} USDT</code>"
            )
        )

    @app.on_message(filters.command("admin") & filters.private)
    async def cmd_admin(client: Client, message: Message):
        user_id = message.from_user.id
        try:
            await message.delete()
        except Exception:
            pass
        if not is_admin(user_id):
            return
        await show_admin_panel(client, user_id, user_id)

    @app.on_callback_query(filters.regex("^admin:menu$"))
    async def cb_admin_menu(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            await callback.answer("⛔ Acceso denegado.", show_alert=True)
            return
        await show_admin_panel(client, callback, user_id)

    @app.on_callback_query(filters.regex("^admin:download_backup$"))
    async def cb_download_backup(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        await callback.answer("⏳ Generando backup...")
        await backup_service.send_automated_backup(client, chat_id=user_id)
        await callback.answer("✅ Backup enviado a tu chat privado.", show_alert=True)

    @app.on_callback_query(filters.regex("^admin:toggle_maintenance$"))
    async def cb_toggle_maintenance(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        async with async_session() as session:
            stmt = select(Setting).where(Setting.key == "maintenance_mode")
            res = await session.execute(stmt)
            setting = res.scalar_one_or_none()

            if not setting:
                setting = Setting(key="maintenance_mode", value="true")
                session.add(setting)
                new_state = True
            else:
                new_state = setting.value != "true"
                setting.value = "true" if new_state else "false"

            await session.commit()

        await callback.answer(f"Mantenimiento {'activado' if new_state else 'desactivado'}.")
        await cb_admin_menu(client, callback)

    @app.on_callback_query(filters.regex("^admin:clear_cache$"))
    async def cb_clear_cache(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        bunai_api.invalidate_cache()
        pricing_service.invalidate_cache()
        await callback.answer("✅ Catálogo sincronizado con BunaiStore.", show_alert=True)
        await cb_admin_menu(client, callback)

    @app.on_callback_query(filters.regex("^admin:broadcast$"))
    async def cb_broadcast_prompt(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        ADMIN_STATES[user_id] = {"action": "waiting_broadcast"}
        text = (
            "📢 <b>DIFUSIÓN MASIVA (BROADCAST)</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "Envía a continuación el mensaje que deseas transmitir a <b>todos los usuarios registrados</b> en el bot.\n\n"
            "<i>Puedes usar formato HTML (negritas, enlaces, etc).</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Volver", callback_data="admin:menu")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_message(filters.private & filters.text & ~filters.command(["start", "admin", "buscar", "search", "catalogo", "catalog", "pedidos", "orders", "depositar", "deposit", "saldo", "wallet", "soporte", "support", "ayuda", "help", "del", "dep"]), group=3)
    async def handle_admin_text(client: Client, message: Message):
        user_id = message.from_user.id
        if not is_admin(user_id):
            message.continue_propagation()
            return

        state = ADMIN_STATES.get(user_id)
        if not state:
            message.continue_propagation()
            return

        # Borrar el texto del administrador para mantener limpia la pantalla única
        try:
            await message.delete()
        except Exception:
            pass

        action = state.get("action")

        if action == "waiting_broadcast":
            ADMIN_STATES.pop(user_id, None)
            broadcast_text = message.text

            status_msg = await render_screen(client, user_id, "⏳ <b>Iniciando difusión masiva...</b>", None)

            async with async_session() as session:
                users_res = await session.execute(select(User.telegram_id))
                user_ids = users_res.scalars().all()

            sent_count = 0
            fail_count = 0

            for uid in user_ids:
                try:
                    await client.send_message(chat_id=uid, text=broadcast_text)
                    sent_count += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    fail_count += 1

            result_text = (
                f"✅ <b>DIFUSIÓN COMPLETADA</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"• <b>Entregados:</b> {sent_count}\n"
                f"• <b>Fallidos/Bloqueados:</b> {fail_count}"
            )
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Volver al Panel", callback_data="admin:menu")]])
            await render_screen(client, user_id, result_text, keyboard)
