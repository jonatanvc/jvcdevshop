import re
from io import BytesIO
from typing import Any, Optional, Tuple
from pyrogram.raw.core.primitives import Int, Long, String, Bytes
from pyrogram.raw.core import TLObject
from pyrogram.raw.all import objects
from pyrogram.types import InlineKeyboardButton as _PyrogramInlineKeyboardButton

def pe(emoji_id: str, fallback: str) -> str:
    """Retorna la etiqueta HTML de Telegram Custom Emoji compatible con Pyrogram"""
    return f'<emoji id={emoji_id}>{fallback}</emoji>'

# --- BOTONES Y MENÚS PRINCIPALES ---
# 40- Botón Catálogo - (5278413853577734640)
EMOJI_CART = pe("5278413853577734640", "🛒")

# 41- Botón Depositar - (5805550320985578625)
EMOJI_CARD = pe("5805550320985578625", "🪙")

# 42- Botón Mis Pedidos - (5211182849297762045)
EMOJI_ORDERS = pe("5211182849297762045", "💼")

# 43- Botón Referidos - (5846191689542145823)
EMOJI_LINK = pe("5846191689542145823", "🔗")

# 44- Botón Mi Perfil - (5208429100951159058)
EMOJI_USER = pe("5208429100951159058", "👤")

# 45- Botón Soporte - (5282843764451195532)
EMOJI_SUPPORT = pe("5282843764451195532", "🆘")

# 46- Botón Panel Admin - (5764638872000533034)
EMOJI_ADMIN = pe("5764638872000533034", "⚙️")

# 47- Botón Volver / Atrás - (5339226763673232550)
EMOJI_BACK = pe("5339226763673232550", "😀")

# 48- Botón Menú Principal - (6028171274939797252)
EMOJI_HOME = pe("6028171274939797252", "🏠")

# 49- Botón Buscar Servicio - (5334882760735598374)
EMOJI_SEARCH = pe("5334882760735598374", "🔍")

# 50- Botón Contactar Admin - (5242628160297641831)
EMOJI_CHAT = pe("5242628160297641831", "💬")

# 51- Botón Categorías - (5244807637157029775)
EMOJI_FOLDER = pe("5244807637157029775", "📁")

# 52- Filtro Disponibles - (5884106131822875141)
EMOJI_GREEN_DOT = pe("5884106131822875141", "🟢")

# 53- Filtro En Oferta - (5276398496008663230)
EMOJI_GIFT = pe("5276398496008663230", "🕶")

# 54- Filtro Agotados - (5470060791883374114)
EMOJI_RED_DOT = pe("5470060791883374114", "🔴")

# 55- Filtro Todos - (5406809207947142040)
EMOJI_MONITOR = pe("5406809207947142040", "🖥")

# 56- Botón Comprar Cantidad - (5778208881301787450)
EMOJI_BUY = pe("5778208881301787450", "🔣")

# 57- Botón Recargar Saldo - (5769248574499983619)
EMOJI_RECHARGE = pe("5769248574499983619", "🌟")

# 58- Botón Compartir Enlace - (5210952531676504517)
EMOJI_SHARE = pe("5210952531676504517", "🔗")

# 60- Botón Activar Alerta Stock - (5424818078833715060)
EMOJI_BELL = pe("5424818078833715060", "🔔")

# 61- Botón Cancelar Alerta Stock - (5767325541547904537)
EMOJI_BELL_OFF = pe("5767325541547904537", "🔕")

# 62- Botón Seguir Comprando - (5769248574499983619)
EMOJI_FINGER_UP = pe("5769248574499983619", "👆")

# 63- Botón Ingresar Otro Monto - (5424818078833715060)
EMOJI_WRITE = pe("5424818078833715060", "✍️")

# 64- Botón Ver Código QR - (5276220667182736079)
EMOJI_PHONE = pe("5276220667182736079", "📲")

# --- ELEMENTOS VISUALES ADICIONALES ---
# Encabezado principal de la tienda (jvcᵈᵉᵛ Store) - (5427168083074628963)
EMOJI_STORE = pe("5427168083074628963", "💎")

