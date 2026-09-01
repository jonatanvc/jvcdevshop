from datetime import datetime, timezone
import zoneinfo
from bot.config import settings

def get_tz() -> zoneinfo.ZoneInfo:
    """Obtiene la zona horaria configurada con fallback seguro"""
    try:
        return zoneinfo.ZoneInfo(settings.TIMEZONE)
    except Exception:
        return zoneinfo.ZoneInfo("America/Santo_Domingo")

def get_now() -> datetime:
    """Retorna la fecha y hora actual exacta en la zona horaria local"""
    return datetime.now(get_tz())

def get_now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Retorna la fecha y hora actual en la zona horaria local como texto"""
    return get_now().strftime(fmt)

def format_dt(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Convierte cualquier fecha UTC a la hora local configurada"""
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(get_tz()).strftime(fmt)
