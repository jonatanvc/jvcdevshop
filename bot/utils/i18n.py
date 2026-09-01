from typing import Dict, Any

LANGUAGES = {
    "es": "🇪🇸 Español",
    "en": "🇺🇸 English",
    "pt": "🇧🇷 Português"
}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "es": {
        # Menú Principal y Navegación
        "welcome_header": "💎 <b>BIENVENIDO A jvcᵈᵉᵛ Store</b> 💎",
        "user_label": "Usuario",
        "balance_bot": "Saldo en Bot",
        "balance_provider": "Saldo Proveedor (Bunai)",
        "orders_made": "Compras Realizadas",
        "select_option": "Selecciona una opción del menú inferior para comenzar:",
        "maintenance_banner": "⚠️ <i>El bot está en modo mantenimiento. Las compras están pausadas temporalmente.</i>\n\n",
        "btn_catalog": "🛒 Catálogo de Servicios",
        "btn_deposit": "💳 Depositar USDT",
        "btn_my_orders": "💼 Mis Pedidos",
        "btn_referrals": "🔗 Referidos",
        "btn_profile": "👤 Mi Perfil",
        "btn_support": "🆘 Soporte & Ayuda",
        "btn_admin": "⚙️ Panel de Administración",
        "btn_back": "Volver",
        "btn_main_menu": "🏠 Menú Principal",
        "btn_refresh": "🔄 Actualizar",
        "btn_search_service": "🔍 Buscar Servicio",
        "btn_contact_admin": "💬 Contactar Administrador",

        # Perfil e Idiomas
        "profile_title": "👤 <b>Perfil de Usuario</b>",
        "lang_label": "Idioma",
        "registered": "Registro",
        "btn_language": "🗣️ Idioma",
        "lang_select_title": "🌐 <b>SELECCIONA TU IDIOMA PREFERIDO</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Elige el idioma con el que deseas utilizar el bot:</i>",
        "lang_changed": "✅ Idioma actualizado a: {lang_name}",

        # Catálogo y Selector de Categorías
        "catalog_header_disponibles": "🟢 <b>PRODUCTOS DISPONIBLES</b> ({count})",
        "catalog_header_agotados": "🔴 <b>PRODUCTOS AGOTADOS</b> ({count})",
        "catalog_header_ofertas": "🎁 <b>PRODUCTOS EN OFERTA</b> ({count})",
        "catalog_header_todos": "📋 <b>TODOS LOS SERVICIOS</b> ({count})",
        "btn_categories": "📂 Categorías",
        "cat_picker_title": "📂 <b>SELECCIONA UNA CATEGORÍA</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Elige la categoría del catálogo que deseas ver:</i>",
        "cat_opt_disponibles": "🟢 Disponibles ({count})",
        "cat_opt_ofertas": "🎁 En Oferta ({count})",
        "cat_opt_agotados": "🔴 Agotados ({count})",
        "cat_opt_todos": "📋 Todos ({count})",
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
        "btn_buy_qty": "🛒 Comprar {qty} (${total} USDT)",
        "btn_recharge_balance": "⊞ Recargar Saldo",
        "btn_share_link": "🔗 Compartir Enlace 📋",
        "btn_view_note": "📝 Ver Nota",
        "admin_note_title": "📝 <b>Nota del Admin:</b>",
        "no_admin_note": "No hay notas adicionales configuradas para este producto.",
        "btn_notify_stock": "🔔 Avisarme cuando haya stock",
        "btn_cancel_stock_alert": "🔕 Alerta Activa (Toca para Cancelar)",
        "alert_activated": "🔔 ¡Alerta activada! Te avisaremos por privado cuando haya stock.",
        "alert_cancelled": "🔕 Alerta de stock cancelada.",
        "promo_offer_text": "🎁 <b>Oferta: Compra {qty}+ ➔ -{discount}% Desc</b>",
        "restock_alert_title": "🔔 <b>¡PRODUCTO RESTABLECIDO EN STOCK!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n📦 <b>Producto:</b> <code>{product}</code>\n💰 <b>Precio:</b> <code>${price} USDT</code>\n🎲 <b>Stock Disponible:</b> <code>{stock} unidades</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>El servicio que estabas esperando ya tiene stock disponible. ¡Aprovecha antes de que se agote!</i>",
        "btn_buy_now": "🛒 Ver y Comprar Ahora",

        # Buscador
        "search_prompt_title": "🔍 <b>BUSCADOR DE SERVICIOS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nEscribe el nombre del servicio que buscas (ejemplo: <code>Gemini</code>, <code>Netflix</code>, <code>Office</code>).\n\n<i>O escribe <code>/buscar nombre</code> en cualquier momento.</i>",
        "search_results_title": "🔍 <b>Resultados para:</b> <i>'{query}'</i> ({count} encontrados):",
        "search_no_results": "🔍 <b>Resultados para:</b> <i>'{query}'</i>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n❌ No se encontraron productos con ese nombre.",

        # Billetera y Depósitos
        "wallet_title": "💳 <b>BILLETERA & DEPÓSITOS USDT</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 <b>Saldo Actual:</b> <code>${balance} USDT</code>\n🌐 <b>Red Aceptada:</b> <code>BNB Smart Chain (BEP-20)</code>\n🔒 <b>Depósito Mínimo:</b> <code>${min_dep} USDT</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Selecciona el monto que deseas recargar o pulsa 'Ingresar Otro Monto':</i>",
        "btn_custom_amount": "✍️ Ingresar Otro Monto",
        "invoice_title": "💳 <b>SOLICITUD DE RECARGA USDT (BEP-20)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n⚠️ <b>IMPORTANTE:</b> Envía <b>EXACTAMENTE</b> la cantidad indicada a continuación para que la acreditación sea automática.\n\n🎯 <b>Monto Exacto a Enviar:</b>\n<code>{exact_val}</code> USDT\n\n📬 <b>Dirección de Billetera (BNB Smart Chain / BEP-20):</b>\n<code>{wallet}</code>\n\n⏳ <b>Tiempo Límite:</b> <code>30 minutos</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Pulsa '📱 Ver Código QR' para escanear desde tu app o realiza la transferencia y luego pulsa 'Ingresar Hash / TxID'.</i>",
        "btn_show_qr": "📱 Ver Código QR",
        "btn_submit_hash": "🔗 Ingresar Hash / TxID",
        "btn_verify_payment": "🔄 Verificar Pago",
        "btn_cancel_request": "❌ Cancelar Solicitud",
        "btn_back_to_invoice": "🔙 Volver a la Solicitud",
        "qr_caption": "📱 <b>CÓDIGO QR DE PAGO BSC (BEP-20)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 <b>Monto a transferir:</b> <code>{exact_val}</code> USDT\n📬 <b>Billetera:</b> <code>{wallet}</code>\n\n<i>Escanea este código directamente desde Trust Wallet, Binance o MetaMask.</i>",
        "custom_amount_prompt": "✍️ <b>INGRESA EL MONTO A DEPOSITAR</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nEscribe la cantidad de USDT que deseas recargar en tu cuenta.\n\n⚠️ <b>Monto Mínimo:</b> <code>{min_dep} USDT</code>\n\n<i>Ejemplo: Envía un mensaje escribiendo <code>15</code> o <code>25.5</code></i>",
        "submit_hash_prompt": "🔗 <b>ENVÍA EL HASH / TXID DE LA TRANSACCIÓN</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nPega a continuación el Hash (TxID) de la transferencia realizada desde tu billetera (Trust Wallet, Binance, MetaMask, etc).\n\n<i>Ejemplo: <code>0x4a8c9b...</code></i>",
        "deposit_cancelled_screen": "❌ <b>SOLICITUD DE RECARGA CANCELADA</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nLa solicitud por <b>${amount} USDT</b> ha sido cancelada correctamente.\n\n<i>Puedes generar una nueva solicitud cuando desees.</i>",
        "btn_new_deposit": "💳 Nueva Recarga",
        "verifying_tx": "⏳ <b>Verificando transacción en la blockchain BSC...</b>\n<i>Consultando nodos de red y confirmaciones.</i>",
        "deposit_success_title": "🎉 <b>¡DEPÓSITO ACREDITADO CON ÉXITO!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 <b>Monto Acreditado:</b> <code>+${amount} USDT</code>\n💳 <b>Nuevo Saldo Total:</b> <code>${balance} USDT</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Ya puedes explorar el catálogo y comprar cualquier servicio digital.</i>",

        # Compras y Checkout
        "processing_order": "⏳ <b>Procesando tu orden de {qty}x {product}...</b>\n<i>Por favor espera unos segundos.</i>",
        "purchase_fail_title": "❌ <b>NO SE PUDO COMPLETAR LA COMPRA</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nEl proveedor rechazó la solicitud (posiblemente sin stock suficiente).\n\n🛡️ <b>Tu saldo de ${total} USDT ha sido reembolsado intacto a tu cuenta.</b>",
        "purchase_success_title": "🎉 <b>¡COMPRA REALIZADA CON ÉXITO!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n📦 <b>Producto:</b> <code>{product}</code> (x{qty})\n💰 <b>Total Pagado:</b> <code>${total} USDT</code>\n🆔 <b>Orden #:</b> <code>ORD_{order_id}</code>{warranty_text}\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🔑 <b>DATOS DE TU SERVICIO:</b>\n<pre>{items}</pre>{after_note}\n\n<i>💡 Puedes consultar tus compras y garantías en cualquier momento desde 'Mis Pedidos'.</i>",
        "btn_view_in_orders": "💼 Ver en 'Mis Pedidos'",
        "btn_continue_shopping": "🛒 Seguir Comprando",

        # Mis Pedidos
        "orders_title": "💼 <b>MIS PEDIDOS ({count} Total)</b>\n<i>Selecciona un pedido para ver los datos entregados:</i>\n",
        "orders_empty": "💼 <b>MIS PEDIDOS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nAún no has realizado ningún pedido.\n\n<i>Explora nuestro catálogo y adquiere tus cuentas y licencias al mejor precio.</i>",
        "order_detail_title": "🛍️ <b>DETALLES DEL PEDIDO #ORD_{order_id}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n📦 <b>Producto:</b> <code>{product}</code> (x{qty})\n💰 <b>Precio Pagado:</b> <code>${total} USDT</code>\n🛡️ <b>Garantía:</b> <code>{warranty}</code>\n📅 <b>Fecha:</b> <code>{date}</code>\n🆔 <b>ID Proveedor:</b> <code>{prov_id}</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🔑 <b>DATOS / CREDENCIALES ENTREGADAS:</b>\n<pre>{items}</pre>",

        # Referidos
        "referrals_title": "🔗 <b>SISTEMA DE REFERIDOS & AFILIADOS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n¡Invita a tus amigos y gana el <b>{percent}% de comisión</b> automática sobre cada recarga de saldo que realicen!\n\n👥 <b>Tus Referidos Registrados:</b> <code>{count} usuarios</code>\n💰 <b>Comisiones Ganadas:</b> <code>${earnings} USDT</code>\n\n🎯 <b>Tu Enlace Exclusivo de Invitación:</b>\n<code>{ref_link}</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Comparte tu enlace y empieza a generar ingresos pasivos.</i>",
        "btn_share_ref": "📢 Compartir Enlace de Referido",

        # Soporte
        "support_text": "🆘 <b>SOPORTE & AYUDA</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n¿Tienes alguna duda sobre tus compras, depósitos o necesitas asistencia?\n\n• <b>Garantía:</b> Si algún servicio con garantía presenta inconvenientes durante el período activo, contáctanos inmediatamente con tu <b>ID de Orden</b>.\n• <b>Depósitos:</b> Los depósitos en USDT BEP-20 se acreditan automáticamente tras la confirmación de la red.\n\n💬 <i>Para contactar directamente a un administrador pulsa el botón inferior:</i>"
    },

    "en": {
        # Main Menu and Navigation
        "welcome_header": "💎 <b>WELCOME TO jvcᵈᵉᵛ Store</b> 💎",
        "user_label": "User",
        "balance_bot": "Bot Balance",
        "balance_provider": "Provider Balance (Bunai)",
        "orders_made": "Completed Orders",
        "select_option": "Select an option from the menu below to get started:",
        "maintenance_banner": "⚠️ <i>The bot is currently in maintenance mode. Purchases are temporarily paused.</i>\n\n",
        "btn_catalog": "🛒 Service Catalog",
        "btn_deposit": "💳 Deposit USDT",
        "btn_my_orders": "💼 My Orders",
        "btn_referrals": "🔗 Referrals",
        "btn_profile": "👤 My Profile",
        "btn_support": "🆘 Support & Help",
        "btn_admin": "⚙️ Admin Panel",
        "btn_back": "Back",
        "btn_main_menu": "🏠 Main Menu",
        "btn_refresh": "🔄 Refresh",
        "btn_search_service": "🔍 Search Service",
        "btn_contact_admin": "💬 Contact Administrator",

        # Profile and Language
        "profile_title": "👤 <b>User Profile</b>",
        "lang_label": "Language",
        "registered": "Registered",
        "btn_language": "🗣️ Language",
        "lang_select_title": "🌐 <b>SELECT YOUR PREFERRED LANGUAGE</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Choose the language you want to use with the bot:</i>",
        "lang_changed": "✅ Language updated to: {lang_name}",

        # Catalog and Category Picker
        "catalog_header_disponibles": "🟢 <b>AVAILABLE PRODUCTS</b> ({count})",
        "catalog_header_agotados": "🔴 <b>OUT OF STOCK PRODUCTS</b> ({count})",
        "catalog_header_ofertas": "🎁 <b>SPECIAL OFFERS</b> ({count})",
        "catalog_header_todos": "📋 <b>ALL SERVICES</b> ({count})",
        "btn_categories": "📂 Categories",
        "cat_picker_title": "📂 <b>SELECT A CATEGORY</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Choose the catalog category you wish to view:</i>",
        "cat_opt_disponibles": "🟢 Available ({count})",
        "cat_opt_ofertas": "🎁 Special Offers ({count})",
        "cat_opt_agotados": "🔴 Out of Stock ({count})",
        "cat_opt_todos": "📋 All Services ({count})",
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
        "btn_buy_qty": "🛒 Buy {qty} (${total} USDT)",
        "btn_recharge_balance": "⊞ Top Up Balance",
        "btn_share_link": "🔗 Share Link 📋",
        "btn_view_note": "📝 View Note",
        "admin_note_title": "📝 <b>Admin Note:</b>",
        "no_admin_note": "No additional terms or notes for this product.",
        "btn_notify_stock": "🔔 Notify me when in stock",
        "btn_cancel_stock_alert": "🔕 Active Alert (Tap to Cancel)",
        "alert_activated": "🔔 Alert activated! We will notify you via DM as soon as stock is available.",
        "alert_cancelled": "🔕 Stock alert cancelled.",
        "promo_offer_text": "🎁 <b>Offer: Buy {qty}+ ➔ -{discount}% Off</b>",
        "restock_alert_title": "🔔 <b>PRODUCT BACK IN STOCK!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n📦 <b>Product:</b> <code>{product}</code>\n💰 <b>Price:</b> <code>${price} USDT</code>\n🎲 <b>Available Stock:</b> <code>{stock} units</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>The service you were waiting for is now in stock. Get it before it runs out!</i>",
        "btn_buy_now": "🛒 View and Buy Now",

        # Search
        "search_prompt_title": "🔍 <b>SERVICE SEARCH</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nType the name of the service you are looking for (e.g., <code>Gemini</code>, <code>Netflix</code>, <code>Office</code>).\n\n<i>Or type <code>/buscar name</code> at any time.</i>",
        "search_results_title": "🔍 <b>Results for:</b> <i>'{query}'</i> ({count} found):",
        "search_no_results": "🔍 <b>Results for:</b> <i>'{query}'</i>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n❌ No products found with that name.",

        # Wallet and Deposits
        "wallet_title": "💳 <b>WALLET & USDT DEPOSITS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 <b>Current Balance:</b> <code>${balance} USDT</code>\n🌐 <b>Accepted Network:</b> <code>BNB Smart Chain (BEP-20)</code>\n🔒 <b>Minimum Deposit:</b> <code>${min_dep} USDT</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Select an amount to top up or tap 'Enter Other Amount':</i>",
        "btn_custom_amount": "✍️ Enter Other Amount",
        "invoice_title": "💳 <b>USDT (BEP-20) DEPOSIT INVOICE</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n⚠️ <b>IMPORTANT:</b> Send <b>EXACTLY</b> the amount shown below for automatic crediting.\n\n🎯 <b>Exact Amount to Send:</b>\n<code>{exact_val}</code> USDT\n\n📬 <b>Wallet Address (BNB Smart Chain / BEP-20):</b>\n<code>{wallet}</code>\n\n⏳ <b>Time Limit:</b> <code>30 minutes</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Tap '📱 View QR Code' to scan from your app or transfer and tap 'Submit Hash / TxID'.</i>",
        "btn_show_qr": "📱 View QR Code",
        "btn_submit_hash": "🔗 Submit Hash / TxID",
        "btn_verify_payment": "🔄 Verify Payment",
        "btn_cancel_request": "❌ Cancel Request",
        "btn_back_to_invoice": "🔙 Back to Invoice",
        "qr_caption": "📱 <b>BSC (BEP-20) PAYMENT QR CODE</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 <b>Amount to send:</b> <code>{exact_val}</code> USDT\n📬 <b>Wallet:</b> <code>{wallet}</code>\n\n<i>Scan this code directly from Trust Wallet, Binance or MetaMask.</i>",
        "custom_amount_prompt": "✍️ <b>ENTER AMOUNT TO DEPOSIT</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nType the amount of USDT you wish to add to your balance.\n\n⚠️ <b>Minimum Amount:</b> <code>{min_dep} USDT</code>\n\n<i>Example: Send a message typing <code>15</code> or <code>25.5</code></i>",
        "submit_hash_prompt": "🔗 <b>SUBMIT TRANSACTION HASH / TXID</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nPaste below the transaction Hash (TxID) from your wallet (Trust Wallet, Binance, MetaMask, etc).\n\n<i>Example: <code>0x4a8c9b...</code></i>",
        "deposit_cancelled_screen": "❌ <b>DEPOSIT REQUEST CANCELLED</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nThe deposit request for <b>${amount} USDT</b> has been cancelled.\n\n<i>You can generate a new request whenever you wish.</i>",
        "btn_new_deposit": "💳 New Deposit",
        "verifying_tx": "⏳ <b>Verifying transaction on the BSC blockchain...</b>\n<i>Checking network nodes and confirmations.</i>",
        "deposit_success_title": "🎉 <b>DEPOSIT CREDITED SUCCESSFULLY!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 <b>Credited Amount:</b> <code>+${amount} USDT</code>\n💳 <b>New Total Balance:</b> <code>${balance} USDT</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>You can now browse the catalog and purchase any digital service.</i>",

        # Purchases and Checkout
        "processing_order": "⏳ <b>Processing your order for {qty}x {product}...</b>\n<i>Please wait a few seconds.</i>",
        "purchase_fail_title": "❌ <b>PURCHASE COULD NOT BE COMPLETED</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nThe provider rejected the request (likely out of stock).\n\n🛡️ <b>Your balance of ${total} USDT has been fully refunded to your account.</b>",
        "purchase_success_title": "🎉 <b>PURCHASE COMPLETED SUCCESSFULLY!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n📦 <b>Product:</b> <code>{product}</code> (x{qty})\n💰 <b>Total Paid:</b> <code>${total} USDT</code>\n🆔 <b>Order #:</b> <code>ORD_{order_id}</code>{warranty_text}\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🔑 <b>YOUR SERVICE CREDENTIALS:</b>\n<pre>{items}</pre>{after_note}\n\n<i>💡 You can view your purchased credentials anytime under 'My Orders'.</i>",
        "btn_view_in_orders": "💼 View in 'My Orders'",
        "btn_continue_shopping": "🛒 Continue Shopping",

        # My Orders
        "orders_title": "💼 <b>MY ORDERS ({count} Total)</b>\n<i>Select an order to view credentials:</i>\n",
        "orders_empty": "💼 <b>MY ORDERS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nYou haven't placed any orders yet.\n\n<i>Explore our catalog and get premium digital accounts at the best price.</i>",
        "order_detail_title": "🛍️ <b>ORDER DETAILS #ORD_{order_id}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n📦 <b>Product:</b> <code>{product}</code> (x{qty})\n💰 <b>Price Paid:</b> <code>${total} USDT</code>\n🛡️ <b>Warranty:</b> <code>{warranty}</code>\n📅 <b>Date:</b> <code>{date}</code>\n🆔 <b>Provider ID:</b> <code>{prov_id}</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🔑 <b>DELIVERED CREDENTIALS:</b>\n<pre>{items}</pre>",

        # Referrals
        "referrals_title": "🔗 <b>REFERRAL & AFFILIATE SYSTEM</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nInvite your friends and earn an automatic <b>{percent}% commission</b> on every balance deposit they make!\n\n👥 <b>Your Registered Referrals:</b> <code>{count} users</code>\n💰 <b>Earned Commissions:</b> <code>${earnings} USDT</code>\n\n🎯 <b>Your Exclusive Referral Link:</b>\n<code>{ref_link}</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Share your link and start earning passive income.</i>",
        "btn_share_ref": "📢 Share Referral Link",

        # Support
        "support_text": "🆘 <b>SUPPORT & HELP</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nDo you have questions about your purchases, deposits or need assistance?\n\n• <b>Warranty:</b> If any service under warranty experiences issues during the active period, contact us immediately with your <b>Order ID</b>.\n• <b>Deposits:</b> USDT BEP-20 deposits are credited automatically after network confirmation.\n\n💬 <i>To contact an administrator directly tap the button below:</i>"
    },

    "pt": {
        # Menu Principal e Navegação
        "welcome_header": "💎 <b>BEM-VINDO À jvcᵈᵉᵛ Store</b> 💎",
        "user_label": "Usuário",
        "balance_bot": "Saldo no Bot",
        "balance_provider": "Saldo Provedor (Bunai)",
        "orders_made": "Compras Realizadas",
        "select_option": "Selecione uma opção no menu abaixo para começar:",
        "maintenance_banner": "⚠️ <i>O bot está em modo de manutenção. As compras estão pausadas temporariamente.</i>\n\n",
        "btn_catalog": "🛒 Catálogo de Serviços",
        "btn_deposit": "💳 Depositar USDT",
        "btn_my_orders": "💼 Meus Pedidos",
        "btn_referrals": "🔗 Referidos",
        "btn_profile": "👤 Meu Perfil",
        "btn_support": "🆘 Suporte & Ajuda",
        "btn_admin": "⚙️ Painel de Administração",
        "btn_back": "Voltar",
        "btn_main_menu": "🏠 Menu Principal",
        "btn_refresh": "🔄 Atualizar",
        "btn_search_service": "🔍 Buscar Serviço",
        "btn_contact_admin": "💬 Contatar Administrador",

        # Perfil e Idiomas
        "profile_title": "👤 <b>Perfil de Usuário</b>",
        "lang_label": "Idioma",
        "registered": "Registro",
        "btn_language": "🗣️ Idioma",
        "lang_select_title": "🌐 <b>SELECIONE SEU IDIOMA PREFERIDO</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Escolha o idioma que deseja usar no bot:</i>",
        "lang_changed": "✅ Idioma atualizado para: {lang_name}",

        # Catálogo e Seletor de Categorias
        "catalog_header_disponibles": "🟢 <b>PRODUTOS DISPONÍVEIS</b> ({count})",
        "catalog_header_agotados": "🔴 <b>PRODUTOS ESGOTADOS</b> ({count})",
        "catalog_header_ofertas": "🎁 <b>OFERTAS ESPECIAIS</b> ({count})",
        "catalog_header_todos": "📋 <b>TODOS OS SERVIÇOS</b> ({count})",
        "btn_categories": "📂 Categorias",
        "cat_picker_title": "📂 <b>SELECIONE UMA CATEGORIA</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Escolha a categoria do catálogo que deseja visualizar:</i>",
        "cat_opt_disponibles": "🟢 Disponíveis ({count})",
        "cat_opt_ofertas": "🎁 Em Oferta ({count})",
        "cat_opt_agotados": "🔴 Esgotados ({count})",
        "cat_opt_todos": "📋 Todos ({count})",
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
        "btn_buy_qty": "🛒 Comprar {qty} (${total} USDT)",
        "btn_recharge_balance": "⊞ Recarregar Saldo",
        "btn_share_link": "🔗 Compartilhar Link 📋",
        "btn_view_note": "📝 Ver Nota",
        "admin_note_title": "📝 <b>Nota do Admin:</b>",
        "no_admin_note": "Sem notas adicionais para este produto.",
        "btn_notify_stock": "🔔 Avisar quando houver estoque",
        "btn_cancel_stock_alert": "🔕 Alerta Ativo (Toque para Cancelar)",
        "alert_activated": "🔔 Alerta ativado! Notificaremos por mensagem privada quando houver estoque.",
        "alert_cancelled": "🔕 Alerta de estoque cancelado.",
        "promo_offer_text": "🎁 <b>Oferta: Compre {qty}+ ➔ -{discount}% Desc</b>",
        "restock_alert_title": "🔔 <b>PRODUTO DE VOLTA AO ESTOQUE!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n📦 <b>Produto:</b> <code>{product}</code>\n💰 <b>Preço:</b> <code>${price} USDT</code>\n🎲 <b>Estoque Disponível:</b> <code>{stock} unidades</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>O serviço que você estava esperando já está disponível. Aproveite antes que acabe!</i>",
        "btn_buy_now": "🛒 Ver e Comprar Agora",

        # Busca
        "search_prompt_title": "🔍 <b>BUSCADOR DE SERVIÇOS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nDigite o nome do serviço procurado (ex: <code>Gemini</code>, <code>Netflix</code>, <code>Office</code>).\n\n<i>Ou digite <code>/buscar nome</code> a qualquer momento.</i>",
        "search_results_title": "🔍 <b>Resultados para:</b> <i>'{query}'</i> ({count} encontrados):",
        "search_no_results": "🔍 <b>Resultados para:</b> <i>'{query}'</i>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n❌ Nenhum produto encontrado com esse nome.",

        # Carteira e Depósitos
        "wallet_title": "💳 <b>CARTEIRA & DEPÓSITOS USDT</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 <b>Saldo Atual:</b> <code>${balance} USDT</code>\n🌐 <b>Rede Aceita:</b> <code>BNB Smart Chain (BEP-20)</code>\n🔒 <b>Depósito Mínimo:</b> <code>${min_dep} USDT</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Selecione o valor que deseja recarregar ou toque em 'Digitar Outro Valor':</i>",
        "btn_custom_amount": "✍️ Digitar Outro Valor",
        "invoice_title": "💳 <b>SOLICITAÇÃO DE RECARGA USDT (BEP-20)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n⚠️ <b>IMPORTANTE:</b> Envie <b>EXACTAMENTE</b> o valor indicado abaixo para que a confirmação seja automática.\n\n🎯 <b>Valor Exato a Enviar:</b>\n<code>{exact_val}</code> USDT\n\n📬 <b>Endereço da Carteira (BNB Smart Chain / BEP-20):</b>\n<code>{wallet}</code>\n\n⏳ <b>Tempo Limite:</b> <code>30 minutos</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Toque em '📱 Ver Código QR' para escanear no seu app ou transfira e toque em 'Informar Hash / TxID'.</i>",
        "btn_show_qr": "📱 Ver Código QR",
        "btn_submit_hash": "🔗 Informar Hash / TxID",
        "btn_verify_payment": "🔄 Verificar Pagamento",
        "btn_cancel_request": "❌ Cancelar Solicitação",
        "btn_back_to_invoice": "🔙 Voltar à Solicitação",
        "qr_caption": "📱 <b>CÓDIGO QR DE PAGAMENTO BSC (BEP-20)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 <b>Valor a transferir:</b> <code>{exact_val}</code> USDT\n📬 <b>Carteira:</b> <code>{wallet}</code>\n\n<i>Escaneie este código diretamente na Trust Wallet, Binance ou MetaMask.</i>",
        "custom_amount_prompt": "✍️ <b>DIGITE O VALOR DO DEPÓSITO</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nDigite a quantidade de USDT que deseja adicionar ao seu saldo.\n\n⚠️ <b>Valor Mínimo:</b> <code>{min_dep} USDT</code>\n\n<i>Exemplo: Envie uma mensagem digitando <code>15</code> ou <code>25.5</code></i>",
        "submit_hash_prompt": "🔗 <b>ENVIE O HASH / TXID DA TRANSAÇÃO</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nCole abaixo o Hash (TxID) da transferência realizada da sua carteira (Trust Wallet, Binance, MetaMask, etc).\n\n<i>Exemplo: <code>0x4a8c9b...</code></i>",
        "deposit_cancelled_screen": "❌ <b>SOLICITAÇÃO DE RECARGA CANCELADA</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nA solicitação de <b>${amount} USDT</b> foi cancelada com sucesso.\n\n<i>Você pode gerar uma nova solicitação quando quiser.</i>",
        "btn_new_deposit": "💳 Nova Recarga",
        "verifying_tx": "⏳ <b>Verificando transação na blockchain BSC...</b>\n<i>Consultando nós da rede e confirmações.</i>",
        "deposit_success_title": "🎉 <b>DEPÓSITO CONFIRMADO COM SUCESSO!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 <b>Valor Creditado:</b> <code>+${amount} USDT</code>\n💳 <b>Novo Saldo Total:</b> <code>${balance} USDT</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Agora você pode navegar pelo catálogo e comprar qualquer serviço.</i>",

        # Compras e Checkout
        "processing_order": "⏳ <b>Processando seu pedido de {qty}x {product}...</b>\n<i>Por favor, aguarde alguns segundos.</i>",
        "purchase_fail_title": "❌ <b>NÃO FOI POSSÍVEL CONCLUIR A COMPRA</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nO provedor recusou o pedido (provavelmente sem estoque).\n\n🛡️ <b>Seu saldo de ${total} USDT foi estornado integralmente para sua conta.</b>",
        "purchase_success_title": "🎉 <b>COMPRA REALIZADA COM SUCESSO!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n📦 <b>Produto:</b> <code>{product}</code> (x{qty})\n💰 <b>Total Pago:</b> <code>${total} USDT</code>\n🆔 <b>Pedido #:</b> <code>ORD_{order_id}</code>{warranty_text}\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🔑 <b>DADOS DO SEU SERVIÇO:</b>\n<pre>{items}</pre>{after_note}\n\n<i>💡 Você pode consultar suas compras e credenciais a qualquer momento em 'Meus Pedidos'.</i>",
        "btn_view_in_orders": "💼 Ver em 'Meus Pedidos'",
        "btn_continue_shopping": "🛒 Continuar Comprando",

        # Meus Pedidos
        "orders_title": "💼 <b>MEUS PEDIDOS ({count} Total)</b>\n<i>Selecione um pedido para ver as credenciais:</i>\n",
        "orders_empty": "💼 <b>MEUS PEDIDOS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nVocê ainda não fez nenhum pedido.\n\n<i>Explore nosso catálogo e adquira contas premium pelo melhor preço.</i>",
        "order_detail_title": "🛍️ <b>DETALHES DO PEDIDO #ORD_{order_id}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n📦 <b>Produto:</b> <code>{product}</code> (x{qty})\n💰 <b>Preço Pago:</b> <code>${total} USDT</code>\n🛡️ <b>Garantia:</b> <code>{warranty}</code>\n📅 <b>Data:</b> <code>{date}</code>\n🆔 <b>ID Provedor:</b> <code>{prov_id}</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🔑 <b>CREDENCIAS ENTREGUES:</b>\n<pre>{items}</pre>",

        # Indicações
        "referrals_title": "🔗 <b>SISTEMA DE INDICAÇÕES & AFILIADOS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nConvide seus amigos e ganhe <b>{percent}% de comissão</b> automática sobre cada recarga de saldo que eles fizerem!\n\n👥 <b>Seus Indicados Registrados:</b> <code>{count} usuários</code>\n💰 <b>Comissões Ganhas:</b> <code>${earnings} USDT</code>\n\n🎯 <b>Seu Link Exclusivo de Convite:</b>\n<code>{ref_link}</code>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Compartilhe seu link e comece a gerar renda passiva.</i>",
        "btn_share_ref": "📢 Compartilhar Link de Indicação",

        # Suporte
        "support_text": "🆘 <b>SUPORTE & AJUDA</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\nTem dúvidas sobre compras, depósitos ou precisa de assistência?\n\n• <b>Garantia:</b> Se algum serviço com garantia apresentar problemas durante o período ativo, entre em contato imediatamente com o seu <b>ID de Pedido</b>.\n• <b>Depósitos:</b> Os depósitos em USDT BEP-20 são creditados automaticamente após a confirmação da rede.\n\n💬 <i>Para falar directamente com um administrador toque no botão abaixo:</i>"
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
