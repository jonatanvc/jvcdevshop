import io
import json
import gzip
from datetime import datetime
from typing import Optional
from pyrogram import Client
from sqlalchemy import select
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, Deposit, Order, Setting, CustomPricing

class BackupService:
    async def generate_backup_file(self) -> io.BytesIO:
        """Exporta toda la base de datos a un archivo comprimido JSON.GZ"""
        async with async_session() as session:
            # 1. Obtener usuarios
            users_res = await session.execute(select(User))
            users = [
                {
                    "telegram_id": u.telegram_id,
                    "username": u.username,
                    "first_name": u.first_name,
                    "balance": float(u.balance),
                    "total_spent": float(u.total_spent),
                    "referred_by": u.referred_by,
                    "created_at": u.created_at.isoformat() if u.created_at else None
                }
                for u in users_res.scalars().all()
            ]

            # 2. Obtener depósitos
            dep_res = await session.execute(select(Deposit))
            deposits = [
                {
                    "id": d.id,
                    "user_id": d.user_id,
                    "base_amount": float(d.base_amount),
                    "exact_amount": float(d.exact_amount),
                    "tx_hash": d.tx_hash,
                    "status": str(d.status),
                    "expires_at": d.expires_at.isoformat() if d.expires_at else None,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "confirmed_at": d.confirmed_at.isoformat() if d.confirmed_at else None
                }
                for d in dep_res.scalars().all()
            ]

            # 3. Obtener órdenes
            ord_res = await session.execute(select(Order))
            orders = [
                {
                    "id": o.id,
                    "user_id": o.user_id,
                    "product_id": o.product_id,
                    "product_name": o.product_name,
                    "quantity": o.quantity,
                    "unit_price": float(o.unit_price),
                    "total_price": float(o.total_price),
                    "provider_order_id": o.provider_order_id,
                    "delivered_items": o.delivered_items,
                    "warranty_hours": o.warranty_hours,
                    "created_at": o.created_at.isoformat() if o.created_at else None
                }
                for o in ord_res.scalars().all()
            ]

            # 4. Obtener settings y custom pricing
            set_res = await session.execute(select(Setting))
            settings_data = {s.key: s.value for s in set_res.scalars().all()}

            cp_res = await session.execute(select(CustomPricing))
            custom_pricing = [
                {
                    "product_id": cp.product_id,
                    "custom_price": float(cp.custom_price) if cp.custom_price else None,
                    "custom_margin": float(cp.custom_margin) if cp.custom_margin else None,
                    "is_hidden": cp.is_hidden
                }
                for cp in cp_res.scalars().all()
            ]

        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "counts": {
                "users": len(users),
                "deposits": len(deposits),
                "orders": len(orders)
            },
            "users": users,
            "deposits": deposits,
            "orders": orders,
            "settings": settings_data,
            "custom_pricing": custom_pricing
        }

        # Serializar y comprimir con gzip
        json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        compressed_io = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_io, mode="wb") as gz:
            gz.write(json_bytes)
        
        now_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        compressed_io.name = f"database_backup_{now_str}.json.gz"
        compressed_io.seek(0)
        return compressed_io

    async def send_automated_backup(self, client: Client, chat_id: Optional[int] = None):
        """Genera y envía el backup al grupo de logs o al admin especificado"""
        target_chat = chat_id or settings.LOG_GROUP_ID
        if not target_chat or target_chat == 0:
            return

        try:
            backup_file = await self.generate_backup_file()
            caption = (
                f"💾 <b>COPIA DE SEGURIDAD AUTOMÁTICA DE BASE DE DATOS</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📅 <b>Fecha:</b> <code>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</code>\n"
                f"🔒 <i>Guarda este archivo. Contiene todos los usuarios, órdenes, compras y balances.</i>"
            )
            await client.send_document(
                chat_id=target_chat,
                document=backup_file,
                caption=caption
            )
        except Exception as e:
            print(f"[BackupService Error] {e}")

backup_service = BackupService()