# ID de Usuario - (5884366771913233289)
EMOJI_ID = pe("5884366771913233289", "🆔")

# Saldo / Dinero - (5375296873982604963)
EMOJI_MONEY = pe("5375296873982604963", "💰")

# Proveedor BunaiStore - (5264733042710181045)
EMOJI_PROVIDER = pe("5264733042710181045", "🏢")

# Compras Realizadas - (5767288471685171967)
EMOJI_SHOPPING = pe("5767288471685171967", "🛍️")

# Actualizar Catálogo - (6030657343744644592)
EMOJI_REFRESH = pe("6030657343744644592", "🔄")

# Advertencia de Mantenimiento - (5276240711795107620)
EMOJI_WARN = pe("5276240711795107620", "⚠️")

# Billetera - (6030443364178992166)
EMOJI_WALLET = pe("6030443364178992166", "👛")

# Idioma - (5370765563226236970)
EMOJI_LANG = pe("5370765563226236970", "🗣️")

# Globo Terráqueo - (5447410659077661506)
EMOJI_GLOBE = pe("5447410659077661506", "🌐")

# Calendario / Fecha - (5413879192267805083)
EMOJI_CALENDAR = pe("5413879192267805083", "📅")

# Banderas de Idioma
EMOJI_FLAG_ES = pe("4916120627582076238", "🇪🇸")
EMOJI_FLAG_EN = pe("4916136269852968195", "🇺🇸")
EMOJI_FLAG_PT = pe("5224688610183228070", "🇧🇷")

# Operación Exitosa / Acreditado - (5208880351690112495)
EMOJI_CHECK = pe("5208880351690112495", "✅")

# Cancelado / Cruz - (5208429100951159058)
EMOJI_CROSS = pe("5208429100951159058", "❌")

# Producto / Caja - (5886285355279193209)
EMOJI_BOX = pe("5886285355279193209", "📦")

# Etiqueta de Precio - (5890883384057533697)
EMOJI_TAG = pe("5890883384057533697", "🏷️")

# Garantía del Producto - (5469641199348363998)
EMOJI_SHIELD = pe("5469641199348363998", "🛡️")

# Candado - (5276262671962892944)
EMOJI_LOCK = pe("5276262671962892944", "🔒")

# Cantidad Seleccionada en Calculadora / Stock - (5190741648237161191)
EMOJI_DICE = pe("5190741648237161191", "🎲")

# Panel de Mantenimiento / Herramientas - (6124926696161286141)
EMOJI_TOOLS = pe("6124926696161286141", "🛠️")

# Estrategia de Precios Activa / Alza - (5244837092042750681)
EMOJI_CHART_UP = pe("5244837092042750681", "📈")

# Monto Exacto a Enviar - (5310278924616356636)
EMOJI_TARGET = pe("5310278924616356636", "🎯")

# Tiempo Límite / Verificando Blockchain - (5451732530048802485)
EMOJI_HOURGLASS = pe("5451732530048802485", "⏳")

# Fiesta / Éxito - (5461151367559141950)
EMOJI_PARTY = pe("5461151367559141950", "🎉")

# Credenciales / Llave - (5330115548900501467)
EMOJI_KEY = pe("5330115548900501467", "🔑")

# Tip Informativo - (5397782960512444700)
EMOJI_IDEA = pe("5397782960512444700", "💡")

# Usuarios Totales - (5422439311196834318)
EMOJI_USERS = pe("5422439311196834318", "👥")

# Difusión Masiva (Broadcast) - (5372926953978341366)
EMOJI_BROADCAST = pe("5372926953978341366", "📢")

# Gasto en Proveedor - (5246762912428603768)
EMOJI_CHART_DOWN = pe("5246762912428603768", "📉")

# Nuevo Producto - (5118474816277447476)
EMOJI_SPARKLES = pe("5118474816277447476", "✨")

# 1- Mensajes y Pantallas - (5334882760735598374)
EMOJI_NOTE = pe("5334882760735598374", "📝")

# 2- Dirección de Billetera / Buzón - (4967677561032148287)
EMOJI_WALLET_ADDR = pe("4967677561032148287", "🌎")

