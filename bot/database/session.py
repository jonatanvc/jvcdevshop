from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from bot.config import settings
from .models import Base

# Crear motor asíncrono para PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Fábrica de sesiones asíncronas
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def init_db():
    """Crea todas las tablas si no existen y aplica migraciones de columnas automáticas"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Migraciones automáticas idempotentes para bases de datos existentes
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(5) DEFAULT 'es';",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_spent NUMERIC(12, 4) DEFAULT 0.0000;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS warranty_hours INTEGER DEFAULT 0;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS provider_order_id VARCHAR(128);",
            "ALTER TABLE stock_alerts ADD COLUMN IF NOT EXISTS product_name VARCHAR(255);"
        ]
        for sql in migrations:
            try:
                await conn.execute(text(sql))
            except Exception as e:
                print(f"[Database Migration Warning] {sql}: {e}")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Generador de sesiones de base de datos para transacciones seguras"""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
