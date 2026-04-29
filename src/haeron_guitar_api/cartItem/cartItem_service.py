from django.forms import ValidationError
from .cartItem_dto import createCartItemDTO
from .cartItem_utils import CartItemConfigResolver
from django.db import transaction
from ..models import CartItem, Cart, Product, PartModel, PartModelOption
import hashlib
import json


class CartItemFactory:
    @staticmethod
    def get_or_create(cart, product, config_hash, snapshot, total_price, quantity):
        item = CartItem.objects.filter(cart=cart, config_hash=config_hash).first()

        if item:
            item.quantity += quantity
            item.save()
            return item

        return CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=quantity,
            config_snapshot=snapshot,
            config_hash=config_hash,
            unit_price=total_price,
        )


class ConfigHashService:
    @staticmethod
    def generate(snapshot):

        config_str = json.dumps(snapshot, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()


class CartItemService:
    @staticmethod
    @transaction.atomic
    def add_item(dto: createCartItemDTO):
        if dto.quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")

        cart = Cart.objects.get(uuid=dto.cart_id, is_active=True)
        product = Product.objects.get(uuid=dto.product_id)

        options = PartModelOption.objects.filter(pk__in=dto.part_model_option_ids or [])
        total_price, snapshot = CartItemConfigResolver.resolve(product.price, options)

        config_hash = ConfigHashService.generate(snapshot)

        return CartItemFactory.get_or_create(
            cart=cart,
            product=product,
            config_hash=config_hash,
            snapshot={"options": snapshot},
            total_price=total_price,
            quantity=dto.quantity,
        )

    @staticmethod
    @transaction.atomic
    def update_quantity(cart_item_id, quantity: int) -> CartItem:
        if quantity < 0:
            raise ValidationError("Quantity of item caanot not be negative")

        try:
            item = CartItem.objects.select_for_update().get(pk=cart_item_id)
        except CartItem.DoesNotExist:
            raise ValidationError("CartItem does not exist")

        if quantity == 0:
            item.delete()
            return None

        item.quantity = quantity
        item.save()
        return item

    @staticmethod
    @transaction.atomic
    def delete_item(cart_item_id) -> bool:

        deleted, _ = CartItem.objects.filter(uuid=cart_item_id).delete()

        return deleted > 0

    @staticmethod
    @transaction.atomic
    def delete_items(cart_item_ids: list) -> int:

        deleted, _ = CartItem.objects.filter(uuid__in=cart_item_ids).delete()

        return deleted
