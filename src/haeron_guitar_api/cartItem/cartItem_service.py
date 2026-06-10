from pprint import pprint
from tracemalloc import Snapshot
from django.forms import ValidationError
from .cartItem_dto import createCartItemDTO
from django.db import transaction
from ..product_configurator.product_type_handlers.product_type_registry import ProductTypeHandlerRegistry
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

        product = (
            Product.objects.select_related("product_type", "product_schema")
            .prefetch_related("product_schema__product_components")
            .get(pk=dto.product_id)
        )
        print("$" * 50)
        pprint(product)
        pprint(product.product_schema)
        pprint(product.product_schema.product_components)
        product_type_code = product.product_type.code
        print(product_type_code)
        print(ProductTypeHandlerRegistry._registry)
        cart = Cart.objects.get(uuid=dto.cart_id, is_active=True)
        total_price = product.price
        snapshot = {}
        if dto.configuration:
            handler = ProductTypeHandlerRegistry.get_handler(product_type_code)
            if not handler:
                raise ValueError("No handler exist for this product type")

            snapshot, total_price = handler.resolve(product, dto.configuration)

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
