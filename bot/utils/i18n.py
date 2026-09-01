from typing import Dict, Any

LANGUAGES = {
    "es": "🇪🇸 Español",
    "en": "🇺🇸 English",
    "pt": "🇧🇷 Português"
}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "es": {
        "welcome_header": "💎 <b>BIENVENIDO A SERVICIOS DIGITALES</b> 💎",
        "user_label": "Usuario",
        "balance_bot": "Saldo en Bot",
        "balance_provider": "Saldo Proveedor (Bunai)",
        "orders_made": "Compras Realizadas",
        "select_option": "Selecciona una opción del menú inferior para comenzar:",
        "btn_catalog": "🛒 Catálogo de Servicios",
        "btn_deposit": "💳 Depositar USDT",
        "btn_my_orders": "💼 Mis Pedidos",
        "btn_referrals": "🔗 Referidos & Ganar",
        "btn_profile": "👤 Mi Perfil",
        "btn_support": "🆘 Soporte & Ayuda",
        "btn_admin": "⚙️ Panel de Administración",
        "profile_title": "👤 <b>Perfil de Usuario</b>",
        "lang_label": "Idioma",
        "registered": "Registro",
        "btn_language": "🗣️ Idioma",
        "btn_back": "Volver",
        "lang_select_title": "🌐 <b>SELECCIONA TU IDIOMA PREFERIDO</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Elige el idioma con el que deseas utilizar el bot:</i>",
        "lang_changed": "✅ Idioma actualizado a: {lang_name}"
    },
    "en": {
        "welcome_header": "💎 <b>WELCOME TO DIGITAL SERVICES</b> 💎",
        "user_label": "User",
        "balance_bot": "Bot Balance",
        "balance_provider": "Provider Balance (Bunai)",
        "orders_made": "Completed Orders",
        "select_option": "Select an option from the menu below to get started:",
        "btn_catalog": "🛒 Service Catalog",
        "btn_deposit": "💳 Deposit USDT",
        "btn_my_orders": "💼 My Orders",
        "btn_referrals": "🔗 Referrals & Earn",
        "btn_profile": "👤 My Profile",
        "btn_support": "🆘 Support & Help",
        "btn_admin": "⚙️ Admin Panel",
        "profile_title": "👤 <b>User Profile</b>",
        "lang_label": "Language",
        "registered": "Registered",
        "btn_language": "🗣️ Language",
        "btn_back": "Back",
        "lang_select_title": "🌐 <b>SELECT YOUR PREFERRED LANGUAGE</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Choose the language you want to use with the bot:</i>",
        "lang_changed": "✅ Language updated to: {lang_name}"
    },
    "pt": {
        "welcome_header": "💎 <b>BEM-VINDO AOS SERVIÇOS DIGITAIS</b> 💎",
        "user_label": "Usuário",
        "balance_bot": "Saldo no Bot",
        "balance_provider": "Saldo Provedor (Bunai)",
        "orders_made": "Compras Realizadas",
        "select_option": "Selecione uma opção no menu abaixo para começar:",
        "btn_catalog": "🛒 Catálogo de Serviços",
        "btn_deposit": "💳 Depositar USDT",
        "btn_my_orders": "💼 Meus Pedidos",
        "btn_referrals": "🔗 Indicar & Ganhar",
        "btn_profile": "👤 Meu Perfil",
        "btn_support": "🆘 Suporte & Ajuda",
        "btn_admin": "⚙️ Painel de Administração",
        "profile_title": "👤 <b>Perfil de Usuário</b>",
        "lang_label": "Idioma",
        "registered": "Registro",
        "btn_language": "🗣️ Idioma",
        "btn_back": "Voltar",
        "lang_select_title": "🌐 <b>SELECIONE SEU IDIOMA PREFERIDO</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Escolha o idioma que deseja usar no bot:</i>",
        "lang_changed": "✅ Idioma atualizado para: {lang_name}"
    }
}

def t(key: str, lang: str = "es", **kwargs) -> str:
    """Obtiene el texto traducido para la clave e idioma solicitados"""
    lang_code = lang.lower() if lang else "es"
    if lang_code not in TRANSLATIONS:
        lang_code = "es"
    
    text = TRANSLATIONS[lang_code].get(key, TRANSLATIONS["es"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
