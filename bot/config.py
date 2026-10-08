from typing import List
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Telegram API
    API_ID: int = Field(gt=0)
    API_HASH: str = Field(min_length=1)
    BOT_TOKEN: str = Field(min_length=1)
    
    # Administradores y Grupo de Auditoría / Canal de Vouchers
    ADMIN_IDS_RAW: str = Field(validation_alias=AliasChoices("ADMIN_IDS", "ADMIN_IDS_RAW"))
    LOG_GROUP_ID: int = 0
    VOUCHERS_CHANNEL_ID: int = 0
    
    # BunaiStore API
    BUNAI_API_KEY: str = Field(min_length=1)
    BUNAI_BASE_URL: str = "https://api.bunaistore.shop/v1"
    
    # 5SIM.net API (Números Virtuales SMS)
    FIVESIM_API_KEY: str = ""
    FIVESIM_BASE_URL: str = "https://5sim.net"
    
    # Blockchain BSC / USDT BEP-20
    ADMIN_WALLET_BSC: str = Field(min_length=1)
    BSC_RPC_URL: str = "https://bsc-dataseed.binance.org/"
    BSC_RPC_FALLBACKS_RAW: str = "https://1rpc.io/bnb,https://rpc.ankr.com/bsc,https://bsc.publicnode.com,https://bsc-dataseed1.defibit.io"
    USDT_CONTRACT_ADDRESS: str = "0x55d398326f99059fF775485246999027B3197955"
    MIN_BLOCK_CONFIRMATIONS: int = Field(default=3, ge=1)
    BSC_MONITOR_INTERVAL_SECONDS: int = Field(default=10, ge=3)
    BSC_INITIAL_SCAN_BLOCKS: int = Field(default=5000, ge=1)
    
    # Parámetros del servicio
    DEFAULT_MARGIN_PERCENT: float = 30.0
    MIN_DEPOSIT_USDT: float = 2.0
    DEPOSIT_EXPIRY_MINUTES: int = Field(default=30, ge=1)
    REFERRAL_COMMISSION_PERCENT: float = 5.0
    QR_IMAGE_PATH: str = "assets/TrustWalletQR.jpg"
    AUTO_BACKUP_HOURS: int = 24
    BACKUP_ENCRYPTION_KEY: str = ""
    TIMEZONE: str = "America/Santo_Domingo"

    # Plan Revendedor VIP
    VIP_MONTHLY_PRICE_USDT: float = 10.0
    VIP_DISCOUNT_PERCENT: float = 20.0
    VIP_REFERRAL_COMMISSION_PERCENT: float = 20.0
    VIP_DURATION_DAYS: int = 30
    
    # Base de Datos
    DATABASE_URL: str = Field(min_length=1)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("ADMIN_IDS_RAW")
    @classmethod
    def validate_admin_ids(cls, value: str) -> str:
        admin_ids = [admin_id.strip() for admin_id in value.split(",")]
        if not admin_ids or any(not admin_id.isdigit() for admin_id in admin_ids):
            raise ValueError("ADMIN_IDS debe contener uno o mas IDs numericos")
        if len(set(admin_ids)) != len(admin_ids):
            raise ValueError("ADMIN_IDS no debe contener IDs duplicados")
        return ",".join(admin_ids)

    @property
    def admin_ids(self) -> List[int]:
        if not self.ADMIN_IDS_RAW:
            return []
        return [int(x.strip()) for x in str(self.ADMIN_IDS_RAW).split(",") if x.strip().isdigit()]

    @property
    def owner_id(self) -> int:
        return self.admin_ids[0]

    def is_owner(self, user_id: int) -> bool:
        return user_id == self.owner_id

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