# 3- Calculadora / Cantidad Seleccionada - (5472404950673791399)
EMOJI_CALC = pe("5472404950673791399", "🧮")

# 4- Estrella / Garantía - (5469641199348363998)
EMOJI_STAR = pe("5469641199348363998", "⭐️")

# 5- Chincheta / Info Adicional de Entrega - (5116161907669074775)
EMOJI_PIN = pe("5116161907669074775", "📌")

# 6 & 15- Disquete / Backup - (4990318000096675490)
EMOJI_DISK = pe("4990318000096675490", "💾")

# 7- Bandeja / Solicitud de Depósito - (5276220667182736079)
EMOJI_INBOX = pe("5276220667182736079", "📥")

# 8- Gráfico de Saldo Restante - (5431577498364158238)
EMOJI_BAR_CHART = pe("5431577498364158238", "📊")

# 9- Etiqueta de Nombre - (6244510079014409289)
EMOJI_NAME_TAG = pe("6244510079014409289", "✅")

# 10- Administrador - (5787467546596743616)
EMOJI_ADMIN_PERSON = pe("5787467546596743616", "🤭")

# Hora en Logs - (5276412364458059956)
EMOJI_CLOCK = pe("5276412364458059956", "⏰")

# Papelera
EMOJI_TRASH = "🗑️"

