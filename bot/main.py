import asyncio
import html
import time
from pathlib import Path
from tempfile import gettempdir
from datetime import datetime, timezone, timedelta
from pyrogram import Client, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import update
from bot.config import settings
from bot.database.session import init_db, async_session, engine
from bot.database.models import Deposit, DepositStatus, Order, User, VirtualNumberOrder
from bot.handlers import register_all_handlers
from bot.services.bunai_client import bunai_api
from bot.services.audit_logger import audit_logger
from bot.services.backup_service import backup_service
from bot.services.stock_watcher import stock_watcher
from bot.services.vip_service import vip_service
from bot.services.deposit_reminder import check_and_send_deposit_reminders
from bot.services import deposit_monitor as deposit_monitor_service
from bot.services.financial_outbox import financial_notification_worker
from bot.services.virtual_numbers import check_and_notify_pending_virtual_orders
from bot.services.fivesim_client import fivesim_api
from bot.handlers.support import retry_pending_admin_ticket_notifications, retry_pending_user_ticket_notifications
from bot.utils.i18n import t
from bot.utils.navigation import USER_LAST_MESSAGES, USER_LAST_MESSAGES_IS_MEDIA, render_screen
from sqlalchemy import text

async def provider_balance_monitor(app: Client):
    """Monitorea periódicamente el saldo en BunaiStore para alertar al canal de auditoría si está bajo"""
    while True:
        try:
            await asyncio.sleep(3600)  # Cada 1 hora
            profile = await bunai_api.get_me()
            if profile.get("error"):
                await audit_logger.log_system_alert(
                    client=app,
                    title="ERROR DE CONEXIÓN CON BUNAISTORE",
                    details=f"No se pudo consultar el saldo: <code>{html.escape(str(profile['error'])[:400])}</code>"
                )
                continue
            balance = float(profile.get("balance", 0.0))
            if balance < 10.0:
                alert_text = (
                    f"Tu saldo actual en BunaiStore es de <b>${balance:.2f} USD</b>.\n"
                    f"<i>Por favor recarga fondos en el bot del proveedor para asegurar entregas continuas.</i>"
                )
                await audit_logger.log_system_alert(
                    client=app,
                    title="SALDO BAJO EN BUNAISTORE",
                    details=alert_text
                )
        except Exception as e:
            print(f"[Monitor Error] {e}")
            await asyncio.sleep(600)

async def fivesim_balance_monitor(app: Client):
    """Monitorea periódicamente el saldo en 5SIM.net para alertar al canal de auditoría si está bajo"""
    while True:
        try:
            await asyncio.sleep(1800)  # Cada 30 minutos
            if not fivesim_api.is_configured():
                await asyncio.sleep(1800)
                continue

            profile = await fivesim_api.get_profile()
            if profile.get("error"):
                await audit_logger.log_system_alert(
                    client=app,
                    title="ERROR DE CONEXIÓN CON 5SIM",
                    details=f"No se pudo consultar el saldo: <code>{html.escape(str(profile['error'])[:400])}</code>"
                )
                continue

            balance = float(profile.get("balance", 0.0))
            # Alerta si el saldo en 5SIM baja de $5.00 USD
            if balance < 5.0:
                alert_text = (
                    f"Tu saldo actual en 5SIM.net es de <b>${balance:.2f} USD</b>.\n"
                    f"<i>Por favor recarga fondos en tu cuenta de 5SIM para asegurar activaciones continuas de números virtuales.</i>"
                )
                await audit_logger.log_system_alert(
                    client=app,
                    title="SALDO BAJO EN 5SIM",
                    details=alert_text
                )
        except Exception as e:
            print(f"[FiveSimBalanceMonitor Error] {e}")
            await asyncio.sleep(600)

