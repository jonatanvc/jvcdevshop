from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Order, Setting
from bot.services.bunai_client import bunai_api
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.i18n import t, LANGUAGES
from bot.services.audit_logger import audit_logger

def get_main_menu_keyboard(user_id: int, lang: str = "es") -> InlineKeyboardMarkup:
    """Genera la botonera inline del menú principal traducida"""
    buttons = [
        [
            InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:disponibles:1")
        ],
        [
            InlineKeyboardButton(t("btn_deposit", lang), callback_data="wallet:deposit_menu"),
            InlineKeyboardButton(t("btn_my_orders", lang), callback_data="orders:page:1")
        ],
        [
            InlineKeyboardButton(t("btn_referrals", lang), callback_data="referrals:view"),
            InlineKeyboardButton(t("btn_profile", lang), callback_data="account:view")
        ],
        [
            InlineKeyboardButton(t("btn_support", lang), callback_data="support:view")
        ]
    ]

    # Botón exclusivo para administradores
    if user_id in settings.admin_ids:
        buttons.append([
            InlineKeyboardButton(t("btn_admin", lang), callback_data="admin:menu")
        ])

    return InlineKeyboardMarkup(buttons)

async def build_main_menu_text(user: User, orders_count: int, session) -> str:
    """Genera el texto de bienvenida del menú principal traducido"""
    lang = user.language or "es"
    m_stmt = select(Setting).where(Setting.key == "maintenance_mode")
    m_res = await session.execute(m_stmt)
    m_setting = m_res.scalar_one_or_none()
    maintenance_banner = ""
    if m_setting and m_setting.value == "true":
        maintenance_banner = t("maintenance_banner", lang)

    user_name = user.first_name or user.username or f"Usuario {user.telegram_id}"

    bunai_line = ""
    if user.telegram_id in settings.admin_ids:
        bunai_data = await bunai_api.get_me()
        bunai_balance = float(bunai_data.get("balance", 0.0))
        bunai_line = f"🏢 <b>{t('balance_provider', lang)}:</b> <code>${bunai_balance:.2f} USD</code>\n"

    text = (
        f"{maintenance_banner}"
        f"{t('welcome_header', lang)}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{t('user_label', lang)}:</b> {user_name}\n"
        f"🆔 <b>ID:</b> <code>{user.telegram_id}</code>\n"
        f"💰 <b>{t('balance_bot', lang)}:</b> <code>${float(user.balance):.2f} USDT</code>\n"
        f"{bunai_line}"
        f"🛍️ <b>{t('orders_made', lang)}:</b> <code>{orders_count}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>{t('select_option', lang)}</i>"
    )
    return text

def build_language_picker_keyboard(current_lang: str) -> InlineKeyboardMarkup:
    """Construye la botonera para seleccionar idioma con marca activa"""
    buttons = []
    for code, name in LANGUAGES.items():
        is_active = "✅ " if code == current_lang else ""
        buttons.append([
            InlineKeyboardButton(f"{is_active}{name} ({code.upper()})", callback_data=f"account:set_lang:{code}")
        ])
    buttons.append([
        InlineKeyboardButton(t("btn_back", current_lang), callback_data="account:view")
    ])
    return InlineKeyboardMarkup(buttons)

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
                    language="es",
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
            keyboard = get_main_menu_keyboard(user_id, user.language)

            await render_screen(client, user_id, text, keyboard)

    @app.on_callback_query(filters.regex("^menu_main$"))
    async def cb_main_menu(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            await callback.answer("⏳ ...", show_alert=False)
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
                    balance=0.0000,
                    language="es"
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

            order_count_stmt = select(func.count(Order.id)).where(Order.user_id == user_id)
            order_count_res = await session.execute(order_count_stmt)
            orders_count = order_count_res.scalar() or 0

            text = await build_main_menu_text(user, orders_count, session)
            keyboard = get_main_menu_keyboard(user_id, user.language)

            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex("^account:view$"))
    async def cb_account_view(client: Client, callback: CallbackQuery):
        """Pantalla de Perfil de Usuario con soporte de idioma"""
        user_id = callback.from_user.id
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return

            lang = user.language or "es"
            reg_date = user.created_at.strftime("%Y-%m-%d")

            bunai_owner_line = ""
            if user_id in settings.admin_ids:
                bunai_data = await bunai_api.get_me()
                bunai_bal = float(bunai_data.get("balance", 0.0))
                bunai_owner_line = f"🏢 <b>{t('balance_provider', lang)}:</b> <code>${bunai_bal:.2f} USD</code>\n"

            text = (
                f"{t('profile_title', lang)}\n\n"
                f"👤 <b>ID:</b> <code>{user.telegram_id}</code>\n"
                f"👛 <b>{t('balance_bot', lang)}:</b> <code>{float(user.balance):.2f} USDT</code>\n"
                f"{bunai_owner_line}"
                f"🗣️ <b>{t('lang_label', lang)}:</b> <code>{lang.upper()}</code> ({LANGUAGES.get(lang, 'Español')})\n"
                f"🌐 <b>Timezone:</b> <code>UTC+00:00</code>\n"
                f"📅 <b>{t('registered', lang)}:</b> <code>{reg_date}</code>"
            )

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(t("btn_my_orders", lang), callback_data="orders:page:1"),
                    InlineKeyboardButton(t("btn_language", lang), callback_data="account:language")
                ],
                [
                    InlineKeyboardButton(t("btn_back", lang), callback_data="menu_main")
                ]
            ])

            await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex("^account:language$"))
    async def cb_account_language(client: Client, callback: CallbackQuery):
        """Muestra el menú interactivo para elegir idioma (ES, EN, PT)"""
        user_id = callback.from_user.id
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            current_lang = user.language if user else "es"

        text = t("lang_select_title", current_lang)
        keyboard = build_language_picker_keyboard(current_lang)
        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^account:set_lang:(es|en|pt)$"))
    async def cb_set_language(client: Client, callback: CallbackQuery):
        """Actualiza el idioma del usuario en la base de datos"""
        new_lang = callback.matches[0].group(1)
        user_id = callback.from_user.id

        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                user.language = new_lang
                await session.commit()

        lang_name = LANGUAGES.get(new_lang, new_lang.upper())
        await callback.answer(t("lang_changed", new_lang, lang_name=lang_name), show_alert=True)
        # Re-renderizar el perfil con el nuevo idioma seleccionado
        await cb_account_view(client, callback)

    @app.on_callback_query(filters.regex("^support:view$"))
    async def cb_support_view(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            lang = user.language if user else "es"

        text = t("support_text", lang)
        admin_tg_url = f"tg://user?id={settings.admin_ids[0]}" if settings.admin_ids else "https://t.me/telegram"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_contact_admin", lang), url=admin_tg_url)],
            [InlineKeyboardButton(t("btn_back", lang), callback_data="menu_main")]
        ])
        await render_screen(client, callback, text, keyboard)