# --- SERVICIOS DIGITALES DEL CATÁLOGO (39 MARCAS) ---
SERVICE_EMOJIS = [
    # 1- Google / Gemini AI — 🤖 - (5310176773114197087)
    (["gemini", "google ai"], "5310176773114197087", "🤖"),
    # 2- Gmail / Cuentas Google 2FA — 🐁 - (5796209712009581332)
    (["gmail", "2fa gmail"], "5796209712009581332", "🐁"),
    # 3- Microsoft 365 / Office 365 — 📱 - (5372937764411031477)
    (["office365", "microsoft 365", "office 365", "microsoft"], "5372937764411031477", "📱"),
    # 4- OneDrive / Almacenamiento Cloud — 📱 - (5370857634440170316)
    (["onedrive"], "5370857634440170316", "📱"),
    # 5- Windows 10 / 11 — 💊 - (5798553402648565182)
    (["windows 10", "windows 11", "windows"], "5798553402648565182", "💊"),
    # 6- Outlook / Hotmail — 🛻 - (5796683820564484775)
    (["outlook", "hotmail"], "5796683820564484775", "🛻"),
    # 7- OpenAI / ChatGPT / Codex — 📱 - (5359726582447487916)
    (["chatgpt", "openai", "codex"], "5359726582447487916", "📱"),
    # 8- Claude AI / Anthropic — ⚙️ - (6124926696161286141)
    (["claude", "anthropic"], "6124926696161286141", "⚙️"),
    # 9- Netflix UHD 4K — 📱 - (5318911503938634641)
    (["netflix"], "5318911503938634641", "📱"),
    # 10- Spotify Premium — 📱 - (5346074681004801565)
    (["spotify"], "5346074681004801565", "📱"),
    # 11- YouTube Premium — 📱 - (5334681713316479679)
    (["youtube"], "5334681713316479679", "📱"),
    # 12- Amazon Prime Video — 📱 - (5346056560537779652)
    (["amazon prime", "prime video", "amazon"], "5346056560537779652", "📱"),
    # 13- Apple Music — 📱 - (5346251367369425932)
    (["apple music", "apple"], "5346251367369425932", "📱"),
    # 14- Crunchyroll Premium — ⚒ - (5796297333637387376)
    (["crunchyroll"], "5796297333637387376", "⚒"),
    # 15- Canva Pro / Canva Edu — 🥀 - (5796214303329620386)
    (["canva"], "5796214303329620386", "🥀"),
    # 16- CapCut Pro — 📱 - (5364339557712020484)
    (["capcut"], "5364339557712020484", "📱"),
    # 17- Adobe Creative Cloud — 📱 - (4996824819715540095)
    (["adobe", "creative cloud"], "4996824819715540095", "📱"),
    # 18- Figma Pro / Edu — 📱 - (5357286671656176924)
    (["figma"], "5357286671656176924", "📱"),
    # 19- Grammarly Premium — 📝 - (5334614570092744019)
    (["grammarly"], "5334614570092744019", "📝"),
    # 20- QuillBot Premium — 👋 - (6226228430459912404)
    (["quillbot"], "6226228430459912404", "👋"),
    # 21- LinkedIn Career / Business — 📱 - (5346024520081751155)
    (["linkedin"], "5346024520081751155", "📱"),
    # 22- Duolingo Plus / Super — 🔫 - (5796371348808799072)
    (["duolingo"], "5796371348808799072", "🔫"),
    # 23- Coursera Plus — 🪙 - (5334540056705126816)
    (["coursera"], "5334540056705126816", "🪙"),
    # 24- Cursor AI — 😵 - (6273793612715138423)
    (["cursor"], "6273793612715138423", "😵"),
    # 25- Grok / SuperGrok / X Premium — 😁 - (6179337489350663129)
    (["supergrok", "grok", "x premium"], "6179337489350663129", "😁"),
    # 26- Kling AI — 📱 - (5335012820935261564)
    (["kling"], "5335012820935261564", "📱"),
    # 27- Leonardo.ai — 😶 - (6133975818591805751)
    (["leonardo"], "6133975818591805751", "😶"),
    # 28- Lovable AI — 👍 - (6104729848675050039)
    (["lovable"], "6104729848675050039", "👍"),
    # 29- HeyGen AI — 😊 - (6318816857230942976)
    (["heygen"], "6318816857230942976", "😊"),
    # 30- Notion AI / Business — 📱 - (5364199932620194408)
    (["notion"], "5364199932620194408", "📱"),
    # 31- OpenArt AI — 📱 - (5359320531944358335)
    (["openart"], "5359320531944358335", "📱"),
    # 32- Google Veo AI — 😭 - (6178962311072456422)
    (["veo"], "6178962311072456422", "😭"),
    # 33- Gamma App AI — 📱 - (5359320531944358335)
    (["gamma"], "5359320531944358335", "📱"),
    # 34- VPN Surfshark — 🍸 - (5796592771552777710)
    (["surfshark"], "5796592771552777710", "🍸"),
    # 35- VPN NordVPN — 🥏 - (5796345694969140339)
    (["nord vpn", "nordvpn"], "5796345694969140339", "🥏"),
    # 36- VPN ExpressVPN — 👨‍⚖️ - (5796153709931009517)
    (["expressvpn"], "5796153709931009517", "👨‍⚖️"),
    # 37- VPN HMA (HideMyAss) — ❤️ - (5807666842214339188)
    (["hma"], "5807666842214339188", "❤️"),
    # 38- Instagram Cuentas Antiguas — 📱 - (5319160079465857105)
    (["instagram"], "5319160079465857105", "📱"),
    # 39- Xbox Game Pass / Códigos — 😙 - (6116431787720712232)
    (["xbox"], "6116431787720712232", "😙"),
]

def get_service_icon(name: str, for_html: bool = False) -> str:
    """
    Retorna el icono de marca correspondiente al producto.
    Si for_html es True, devuelve la etiqueta <tg-emoji> animada.
    Si for_html es False (para botones), devuelve el carácter de emoji limpio.
    """
    name_lower = name.lower()
    
    # Coincidencias específicas prioritarias
    if "onedrive" in name_lower:
        eid, fb = "5370857634440170316", "📱"
        return pe(eid, fb) if for_html else fb
    if "2fa gmail" in name_lower or "gmail" in name_lower:
        eid, fb = "5796209712009581332", "🐁"
        return pe(eid, fb) if for_html else fb
    if "outlook" in name_lower or "hotmail" in name_lower:
        eid, fb = "5796683820564484775", "🛻"
        return pe(eid, fb) if for_html else fb
    if "windows" in name_lower:
        eid, fb = "5798553402648565182", "💊"
        return pe(eid, fb) if for_html else fb

    for keywords, eid, fb in SERVICE_EMOJIS:
        if any(k in name_lower for k in keywords):
            return pe(eid, fb) if for_html else fb
            
    return pe("5890883384057533697", "🏷️") if for_html else "🏷️"