async def deposit_expiry_worker(app: Client):
    """Limpia periódicamente depósitos pendientes expirados (Anti-Memory/Lock Leak)"""
    while True:
        try:
            await asyncio.sleep(30)
            async with async_session() as session:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                verification_cutoff = now - timedelta(minutes=15)
                expired_rows = (await session.execute(
                    update(Deposit)
                    .where(Deposit.status == DepositStatus.PENDING, Deposit.expires_at <= now)
                    .values(status=DepositStatus.EXPIRED)
                    .returning(
                        Deposit.id,
                        Deposit.user_id,
                        Deposit.exact_amount,
                        Deposit.user_message_id,
                        Deposit.user_message_is_media,
                        Deposit.log_message_id,
                    )
                )).all()
                await session.execute(
                    update(Deposit)
                    .where(
                        Deposit.status == DepositStatus.VERIFYING,
                        Deposit.verification_started_at < verification_cutoff,
                        Deposit.expires_at <= now
                    )
                    .values(
                        status=DepositStatus.EXPIRED,
                        tx_hash=None,
                        verification_started_at=None
                    )
                )
                await session.execute(
                    update(Deposit)
                    .where(
                        Deposit.status == DepositStatus.VERIFYING,
                        Deposit.verification_started_at < verification_cutoff,
                        Deposit.expires_at > now
                    )
                    .values(
                        status=DepositStatus.PENDING,
                        tx_hash=None,
                        verification_started_at=None
                    )
                )
                await session.commit()

            for deposit_id, user_id, exact_amount, user_message_id, is_media, log_message_id in expired_rows:
                async with async_session() as session:
                    user = await session.get(User, user_id)
                    lang = user.language if user else "es"
                    deposit = await session.get(Deposit, deposit_id)
                    if deposit:
                        deposit.user_message_is_media = False
                        await session.commit()

                if user_message_id:
                    if is_media:
                        try:
                            await app.delete_messages(user_id, user_message_id)
                        except Exception:
                            pass
                        USER_LAST_MESSAGES.pop(user_id, None)
                        USER_LAST_MESSAGES_IS_MEDIA.pop(user_id, None)
                    else:
                        USER_LAST_MESSAGES[user_id] = user_message_id
                        USER_LAST_MESSAGES_IS_MEDIA[user_id] = False
                expired_text = t(
                    "deposit_expired_screen",
                    lang,
                    amount=f"{float(exact_amount):.6f}",
                )
                expired_keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("btn_new_deposit", lang), callback_data="wallet:deposit_menu")
                ]])
                expired_message = await render_screen(app, user_id, expired_text, expired_keyboard)
                if expired_message:
                    async with async_session() as session:
                        await session.execute(
                            update(Deposit)
                            .where(Deposit.id == deposit_id)
                            .values(
                                user_message_id=expired_message.id,
                                user_message_is_media=False,
                            )
                        )
                        await session.commit()
                await audit_logger.log_deposit_expired(
                    app, deposit_id, user_id, float(exact_amount), log_message_id
                )
        except Exception as e:
            print(f"[ExpiryWorker Error] {e}")
            await asyncio.sleep(30)

async def stale_orders_worker(app: Client):
    """Moves provider requests left in flight by a process crash into manual review."""
    while True:
        try:
            await asyncio.sleep(60)
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
            async with async_session() as session:
                bunai_rows = (await session.execute(
                    update(Order)
                    .where(Order.status == "PROCESSING", Order.created_at < cutoff)
                    .values(status="REVIEW")
                    .returning(Order.id, Order.user_id)
                )).all()
                vnum_rows = (await session.execute(
                    update(VirtualNumberOrder)
                    .where(VirtualNumberOrder.status == "PROCESSING", VirtualNumberOrder.created_at < cutoff)
                    .values(status="REVIEW")
                    .returning(VirtualNumberOrder.id, VirtualNumberOrder.user_id)
                )).all()
                await session.commit()

            for order_id, user_id in bunai_rows:
                await audit_logger.log_system_alert(
                    app,
                    "ORDEN BUNAI REQUIERE REVISIÓN",
                    f"La orden <code>ORD_{order_id}</code> quedó en proceso por más de 5 minutos; no se reembolsó automáticamente."
                )
                try:
                    await app.send_message(user_id, f"⏳ Tu orden #{order_id} está en revisión. No la vuelvas a solicitar; soporte confirmará el resultado.")
                except Exception:
                    pass

            for order_id, user_id in vnum_rows:
                await audit_logger.log_system_alert(
                    app,
                    "ORDEN 5SIM REQUIERE REVISIÓN",
                    f"La orden virtual local <code>VNUM_{order_id}</code> quedó en proceso por más de 5 minutos; conserva su reserva."
                )
                try:
                    await app.send_message(user_id, f"⏳ Tu orden de número #{order_id} está en revisión. No vuelvas a solicitar otro número hasta recibir respuesta de soporte.")
                except Exception:
                    pass
        except Exception as e:
            print(f"[StaleOrdersWorker Error] {type(e).__name__}")
            await asyncio.sleep(60)

