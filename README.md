# 🤖 Bot de Reventa de Servicios Digitales (Telegram + BunaiStore + USDT BEP-20)

Bot de Telegram desarrollado en **Python (Pyrogram)** con arquitectura de **1 solo mensaje editable**, pagos automáticos descentralizados en **USDT BEP-20**, catálogo sincronizado en tiempo real con **BunaiStore API**, sistema de auditoría en grupo privado para el Owner, y empaquetado para despliegue directo en **Dokploy (Hostinger VPS)** con **Docker Compose y PostgreSQL**.

---

## 🌟 Características Principales

* **📱 Interfaz de Usuario Fluida (1 Solo Mensaje):** Navegación completa mediante botones inline sin generar spam en el chat.
* **🛒 Catálogo con 4 Filtros & Paginación de 8 Ítems:**
  * 🟢 **Disponibles:** Solo productos con inventario activo o ilimitado (`∞`).
  * 🔴 **Agotados:** Productos sin stock con indicador claro.
  * 🔥 **Ofertas:** Productos con promociones y descuentos por volumen.
  * 📋 **Todos:** Listado completo del catálogo.
* **💳 Depósitos Automatizados en USDT BEP-20:**
  * Monto mínimo de $2.00 USDT con botones rápidos ($2, $5, $10, $20, $50) o entrada personalizada.
  * Generación de decimales únicos (ej. `5.034 USDT`) válidos por 30 minutos.
  * Verificación on-chain mediante nodo RPC de BNB Smart Chain validando contrato oficial de USDT, receptor y monto exacto.
* **👥 Canal / Grupo Privado de Auditoría (DB del Owner):**
  * Registro en tiempo real de todas las compras con credenciales y cuentas entregadas.
  * Registro de depósitos solicitados y confirmados con enlace a BscScan.
  * Alertas de saldo bajo en BunaiStore (< $10 USD).
* **🛡️ Seguridad Anti-Exploits Bancaria:**
  * Protección anti-reuso de Hash (Anti-Replay Attack).
  * Transacciones ACID con bloqueo de fila en PostgreSQL contra doble-gasto concurrente.
  * Rollback automático en caso de falta de stock en el proveedor.
  * Throttling anti-flood.
* **⚙️ Panel de Administración en Telegram:**
  * Métricas de usuarios, depósitos y ventas en vivo.
  * Ajuste de margen de ganancia global en tiempo real.
  * Difusión masiva (Broadcast) a todos los usuarios.
  * Modo mantenimiento activable con 1 toque.

---

## 🚀 Despliegue en Dokploy (Hostinger VPS)

### Paso 1: Crear el Proyecto en Dokploy
1. Abre tu panel de **Dokploy**.
2. Ve a **Projects** ➔ Crea un nuevo proyecto (ej. `Servicios-Bot`).
3. Añade un servicio de tipo **Compose**.

### Paso 2: Configurar las Variables de Entorno en Dokploy
En la pestaña **Environment** de tu servicio en Dokploy, copia y completa las siguientes variables (basadas en `.env.example`):

```env
API_ID=tu_api_id_de_telegram
API_HASH=tu_api_hash_de_telegram
BOT_TOKEN=tu_token_de_botfather
ADMIN_IDS=tu_telegram_id
LOG_GROUP_ID=-1001234567890

BUNAI_API_KEY=Shop::_3a2klpvDK9_SH2FY46suaM5pb8
BUNAI_BASE_URL=https://api.bunaistore.shop/v1

ADMIN_WALLET_BSC=0xTuBilleteraPersonalBSC
BSC_RPC_URL=https://bsc-dataseed.binance.org/
USDT_CONTRACT_ADDRESS=0x55d398326f99059fF775485246999027B3197955

DEFAULT_MARGIN_PERCENT=30.0
MIN_DEPOSIT_USDT=2.0
REFERRAL_COMMISSION_PERCENT=5.0

POSTGRES_USER=postgres
POSTGRES_PASSWORD=un_password_seguro_aqui
POSTGRES_DB=services_bot
```

### Paso 3: Desplegar con Docker Compose
Pega el contenido de `docker-compose.yml` en la pestaña **Compose** de Dokploy y pulsa **Deploy**.

Dokploy creará automáticamente:
1. El contenedor `db` con **PostgreSQL 16** y volumen persistente (`postgres_data`).
2. El contenedor `bot` con **Python 3.11** y Pyrogram.

---

## 🛠️ Cómo obtener los IDs requeridos

1. **`API_ID` y `API_HASH`:** Se obtienen gratuitamente en [my.telegram.org/apps](https://my.telegram.org/apps).
2. **`BOT_TOKEN`:** Se genera al crear el bot con [@BotFather](https://t.me/BotFather) en Telegram.
3. **`LOG_GROUP_ID`:**
   * Crea un grupo o canal privado en Telegram para tus registros.
   * Agrega tu bot como **Administrador** del grupo.
   * Reenvía un mensaje del grupo al bot [@userinfobot](https://t.me/userinfobot) o [@RawDataBot](https://t.me/RawDataBot) para obtener el ID negativo (ej: `-1001234567890`).