# ==============================================================================
# SISTEMA DINÁMICO DE PARSEO DE EMOJIS (Compatible con Pyrogram)
# ==============================================================================

EMOJI_MAP_CORE = {
    # --- Identidad y Menú Principal ---
    "💎": "5427168083074628963",
    "👤": "5275979556308674886",
    "🆔": "5884366771913233289",
    "💰": "5375296873982604963",
    "💵": "5409048419211682843",
    "🏦": "5264733042710181045",
    "🛍️": "5767288471685171967",
    "🛍": "5767288471685171967",
    "🛒": "5278613311858959074",
    "🪙": "5805550320985578625",
    "💳": "5445353829304387411",
    "💼": "5445221832074483553",
    "🔗": "5289511602393984968",
    "🆘": "6021798595739523148",
    "⚙️": "5341715473882955310",
    "⚙": "5341715473882955310",
    "😀": "5465353434712528673",
    "🏠": "5350404270032166927",
    "🔄": "6030657343744644592",
    "🔍": "5276395476646653290",
    "💬": "5443038326535759644",
    "⚠️": "5447644880824181073",
    "⚠": "5447644880824181073",

    # --- Mensajes, Billetera y Pedidos ---
    "📝": "5334882760735598374",
    "🌎": "4967677561032148287",
    "🧮": "5472404950673791399",
    "⭐️": "5469641199348363998",
    "⭐": "5469641199348363998",
    "📌": "5116161907669074775",
    "💾": "4990318000096675490",
    "📥": "5276220667182736079",
    "📊": "5431577498364158238",
    "✅": "6244510079014409289",
    "🤭": "5787467546596743616",

    # --- Controles y Administración ---
    "🛠️": "5462921117423384478",
    "🛠": "5462921117423384478",
    "🌀": "5370715282044100355",
    "📣": "5424818078833715060",
    "📢": "5424818078833715060",
    "◀️": "5465353434712528673",
    "◀": "5465353434712528673",
    "🔵": "5339366229851260759",
    "⏺️": "5339366229851260759",
    "⏺": "5339366229851260759",
    "⏩": "5465152894099540081",
    "▶️": "5465152894099540081",
    "▶": "5465152894099540081",
    "📁": "5244807637157029775",
    "🟢": "5884106131822875141",
    "🕶": "5276398496008663230",
    "🕶️": "5276398496008663230",
    "🔴": "5470060791883374114",
    "🖥": "5406809207947142040",
    "🖥️": "5406809207947142040",
    "📲": "5407025283456835913",
    "✍️": "5334882760735598374",
    "✍": "5334882760735598374",
    "❌": "5208429100951159058",
    "📦": "5886285355279193209",
    "🏷️": "5890883384057533697",
    "🏷": "5890883384057533697",
    "🔒": "5276262671962892944",
    "🎲": "5190741648237161191",
    "📈": "5244837092042750681",
    "🎯": "5310278924616356636",
    "⏳": "5451732530048802485",
    "🎉": "5461151367559141950",
    "🔑": "5330115548900501467",
    "💡": "5397782960512444700",
    "👥": "5422439311196834318",
    "📉": "5246762912428603768",
    "✨": "5118474816277447476",
    "⏰": "5276412364458059956",
    "🔔": "5242628160297641831",
    "🔕": "5208429100951159058",
    "🌐": "5447410659077661506",
    "📅": "5413879192267805083",
    "🗣️": "5370765563226236970",
    "🗣": "5370765563226236970",
    "🇪🇸": "4916120627582076238",
    "🇺🇸": "4916136269852968195",
    "🇧🇷": "5224688610183228070",
    "🔣": "5778208881301787450",
    "🌟": "5769248574499983619",
    "👆": "5769248574499983619",

    # --- Servicios y Marcas del Catálogo ---
    "🤖": "5310176773114197087",  # Google / Gemini
    "🐁": "5796209712009581332",  # Gmail
    "💊": "5798553402648565182",  # Windows 10/11
    "🛻": "5796683820564484775",  # Outlook / Hotmail
    "⚒": "5796297333637387376",  # Crunchyroll
    "🥀": "5796214303329620386",  # Canva
    "👋": "6226228430459912404",  # QuillBot
    "🔫": "5796371348808799072",  # Duolingo
    "😵": "6273793612715138423",  # Cursor AI
    "😁": "6179337489350663129",  # Grok
    "😶": "6133975818591805751",  # Leonardo AI
    "👍": "6104729848675050039",  # Lovable AI
    "😊": "6318816857230942976",  # HeyGen
    "😭": "6178962311072456422",  # Veo AI
    "🍸": "5796592771552777710",  # Surfshark
    "🥏": "5796345694969140339",  # NordVPN
    "👨‍⚖️": "5796153709931009517",  # ExpressVPN
    "❤️": "5807666842214339188",  # HMA
    "😙": "6116431787720712232",  # Xbox
    "🔙": "5465353434712528673",  # Volver
    "📋": "5334544901428229844",  # Portapapeles
    "🗑️": "4990318000096675490",  # Borrar
    "🗑": "4990318000096675490",
    "🛡️": "5469641199348363998",  # Escudo
    "🛡": "5469641199348363998",
    "👛": "6030443364178992166",  # Billetera
}