async def stock_restock_monitor(app: Client):
    """Monitorea periódicamente el catálogo para alertar por DM a usuarios suscritos a productos reabastecidos"""
    while True:
        try:
            await asyncio.sleep(60)  # Cada 60 segundos
            await stock_watcher.check_and_notify_restocks(app)
        except Exception as e:
            print(f"[StockRestockMonitor Error] {e}")
            await asyncio.sleep(60)

async def vip_maintenance_monitor(app: Client):
    """Monitorea periódicamente las membresías VIP para alertar a las 24h y 2h antes (fijando el mensaje) y gestionar expiraciones"""
    while True:
        try:
            await asyncio.sleep(60)  # Cada 60 segundos
            await vip_service.check_and_notify_expirations(app)
        except Exception as e:
            print(f"[VIPMaintenanceMonitor Error] {e}")
            await asyncio.sleep(60)

async def daily_backup_worker(app: Client):
    """Genera y envía automáticamente una copia de seguridad de la base de datos cada 24 horas"""
    while True:
        try:
            await backup_service.send_automated_backup(app)
        except Exception as e:
            print(f"[DailyBackupWorker Error] {e}")
        await asyncio.sleep(settings.AUTO_BACKUP_HOURS * 3600)

async def support_notification_worker(app: Client):
    """Reintenta notificaciones de soporte pendientes almacenadas en la base de datos."""
    while True:
        try:
            await retry_pending_admin_ticket_notifications(app)
            await retry_pending_user_ticket_notifications(app)
        except Exception as e:
            print(f"[SupportNotificationWorker Error] {e}")
        await asyncio.sleep(60)
async def deposit_reminder_worker(app: Client):
    """Monitorea periódicamente depósitos pendientes para enviar recordatorio amistoso a los 15-45 minutos (anti-abandono)"""
    while True:
        try:
            await asyncio.sleep(60)  # Cada 60 segundos
            await check_and_send_deposit_reminders(app)
        except Exception as e:
            print(f"[DepositReminderWorker Error] {e}")
            await asyncio.sleep(60)

async def virtual_numbers_worker(app: Client):
    """Monitorea órdenes de números virtuales pendientes cada 4 segundos para notificar recepción de SMS o expiración/reembolso"""
    while True:
        try:
            await asyncio.sleep(4)
            await check_and_notify_pending_virtual_orders(app)
        except Exception as e:
            print(f"[VirtualNumbersWorker Error] {e}")
            await asyncio.sleep(5)

async def bot_health_worker(app: Client):
    health_file = Path(gettempdir()) / "bot-health"
    scanner_alerted = False
    while True:
        database_healthy = False
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            database_healthy = True
        except Exception as exc:
            print(f"[HealthCheck] PostgreSQL no disponible: {type(exc).__name__}")

        scanner_last_success = deposit_monitor_service.last_successful_scan_at
        scanner_timeout = max(180, settings.BSC_MONITOR_INTERVAL_SECONDS * 3 + 30)
        scanner_healthy = (
            scanner_last_success is not None
            and time.monotonic() - scanner_last_success <= scanner_timeout
        )
        if app.is_connected and database_healthy and scanner_healthy:
            health_file.touch()
            scanner_alerted = False
        else:
            health_file.unlink(missing_ok=True)
            if app.is_connected and database_healthy and not scanner_healthy and not scanner_alerted:
                scanner_phase = deposit_monitor_service.scanner_scan_phase
                if deposit_monitor_service.scanner_scan_in_progress:
                    scan_duration = int(
                        time.monotonic() - deposit_monitor_service.scanner_scan_started_at
                    ) if deposit_monitor_service.scanner_scan_started_at is not None else 0
                    scanner_status = f"Escaneo en curso: {scanner_phase} ({scan_duration} s)."
                    if deposit_monitor_service.scanner_last_error_type:
                        scanner_status += (
                            f" Último intento fallido en {deposit_monitor_service.scanner_last_error_phase}: "
                            f"{deposit_monitor_service.scanner_last_error_type}."
                        )
                elif deposit_monitor_service.scanner_last_error_type:
                    scanner_status = (
                        f"Último intento fallido en {deposit_monitor_service.scanner_last_error_phase}: "
                        f"{deposit_monitor_service.scanner_last_error_type}."
                    )
                else:
                    scanner_status = "No hay un escaneo activo ni un error registrado."
                details = (
                    f"No se completó un escaneo BSC correctamente en los últimos {scanner_timeout} segundos. "
                    f"{scanner_status}"
                )
                print(f"[HealthCheck] SCANNER BSC ATRASADO: {details}")
                await audit_logger.log_system_alert(
                    client=app,
                    title="SCANNER BSC ATRASADO",
                    details=details,
                )
                scanner_alerted = True
        await asyncio.sleep(20)

