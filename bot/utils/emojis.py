"""
Módulo de Emojis Premium de Telegram.
Formatea automáticamente cada emoji como `<tg-emoji emoji-id="{ID}">{FALLBACK}</tg-emoji>`
para renderizado vectorial y animado en clientes Telegram.
"""

def pe(emoji_id: str, fallback: str) -> str:
    """Retorna la etiqueta HTML de Telegram Custom Emoji"""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

# 1- Encabezado principal de la tienda (jvcᵈᵉᵛ Store) - (5427168083074628963)
EMOJI_STORE = pe("5427168083074628963", "💎")

# 2- Etiqueta de Usuario / Mi Perfil - (5275979556308674886)
EMOJI_USER = pe("5275979556308674886", "👤")

# 3- ID de Usuario / Mi Perfil - (5884366771913233289)
EMOJI_ID = pe("5884366771913233289", "🆔")

# 4- Saldo en Bot / Precios / Ganancias - (5375296873982604963)
EMOJI_MONEY = pe("5375296873982604963", "💰")

# 5- Saldo Proveedor BunaiStore - (5264733042710181045)
EMOJI_PROVIDER = pe("5264733042710181045", "🏢")

# 6- Compras Realizadas / Listado de Pedidos - (5767288471685171967)
EMOJI_SHOPPING = pe("5767288471685171967", "🛍️")

# 7- Catálogo de Servicios / Botón Comprar - (5278613311858959074)
EMOJI_CART = pe("5278613311858959074", "🛒")

# 8- Depositar USDT / Billetera / Nueva Recarga - (5445353829304387411)
EMOJI_CARD = pe("5445353829304387411", "💳")

# 9- Mis Pedidos - (5445221832074483553)
EMOJI_ORDERS = pe("5445221832074483553", "💼")

# 10- Sistema de Referidos / Enlace de Invitación / TxHash - (5289511602393984968)
EMOJI_LINK = pe("5289511602393984968", "🔗")

# 11- Soporte & Ayuda - (6021798595739523148)
EMOJI_SUPPORT = pe("6021798595739523148", "🆘")

# 12- Panel de Administración - (5341715473882955310)
EMOJI_ADMIN = pe("5341715473882955310", "⚙️")

# 13- Volver al Menú Principal - (5350404270032166927)
EMOJI_HOME = pe("5350404270032166927", "🏠")

# 14- Actualizar Catálogo / Verificar Pago - (6030657343744644592)
EMOJI_REFRESH = pe("6030657343744644592", "🔄")

# 15- Buscar Servicio - (5276395476646653290)
EMOJI_SEARCH = pe("5276395476646653290", "🔍")

# 16- Contactar Administrador / Ayuda - (5443038326535759644)
EMOJI_CHAT = pe("5443038326535759644", "💬")

# 17- Advertencia de Mantenimiento / Monto Mínimo - (5276240711795107620)
EMOJI_WARN = pe("5276240711795107620", "⚠️")

# 18- Billetera / Saldo del Usuario / Total a Pagar - (6030443364178992166)
EMOJI_WALLET = pe("6030443364178992166", "👛")

# 19- Idioma Seleccionado - (5370765563226236970)
EMOJI_LANG = pe("5370765563226236970", "🗣️")

# 20- Menú de Idiomas / Red Blockchain / Zona Horaria - (5447410659077661506)
EMOJI_GLOBE = pe("5447410659077661506", "🌐")

# 21- Fecha de Registro / Fecha del Pedido - (5413879192267805083)
EMOJI_CALENDAR = pe("5413879192267805083", "📅")

# 22- Idioma Español - (4916120627582076238)
EMOJI_FLAG_ES = pe("4916120627582076238", "🇪🇸")

# 23- Idioma Inglés - (4916136269852968195)
EMOJI_FLAG_EN = pe("4916136269852968195", "🇺🇸")

# 24- Idioma Portugués - (5224688610183228070)
EMOJI_FLAG_PT = pe("5224688610183228070", "🇧🇷")

# 25- Idioma Activo / Operación Exitosa / Acreditado - (5208880351690112495)
EMOJI_CHECK = pe("5208880351690112495", "✅")