def _build_final_emoji_map() -> dict[str, str]:
    mapping = {}
    for em_char, em_id in EMOJI_MAP_CORE.items():
        mapping[em_char] = em_id
        clean = em_char.replace("\ufe0f", "")
        mapping[clean] = em_id
        mapping[clean + "\ufe0f"] = em_id
    return mapping

EMOJI_MAP = _build_final_emoji_map()

_ESCAPED_KEYS = [re.escape(k) for k in sorted(EMOJI_MAP.keys(), key=lambda x: len(x), reverse=True) if k]
_EMOJI_REGEX_PATTERN = re.compile("|".join(_ESCAPED_KEYS)) if _ESCAPED_KEYS else None
_PROTECTED_TAGS_REGEX = re.compile(r'<emoji[^>]*>.*?</emoji>|<tg-emoji[^>]*>.*?</tg-emoji>|<[^>]+>', re.DOTALL)
_TG_EMOJI_CONVERTER = re.compile(r'<tg-emoji emoji-id="(\d+)">([^<]+)</tg-emoji>')

def parse_emojis(text: str) -> str:
    """
    Convierte dinámicamente emojis unicode a etiquetas <emoji id=...> compatibles
    nativamente con el parser HTML de Pyrogram (MessageEntityCustomEmoji).
    """
    if not text:
        return text

    # Compatibilidad retroactiva: convertir cualquier <tg-emoji> a <emoji>
    text = _TG_EMOJI_CONVERTER.sub(r'<emoji id=\1>\2</emoji>', text)

    if not _EMOJI_REGEX_PATTERN:
        return text

    segments = []
    last_idx = 0
    for match in _PROTECTED_TAGS_REGEX.finditer(text):
        start, end = match.span()
        if start > last_idx:
            plain_part = text[last_idx:start]
            segments.append(_EMOJI_REGEX_PATTERN.sub(lambda m: f'<emoji id={EMOJI_MAP[m.group(0)]}>{m.group(0)}</emoji>', plain_part))
        segments.append(match.group(0))
        last_idx = end

    if last_idx < len(text):
        segments.append(_EMOJI_REGEX_PATTERN.sub(lambda m: f'<emoji id={EMOJI_MAP[m.group(0)]}>{m.group(0)}</emoji>', text[last_idx:]))

    return "".join(segments)

p = parse_emojis

# --- CONSTRUCTORES RAW MTPROTO PARA BOTONES CON EMOJI PREMIUM (CAPA 180+) ---

