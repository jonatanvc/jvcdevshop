from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Telegram API
    API_ID: int = 12345678
    API_HASH: str = "your_api_hash"
    BOT_TOKEN: str = "your_bot_token"
    
    # Administradores y Grupo de Auditoría
    ADMIN_IDS_RAW: str = "8670239783"
    LOG_GROUP_ID: int = 0
    
    # BunaiStore API
    BUNAI_API_KEY: str = "Shop::_3a2klpvDK9_SH2FY46suaM5pb8"
    BUNAI_BASE_URL: str = "https://api.bunaistore.shop/v1"
    
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
    def rpc_endpoints(self) -> List[str]:
        endpoints = [self.BSC_RPC_URL]
        if self.BSC_RPC_FALLBACKS_RAW:
            fallbacks = [x.strip() for x in self.BSC_RPC_FALLBACKS_RAW.split(",") if x.strip()]
            for fb in fallbacks:
                if fb not in endpoints:
                    endpoints.append(fb)
        return endpoints

settings = Settings()
