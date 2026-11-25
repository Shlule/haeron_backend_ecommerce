from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from ..models import Cart, Order, OrderItem
from ..partners import partner_service
from .checkout_dto import CustomerDTO


class CheckoutService:
    REQUIRED = {
        "email": "l'e-mail",
        "first_name": "le prénom",
        "last_name": "le nom",
        "address": "l'adresse",
        "postal_code": "le code postal",
        "city": "la ville",
    }

    @staticmethod
    @transaction.atomic
    def checkout(idempotency_key, customer: CustomerDTO, user=None, session_key=None, accepted_at=None, partner_code=""):
        """Turns the active cart into a pending order (waiting for the payment) and closes the cart.
        accepted_at : when the customer accepted the CGV and the colour terms, kept on the order as proof.
        partner_code : code of a partner (typed or from its link), gives its discount (see partners/partner_service.py)."""
        if not user and not session_key:
            raise ValueError("User or session_key are not either present")

        # the same key sent twice (double click, network retry) gives back the same order
        order = Order.objects.filter(idempotency_key=idempotency_key).first()
        if order:
            return order

        CheckoutService._check_customer(customer)

        carts = Cart.objects.select_for_update().filter(is_active=True)
        cart = carts.filter(user=user).first() if user else carts.filter(session_key=session_key, user__isnull=True).first()
        items = list(cart.cart_items.select_related("product")) if cart else []
        if not items:
            raise ValidationError("Votre panier est vide.")

        order = Order.objects.create(
            user=user,
            idempotency_key=idempotency_key,
            status="pending",
            email=customer.email.strip(),
            first_name=customer.first_name.strip(),
            last_name=customer.last_name.strip(),
            phone=customer.phone.strip(),
            address=customer.address.strip(),
            postal_code=customer.postal_code.strip(),
            city=customer.city.strip(),
            country=(customer.country or "FR").strip().upper(),
            terms_accepted_at=accepted_at,
            colour_terms_accepted_at=accepted_at,
        )

        # every line in one insert
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    product_id=item.product.uuid,
                    product_name=item.product.name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    config_snapshot=item.config_snapshot or {},
                    config_hash=item.config_hash or "",
                )
                for item in items
            ]
        )
        total = sum((item.unit_price * item.quantity for item in items), Decimal("0.00"))

        # partner code : discount on the total, partner and rates kept on the order
        order.total_price = partner_service.apply_to_order(order, partner_code, total)
        order.save(
            update_fields=[
                "total_price", "partner", "partner_code", "discount_percent", "discount_amount", "commission_percent"
            ]
        )

        # the cart is now an order : the next visit starts a new cart
        cart.is_active = False
        cart.save(update_fields=["is_active"])

        return order

    @staticmethod
    def _check_customer(customer: CustomerDTO):
        missing = [label for field, label in CheckoutService.REQUIRED.items() if not getattr(customer, field, "").strip()]
        if missing:
            raise ValidationError(f"Merci d'indiquer {', '.join(missing)}.")
        try:
            validate_email(customer.email.strip())
        except ValidationError:
            raise ValidationError("Cette adresse e-mail n'est pas valide.")
        if len(customer.country.strip()) != 2:
            raise ValidationError("Le pays doit être un code à deux lettres (FR, BE...).")