class RawKeyboardButtonStyle(TLObject):
    ID = 0x4fdd3430
    QUALNAME = "types.KeyboardButtonStyle"

    def __init__(self, *, icon: Optional[int] = None, bg_primary: bool = False, bg_danger: bool = False, bg_success: bool = False):
        self.icon = int(icon) if icon is not None else None
        self.bg_primary = bg_primary
        self.bg_danger = bg_danger
        self.bg_success = bg_success

    @staticmethod
    def read(b: BytesIO, *args: Any) -> "RawKeyboardButtonStyle":
        flags = Int.read(b)
        bg_primary = bool(flags & (1 << 0))
        bg_danger = bool(flags & (1 << 1))
        bg_success = bool(flags & (1 << 2))
        icon = Long.read(b) if bool(flags & (1 << 3)) else None
        return RawKeyboardButtonStyle(icon=icon, bg_primary=bg_primary, bg_danger=bg_danger, bg_success=bg_success)

    def write(self, *args: Any) -> bytes:
        b = BytesIO()
        b.write(Int(self.ID, False))
        flags = 0
        if self.bg_primary: flags |= (1 << 0)
        if self.bg_danger: flags |= (1 << 1)
        if self.bg_success: flags |= (1 << 2)
        if self.icon is not None: flags |= (1 << 3)
        b.write(Int(flags))
        if self.icon is not None:
            b.write(Long(self.icon))
        return b.getvalue()

class RawKeyboardButtonCallback(TLObject):
    ID = 0xe62bc960
    QUALNAME = "types.KeyboardButtonCallback"

    def __init__(self, *, text: str, data: bytes, style: Optional[RawKeyboardButtonStyle] = None, requires_password: Optional[bool] = None):
        self.text = text
        self.data = data
        self.style = style
        self.requires_password = requires_password

    @staticmethod
    def read(b: BytesIO, *args: Any) -> "RawKeyboardButtonCallback":
        flags = Int.read(b)
        requires_password = bool(flags & (1 << 0))
        style = TLObject.read(b) if bool(flags & (1 << 10)) else None
        text = String.read(b)
        data = Bytes.read(b)
        return RawKeyboardButtonCallback(text=text, data=data, style=style, requires_password=requires_password)

    def write(self, *args: Any) -> bytes:
        b = BytesIO()
        b.write(Int(self.ID, False))
        flags = 0
        if self.requires_password: flags |= (1 << 0)
        if self.style is not None: flags |= (1 << 10)
        b.write(Int(flags))
        if self.style is not None:
            b.write(self.style.write())
        b.write(String(self.text))
        b.write(Bytes(self.data))
        return b.getvalue()

class RawKeyboardButtonUrl(TLObject):
    ID = 0x258aff05
    QUALNAME = "types.KeyboardButtonUrl"

    def __init__(self, *, text: str, url: str, style: Optional[RawKeyboardButtonStyle] = None):
        self.text = text
        self.url = url
        self.style = style

    @staticmethod
    def read(b: BytesIO, *args: Any) -> "RawKeyboardButtonUrl":
        flags = Int.read(b)
        style = TLObject.read(b) if bool(flags & (1 << 10)) else None
        text = String.read(b)
        url = String.read(b)
        return RawKeyboardButtonUrl(text=text, url=url, style=style)

    def write(self, *args: Any) -> bytes:
        b = BytesIO()
        b.write(Int(self.ID, False))
        flags = 0
        if self.style is not None: flags |= (1 << 10)
        b.write(Int(flags))
        if self.style is not None:
            b.write(self.style.write())
        b.write(String(self.text))
        b.write(String(self.url))
        return b.getvalue()

objects[RawKeyboardButtonStyle.ID] = RawKeyboardButtonStyle
objects[RawKeyboardButtonCallback.ID] = RawKeyboardButtonCallback
objects[RawKeyboardButtonUrl.ID] = RawKeyboardButtonUrl

# Monkeypatch del serializador write() de Pyrogram para inyectar style.icon en MTProto
_orig_btn_write = _PyrogramInlineKeyboardButton.write

async def _custom_btn_write(self, client: Any):
    icon_id = getattr(self, "icon_custom_emoji_id", None)
    if icon_id:
        try:
            icon_int = int(str(icon_id).strip())
            style = RawKeyboardButtonStyle(icon=icon_int)
            if self.callback_data is not None:
                data = bytes(self.callback_data, "utf-8") if isinstance(self.callback_data, str) else self.callback_data
                return RawKeyboardButtonCallback(
                    text=self.text,
                    data=data,
                    style=style
                )
            if self.url is not None:
                return RawKeyboardButtonUrl(
                    text=self.text,
                    url=self.url,
                    style=style
                )
        except Exception:
            pass
    return await _orig_btn_write(self, client)