async def main():
    print("==================================================")
    print("🚀 INICIANDO BOT DE REVENTA DE SERVICIOS DIGITALES")
    print("==================================================")

    # 1. Inicializar Base de Datos PostgreSQL
    print("📦 Inicializando tablas en PostgreSQL...")
    try:
        await init_db()
        print("✅ Base de datos conectada e inicializada correctamente.")
    except Exception as e:
        print(f"❌ Error al conectar con PostgreSQL: {type(e).__name__}")
        raise RuntimeError("No se pudo inicializar PostgreSQL; se cancela el inicio") from None

    # 2. Inicializar Cliente Pyrogram
    import os
    os.makedirs("sessions", exist_ok=True)
    os.makedirs("assets", exist_ok=True)

    app = Client(
        name="services_bot_session",
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        bot_token=settings.BOT_TOKEN,
        workdir="sessions"
    )

    # 3. Registrar todos los manejadores de eventos
    register_all_handlers(app)

    # 4. Iniciar bot
    await app.start()
    bot_info = await app.get_me()
    print(f"🤖 Bot iniciado con éxito como @{bot_info.username} (ID: {bot_info.id})")

    # Registrar comandos en la interfaz de Telegram
    try:
        from pyrogram.types import BotCommand
        await app.set_bot_commands([
            BotCommand("start", "💎 Menú Principal"),
            BotCommand("catalogo", "🛒 Ver Catálogo de Servicios"),
            BotCommand("buscar", "🔍 Buscar un Servicio"),
            BotCommand("pedidos", "💼 Mis Pedidos y Licencias"),
            BotCommand("depositar", "💳 Recargar Saldo USDT"),
            BotCommand("soporte", "🆘 Ayuda y Contacto Admin"),
            BotCommand("admin", "⚙️ Panel de Control (Admins)"),
            BotCommand("vip", "👑 Gestión VIP (Admin)")
        ])
    except Exception as e:
        print(f"[SetBotCommands Warning]: {e}")

    # 5. Notificar inicio al canal de auditoría
    await audit_logger.log_system_alert(
        client=app,
        title="BOT INICIADO Y ACTIVO",
        details=f"El bot <b>@{bot_info.username}</b> ha iniciado sesión y se encuentra listo para operar."
    )

    # 6. Lanzar monitores y workers en segundo plano
    background_tasks = [
        asyncio.create_task(provider_balance_monitor(app), name="provider-balance"),
        asyncio.create_task(fivesim_balance_monitor(app), name="fivesim-balance"),
        asyncio.create_task(deposit_expiry_worker(app), name="deposit-expiry"),
        asyncio.create_task(deposit_monitor_service.deposit_monitor_worker(app), name="bsc-deposit-monitor"),
        asyncio.create_task(financial_notification_worker(app), name="financial-notifications"),
        asyncio.create_task(stale_orders_worker(app), name="stale-orders-review"),
        asyncio.create_task(deposit_reminder_worker(app), name="deposit-reminders"),
        asyncio.create_task(virtual_numbers_worker(app), name="virtual-numbers"),
        asyncio.create_task(stock_restock_monitor(app), name="stock-restock"),
        asyncio.create_task(vip_maintenance_monitor(app), name="vip-maintenance"),
        asyncio.create_task(daily_backup_worker(app), name="daily-backup"),
        asyncio.create_task(support_notification_worker(app), name="support-notifications"),
        asyncio.create_task(bot_health_worker(app), name="bot-health"),
    ]

    # Mantener en ejecución con cierre controlado de recursos
    try:
        await idle()
    finally:
        print("\n🛑 Deteniendo bot y liberando recursos de red y base de datos...")
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        try:
            await app.stop()
        except Exception:
            pass
        try:
            await bunai_api.close()
        except Exception:
            pass
        try:
            await fivesim_api.close()
        except Exception:
            pass
        try:
            from bot.database.session import engine
            await engine.dispose()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Bot detenido de forma segura.")
