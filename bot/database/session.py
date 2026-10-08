from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from bot.config import settings
from alembic import command
from alembic.config import Config

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
    """Aplica el baseline de esquema compatible con instalaciones existentes."""
    config = Config("alembic.ini")
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync_connection: _upgrade_schema(config, sync_connection))


def _upgrade_schema(config: Config, connection) -> None:
    config.attributes["connection"] = connection
    command.upgrade(config, "head")

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
