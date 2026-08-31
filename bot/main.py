import asyncio
from datetime import datetime
from pyrogram import Client, idle
from sqlalchemy import update
from bot.config import settings
from bot.database.session import init_db, async_session
from bot.database.models import Deposit, DepositStatus
from bot.handlers import register_all_handlers
from bot.services.bunai_client import bunai_api
from bot.services.audit_logger import audit_logger
from bot.services.backup_service import backup_service
from bot.services.stock_watcher import stock_watcher

async def provider_balance_monitor(app: Client):
    """Monitorea periódicamente el saldo en BunaiStore para alertar al Owner si está bajo"""
    while True:
        try:
            await asyncio.sleep(3600)  # Cada 1 hora
            profile = await bunai_api.get_me()
            balance = float(profile.get("balance", 0.0))
            if balance < 10.0:
                await audit_logger.log_system_alert(
                    client=app,
                    title="SALDO BAJO EN BUNAISTORE",
                    details=(
                        f"Tu saldo actual en BunaiStore es de <b>${balance:.2f} USD</b>.\n"
                        f"<i>Por favor recarga fondos en el bot del proveedor para asegurar entregas continuas.</i>"
                    )
                )
        except Exception as e:
            print(f"[Monitor Error] {e}")
            await asyncio.sleep(600)

async def deposit_expiry_worker():
    """Limpia periódicamente depósitos pendientes expirados (Anti-Memory/Lock Leak)"""
    while True:
        try:
            await asyncio.sleep(300)  # Cada 5 minutos
            async with async_session() as session:
                now = datetime.utcnow()
                stmt = (
                    update(Deposit)
                    .where(Deposit.status == DepositStatus.PENDING, Deposit.expires_at < now)
                    .values(status=DepositStatus.EXPIRED)
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as e:
            print(f"[ExpiryWorker Error] {e}")
            await asyncio.sleep(300)

async def stock_restock_monitor(app: Client):
    """Monitorea periódicamente el catálogo para alertar por DM a usuarios suscritos a productos reabastecidos"""
    while True:
        try:
            await asyncio.sleep(60)  # Cada 60 segundos
            await stock_watcher.check_and_notify_restocks(app)
        except Exception as e:
            print(f"[StockRestockMonitor Error] {e}")
            await asyncio.sleep(60)

async def daily_backup_worker(app: Client):
    """Genera y envía automáticamente una copia de seguridad de la base de datos cada 24 horas"""
    while True:
        try:
            interval = settings.AUTO_BACKUP_HOURS * 3600
            await asyncio.sleep(interval)
            await backup_service.send_automated_backup(app)
        except Exception as e:
            print(f"[DailyBackupWorker Error] {e}")
            await asyncio.sleep(3600)

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
        print(f"❌ Error al conectar con la base de datos PostgreSQL: {e}")

    # 2. Inicializar Cliente Pyrogram
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

    # 5. Notificar inicio al canal de auditoría
    await audit_logger.log_system_alert(
        client=app,
        title="BOT INICIADO Y ACTIVO",
        details=f"El bot <b>@{bot_info.username}</b> ha iniciado sesión y se encuentra listo para operar."
    )

    # 6. Lanzar monitores y workers en segundo plano
    asyncio.create_task(provider_balance_monitor(app))
    asyncio.create_task(deposit_expiry_worker())
    asyncio.create_task(stock_restock_monitor(app))
    asyncio.create_task(daily_backup_worker(app))

    # Mantener en ejecución
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Bot detenido de forma segura.")
