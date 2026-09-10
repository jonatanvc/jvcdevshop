import secrets
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Tuple, Optional, List, Dict, Any
from sqlalchemy import select, func, update
from bot.database.models import User, Coupon, CouponUsage, GiftCard, Order

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class PromoService:
    def generate_gift_code(self) -> str:
        """Genera un código aleatorio seguro tipo GIFT-XXXX-YYYY"""
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        part1 = "".join(secrets.choice(chars) for _ in range(4))
        part2 = "".join(secrets.choice(chars) for _ in range(4))
        return f"GIFT-{part1}-{part2}"

    async def create_coupon(
        self,
        session,
        code: str,
        discount_type: str,
        discount_value: float,
        min_purchase: float = 0.0,
        max_uses: int = 0,
        user_limit: int = 1,
        duration_days: int = 0
    ) -> Tuple[bool, str, Optional[Coupon]]:
        """Crea un nuevo cupón de descuento en la base de datos"""
        clean_code = code.strip().upper()
        if not clean_code or len(clean_code) < 3:
            return False, "El código debe tener al menos 3 caracteres.", None

        # Comprobar si ya existe
        stmt = select(Coupon).where(Coupon.code == clean_code)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            return False, f"El cupón '{clean_code}' ya existe en el sistema.", None

        if discount_type not in ("percent", "fixed"):
            return False, "Tipo de descuento inválido (debe ser percent o fixed).", None

        if discount_value <= 0:
            return False, "El valor del descuento debe ser mayor a 0.", None

        if discount_type == "percent" and discount_value > 90:
            return False, "El porcentaje de descuento no puede ser mayor al 90%.", None

        expires_at = None
        if duration_days > 0:
            expires_at = utc_now() + timedelta(days=duration_days)

        coupon = Coupon(
            code=clean_code,
            discount_type=discount_type,
            discount_value=Decimal(str(round(discount_value, 2))),
            min_purchase=Decimal(str(round(min_purchase, 2))),
            max_uses=max_uses,
            current_uses=0,
            user_limit=user_limit,
            is_active=True,
            expires_at=expires_at,
            created_at=utc_now()
        )
        session.add(coupon)
        await session.commit()
        await session.refresh(coupon)
        return True, "Cupón creado exitosamente.", coupon

    async def validate_coupon(
        self,
        session,
        code: str,
        user_id: int,
        cart_amount: float
    ) -> Tuple[bool, str, Optional[Coupon], float]:
        """
        Valida si un cupón es aplicable a un usuario y carrito determinado.
        Retorna: (is_valid, message, coupon_obj, discount_amount)
        """
        clean_code = code.strip().upper()
        stmt = select(Coupon).where(Coupon.code == clean_code)
        res = await session.execute(stmt)
        coupon = res.scalar_one_or_none()

        if not coupon:
            return False, "❌ Cupón no válido o inexistente.", None, 0.0

        if not coupon.is_active:
            return False, "❌ Este cupón se encuentra desactivado.", None, 0.0

        now = utc_now()
        if coupon.expires_at and coupon.expires_at < now:
            return False, "❌ Este cupón ha expirado.", None, 0.0

        if coupon.max_uses > 0 and coupon.current_uses >= coupon.max_uses:
            return False, "❌ Este cupón ha alcanzado el límite máximo de usos.", None, 0.0

        if coupon.min_purchase > 0 and Decimal(str(cart_amount)) < coupon.min_purchase:
            return False, f"❌ Compra mínima requerida para este cupón: ${float(coupon.min_purchase):.2f} USDT.", None, 0.0

        # Validar límite de uso por usuario
        usage_stmt = select(func.count(CouponUsage.id)).where(
            CouponUsage.coupon_id == coupon.id,
            CouponUsage.user_id == user_id
        )
        usage_res = await session.execute(usage_stmt)
        user_uses = usage_res.scalar() or 0

        if coupon.user_limit > 0 and user_uses >= coupon.user_limit:
            return False, "❌ Ya has alcanzado el límite de uso de este cupón.", None, 0.0

        # Calcular monto de descuento
        val = float(coupon.discount_value)
        if coupon.discount_type == "percent":
            discount = round(cart_amount * (val / 100.0), 2)
        else:
            discount = min(val, cart_amount)

        return True, "Cupón válido", coupon, discount

    async def consume_coupon(
        self,
        session,
        coupon_id: int,
        user_id: int,
        order_id: Optional[int],
        discount_amount: float
    ):
        """Registra el uso efectivo de un cupón tras la compra"""
        stmt = select(Coupon).where(Coupon.id == coupon_id)
        res = await session.execute(stmt)
        coupon = res.scalar_one_or_none()
        if coupon:
            coupon.current_uses += 1
            usage = CouponUsage(
                coupon_id=coupon.id,
                user_id=user_id,
                order_id=order_id,
                discount_amount=Decimal(str(round(discount_amount, 2))),
                used_at=utc_now()
            )
            session.add(usage)
            # Limpiar cupón activo del usuario
            await session.execute(
                update(User).where(User.telegram_id == user_id).values(active_coupon_code=None)
            )

    async def create_gift_cards(
        self,
        session,
        amount: float,
        count: int = 1,
        created_by: int = 0
    ) -> List[GiftCard]:
        """Genera una o varias tarjetas de regalo con saldo USDT"""
        cards = []
        amount_dec = Decimal(str(round(amount, 2)))
        for _ in range(max(1, min(count, 50))):
            code = self.generate_gift_code()
            card = GiftCard(
                code=code,
                amount=amount_dec,
                is_redeemed=False,
                created_by=created_by,
                created_at=utc_now()
            )
            session.add(card)
            cards.append(card)
        await session.commit()
        for c in cards:
            await session.refresh(c)
        return cards

    async def redeem_gift_card(
        self,
        session,
        code: str,
        user_id: int
    ) -> Tuple[bool, str, float]:
        """
        Canjea de forma atómica una tarjeta de regalo e incrementa el saldo del usuario.
        Retorna: (éxito, mensaje, monto_acreditado)
        """
        clean_code = code.strip().upper()
        # Bloqueo transaccional de fila para evitar race conditions
        stmt = select(GiftCard).where(GiftCard.code == clean_code).with_for_update()
        res = await session.execute(stmt)
        card = res.scalar_one_or_none()

        if not card:
            return False, "❌ Tarjeta de regalo no válida o inexistente.", 0.0

        if card.is_redeemed:
            return False, "❌ Esta tarjeta de regalo ya ha sido canjeada.", 0.0

        now = utc_now()
        if card.expires_at and card.expires_at < now:
            return False, "❌ Esta tarjeta de regalo ha expirado.", 0.0

        # Bloquear usuario para incrementar saldo
        u_stmt = select(User).where(User.telegram_id == user_id).with_for_update()
        u_res = await session.execute(u_stmt)
        user = u_res.scalar_one_or_none()

        if not user:
            return False, "❌ Error al cargar tu cuenta de usuario.", 0.0

        credited_amount = float(card.amount)
        user.balance = Decimal(str(round(float(user.balance) + credited_amount, 4)))
        card.is_redeemed = True
        card.redeemed_by = user_id
        card.redeemed_at = now

        await session.commit()
        return True, "¡Tarjeta de regalo canjeada con éxito!", credited_amount

promo_service = PromoService()
