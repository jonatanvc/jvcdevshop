from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Order, Setting
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.services.audit_logger import audit_logger

def get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Genera la botonera inline del menú principal"""
    buttons = [
        [
            InlineKeyboardButton("🛒 Catálogo de Servicios", callback_data="catalog:disponibles:1")
        ],
        [
            InlineKeyboardButton("💳 Depositar USDT", callback_data="wallet:deposit_menu"),
            InlineKeyboardButton("💼 Mis Pedidos", callback_data="orders:page:1")
        ],
        [
            InlineKeyboardButton("🔗 Referidos & Ganar", callback_data="referrals:view"),
            InlineKeyboardButton("👤 Mi Perfil", callback_data="account:view")
        ],
        [
            InlineKeyboardButton("🆘 Soporte & Ayuda", callback_data="support:view")
        ]
    ]

    # Botón exclusivo para administradores
    if user_id in settings.admin_ids:
        buttons.append([
            InlineKeyboardButton("⚙️ Panel de Administración", callback_data="admin:menu")
        ])

    return InlineKeyboardMarkup(buttons)

async def build_main_menu_text(user: User, orders_count: int, session) -> str:
    """Genera el texto de bienvenida del menú principal"""
    m_stmt = select(Setting).where(Setting.key == "maintenance_mode")
    m_res = await session.execute(m_stmt)
    m_setting = m_res.scalar_one_or_none()
    maintenance_banner = ""
    if m_setting and m_setting.value == "true":
        maintenance_banner = "⚠️ <i>El bot está en modo mantenimiento. Las compras están pausadas temporalmente.</i>\n\n"

    user_name = user.first_name or user.username or f"Usuario {user.telegram_id}"

    text = (
        f"{maintenance_banner}"
        f"💎 <b>BIENVENIDO A SERVICIOS DIGITALES</b> 💎\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Usuario:</b> {user_name}\n"
        f"🆔 <b>ID:</b> <code>{user.telegram_id}</code>\n"
        f"💰 <b>Saldo Disponible:</b> <code>${float(user.balance):.2f} USDT</code>\n"
        f"🛍️ <b>Compras Realizadas:</b> <code>{orders_count}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Selecciona una opción del menú inferior para comenzar:</i>"
    )
    return text

def register_start_handlers(app: Client):

    @app.on_message(filters.command("start") & filters.private)
    async def cmd_start(client: Client, message: Message):
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name or "Usuario"

        # Borrar el comando /start del usuario para mantener 1 solo mensaje
        try:
            await message.delete()
        except Exception:
            pass

        # Procesar código de referido si existe (/start ref_123456)
        referrer_id = None
        if len(message.command) > 1:
            arg = message.command[1]
            if arg.startswith("ref_") and arg[4:].isdigit():
                ref_candidate = int(arg[4:])
                if ref_candidate != user_id:
                    referrer_id = ref_candidate

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    telegram_id=user_id,
                    username=username,
                    first_name=first_name,
                    balance=0.0000,
                    referred_by=referrer_id
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

                await audit_logger.log_new_user(client, user_id, username, first_name)
            else:
                user.username = username
                user.first_name = first_name
                await session.commit()

            order_count_stmt = select(func.count(Order.id)).where(Order.user_id == user_id)
            order_count_res = await session.execute(order_count_stmt)
            orders_count = order_count_res.scalar() or 0

            text = await build_main_menu_text(user, orders_count, session)
            keyboard = get_main_menu_keyboard(user_id)

            await render_screen(client, user_id, text, keyboard)

    @app.on_callback_query(filters.regex("^menu_main$"))
    async def cb_main_menu(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer("⏳ Por favor espera un momento...", show_alert=False)
            return

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    telegram_id=user_id,
                    username=callback.from_user.username,
                    first_name=callback.from_user.first_name or "Usuario",
                    balance=0.0000
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

            order_count_stmt = select(func.count(Order.id)).where(Order.user_id == user_id)
            order_count_res = await session.execute(order_count_stmt)
            orders_count = order_count_res.scalar() or 0

            text = await build_main_menu_text(user, orders_count, session)
            keyboard = get_main_menu_keyboard(user_id)

            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex("^account:view$"))
    async def cb_account_view(client: Client, callback: CallbackQuery):
        """Pantalla de Perfil de Usuario idéntica a la Foto 1 de referencia"""
        user_id = callback.from_user.id
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return

            reg_date = user.created_at.strftime("%Y-%m-%d")

            text = (
                f"👤 <b>Perfil de Usuario</b>\n\n"
                f"👤 <b>ID:</b> <code>{user.telegram_id}</code>\n"
                f"👛 <b>Saldo:</b> <code>{float(user.balance):.2f} USDT</code>\n"
                f"🗣️ <b>Idioma:</b> <code>ES</code>\n"
                f"🌐 <b>Timezone:</b> <code>UTC+00:00</code>\n"
                f"📅 <b>Registro:</b> <code>{reg_date}</code>"
            )

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💼 Mis Pedidos", callback_data="orders:page:1"),
                    InlineKeyboardButton("🗣️ Idioma", callback_data="account:language")
                ],
                [
                    InlineKeyboardButton("Volver", callback_data="menu_main")
                ]
            ])

            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex("^account:language$"))
    async def cb_account_language(client: Client, callback: CallbackQuery):
        await callback.answer("🗣️ Idioma actual: Español (ES)", show_alert=True)

    @app.on_callback_query(filters.regex("^support:view$"))
    async def cb_support_view(client: Client, callback: CallbackQuery):
        text = (
            f"🆘 <b>SOPORTE & AYUDA</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"¿Tienes alguna duda sobre tus compras, depósitos o necesitas asistencia?\n\n"
            f"• <b>Garantía:</b> Si algún servicio con garantía presenta inconvenientes durante el período activo, contáctanos inmediatamente con tu <b>ID de Orden</b>.\n"
            f"• <b>Depósitos:</b> Los depósitos en USDT BEP-20 se acreditan automáticamente tras la confirmación de la red.\n\n"
            f"💬 <i>Para contactar directamente a un administrador pulsa el botón inferior:</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Contactar Administrador", url=f"tg://user?id={settings.admin_ids[0]}" if settings.admin_ids else "https://t.me/telegram")],
            [InlineKeyboardButton("Volver", callback_data="menu_main")]
        ])
        await render_screen(client, callback, text, keyboard)