_PyrogramInlineKeyboardButton.write = _custom_btn_write

_UNICODE_EMOJI_CLEANER = re.compile(
    r'[\U00010000-\U0010ffff\u2600-\u27ff\u2b00-\u2bfc\u2300-\u23ff\u200d\ufe0f\u20e3\u2190-\u21ff\u2934-\u2935\u3297\u3299]'
)

def format_button_info(text: str) -> Tuple[str, Optional[str], str]:
    """
    Construye la información del botón (idéntico al bot de confesiones):
    - Extrae icon_custom_emoji_id según el catálogo de Emojis Animados Premium.
    - Remueve TODOS los emojis unicode del texto para evitar que aparezcan 2 emojis duplicados
      cuando Telegram renderiza el icono animado en el botón.
    - Retorna (texto_sin_emoji, icon_id, texto_completo_con_emoji).
    """
    clean_text = re.sub(r'<[^>]+>', '', str(text)).strip()
    text_str = clean_text
    icon_id = None

    # 1. Buscar si comienza con algún emoji del catálogo
    for emoji_char, em_id in sorted(EMOJI_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if text_str.startswith(emoji_char):
            icon_id = em_id
            text_str = text_str[len(emoji_char):].strip().lstrip(" \ufe0f")
            break

    # 2. Si no empieza con emoji, buscar si contiene un emoji en el texto
    if not icon_id:
        for emoji_char, em_id in sorted(EMOJI_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if emoji_char in text_str:
                icon_id = em_id
                text_str = text_str.replace(emoji_char, "").strip()
                break

    if icon_id:
        text_str = _UNICODE_EMOJI_CLEANER.sub('', text_str).strip()

    final_text = text_str if text_str else clean_text
    return final_text, icon_id, clean_text

def parse_keyboard(reply_markup: Any) -> Any:
    """
    Procesa y parsea absolutamente todos los botones de la botonera inline:
    1. Limpia cualquier residuo de tags HTML.
    2. Asocia icon_custom_emoji_id inyectando el icono animado de Telegram Premium.
    3. Remueve el emoji duplicado del texto (idéntico a telegram-confesiones-bot).
    """
    if not reply_markup or not hasattr(reply_markup, "inline_keyboard"):
        return reply_markup

    for row in reply_markup.inline_keyboard:
        for btn in row:
            if btn and hasattr(btn, "text") and btn.text:
                final_text, icon_id, full_text = format_button_info(btn.text)
                btn._fallback_text = full_text
                if icon_id:
                    btn.text = final_text
                    btn.icon_custom_emoji_id = str(icon_id)
                else:
                    btn.text = full_text

    return reply_markup

def InlineKeyboardButton(text: str, *args: Any, **kwargs: Any) -> _PyrogramInlineKeyboardButton:
    """
    Construye InlineKeyboardButton inyectando icon_custom_emoji_id cuando coincide
    con el catálogo de Emojis Animados Premium de Telegram, y remueve el emoji unicode
    del texto para evitar que aparezcan 2 emojis duplicados en el botón (idéntico al bot de confesiones).
    """
    final_text, icon_id, full_text = format_button_info(text)
    if icon_id:
        btn = _PyrogramInlineKeyboardButton(text=final_text, *args, **kwargs)
        btn.icon_custom_emoji_id = str(icon_id)
        btn._fallback_text = full_text
        return btn
    else:
        btn = _PyrogramInlineKeyboardButton(text=full_text, *args, **kwargs)
        btn._fallback_text = full_text
        return btn

def strip_keyboard_icons(reply_markup: Any) -> Any:
    """Restaura los botones estándar eliminando icon_custom_emoji_id si Telegram rechaza el formato"""
    if not reply_markup or not hasattr(reply_markup, "inline_keyboard"):
        return reply_markup
    for row in reply_markup.inline_keyboard:
        for btn in row:
            if hasattr(btn, "icon_custom_emoji_id"):
                delattr(btn, "icon_custom_emoji_id")
            if hasattr(btn, "_fallback_text"):
                btn.text = btn._fallback_text
    return reply_markup