# 26- Catálogo, Filtros & Categorías - (6039630677182254664)
EMOJI_FOLDER = pe("6039630677182254664", "📂")

# 27- Categoría Disponibles / Estado Activo - (5211182849297762045)
EMOJI_GREEN_DOT = pe("5211182849297762045", "🟢")

# 28- Categoría En Oferta / Descuentos por Volumen - (5276422526350681413)
EMOJI_GIFT = pe("5276422526350681413", "🎁")

# 29- Categoría Agotados / Mantenimiento Activo / Cancelado - (5208429100951159058)
EMOJI_RED_DOT = pe("5208429100951159058", "🔴")
EMOJI_CROSS = pe("5208429100951159058", "❌")

# 30- Ingresar Monto Personalizado - (5197269100878907942)
EMOJI_WRITE = pe("5197269100878907942", "✍️")

# 31 & 43- Producto / Precio Base / Icono por Defecto - (5886285355279193209 / 5890883384057533697)
EMOJI_BOX = pe("5886285355279193209", "📦")
EMOJI_TAG = pe("5890883384057533697", "🏷️")

# 33- Garantía del Producto - (5469641199348363998)
EMOJI_SHIELD = pe("5469641199348363998", "🛡️")

# 34- Garantía / Candado / Reembolso Seguro - (5276262671962892944)
EMOJI_LOCK = pe("5276262671962892944", "🔒")

# 36 & 53- Ver Nota del Administrador / Términos - (5334882760735598374)
EMOJI_NOTE = pe("5334882760735598374", "📝")

# 37- Notificar cuando haya Stock / Alerta Restock - (5242628160297641831)
EMOJI_BELL = pe("5242628160297641831", "🔔")

# 38- Alerta de Stock Activa (Cancelar) - (5244807637157029775)
EMOJI_BELL_OFF = pe("5244807637157029775", "🔕")

# 39- Cantidad Seleccionada en Calculadora / Stock - (5190741648237161191)
EMOJI_DICE = pe("5190741648237161191", "🎲")

# 45- Ver Código QR de Pago / Teléfono - (5370857634440170316)
EMOJI_PHONE = pe("5370857634440170316", "📱")

# 48- Panel de Mantenimiento / Herramientas - (6124926696161286141)
EMOJI_TOOLS = pe("6124926696161286141", "🛠️")

# 58 & 76- Estrategia de Precios Activa / Alza - (5244837092042750681)
EMOJI_CHART_UP = pe("5244837092042750681", "📈")

# 59- Monto Exacto a Enviar - (5310278924616356636)
EMOJI_TARGET = pe("5310278924616356636", "🎯")

# 61- Tiempo Límite / Verificando Blockchain / Procesando - (5451732530048802485)
EMOJI_HOURGLASS = pe("5451732530048802485", "⏳")

# 63- Volver a la Factura / Atrás - (5224623116226932045)
EMOJI_BACK = pe("5224623116226932045", "🔙")

# 65- Depósito Confirmado / Compra Exitosa - (5461151367559141950)
EMOJI_PARTY = pe("5461151367559141950", "🎉")

# 66- Credenciales / Cuentas / Licencias Entregadas - (5330115548900501467)
EMOJI_KEY = pe("5330115548900501467", "🔑")

# 68 & 69- Tip informativo / Instrucciones - (5397782960512444700)
EMOJI_IDEA = pe("5397782960512444700", "💡")

# 70- Usuarios Referidos / Usuarios Totales - (5422439311196834318)
EMOJI_USERS = pe("5422439311196834318", "👥")

# 71- Compartir Enlace / Difusión Masiva (Broadcast) - (5372926953978341366)
EMOJI_BROADCAST = pe("5372926953978341366", "📢")

# 75- Gasto Total en Proveedor - (5246762912428603768)
EMOJI_CHART_DOWN = pe("5246762912428603768", "📉")

# 80- Nuevo Producto Añadido por Proveedor - (5118474816277447476)
EMOJI_SPARKLES = pe("5118474816277447476", "✨")

# 82- Hora y Fecha Exacta en Logs - (5276412364458059956)
EMOJI_CLOCK = pe("5276412364458059956", "⏰")

# Otros útiles
EMOJI_TRASH = "🗑️"
