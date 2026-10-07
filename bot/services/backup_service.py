import io
import json
import gzip
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional
from cryptography.fernet import Fernet
from pyrogram import Client
from sqlalchemy import DateTime, Enum as SqlEnum, Numeric, func, insert, select, text
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import Base
from bot.utils.time_utils import get_now_str
from bot.utils.emojis import EMOJI_CALENDAR, EMOJI_LOCK, EMOJI_DISK, parse_emojis

class BackupService:
    @staticmethod
    def _serialize_value(value):
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    async def generate_backup_file(self) -> io.BytesIO:
        """Exporta todas las tablas del modelo, comprime y cifra el resultado."""
        if not settings.BACKUP_ENCRYPTION_KEY:
            raise RuntimeError("BACKUP_ENCRYPTION_KEY es necesaria para generar backups")

        try:
            cipher = Fernet(settings.BACKUP_ENCRYPTION_KEY.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise RuntimeError("BACKUP_ENCRYPTION_KEY no es una clave Fernet válida") from exc

        tables = {}
        async with async_session() as session:
            async with session.begin():
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                for mapper in sorted(Base.registry.mappers, key=lambda item: item.local_table.name):
                    model = mapper.class_
                    result = await session.execute(select(model))
                    rows = result.scalars().all()
                    tables[model.__tablename__] = [
                        {
                            attribute.key: self._serialize_value(getattr(row, attribute.key))
                            for attribute in mapper.column_attrs
                        }
                        for row in rows
                    ]

        data = {
            "format_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "counts": {table: len(rows) for table, rows in tables.items()},
            "tables": tables
        }

        # Serializar y comprimir con gzip
        json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        compressed_io = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_io, mode="wb") as gz:
            gz.write(json_bytes)

        encrypted_bytes = cipher.encrypt(compressed_io.getvalue())
        now_str = get_now_str("%Y%m%d_%H%M%S")
        backup_file = io.BytesIO(encrypted_bytes)
        backup_file.name = f"database_backup_{now_str}.json.gz.enc"
        backup_file.seek(0)
        return backup_file

    @staticmethod
    def _deserialize_value(column, value):
        if value is None:
            return None
        if isinstance(column.type, DateTime):
            return datetime.fromisoformat(value)
        if isinstance(column.type, Numeric):
            return Decimal(value)
        if isinstance(column.type, SqlEnum):
            return column.type.enum_class(value)
        return value

    async def restore_backup_file(self, encrypted_backup) -> Dict[str, int]:
        """Restore a versioned encrypted backup into an empty database only."""
        if not settings.BACKUP_ENCRYPTION_KEY:
            raise RuntimeError("BACKUP_ENCRYPTION_KEY es necesaria para restaurar backups")

        cipher = Fernet(settings.BACKUP_ENCRYPTION_KEY.encode("ascii"))
        encrypted_bytes = encrypted_backup.read() if hasattr(encrypted_backup, "read") else encrypted_backup
        try:
            compressed_bytes = cipher.decrypt(encrypted_bytes)
            data = json.loads(gzip.decompress(compressed_bytes))
        except Exception as exc:
            raise ValueError("El backup no es válido o no coincide con BACKUP_ENCRYPTION_KEY") from exc

        if data.get("format_version") != 1 or not isinstance(data.get("tables"), dict):
            raise ValueError("Versión o estructura de backup no compatible")

        model_by_table = {
            mapper.local_table.name: mapper.class_
            for mapper in Base.registry.mappers
        }
        if set(data["tables"]) != set(model_by_table):
            raise ValueError("El backup no contiene exactamente las tablas de este modelo")

        dependencies = {}
        for table_name, model in model_by_table.items():
            dependencies[table_name] = {
                foreign_key.column.table.name
                for column in model.__table__.columns
                for foreign_key in column.foreign_keys
                if foreign_key.column.table.name != table_name
            }

        restore_order = []
        remaining = set(model_by_table)
        while remaining:
            ready = sorted(
                table for table in remaining
                if dependencies[table].isdisjoint(remaining)
            )
            if not ready:
                raise ValueError("No se pudo resolver el orden de restauración por claves foráneas")
            restore_order.extend(ready)
            remaining.difference_update(ready)

        counts = {}
        async with async_session() as session:
            async with session.begin():
                for table_name in restore_order:
                    model = model_by_table[table_name]
                    existing_count = await session.scalar(
                        select(func.count()).select_from(model)
                    )
                    if existing_count:
                        raise RuntimeError("La restauración requiere una base de datos vacía")

                for table_name in restore_order:
                    model = model_by_table[table_name]
                    columns = {column.key: column for column in model.__table__.columns}
                    rows = data["tables"][table_name]
                    restored_rows = []
                    for row in rows:
                        if not isinstance(row, dict) or set(row) != set(columns):
                            raise ValueError(f"Estructura de fila inválida en {table_name}")
                        restored_rows.append({
                            name: self._deserialize_value(columns[name], value)
                            for name, value in row.items()
                        })
                    if restored_rows:
                        await session.execute(insert(model), restored_rows)
                    counts[table_name] = len(restored_rows)

                for table_name, model in model_by_table.items():
                    for column in model.__table__.primary_key.columns:
                        if column.autoincrement is not True:
                            continue
                        max_id = await session.scalar(select(func.max(column)))
                        if max_id is not None:
                            await session.execute(
                                text("SELECT setval(pg_get_serial_sequence(:table_name, :column_name), :max_id, true)"),
                                {"table_name": table_name, "column_name": column.name, "max_id": max_id}
                            )

        return counts

    async def send_automated_backup(self, client: Client, chat_id: Optional[int] = None) -> bool:
        """Genera y envía el backup al grupo de logs o al admin especificado"""
        target_chat = chat_id or settings.LOG_GROUP_ID
        if not target_chat or target_chat == 0:
            return False

        try:
            backup_file = await self.generate_backup_file()
            caption = (
                f"{EMOJI_DISK} <b>COPIA DE SEGURIDAD AUTOMÁTICA DE BASE DE DATOS</b>\n\n"
                f"{EMOJI_CALENDAR} <b>Fecha:</b> <code>{get_now_str('%Y-%m-%d %H:%M:%S')}</code>\n"
                f"{EMOJI_LOCK} <i>Backup cifrado. Se necesita BACKUP_ENCRYPTION_KEY para restaurarlo.</i>"
            )
            await client.send_document(
                chat_id=target_chat,
                document=backup_file,
                caption=parse_emojis(caption)
            )
            return True
        except Exception as e:
            print(f"[BackupService Error] {e}")
            return False

backup_service = BackupService()
