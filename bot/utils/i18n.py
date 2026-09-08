from typing import Dict
from bot.utils.emojis import (
    EMOJI_STORE, EMOJI_USER, EMOJI_ID, EMOJI_MONEY, EMOJI_SHOPPING,
    EMOJI_CARD, EMOJI_ORDERS, EMOJI_LINK, EMOJI_SUPPORT,
    EMOJI_SEARCH, EMOJI_CHAT, EMOJI_WARN, EMOJI_GLOBE, EMOJI_CALENDAR,
    EMOJI_CHECK, EMOJI_FOLDER, EMOJI_GREEN_DOT, EMOJI_GIFT, EMOJI_RED_DOT,
    EMOJI_CROSS, EMOJI_WRITE, EMOJI_BOX, EMOJI_SHIELD, EMOJI_LOCK,
    EMOJI_NOTE, EMOJI_BELL, EMOJI_BELL_OFF, EMOJI_DICE, EMOJI_PHONE,
    EMOJI_TARGET, EMOJI_HOURGLASS, EMOJI_PARTY, EMOJI_KEY, EMOJI_IDEA,
    EMOJI_USERS, EMOJI_MONITOR, EMOJI_WALLET_ADDR
)

LANGUAGES = {
    "es": "🇪🇸 Español",
    "en": "🇺🇸 English",
    "pt": "🇧🇷 Português"
}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "es": {
        # Menú Principal y Navegación
        "welcome_header": f"{EMOJI_STORE} <b>BIENVENIDO A jvcᵈᵉᵛ Store</b> {EMOJI_STORE}",
        "user_label": "Usuario",
        "balance_bot": "Saldo en Bot",
        "balance_provider": "Saldo Proveedor (Bunai)",
        "orders_made": "Compras Realizadas",
        "select_option": "Selecciona una opción del menú inferior para comenzar:",
        "maintenance_banner": f"{EMOJI_WARN} <i>El bot está en modo mantenimiento. Las compras están pausadas temporalmente.</i>\n\n",
        "btn_catalog": "🛒 Catálogo de Servicios",
        "btn_deposit": "🪙 Depositar USDT",
        "btn_my_orders": "💼 Mis Pedidos",
        "btn_referrals": "🔗 Referidos",
        "btn_profile": "👤 Mi Perfil",
        "btn_support": "🆘 Soporte & Ayuda",
        "btn_admin": "⚙️ Panel de Administración",
        "btn_back": "😀 Volver",
        "btn_cancel": "❌ Cancelar",
        "btn_main_menu": "🏠 Menú Principal",
        "btn_refresh": "🔄 Actualizar",
        "btn_search_service": "🔍 Buscar Servicio",
        "btn_contact_admin": "💬 Contactar Administrador",

        # Perfil e Idiomas
        "profile_title": f"{EMOJI_USER} <b>Perfil de Usuario</b>",
        "lang_label": "Idioma",
        "registered": "Registro",
        "btn_language": "🗣️ Idioma",
        "lang_select_title": f"{EMOJI_GLOBE} <b>SELECCIONA TU IDIOMA PREFERIDO</b>\n\n<i>Elige el idioma con el que deseas utilizar el bot:</i>",
        "lang_changed": f"{EMOJI_CHECK} Idioma actualizado a: {{lang_name}}",

        # Catálogo y Selector de Categorías
        "catalog_header_disponibles": f"{EMOJI_GREEN_DOT} <b>PRODUCTOS DISPONIBLES</b> ({{count}})",
        "catalog_header_agotados": f"{EMOJI_RED_DOT} <b>PRODUCTOS AGOTADOS</b> ({{count}})",
        "catalog_header_ofertas": f"{EMOJI_GIFT} <b>PRODUCTOS EN OFERTA</b> ({{count}})",
        "catalog_header_todos": f"{EMOJI_MONITOR} <b>TODOS LOS SERVICIOS</b> ({{count}})",
        "btn_categories": "📁 Categorías",
        "cat_picker_title": f"{EMOJI_FOLDER} <b>SELECCIONA UNA CATEGORÍA</b>\n\n<i>Elige la categoría del catálogo que deseas ver:</i>",
        "cat_opt_disponibles": "🟢 Disponibles ({count})",
        "cat_opt_ofertas": "🕶 En Oferta ({count})",
        "cat_opt_agotados": "🔴 Agotados ({count})",
        "cat_opt_todos": "🖥 Todos ({count})",
        "catalog_empty": "No hay productos en esta categoría por el momento.",
        "stock_unlimited": "Ilimitado (∞)",
        "stock_out": "Agotado",
        "product_label": "Producto",
        "base_price_label": "Precio Base",
        "available_stock_label": "Stock Disponible",
        "warranty_label": "Garantía",
        "no_warranty": "Sin Garantía",
        "warranty_days": "{days} Días",
        "warranty_hours": "{hours} Horas",
        "selected_qty": "Cant. Seleccionada",
        "total_amount": "Monto Total",
        "your_balance": "Saldo",
        "btn_buy_qty": "🔣 Comprar {qty} (${total} USDT)",
        "btn_recharge_balance": "🌟 Recargar Saldo",
        "btn_share_link": "🔗 Compartir Enlace 📋",
        "btn_view_note": "📝 Ver Nota",
        "admin_note_title": f"{EMOJI_NOTE} <b>Nota del Admin:</b>",
        "no_admin_note": "No hay notas adicionales configuradas para este producto.",
        "btn_notify_stock": "🔔 Avisarme cuando haya stock",
        "btn_cancel_stock_alert": "🔕 Alerta Activa (Toca para Cancelar)",
        "alert_activated": f"{EMOJI_BELL} ¡Alerta activada! Te avisaremos por privado cuando haya stock.",
        "alert_cancelled": f"{EMOJI_BELL_OFF} Alerta de stock cancelada.",
        "promo_offer_text": f"{EMOJI_GIFT} <b>Oferta: Compra {{qty}}+ ➔ -{{discount}}% Desc</b>",
        "restock_alert_title": f"{EMOJI_BELL} <b>¡PRODUCTO RESTABLECIDO EN STOCK!</b>\n\n{EMOJI_BOX} <b>Producto:</b> <code>{{product}}</code>\n{EMOJI_MONEY} <b>Precio:</b> <code>${{price}} USDT</code>\n{EMOJI_DICE} <b>Stock Disponible:</b> <code>{{stock}} unidades</code>\n\n<i>El servicio que estabas esperando ya tiene stock disponible. ¡Aprovecha antes de que se agote!</i>",
        "btn_buy_now": "🔣 Ver y Comprar Ahora",

        # Buscador
        "search_prompt_title": f"{EMOJI_SEARCH} <b>BUSCADOR DE SERVICIOS</b>\n\nEscribe el nombre del servicio que buscas (ejemplo: <code>Gemini</code>, <code>Netflix</code>, <code>Office</code>).\n\n<i>O escribe <code>/buscar nombre</code> en cualquier momento.</i>",
        "search_results_title": f"{EMOJI_SEARCH} <b>Resultados para:</b> <i>'{{query}}'</i> ({{count}} encontrados):",
        "search_no_results": f"{EMOJI_SEARCH} <b>Resultados para:</b> <i>'{{query}}'</i>\n\n{EMOJI_CROSS} No se encontraron productos con ese nombre.",

        # Billetera y Depósitos
        "wallet_title": f"{EMOJI_CARD} <b>BILLETERA & DEPÓSITOS USDT</b>\n\n{EMOJI_MONEY} <b>Saldo Actual:</b> <code>${{balance}} USDT</code>\n{EMOJI_GLOBE} <b>Red Aceptada:</b> <code>BNB Smart Chain (BEP-20)</code>\n{EMOJI_LOCK} <b>Depósito Mínimo:</b> <code>${{min_dep}} USDT</code>\n\n<i>Selecciona el monto que deseas recargar o pulsa 'Ingresar Otro Monto':</i>",
        "btn_custom_amount": "✍️ Ingresar Otro Monto",
        "invoice_title": f"{EMOJI_CARD} <b>SOLICITUD DE RECARGA USDT (BEP-20)</b>\n\n{EMOJI_WARN} <b>IMPORTANTE:</b> Envía <b>EXACTAMENTE</b> la cantidad indicada a continuación para que la acreditación sea automática.\n\n{EMOJI_TARGET} <b>Monto Exacto a Enviar:</b>\n<code>{{exact_val}}</code> USDT\n\n{EMOJI_WALLET_ADDR} <b>Dirección de Billetera (BNB Smart Chain / BEP-20):</b>\n<code>{{wallet}}</code>\n\n{EMOJI_HOURGLASS} <b>Tiempo Límite:</b> <code>30 minutos</code>\n\n<i>Pulsa '📲 Ver Código QR' para escanear desde tu app o realiza la transferencia y luego pulsa 'Ingresar Hash / TxID'.</i>",
        "btn_show_qr": "📲 Ver Código QR",
        "btn_submit_hash": "🔗 Ingresar Hash / TxID",
        "btn_verify_payment": "🔄 Verificar Pago",
        "btn_cancel_request": "❌ Cancelar Solicitud",
        "btn_back_to_invoice": "🔙 Volver a la Solicitud",
        "qr_caption": f"{EMOJI_PHONE} <b>CÓDIGO QR DE PAGO BSC (BEP-20)</b>\n\n{EMOJI_TARGET} <b>Monto a transferir:</b> <code>{{exact_val}}</code> USDT\n{EMOJI_WALLET_ADDR} <b>Billetera:</b> <code>{{wallet}}</code>\n\n<i>Escanea este código directamente desde Trust Wallet, Binance o MetaMask.</i>",
        "custom_amount_prompt": f"{EMOJI_WRITE} <b>INGRESA EL MONTO A DEPOSITAR</b>\n\nEscribe la cantidad de USDT que deseas recargar en tu cuenta.\n\n{EMOJI_WARN} <b>Monto Mínimo:</b> <code>{{min_dep}} USDT</code>\n\n<i>Ejemplo: Envía un mensaje escribiendo <code>15</code> o <code>25.5</code></i>",
        "submit_hash_prompt": f"{EMOJI_LINK} <b>ENVÍA EL HASH / TXID DE LA TRANSACCIÓN</b>\n\nPega a continuación el Hash (TxID) de la transferencia realizada desde tu billetera (Trust Wallet, Binance, MetaMask, etc).\n\n<i>Ejemplo: <code>0x4a8c9b...</code></i>",
        "deposit_cancelled_screen": f"{EMOJI_CROSS} <b>SOLICITUD DE RECARGA CANCELADA</b>\n\nLa solicitud por <b>${{amount}} USDT</b> ha sido cancelada correctamente.\n\n<i>Puedes generar una nueva solicitud cuando desees.</i>",
        "btn_new_deposit": "🪙 Nueva Recarga",
        "verifying_tx": f"{EMOJI_HOURGLASS} <b>Verificando transacción en la blockchain BSC...</b>\n<i>Consultando nodos de red y confirmaciones.</i>",
        "deposit_success_title": f"{EMOJI_PARTY} <b>¡DEPÓSITO ACREDITADO CON ÉXITO!</b>\n\n{EMOJI_MONEY} <b>Monto Acreditado:</b> <code>+${{amount}} USDT</code>\n{EMOJI_CARD} <b>Nuevo Saldo Total:</b> <code>${{balance}} USDT</code>\n\n<i>Ya puedes explorar el catálogo y comprar cualquier servicio digital.</i>",

        # Compras y Checkout
        "processing_order": f"{EMOJI_HOURGLASS} <b>Procesando tu orden de {{qty}}x {{product}}...</b>\n<i>Por favor espera unos segundos.</i>",
        "purchase_fail_title": f"{EMOJI_CROSS} <b>NO SE PUDO COMPLETAR LA COMPRA</b>\n\nEl proveedor rechazó la solicitud (posiblemente sin stock suficiente).\n\n{EMOJI_SHIELD} <b>Tu saldo de ${{total}} USDT ha sido reembolsado intacto a tu cuenta.</b>",
        "purchase_success_title": f"{EMOJI_PARTY} <b>¡COMPRA REALIZADA CON ÉXITO!</b>\n\n{EMOJI_BOX} <b>Producto:</b> <code>{{product}}</code> (x{{qty}})\n{EMOJI_MONEY} <b>Total Pagado:</b> <code>${{total}} USDT</code>\n{EMOJI_ID} <b>Orden #:</b> <code>ORD_{{order_id}}</code>{{warranty_text}}\n\n{EMOJI_KEY} <b>DATOS DE TU SERVICIO:</b>\n<pre>{{items}}</pre>{{after_note}}\n\n<i>{EMOJI_IDEA} Puedes consultar tus compras y garantías en cualquier momento desde 'Mis Pedidos'.</i>",
        "btn_view_in_orders": "💼 Ver en 'Mis Pedidos'",
        "btn_continue_shopping": "👆 Seguir Comprando",

        # Mis Pedidos
        "orders_title": f"{EMOJI_ORDERS} <b>MIS PEDIDOS ({{count}} Total)</b>\n<i>Selecciona un pedido para ver los datos entregados:</i>\n",
        "orders_empty": f"{EMOJI_ORDERS} <b>MIS PEDIDOS</b>\n\nAún no has realizado ningún pedido.\n\n<i>Explora nuestro catálogo y adquiere tus cuentas y licencias al mejor precio.</i>",
        "order_detail_title": f"{EMOJI_SHOPPING} <b>DETALLES DEL PEDIDO #ORD_{{order_id}}</b>\n\n{EMOJI_BOX} <b>Producto:</b> <code>{{product}}</code> (x{{qty}})\n{EMOJI_MONEY} <b>Precio Pagado:</b> <code>${{total}} USDT</code>\n{EMOJI_SHIELD} <b>Garantía:</b> <code>{{warranty}}</code>\n{EMOJI_CALENDAR} <b>Fecha:</b> <code>{{date}}</code>\n{EMOJI_ID} <b>ID Proveedor:</b> <code>{{prov_id}}</code>\n\n{EMOJI_KEY} <b>DATOS / CREDENCIALES ENTREGADAS:</b>\n<pre>{{items}}</pre>",

        # Referidos
        "referrals_title": f"{EMOJI_LINK} <b>SISTEMA DE REFERIDOS & AFILIADOS</b>\n\n¡Invita a tus amigos y gana el <b>{{percent}}% de comisión</b> automática sobre cada recarga de saldo que realicen!\n\n{EMOJI_USERS} <b>Tus Referidos Registrados:</b> <code>{{count}} usuarios</code>\n{EMOJI_MONEY} <b>Comisiones Ganadas:</b> <code>${{earnings}} USDT</code>\n\n{EMOJI_TARGET} <b>Tu Enlace Exclusivo de Invitación:</b>\n<code>{{ref_link}}</code>\n\n<i>Comparte tu enlace y empieza a generar ingresos pasivos.</i>",
        "btn_share_ref": "📢 Compartir Enlace",

        # Soporte
        "support_text": f"{EMOJI_SUPPORT} <b>SOPORTE & AYUDA</b>\n\n¿Tienes alguna duda sobre tus compras, depósitos o necesitas asistencia?\n\n• <b>Garantía:</b> Si algún servicio con garantía presenta inconvenientes durante el período activo, contáctanos inmediatamente con tu <b>ID de Orden</b>.\n• <b>Depósitos:</b> Los depósitos en USDT BEP-20 se acreditan automáticamente tras la confirmación de la red.\n\n{EMOJI_CHAT} <i>Para contactar directamente a un administrador pulsa el botón inferior:</i>",

        # Plan Revendedor VIP
        "btn_vip_plan": "👑 Plan Revendedor VIP (20% OFF)",
        "btn_vip_my_plan": "👑 Mi Membresía VIP",
        "btn_activate_vip": "⭐ Activar Plan VIP (10 USDT / 30 días)",
        "btn_renew_vip": "🔄 Renovar Plan VIP (10 USDT)",
        "btn_confirm_pay_vip": "✅ Confirmar y Pagar 10 USDT",
        "btn_copy_client": "📋 Copiar para Cliente",
        "vip_status_regular": "Regular",
        "vip_status_active": "⭐ Revendedor VIP",
        "vip_confirm_title": (
            f"👑 <b>CONFIRMAR COMPRA - PLAN REVENDEDOR VIP</b>\n\n"
            f"¿Deseas activar tu <b>Membresía Revendedor VIP</b> por <b>30 días</b>?\n\n"
            f"💵 <b>Costo del Plan:</b> <code>10.00 USDT</code>\n"
            f"⏳ <b>Duración:</b> <code>30 días</code>\n"
            f"💳 <b>Tu Saldo Actual:</b> <code>${{balance}} USDT</code>\n\n"
            f"<i>Al confirmar, se debitarán 10.00 USDT de tu saldo del bot y se activará inmediatamente tu tarifa del 20% OFF.</i>"
        ),
        "vip_info_title": (
            f"👑 <b>PLAN PARA REVENDEDORES VIP</b>\n\n"
            f"¿Revendes servicios digitales o quieres maximizar tus ganancias? Conviértete en <b>Socio VIP</b> y accede a los mejores márgenes del mercado:\n\n"
            f"💎 <b>20% de Descuento Automático:</b> Precios mayoristas aplicados directamente en todo nuestro catálogo.\n"
            f"⚡ <b>Alertas de Stock Prioritarias:</b> Entérate antes que nadie cuando reponemos servicios de alta demanda.\n"
            f"📋 <b>Entrega Marca Blanca:</b> Botón exclusivo para copiar los accesos limpios y formateados, listos para enviar a tus clientes por WhatsApp sin marcas ni logos.\n"
            f"👥 <b>Doble Comisión en Referidos:</b> Gana el <b>20% de comisión</b> sobre cada recarga de tus invitados (vs 5% regular).\n"
            f"🛡️ <b>Atención Prioritaria:</b> Soporte y garantías rápidas.\n\n"
            f"💵 <b>Inversión:</b> <code>10.00 USDT</code> / 30 días\n"
            f"<i>(¡La mitad de lo que cobra la competencia por los mismos beneficios!)</i>"
        ),
        "vip_active_title": (
            f"👑 <b>TU MEMBRESÍA VIP ESTÁ ACTIVA</b>\n\n"
            f"Disfrutas de todas las ventajas y el <b>20% OFF</b> en todo el catálogo.\n\n"
            f"📅 <b>Vence el:</b> <code>{{expires_at}}</code>\n"
            f"⏳ <b>Tiempo restante:</b> <code>{{days_left}} días</code>\n\n"
            f"<i>Puedes renovar con anticipación en cualquier momento para extender tu período 30 días más.</i>"
        ),
        "vip_success_activated": (
            f"🎉 <b>¡BIENVENIDO AL PLAN REVENDEDOR VIP!</b>\n\n"
            f"Tu membresía ha sido activada con éxito por <b>30 días</b>.\n\n"
            f"🌟 <b>Beneficios activos:</b>\n"
            f"• 20% de descuento automático en todo el catálogo.\n"
            f"• Alertas tempranas de stock.\n"
            f"• Formato de entrega limpia para clientes.\n"
            f"• 20% de comisiones por referidos.\n\n"
            f"📅 <b>Válido hasta:</b> <code>{{expires_at}}</code>"
        ),
        "vip_insufficient_funds": (
            f"⚠️ <b>SALDO INSUFICIENTE</b>\n\n"
            f"Para activar el Plan VIP necesitas <b>10.00 USDT</b> en tu saldo del bot.\n"
            f"Tu saldo actual es de: <code>${{balance}} USDT</code>.\n\n"
            f"<i>Por favor recarga tu saldo para continuar.</i>"
        ),
        "vip_warn_24h_msg": (
            f"⚠️ <b>¡TU MEMBRESÍA VIP VENCE EN 24 HORAS!</b> ⚠️\n\n"
            f"Te recordamos que a tu Plan Revendedor VIP le quedan menos de <b>24 horas</b> de vigencia (Vence: <code>{{expires_at}}</code>).\n\n"
            f"Renueva ahora para no perder tu <b>20% de descuento</b> ni tus beneficios exclusivos."
        ),
        "vip_warn_2h_msg": (
            f"🚨 <b>¡URGENTE: TU MEMBRESÍA VIP VENCE EN 2 HORAS!</b> 🚨\n\n"
            f"Tu Plan Revendedor VIP vencerá hoy a las <code>{{expires_at}}</code>.\n\n"
            f"<i>Renueva tu suscripción inmediatamente para mantener tus tarifas preferenciales de distribuidor.</i>"
        ),
        "vip_expired_msg": (
            f"❌ <b>TU MEMBRESÍA VIP HA FINALIZADO</b>\n\n"
            f"Tu período de 30 días ha concluido y tu cuenta ha regresado al estado Regular.\n\n"
            f"<i>Puedes reactivar tu membresía VIP en cualquier momento por 10 USDT para volver a disfrutar del 20% OFF.</i>"
        ),
        "vip_admin_granted_msg": (
            f"👑 <b>¡MEMBRESÍA VIP OTORGADA POR ADMINISTRADOR!</b>\n\n"
            f"Un administrador te ha otorgado acceso al <b>Plan Revendedor VIP</b> por <b>{{days}} días</b>.\n\n"
            f"📅 <b>Vigente hasta:</b> <code>{{expires_at}}</code>\n\n"
            f"<i>¡Aprovecha tu 20% de descuento en todo el catálogo!</i>"
        ),
        "vip_client_template": (
            f"✨ <b>Tu Servicio Digital</b> ✨\n\n"
            f"📦 <b>Producto:</b> {{product}}\n"
            f"🔑 <b>Datos de Acceso:</b>\n<pre>{{items}}</pre>"
            f"{{warranty_text}}"
            f"{{after_note}}\n\n"
            f"<i>¡Gracias por tu compra! Si necesitas soporte contáctanos.</i>"
        )
    },

    "en": {
        # Main Menu and Navigation
        "welcome_header": f"{EMOJI_STORE} <b>WELCOME TO jvcᵈᵉᵛ Store</b> {EMOJI_STORE}",
        "user_label": "User",
        "balance_bot": "Bot Balance",
        "balance_provider": "Provider Balance (Bunai)",
        "orders_made": "Completed Orders",
        "select_option": "Select an option from the menu below to get started:",
        "maintenance_banner": f"{EMOJI_WARN} <i>The bot is currently in maintenance mode. Purchases are temporarily paused.</i>\n\n",
        "btn_catalog": "🛒 Service Catalog",
        "btn_deposit": "🪙 Deposit USDT",
        "btn_my_orders": "💼 My Orders",
        "btn_referrals": "🔗 Referrals",
        "btn_profile": "👤 My Profile",
        "btn_support": "🆘 Support & Help",
        "btn_admin": "⚙️ Admin Panel",
        "btn_back": "😀 Back",
        "btn_cancel": "❌ Cancel",
        "btn_main_menu": "🏠 Main Menu",
        "btn_refresh": "🔄 Refresh",
        "btn_search_service": "🔍 Search Service",
        "btn_contact_admin": "💬 Contact Administrator",

        # Profile and Language
        "profile_title": f"{EMOJI_USER} <b>User Profile</b>",
        "lang_label": "Language",
        "registered": "Registered",
        "btn_language": "🗣️ Language",
        "lang_select_title": f"{EMOJI_GLOBE} <b>SELECT YOUR PREFERRED LANGUAGE</b>\n\n<i>Choose the language you want to use with the bot:</i>",
        "lang_changed": f"{EMOJI_CHECK} Language updated to: {{lang_name}}",

        # Catalog and Category Picker
        "catalog_header_disponibles": f"{EMOJI_GREEN_DOT} <b>AVAILABLE PRODUCTS</b> ({{count}})",
        "catalog_header_agotados": f"{EMOJI_RED_DOT} <b>OUT OF STOCK PRODUCTS</b> ({{count}})",
        "catalog_header_ofertas": f"{EMOJI_GIFT} <b>SPECIAL OFFERS</b> ({{count}})",
        "catalog_header_todos": f"{EMOJI_MONITOR} <b>ALL SERVICES</b> ({{count}})",
        "btn_categories": "📁 Categories",
        "cat_picker_title": f"{EMOJI_FOLDER} <b>SELECT A CATEGORY</b>\n\n<i>Choose the catalog category you wish to view:</i>",
        "cat_opt_disponibles": "🟢 Available ({count})",
        "cat_opt_ofertas": "🕶 Special Offers ({count})",
        "cat_opt_agotados": "🔴 Out of Stock ({count})",
        "cat_opt_todos": "🖥 All Services ({count})",
        "catalog_empty": "There are no products in this category at the moment.",
        "stock_unlimited": "Unlimited (∞)",
        "stock_out": "Out of Stock",
        "product_label": "Product",
        "base_price_label": "Base Price",
        "available_stock_label": "Available Stock",
        "warranty_label": "Warranty",
        "no_warranty": "No Warranty",
        "warranty_days": "{days} Days",
        "warranty_hours": "{hours} Hours",
        "selected_qty": "Selected Qty",
        "total_amount": "Total Amount",
        "your_balance": "Balance",
        "btn_buy_qty": "🔣 Buy {qty} (${total} USDT)",
        "btn_recharge_balance": "🌟 Top Up Balance",
        "btn_share_link": "🔗 Share Link 📋",
        "btn_view_note": "📝 View Note",
        "admin_note_title": f"{EMOJI_NOTE} <b>Admin Note:</b>",
        "no_admin_note": "No additional terms or notes for this product.",
        "btn_notify_stock": "🔔 Notify me when in stock",
        "btn_cancel_stock_alert": "🔕 Active Alert (Tap to Cancel)",
        "alert_activated": f"{EMOJI_BELL} Alert activated! We will notify you via DM as soon as stock is available.",
        "alert_cancelled": f"{EMOJI_BELL_OFF} Stock alert cancelled.",
        "promo_offer_text": f"{EMOJI_GIFT} <b>Offer: Buy {{qty}}+ ➔ -{{discount}}% Off</b>",
        "restock_alert_title": f"{EMOJI_BELL} <b>PRODUCT BACK IN STOCK!</b>\n\n{EMOJI_BOX} <b>Product:</b> <code>{{product}}</code>\n{EMOJI_MONEY} <b>Price:</b> <code>${{price}} USDT</code>\n{EMOJI_DICE} <b>Available Stock:</b> <code>{{stock}} units</code>\n\n<i>The service you were waiting for is now in stock. Get it before it runs out!</i>",
        "btn_buy_now": "🔣 View and Buy Now",

        # Search
        "search_prompt_title": f"{EMOJI_SEARCH} <b>SERVICE SEARCH</b>\n\nType the name of the service you are looking for (e.g., <code>Gemini</code>, <code>Netflix</code>, <code>Office</code>).\n\n<i>Or type <code>/buscar name</code> at any time.</i>",
        "search_results_title": f"{EMOJI_SEARCH} <b>Results for:</b> <i>'{{query}}'</i> ({{count}} found):",
        "search_no_results": f"{EMOJI_SEARCH} <b>Results for:</b> <i>'{{query}}'</i>\n\n{EMOJI_CROSS} No products found with that name.",

        # Wallet and Deposits
        "wallet_title": f"{EMOJI_CARD} <b>WALLET & USDT DEPOSITS</b>\n\n{EMOJI_MONEY} <b>Current Balance:</b> <code>${{balance}} USDT</code>\n{EMOJI_GLOBE} <b>Accepted Network:</b> <code>BNB Smart Chain (BEP-20)</code>\n{EMOJI_LOCK} <b>Minimum Deposit:</b> <code>${{min_dep}} USDT</code>\n\n<i>Select an amount to top up or tap 'Enter Other Amount':</i>",
        "btn_custom_amount": "✍️ Enter Other Amount",
        "invoice_title": f"{EMOJI_CARD} <b>USDT (BEP-20) DEPOSIT INVOICE</b>\n\n{EMOJI_WARN} <b>IMPORTANT:</b> Send <b>EXACTLY</b> the amount shown below for automatic crediting.\n\n{EMOJI_TARGET} <b>Exact Amount to Send:</b>\n<code>{{exact_val}}</code> USDT\n\n{EMOJI_WALLET_ADDR} <b>Wallet Address (BNB Smart Chain / BEP-20):</b>\n<code>{{wallet}}</code>\n\n{EMOJI_HOURGLASS} <b>Time Limit:</b> <code>30 minutes</code>\n\n<i>Tap '📲 View QR Code' to scan from your app or transfer and tap 'Submit Hash / TxID'.</i>",
        "btn_show_qr": "📲 View QR Code",
        "btn_submit_hash": "🔗 Submit Hash / TxID",
        "btn_verify_payment": "🔄 Verify Payment",
        "btn_cancel_request": "❌ Cancel Request",
        "btn_back_to_invoice": "🔙 Back to Invoice",
        "qr_caption": f"{EMOJI_PHONE} <b>BSC (BEP-20) PAYMENT QR CODE</b>\n\n{EMOJI_TARGET} <b>Amount to send:</b> <code>{{exact_val}}</code> USDT\n{EMOJI_WALLET_ADDR} <b>Wallet:</b> <code>{{wallet}}</code>\n\n<i>Scan this code directly from Trust Wallet, Binance or MetaMask.</i>",
        "custom_amount_prompt": f"{EMOJI_WRITE} <b>ENTER AMOUNT TO DEPOSIT</b>\n\nType the amount of USDT you wish to add to your balance.\n\n{EMOJI_WARN} <b>Minimum Amount:</b> <code>{{min_dep}} USDT</code>\n\n<i>Example: Send a message typing <code>15</code> or <code>25.5</code></i>",
        "submit_hash_prompt": f"{EMOJI_LINK} <b>SUBMIT TRANSACTION HASH / TXID</b>\n\nPaste below the transaction Hash (TxID) from your wallet (Trust Wallet, Binance, MetaMask, etc).\n\n<i>Example: <code>0x4a8c9b...</code></i>",
        "deposit_cancelled_screen": f"{EMOJI_CROSS} <b>DEPOSIT REQUEST CANCELLED</b>\n\nThe deposit request for <b>${{amount}} USDT</b> has been cancelled.\n\n<i>You can generate a new request whenever you wish.</i>",
        "btn_new_deposit": "🪙 New Deposit",
        "verifying_tx": f"{EMOJI_HOURGLASS} <b>Verifying transaction on the BSC blockchain...</b>\n<i>Checking network nodes and confirmations.</i>",
        "deposit_success_title": f"{EMOJI_PARTY} <b>DEPOSIT CREDITED SUCCESSFULLY!</b>\n\n{EMOJI_MONEY} <b>Credited Amount:</b> <code>+${{amount}} USDT</code>\n{EMOJI_CARD} <b>New Total Balance:</b> <code>${{balance}} USDT</code>\n\n<i>You can now browse the catalog and purchase any digital service.</i>",

        # Purchases and Checkout
        "processing_order": f"{EMOJI_HOURGLASS} <b>Processing your order for {{qty}}x {{product}}...</b>\n<i>Please wait a few seconds.</i>",
        "purchase_fail_title": f"{EMOJI_CROSS} <b>PURCHASE COULD NOT BE COMPLETED</b>\n\nThe provider rejected the request (likely out of stock).\n\n{EMOJI_SHIELD} <b>Your balance of ${{total}} USDT has been fully refunded to your account.</b>",
        "purchase_success_title": f"{EMOJI_PARTY} <b>PURCHASE COMPLETED SUCCESSFULLY!</b>\n\n{EMOJI_BOX} <b>Product:</b> <code>{{product}}</code> (x{{qty}})\n{EMOJI_MONEY} <b>Total Paid:</b> <code>${{total}} USDT</code>\n{EMOJI_ID} <b>Order #:</b> <code>ORD_{{order_id}}</code>{{warranty_text}}\n\n{EMOJI_KEY} <b>YOUR SERVICE CREDENTIALS:</b>\n<pre>{{items}}</pre>{{after_note}}\n\n<i>{EMOJI_IDEA} You can view your purchased credentials anytime under 'My Orders'.</i>",
        "btn_view_in_orders": "💼 View in 'My Orders'",
        "btn_continue_shopping": "👆 Continue Shopping",

        # My Orders
        "orders_title": f"{EMOJI_ORDERS} <b>MY ORDERS ({{count}} Total)</b>\n<i>Select an order to view credentials:</i>\n",
        "orders_empty": f"{EMOJI_ORDERS} <b>MY ORDERS</b>\n\nYou haven't placed any orders yet.\n\n<i>Explore our catalog and get premium digital accounts at the best price.</i>",
        "order_detail_title": f"{EMOJI_SHOPPING} <b>ORDER DETAILS #ORD_{{order_id}}</b>\n\n{EMOJI_BOX} <b>Product:</b> <code>{{product}}</code> (x{{qty}})\n{EMOJI_MONEY} <b>Price Paid:</b> <code>${{total}} USDT</code>\n{EMOJI_SHIELD} <b>Warranty:</b> <code>{{warranty}}</code>\n{EMOJI_CALENDAR} <b>Date:</b> <code>{{date}}</code>\n{EMOJI_ID} <b>Provider ID:</b> <code>{{prov_id}}</code>\n\n{EMOJI_KEY} <b>DELIVERED CREDENTIALS:</b>\n<pre>{{items}}</pre>",

        # Referrals
        "referrals_title": f"{EMOJI_LINK} <b>REFERRAL & AFFILIATE SYSTEM</b>\n\nInvite your friends and earn an automatic <b>{{percent}}% commission</b> on every balance deposit they make!\n\n{EMOJI_USERS} <b>Your Registered Referrals:</b> <code>{{count}} users</code>\n{EMOJI_MONEY} <b>Earned Commissions:</b> <code>${{earnings}} USDT</code>\n\n{EMOJI_TARGET} <b>Your Exclusive Referral Link:</b>\n<code>{{ref_link}}</code>\n\n<i>Share your link and start earning passive income.</i>",
        "btn_share_ref": "📢 Share Referral Link",

        # Support
        "support_text": f"{EMOJI_SUPPORT} <b>SUPPORT & HELP</b>\n\nDo you have questions about your purchases, deposits or need assistance?\n\n• <b>Warranty:</b> If any service under warranty experiences issues during the active period, contact us immediately with your <b>Order ID</b>.\n• <b>Deposits:</b> USDT BEP-20 deposits are credited automatically after network confirmation.\n\n{EMOJI_CHAT} <i>To contact an administrator directly tap the button below:</i>",

        # VIP Reseller Plan
        "btn_vip_plan": "👑 VIP Reseller Plan (20% OFF)",
        "btn_vip_my_plan": "👑 My VIP Membership",
        "btn_activate_vip": "⭐ Activate VIP Plan (10 USDT / 30 days)",
        "btn_renew_vip": "🔄 Renew VIP Plan (10 USDT)",
        "btn_confirm_pay_vip": "✅ Confirm and Pay 10 USDT",
        "btn_copy_client": "📋 Copy for Customer",
        "vip_status_regular": "Regular",
        "vip_status_active": "⭐ VIP Reseller",
        "vip_confirm_title": (
            f"👑 <b>CONFIRM PURCHASE - VIP RESELLER PLAN</b>\n\n"
            f"Do you want to activate your <b>VIP Reseller Membership</b> for <b>30 days</b>?\n\n"
            f"💵 <b>Plan Cost:</b> <code>10.00 USDT</code>\n"
            f"⏳ <b>Duration:</b> <code>30 days</code>\n"
            f"💳 <b>Your Current Balance:</b> <code>${{balance}} USDT</code>\n\n"
            f"<i>Upon confirmation, 10.00 USDT will be deducted from your bot balance and your 20% OFF rates will be activated immediately.</i>"
        ),
        "vip_info_title": (
            f"👑 <b>VIP RESELLER PLAN</b>\n\n"
            f"Do you resell digital services or want to maximize profits? Become a <b>VIP Partner</b> and get the highest margins:\n\n"
            f"💎 <b>20% Automatic Discount:</b> Wholesale prices across our entire catalog.\n"
            f"⚡ <b>Priority Restock Alerts:</b> Get notified before anyone else when popular services restock.\n"
            f"📋 <b>White-Label Delivery:</b> Clean, formatted credentials ready to forward to your WhatsApp clients with zero store branding.\n"
            f"👥 <b>Double Referral Commission:</b> Earn <b>20% commission</b> on your referrals' deposits (vs 5% regular).\n"
            f"🛡️ <b>Priority Support:</b> Fast warranty resolutions.\n\n"
            f"💵 <b>Price:</b> <code>10.00 USDT</code> / 30 days\n"
            f"<i>(Half of what competitors charge for identical perks!)</i>"
        ),
        "vip_active_title": (
            f"👑 <b>YOUR VIP MEMBERSHIP IS ACTIVE</b>\n\n"
            f"You enjoy all exclusive benefits and <b>20% OFF</b> catalog-wide.\n\n"
            f"📅 <b>Expires on:</b> <code>{{expires_at}}</code>\n"
            f"⏳ <b>Days left:</b> <code>{{days_left}} days</code>\n\n"
            f"<i>You can renew anytime to extend your plan by another 30 days.</i>"
        ),
        "vip_success_activated": (
            f"🎉 <b>WELCOME TO THE VIP RESELLER PLAN!</b>\n\n"
            f"Your membership is now active for <b>30 days</b>.\n\n"
            f"🌟 <b>Active Perks:</b>\n"
            f"• 20% automatic discount on all services.\n"
            f"• Early restock alerts.\n"
            f"• White-label delivery format.\n"
            f"• 20% referral commissions.\n\n"
            f"📅 <b>Valid until:</b> <code>{{expires_at}}</code>"
        ),
        "vip_insufficient_funds": (
            f"⚠️ <b>INSUFFICIENT BALANCE</b>\n\n"
            f"To activate the VIP Plan you need <b>10.00 USDT</b> in your bot balance.\n"
            f"Your current balance is: <code>${{balance}} USDT</code>.\n\n"
            f"<i>Please top up your balance to proceed.</i>"
        ),
        "vip_warn_24h_msg": (
            f"⚠️ <b>YOUR VIP MEMBERSHIP EXPIRES IN 24 HOURS!</b> ⚠️\n\n"
            f"Your VIP Reseller Plan expires in less than <b>24 hours</b> (Expires: <code>{{expires_at}}</code>).\n\n"
            f"Renew now to keep your <b>20% discount</b> and perks active."
        ),
        "vip_warn_2h_msg": (
            f"🚨 <b>URGENT: YOUR VIP MEMBERSHIP EXPIRES IN 2 HOURS!</b> 🚨\n\n"
            f"Your VIP Reseller Plan expires today at <code>{{expires_at}}</code>.\n\n"
            f"<i>Renew immediately to maintain your wholesale pricing.</i>"
        ),
        "vip_expired_msg": (
            f"❌ <b>YOUR VIP MEMBERSHIP HAS EXPIRED</b>\n\n"
            f"Your 30-day period ended and your account reverted to Regular status.\n\n"
            f"<i>You can reactivate anytime for 10 USDT to restore your 20% OFF.</i>"
        ),
        "vip_admin_granted_msg": (
            f"👑 <b>VIP MEMBERSHIP GRANTED BY ADMIN!</b>\n\n"
            f"An administrator has granted you <b>VIP Reseller</b> access for <b>{{days}} days</b>.\n\n"
            f"📅 <b>Valid until:</b> <code>{{expires_at}}</code>\n\n"
            f"<i>Enjoy your 20% discount on all digital services!</i>"
        ),
        "vip_client_template": (
            f"✨ <b>Your Digital Service</b> ✨\n\n"
            f"📦 <b>Product:</b> {{product}}\n"
            f"🔑 <b>Login Details:</b>\n<pre>{{items}}</pre>"
            f"{{warranty_text}}"
            f"{{after_note}}\n\n"
            f"<i>Thank you for your purchase!</i>"
        )
    },

    "pt": {
        # Menu Principal e Navegação
        "welcome_header": f"{EMOJI_STORE} <b>BEM-VINDO À jvcᵈᵉᵛ Store</b> {EMOJI_STORE}",
        "user_label": "Usuário",
        "balance_bot": "Saldo no Bot",
        "balance_provider": "Saldo Provedor (Bunai)",
        "orders_made": "Compras Realizadas",
        "select_option": "Selecione uma opção no menu abaixo para começar:",
        "maintenance_banner": f"{EMOJI_WARN} <i>O bot está em modo de manutenção. As compras estão pausadas temporariamente.</i>\n\n",
        "btn_catalog": "🛒 Catálogo de Serviços",
        "btn_deposit": "🪙 Depositar USDT",
        "btn_my_orders": "💼 Meus Pedidos",
        "btn_referrals": "🔗 Referidos",
        "btn_profile": "👤 Meu Perfil",
        "btn_support": "🆘 Suporte & Ajuda",
        "btn_admin": "⚙️ Painel de Administração",
        "btn_back": "😀 Voltar",
        "btn_cancel": "❌ Cancelar",
        "btn_main_menu": "🏠 Menu Principal",
        "btn_refresh": "🔄 Atualizar",
        "btn_search_service": "🔍 Buscar Serviço",
        "btn_contact_admin": "💬 Contatar Administrador",

        # Perfil e Idiomas
        "profile_title": f"{EMOJI_USER} <b>Perfil de Usuário</b>",
        "lang_label": "Idioma",
        "registered": "Registro",
        "btn_language": "🗣️ Idioma",
        "lang_select_title": f"{EMOJI_GLOBE} <b>SELECIONE SEU IDIOMA PREFERIDO</b>\n\n<i>Escolha o idioma que deseja usar no bot:</i>",
        "lang_changed": f"{EMOJI_CHECK} Idioma atualizado para: {{lang_name}}",

        # Catálogo e Seletor de Categorias
        "catalog_header_disponibles": f"{EMOJI_GREEN_DOT} <b>PRODUTOS DISPONÍVEIS</b> ({{count}})",
        "catalog_header_agotados": f"{EMOJI_RED_DOT} <b>PRODUTOS ESGOTADOS</b> ({{count}})",
        "catalog_header_ofertas": f"{EMOJI_GIFT} <b>OFERTAS ESPECIAIS</b> ({{count}})",
        "catalog_header_todos": f"{EMOJI_MONITOR} <b>TODOS OS SERVIÇOS</b> ({{count}})",
        "btn_categories": "📁 Categorias",
        "cat_picker_title": f"{EMOJI_FOLDER} <b>SELECIONE UMA CATEGORIA</b>\n\n<i>Escolha a categoria do catálogo que deseja visualizar:</i>",
        "cat_opt_disponibles": "🟢 Disponíveis ({count})",
        "cat_opt_ofertas": "🕶 Em Oferta ({count})",
        "cat_opt_agotados": "🔴 Esgotados ({count})",
        "cat_opt_todos": "🖥 Todos ({count})",
        "catalog_empty": "Não há produtos nesta categoria no momento.",
        "stock_unlimited": "Ilimitado (∞)",
        "stock_out": "Esgotado",
        "product_label": "Produto",
        "base_price_label": "Preço Base",
        "available_stock_label": "Estoque Disponível",
        "warranty_label": "Garantia",
        "no_warranty": "Sem Garantia",
        "warranty_days": "{days} Dias",
        "warranty_hours": "{hours} Horas",
        "selected_qty": "Qtd. Selecionada",
        "total_amount": "Valor Total",
        "your_balance": "Saldo",
        "btn_buy_qty": "🔣 Comprar {qty} (${total} USDT)",
        "btn_recharge_balance": "🌟 Recarregar Saldo",
        "btn_share_link": "🔗 Compartilhar Link 📋",
        "btn_view_note": "📝 Ver Nota",
        "admin_note_title": f"{EMOJI_NOTE} <b>Nota do Admin:</b>",
        "no_admin_note": "Sem notas adicionais para este produto.",
        "btn_notify_stock": "🔔 Avisar quando houver estoque",
        "btn_cancel_stock_alert": "🔕 Alerta Ativo (Toque para Cancelar)",
        "alert_activated": f"{EMOJI_BELL} Alerta ativado! Notificaremos por mensagem privada quando houver estoque.",
        "alert_cancelled": f"{EMOJI_BELL_OFF} Alerta de estoque cancelado.",
        "promo_offer_text": f"{EMOJI_GIFT} <b>Oferta: Compre {{qty}}+ ➔ -{{discount}}% Desc</b>",
        "restock_alert_title": f"{EMOJI_BELL} <b>PRODUTO DE VOLTA AO ESTOQUE!</b>\n\n{EMOJI_BOX} <b>Produto:</b> <code>{{product}}</code>\n{EMOJI_MONEY} <b>Preço:</b> <code>${{price}} USDT</code>\n{EMOJI_DICE} <b>Estoque Disponível:</b> <code>{{stock}} unidades</code>\n\n<i>O serviço que você estava esperando já está disponível. Aproveite antes que acabe!</i>",
        "btn_buy_now": "🔣 Ver e Comprar Agora",

        # Busca
        "search_prompt_title": f"{EMOJI_SEARCH} <b>BUSCADOR DE SERVIÇOS</b>\n\nDigite o nome do serviço procurado (ex: <code>Gemini</code>, <code>Netflix</code>, <code>Office</code>).\n\n<i>Ou digite <code>/buscar nome</code> a qualquer momento.</i>",
        "search_results_title": f"{EMOJI_SEARCH} <b>Resultados para:</b> <i>'{{query}}'</i> ({{count}} encontrados):",
        "search_no_results": f"{EMOJI_SEARCH} <b>Resultados para:</b> <i>'{{query}}'</i>\n\n{EMOJI_CROSS} Nenhum produto encontrado com esse nome.",

        # Carteira e Depósitos
        "wallet_title": f"{EMOJI_CARD} <b>CARTEIRA & DEPÓSITOS USDT</b>\n\n{EMOJI_MONEY} <b>Saldo Atual:</b> <code>${{balance}} USDT</code>\n{EMOJI_GLOBE} <b>Rede Aceita:</b> <code>BNB Smart Chain (BEP-20)</code>\n{EMOJI_LOCK} <b>Depósito Mínimo:</b> <code>${{min_dep}} USDT</code>\n\n<i>Selecione o valor que deseja recarregar ou toque em 'Digitar Outro Valor':</i>",
        "btn_custom_amount": "✍️ Digitar Outro Valor",
        "invoice_title": f"{EMOJI_CARD} <b>SOLICITAÇÃO DE RECARGA USDT (BEP-20)</b>\n\n{EMOJI_WARN} <b>IMPORTANTE:</b> Envie <b>EXACTAMENTE</b> o valor indicado abaixo para que a confirmação seja automática.\n\n{EMOJI_TARGET} <b>Valor Exato a Enviar:</b>\n<code>{{exact_val}}</code> USDT\n\n{EMOJI_WALLET_ADDR} <b>Endereço da Carteira (BNB Smart Chain / BEP-20):</b>\n<code>{{wallet}}</code>\n\n{EMOJI_HOURGLASS} <b>Tempo Limite:</b> <code>30 minutos</code>\n\n<i>Toque em '📲 Ver Código QR' para escanear no seu app ou transfira e toque em 'Informar Hash / TxID'.</i>",
        "btn_show_qr": "📲 Ver Código QR",
        "btn_submit_hash": "🔗 Informar Hash / TxID",
        "btn_verify_payment": "🔄 Verificar Pagamento",
        "btn_cancel_request": "❌ Cancelar Solicitação",
        "btn_back_to_invoice": "🔙 Voltar à Solicitação",
        "qr_caption": f"{EMOJI_PHONE} <b>CÓDIGO QR DE PAGAMENTO BSC (BEP-20)</b>\n\n{EMOJI_TARGET} <b>Valor a transferir:</b> <code>{{exact_val}}</code> USDT\n{EMOJI_WALLET_ADDR} <b>Carteira:</b> <code>{{wallet}}</code>\n\n<i>Escaneie este código diretamente na Trust Wallet, Binance ou MetaMask.</i>",
        "custom_amount_prompt": f"{EMOJI_WRITE} <b>DIGITE O VALOR DO DEPÓSITO</b>\n\nDigite a quantidade de USDT que deseja adicionar ao seu saldo.\n\n{EMOJI_WARN} <b>Valor Mínimo:</b> <code>{{min_dep}} USDT</code>\n\n<i>Exemplo: Envie uma mensagem digitando <code>15</code> ou <code>25.5</code></i>",
        "submit_hash_prompt": f"{EMOJI_LINK} <b>ENVIE O HASH / TXID DA TRANSAÇÃO</b>\n\nCole abaixo o Hash (TxID) da transferência realizada da sua carteira (Trust Wallet, Binance, MetaMask, etc).\n\n<i>Exemplo: <code>0x4a8c9b...</code></i>",
        "deposit_cancelled_screen": f"{EMOJI_CROSS} <b>SOLICITAÇÃO DE RECARGA CANCELADA</b>\n\nA solicitação de <b>${{amount}} USDT</b> foi cancelada com sucesso.\n\n<i>Você pode gerar uma nova solicitação quando quiser.</i>",
        "btn_new_deposit": "🪙 Nova Recarga",
        "verifying_tx": f"{EMOJI_HOURGLASS} <b>Verificando transação na blockchain BSC...</b>\n<i>Consultando nós da rede e confirmações.</i>",
        "deposit_success_title": f"{EMOJI_PARTY} <b>DEPÓSITO CONFIRMADO COM SUCESSO!</b>\n\n{EMOJI_MONEY} <b>Valor Creditado:</b> <code>+${{amount}} USDT</code>\n{EMOJI_CARD} <b>Novo Saldo Total:</b> <code>${{balance}} USDT</code>\n\n<i>Agora você pode navegar pelo catálogo e comprar qualquer serviço.</i>",

        # Compras e Checkout
        "processing_order": f"{EMOJI_HOURGLASS} <b>Processando seu pedido de {{qty}}x {{product}}...</b>\n<i>Por favor, aguarde alguns segundos.</i>",
        "purchase_fail_title": f"{EMOJI_CROSS} <b>NÃO FOI POSSÍVEL CONCLUIR A COMPRA</b>\n\nO provedor recusou o pedido (provavelmente sem estoque).\n\n{EMOJI_SHIELD} <b>Seu saldo de ${{total}} USDT foi estornado integralmente para sua conta.</b>",
        "purchase_success_title": f"{EMOJI_PARTY} <b>COMPRA REALIZADA COM SUCESSO!</b>\n\n{EMOJI_BOX} <b>Produto:</b> <code>{{product}}</code> (x{{qty}})\n{EMOJI_MONEY} <b>Total Pago:</b> <code>${{total}} USDT</code>\n{EMOJI_ID} <b>Pedido #:</b> <code>ORD_{{order_id}}</code>{{warranty_text}}\n\n{EMOJI_KEY} <b>DADOS DO SEU SERVIÇO:</b>\n<pre>{{items}}</pre>{{after_note}}\n\n<i>{EMOJI_IDEA} Você pode consultar suas compras e credenciais a qualquer momento em 'Meus Pedidos'.</i>",
        "btn_view_in_orders": "💼 Ver em 'Meus Pedidos'",
        "btn_continue_shopping": "👆 Continuar Comprando",

        # Meus Pedidos
        "orders_title": f"{EMOJI_ORDERS} <b>MEUS PEDIDOS ({{count}} Total)</b>\n<i>Selecione um pedido para ver as credenciais:</i>\n",
        "orders_empty": f"{EMOJI_ORDERS} <b>MEUS PEDIDOS</b>\n\nVocê ainda não fez nenhum pedido.\n\n<i>Explore nosso catálogo e adquira contas premium pelo melhor preço.</i>",
        "order_detail_title": f"{EMOJI_SHOPPING} <b>DETALHES DO PEDIDO #ORD_{{order_id}}</b>\n\n{EMOJI_BOX} <b>Produto:</b> <code>{{product}}</code> (x{{qty}})\n{EMOJI_MONEY} <b>Preço Pago:</b> <code>${{total}} USDT</code>\n{EMOJI_SHIELD} <b>Garantia:</b> <code>{{warranty}}</code>\n{EMOJI_CALENDAR} <b>Data:</b> <code>{{date}}</code>\n{EMOJI_ID} <b>ID Provedor:</b> <code>{{prov_id}}</code>\n\n{EMOJI_KEY} <b>CREDENCIAS ENTREGUES:</b>\n<pre>{{items}}</pre>",

        # Indicações
        "referrals_title": f"{EMOJI_LINK} <b>SISTEMA DE INDICAÇÕES & AFILIADOS</b>\n\nConvide seus amigos e ganhe <b>{{percent}}% de comissão</b> automática sobre cada recarga de saldo que eles fizerem!\n\n{EMOJI_USERS} <b>Seus Indicados Registrados:</b> <code>{{count}} usuários</code>\n{EMOJI_MONEY} <b>Comissões Ganhas:</b> <code>${{earnings}} USDT</code>\n\n{EMOJI_TARGET} <b>Seu Link Exclusivo de Convite:</b>\n<code>{{ref_link}}</code>\n\n<i>Compartilhe seu link e comece a gerar renda passiva.</i>",
        "btn_share_ref": "📢 Compartilhar Link de Indicação",

        # Suporte
        "support_text": f"{EMOJI_SUPPORT} <b>SUPORTE & AJUDA</b>\n\nTem dúvidas sobre compras, depósitos ou precisa de assistência?\n\n• <b>Garantia:</b> Se algum serviço com garantia apresentar problemas durante o período ativo, entre em contato imediatamente com o seu <b>ID de Pedido</b>.\n• <b>Depósitos:</b> Os depósitos em USDT BEP-20 são creditados automaticamente após a confirmação da rede.\n\n{EMOJI_CHAT} <i>Para falar directamente com um administrador toque no botão abaixo:</i>",

        # Plano Revendedor VIP
        "btn_vip_plan": "👑 Plano Revendedor VIP (20% OFF)",
        "btn_vip_my_plan": "👑 Minha Assinatura VIP",
        "btn_activate_vip": "⭐ Ativar Plano VIP (10 USDT / 30 dias)",
        "btn_renew_vip": "🔄 Renovar Plano VIP (10 USDT)",
        "btn_confirm_pay_vip": "✅ Confirmar e Pagar 10 USDT",
        "btn_copy_client": "📋 Copiar para Cliente",
        "vip_status_regular": "Regular",
        "vip_status_active": "⭐ Revendedor VIP",
        "vip_confirm_title": (
            f"👑 <b>CONFIRMAR COMPRA - PLANO REVENDEDOR VIP</b>\n\n"
            f"Deseja ativar sua <b>Assinatura Revendedor VIP</b> por <b>30 dias</b>?\n\n"
            f"💵 <b>Valor do Plano:</b> <code>10.00 USDT</code>\n"
            f"⏳ <b>Duração:</b> <code>30 dias</code>\n"
            f"💳 <b>Seu Saldo Atual:</b> <code>${{balance}} USDT</code>\n\n"
            f"<i>Ao confirmar, 10.00 USDT serão debitados do seu saldo do bot e suas tarifas de 20% OFF serão ativadas imediatamente.</i>"
        ),
        "vip_info_title": (
            f"👑 <b>PLANO PARA REVENDEDORES VIP</b>\n\n"
            f"Revende serviços digitais ou quer maximizar seus lucros? Torne-se um <b>Parceiro VIP</b> e tenha as melhores margens do mercado:\n\n"
            f"💎 <b>20% de Desconto Automático:</b> Preços no atacado aplicados diretamente em todo o catálogo.\n"
            f"⚡ <b>Alertas de Estoque Prioritários:</b> Seja notificado antes de todo mundo quando serviços populares voltarem ao estoque.\n"
            f"📋 <b>Entrega Marca Branca:</b> Botão exclusivo para copiar as credenciais limpas e formatadas, prontas para enviar aos seus clientes no WhatsApp sem links nem marcas.\n"
            f"👥 <b>Comissão Dupla em Indicações:</b> Ganhe <b>20% de comissão</b> sobre cada recarga de saldo dos seus indicados (vs 5% regular).\n"
            f"🛡️ <b>Suporte Prioritário:</b> Atendimento ágil e garantia rápida.\n\n"
            f"💵 <b>Investimento:</b> <code>10.00 USDT</code> / 30 dias\n"
            f"<i>(Metade do preço cobrado pelos concorrentes pelos mesmos benefícios!)</i>"
        ),
        "vip_active_title": (
            f"👑 <b>SUA ASSINATURA VIP ESTÁ ATIVA</b>\n\n"
            f"Você aproveita todas as vantagens e <b>20% OFF</b> em todo o catálogo.\n\n"
            f"📅 <b>Expira em:</b> <code>{{expires_at}}</code>\n"
            f"⏳ <b>Dias restantes:</b> <code>{{days_left}} dias</code>\n\n"
            f"<i>Você pode renovar a qualquer momento para estender por mais 30 dias.</i>"
        ),
        "vip_success_activated": (
            f"🎉 <b>BEM-VINDO AO PLANO REVENDEDOR VIP!</b>\n\n"
            f"Sua assinatura foi ativada com sucesso por <b>30 dias</b>.\n\n"
            f"🌟 <b>Benefícios ativos:</b>\n"
            f"• 20% de desconto automático no catálogo.\n"
            f"• Alertas de estoque antecipados.\n"
            f"• Formato de entrega limpo para clientes.\n"
            f"• 20% de comissão de indicações.\n\n"
            f"📅 <b>Válido até:</b> <code>{{expires_at}}</code>"
        ),
        "vip_insufficient_funds": (
            f"⚠️ <b>SALDO INSUFICIENTE</b>\n\n"
            f"Para ativar o Plano VIP você precisa de <b>10.00 USDT</b> no seu saldo do bot.\n"
            f"Seu saldo atual é de: <code>${{balance}} USDT</code>.\n\n"
            f"<i>Por favor recarregue seu saldo para continuar.</i>"
        ),
        "vip_warn_24h_msg": (
            f"⚠️ <b>SUA ASSINATURA VIP EXPIRA EM 24 HORAS!</b> ⚠️\n\n"
            f"Lembramos que seu Plano Revendedor VIP tem menos de <b>24 horas</b> restantes (Expira: <code>{{expires_at}}</code>).\n\n"
            f"Renove agora para não perder seus <b>20% de desconto</b> e vantagens exclusivas."
        ),
        "vip_warn_2h_msg": (
            f"🚨 <b>URGENTE: SUA ASSINATURA VIP EXPIRA EM 2 HORAS!</b> 🚨\n\n"
            f"Seu Plano Revendedor VIP vai expirar hoje às <code>{{expires_at}}</code>.\n\n"
            f"<i>Renove imediatamente para manter seus preços de distribuidor.</i>"
        ),
        "vip_expired_msg": (
            f"❌ <b>SUA ASSINATURA VIP TERMINOU</b>\n\n"
            f"Seu período de 30 dias terminou e sua conta voltou ao status Regular.\n\n"
            f"<i>Você pode reativar a qualquer momento por 10 USDT para recuperar o 20% OFF.</i>"
        ),
        "vip_admin_granted_msg": (
            f"👑 <b>ASSINATURA VIP CONCEDIDA PELO ADMINISTRADOR!</b>\n\n"
            f"Um administrador concedeu acesso ao <b>Plano Revendedor VIP</b> por <b>{{days}} dias</b>.\n\n"
            f"📅 <b>Válido até:</b> <code>{{expires_at}}</code>\n\n"
            f"<i>Aproveite seu desconto de 20% em todo o catálogo!</i>"
        ),
        "vip_client_template": (
            f"✨ <b>Seu Serviço Digital</b> ✨\n\n"
            f"📦 <b>Produto:</b> {{product}}\n"
            f"🔑 <b>Dados de Acesso:</b>\n<pre>{{items}}</pre>"
            f"{{warranty_text}}"
            f"{{after_note}}\n\n"
            f"<i>Obrigado pela sua compra!</i>"
        )
    }
}

def t(key: str, lang: str = "es", **kwargs) -> str:
    """Obtiene el texto traducido para la clave e idioma solicitados con formateo robusto"""
    lang_code = lang.lower() if lang else "es"
    if lang_code not in TRANSLATIONS:
        lang_code = "es"
    
    text = TRANSLATIONS[lang_code].get(key, TRANSLATIONS["es"].get(key, key))
    if kwargs:
        try:
            safe_kwargs = {k: str(v) for k, v in kwargs.items()}
            return text.format(**safe_kwargs)
        except Exception:
            result = text
            for k, v in kwargs.items():
                result = result.replace(f"{{{k}}}", str(v))
            return result
    return text
