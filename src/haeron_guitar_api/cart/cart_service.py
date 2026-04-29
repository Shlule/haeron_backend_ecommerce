from datetime import timedelta
from django.utils import timezone
from django.db import IntegrityError, transaction
from .cart_dto import CreateCartDTO
from ..models import Cart, CartItem


class CartService:
    CART_LIFETIME_DAY = 15

    @staticmethod
    def get_or_create_cart(dto: CreateCartDTO):
        user = dto.user
        if user:
            cart, created = Cart.objects.get_or_create(
                user=user, is_active=True, defaults=CartService._default_cart_data()
            )
            return cart

        session_key = dto.session_key
        if session_key:
            cart, created = Cart.objects.get_or_create(
                session_key=session_key, is_active=True, defaults=CartService._default_cart_data()
            )
            return cart

        raise ValueError("Either user or session mus be provided")

    @staticmethod
    def _default_cart_data():
        now = timezone.now()
        return {"expires_at": now + timedelta(days=CartService.CART_LIFETIME_DAY)}

    @staticmethod
    def touch(cart: Cart):
        cart.last_activity_at = timezone.now()
        cart.expires_at = timezone.now() + timedelta(days=CartService.CART_LIFETIME_DAY)
        cart.save(update_fields=["last_activity_at", "expires_at"])

    @staticmethod
    def expire_old_carts():
        Cart.objects.filter(expires_at__lt=timezone.now(), is_active=True).update(is_active=False)

    @staticmethod
    @transaction.atomic
    def merge_guest_to_user(guest_cart, user):

        user_cart = Cart.objects.select_for_update().filter(user=user, is_active=True).first()

        if not user_cart:
            guest_cart.user = user
            guest_cart.session_key = None
            guest_cart.save()
            return guest_cart

        guest_items = guest_cart.cart_items.select_for_update().all()

        for guest_item in guest_items:
            try:
                existing_item = user_cart.cart_items.select_for_update().get(config_hash=guest_item.config_hash)

                existing_item.quantity += guest_item.quantity
                existing_item.save()

            except CartItem.DoesNotExist:
                guest_item.cart = user_cart
                guest_item.save()

        guest_cart.is_active = False
        guest_cart.save()

        return user_cart
