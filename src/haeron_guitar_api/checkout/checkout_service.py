from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

from ..models import OrderItem, Order
from haeron_guitar_api.cart.cart_service import CartService
from haeron_guitar_api.cart.cart_dto import CreateCartDTO


class CheckoutService:
    @transaction.atomic
    def checkout(idempotency_key, user=None, session_key=None):
        if not user and not session_key:
            raise ValueError("User or session_key are not either present")

        order = Order.objects.filter(idempotency_key=idempotency_key).first()
        if order:
            return order

        cart = CartService.get_or_create_cart(CreateCartDTO(user=user, session_key=session_key))

        order = Order.objects.create(
            user=cart.user,
            idempotency_key=idempotency_key,
            total_price=0,
            status="pending",
        )

        total = Decimal("0.00")

        for item in cart.cart_items.all():
            OrderItem.objects.create(
                order=order,
                product_id=item.product.uuid,
                product_name=item.product.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                config_snapshot=item.config_snapshot,
                config_hash=item.config_hash,
            )

            total += item.unit_price * item.quantity

        order.total_price = total
        order.save()

        # cart.is_active = False
        # cart.save()

        return order
