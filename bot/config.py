from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Telegram API
    API_ID: int = 12345678
    API_HASH: str = "your_api_hash"
    BOT_TOKEN: str = "your_bot_token"
    
    # Administradores y Grupo de Auditoría / Canal de Vouchers
    ADMIN_IDS_RAW: str = "8670239783"
    LOG_GROUP_ID: int = 0
    VOUCHERS_CHANNEL_ID: int = 0
    
    # BunaiStore API
    BUNAI_API_KEY: str = "Shop::_3a2klpvDK9_SH2FY46suaM5pb8"
    BUNAI_BASE_URL: str = "https://api.bunaistore.shop/v1"
    
    # 5SIM.net API (Números Virtuales SMS)
    FIVESIM_API_KEY: str = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4MTY4NDk3NjEsImlhdCI6MTc4NTMxMzc2MSwicmF5IjoiNjllMGI2ZjQ2OGJmMjdhYzIyYTQzYzI4ZmRlYTVjMzgiLCJzdWIiOjM4ODg1Mjl9.gu54FGHVRKWfCXkQc8UWy8raq6w4rR4tsHLnrzOe4kyb4pOX2dxNc5EuCQDy0Xe1Luixgnh_Wl8Fadu-fshwT-GuHxSGqEJWZkbmgJLKPiscrtXW3lbpMUlWjgbomkQVArP2PqP-pXGJ-jvAeeeqKP2r-C6qK8NxrdhGuKo90oDt-1KVXlecabFKXlYT9RwxZCAPyTD63QCO3oVZ_Ae4GKpbxxWxUmwl-WTtf1h23fdQpzIkAgIgMJXd9o0Zf_Nr7Uo3Kk78U-bNXZLqsmY8lxDwRmCG98khxJFkyFUNZrj3mK90nL7WE1MhdIlHx9JarIPQ77olY6yGgS1_I6WIaA"
    FIVESIM_BASE_URL: str = "https://5sim.net"
    
    # Blockchain BSC / USDT BEP-20
    ADMIN_WALLET_BSC: str = "0x540532E72e08fdaAB525f5D692ea97C40CCE5d24"
    BSC_RPC_URL: str = "https://bsc-dataseed.binance.org/"
    BSC_RPC_FALLBACKS_RAW: str = "https://1rpc.io/bnb,https://rpc.ankr.com/bsc,https://bsc.publicnode.com,https://bsc-dataseed1.defibit.io"
    USDT_CONTRACT_ADDRESS: str = "0x55d398326f99059fF775485246999027B3197955"
    MIN_BLOCK_CONFIRMATIONS: int = 3
    
    # Parámetros del servicio
    DEFAULT_MARGIN_PERCENT: float = 30.0
    MIN_DEPOSIT_USDT: float = 2.0
    REFERRAL_COMMISSION_PERCENT: float = 5.0
    QR_IMAGE_PATH: str = "assets/TrustWalletQR.jpg"
    AUTO_BACKUP_HOURS: int = 24
    TIMEZONE: str = "America/Santo_Domingo"

    # Plan Revendedor VIP
    VIP_MONTHLY_PRICE_USDT: float = 10.0
    VIP_DISCOUNT_PERCENT: float = 20.0
    VIP_REFERRAL_COMMISSION_PERCENT: float = 20.0
    VIP_DURATION_DAYS: int = 30
    
    # Base de Datos
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres_secure_pass@localhost:5432/services_bot"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def admin_ids(self) -> List[int]:
        if not self.ADMIN_IDS_RAW:
            return []
        return [int(x.strip()) for x in str(self.ADMIN_IDS_RAW).split(",") if x.strip().isdigit()]

    @property
    def owner_id(self) -> int:
        if self.admin_ids:
            return self.admin_ids[0]
        return 8670239783

    def is_owner(self, user_id: int) -> bool:
        return bool(user_id == 8670239783 or (self.admin_ids and user_id in self.admin_ids))

    @property
    def rpc_endpoints(self) -> List[str]:
        endpoints = [self.BSC_RPC_URL]
        if self.BSC_RPC_FALLBACKS_RAW:
            fallbacks = [x.strip() for x in self.BSC_RPC_FALLBACKS_RAW.split(",") if x.strip()]
            for fb in fallbacks:
                if fb not in endpoints:
                    endpoints.append(fb)
        return endpoints

settings = Settings()
