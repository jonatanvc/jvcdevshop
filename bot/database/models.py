import enum
from datetime import datetime
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
    Index,
    UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="orders")

class StockAlert(Base):
    __tablename__ = "stock_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
