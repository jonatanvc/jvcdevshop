import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Numeric,
    DateTime,
    Boolean,
    Text,
    Enum,
    ForeignKey,
    Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class DepositStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(64), nullable=True)
    first_name = Column(String(128), nullable=True)
    balance = Column(Numeric(12, 4), default=0.0000, nullable=False)
    total_spent = Column(Numeric(12, 4), default=0.0000, nullable=False)
    language = Column(String(5), default="es", nullable=False)
    referred_by = Column(BigInteger, nullable=True)
    is_vip = Column(Boolean, default=False, nullable=False, index=True)
    vip_expires_at = Column(DateTime, nullable=True, index=True)
    vip_warned_24h = Column(Boolean, default=False, nullable=False)
    vip_warned_2h = Column(Boolean, default=False, nullable=False)
    active_coupon_code = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    deposits = relationship("Deposit", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    stock_alerts = relationship("StockAlert", back_populates="user", cascade="all, delete-orphan")

class Deposit(Base):
    __tablename__ = "deposits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    base_amount = Column(Numeric(12, 4), nullable=False)
    exact_amount = Column(Numeric(12, 4), nullable=False, index=True)
    tx_hash = Column(String(128), unique=True, nullable=True, index=True)
    status = Column(Enum(DepositStatus), default=DepositStatus.PENDING, nullable=False, index=True)
    reminder_sent = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    log_message_id = Column(BigInteger, nullable=True)

    user = relationship("User", back_populates="deposits")

    __table_args__ = (
        Index("ix_deposits_user_status", "user_id", "status"),
    )

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    product_id = Column(String(64), nullable=False)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Numeric(12, 4), nullable=False)
    total_price = Column(Numeric(12, 4), nullable=False)
    provider_order_id = Column(String(128), nullable=True)
    delivered_items = Column(Text, nullable=False)
    warranty_hours = Column(Integer, default=0, nullable=False)
    rating = Column(Integer, nullable=True)
    voucher_message_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="orders")

class StockAlert(Base):
    __tablename__ = "stock_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    notified_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="stock_alerts")

    __table_args__ = (
        Index("ix_stock_alerts_active", "product_id", "is_active"),
    )

class CustomPricing(Base):
    __tablename__ = "custom_pricing"

    product_id = Column(String(64), primary_key=True)
    custom_price = Column(Numeric(12, 4), nullable=True)
    custom_margin = Column(Numeric(5, 2), nullable=True)
    is_hidden = Column(Boolean, default=False, nullable=False)

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)

class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    discount_type = Column(String(16), default="percent", nullable=False)  # "percent" o "fixed"
    discount_value = Column(Numeric(10, 2), nullable=False)  # e.g. 10.00 (% o USDT)
    min_purchase = Column(Numeric(10, 2), default=0.0, nullable=False)
    max_uses = Column(Integer, default=0, nullable=False)  # 0 = ilimitado
    current_uses = Column(Integer, default=0, nullable=False)
    user_limit = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    usages = relationship("CouponUsage", back_populates="coupon", cascade="all, delete-orphan")

class CouponUsage(Base):
    __tablename__ = "coupon_usages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    discount_amount = Column(Numeric(10, 2), nullable=False)
    used_at = Column(DateTime, default=utc_now, nullable=False)

    coupon = relationship("Coupon", back_populates="usages")
    user = relationship("User")
    order = relationship("Order")

class GiftCard(Base):
    __tablename__ = "gift_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    is_redeemed = Column(Boolean, default=False, nullable=False, index=True)
    redeemed_by = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=True, index=True)
    redeemed_at = Column(DateTime, nullable=True)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[redeemed_by])

class VirtualNumberOrder(Base):
    __tablename__ = "virtual_number_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    fivesim_order_id = Column(BigInteger, unique=True, nullable=False, index=True)
    phone = Column(String(32), nullable=False)
    service_name = Column(String(64), nullable=False, index=True)
    country = Column(String(64), nullable=False)
    operator = Column(String(64), nullable=False, default="any")
    cost_usd = Column(Numeric(10, 4), nullable=False)
    price_usdt = Column(Numeric(10, 4), nullable=False)
    sms_code = Column(String(32), nullable=True)
    sms_full_text = Column(Text, nullable=True)
    status = Column(String(20), default="PENDING", nullable=False, index=True)  # PENDING, RECEIVED, FINISHED, CANCELLED, TIMEOUT
    is_refunded = Column(Boolean, default=False, nullable=False)
    voucher_message_id = Column(BigInteger, nullable=True)
    rating = Column(Integer, nullable=True)
    payment_method = Column(String(16), default="bot", nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User")

