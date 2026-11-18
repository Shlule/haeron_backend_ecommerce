from django.forms import ValidationError
from .cartItem_dto import createCartItemDTO
from ..cart.cart_service import CartService
from django.db import transaction
from ..product_configurator.product_type_handlers.product_type_registry import ProductTypeHandlerRegistry
from ..models import CartItem, Product
from haeron_guitar_api.cart.cart_dto import CreateCartDTO
from haeron_guitar_api.product_configurator.configuration_normalizer import ConfigurationNormalizer
from haeron_guitar_api.product_configurator.configuration_rule_engine import RuleEngine
from haeron_guitar_api.product_configurator.product_loader import load_product
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
    def add_item(dto: createCartItemDTO, user=None, session_key=None):
        if dto.quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")

        product = CartItemService._product(dto.product_id)
        if not product.is_visible:
            raise ValidationError("Ce produit n'est plus en vente.")
        cart = CartService.get_or_create_cart(CreateCartDTO(user=user, session_key=session_key))
        snapshot, total_price, config_hash = CartItemService._resolve(product, dto.configuration)

        return CartItemFactory.get_or_create(
            cart=cart,
            product=product,
            config_hash=config_hash,
            snapshot=snapshot,
            total_price=total_price,
            quantity=dto.quantity,
        )

    @staticmethod
    @transaction.atomic
    def reconfigure_item(item: CartItem, configuration) -> CartItem:
        """Replaces the configuration of a cart line (checked and priced again).
        If the cart already holds the same configuration, both lines are merged."""
        snapshot, total_price, config_hash = CartItemService._resolve(item.product, configuration)
        same = CartItem.objects.filter(cart=item.cart, config_hash=config_hash).exclude(pk=item.pk).first()
        if same:
            same.quantity += item.quantity
            same.save()
            item.delete()
            return same
        item.config_snapshot = snapshot
        item.config_hash = config_hash
        item.unit_price = total_price
        item.save()
        return item

    @staticmethod
    def _product(product_id):
        return load_product(product_id)

    @staticmethod
    def _resolve(product, configuration):
        """Checks a configuration against the product rules and prices it : (snapshot, unit price, hash)."""
        total_price = product.price
        snapshot = {}
        if configuration:
            handler = ProductTypeHandlerRegistry.get_handler(product.product_type.code)
            if not handler:
                raise ValueError("No handler exist for this product type")

            snapshot, total_price = handler.resolve(product, configuration)

        # a product without schema is not configurable : no rule to check
        engine = RuleEngine()
        rules_snapshot = engine.collect_rules(product)["rules"] if product.product_schema_id else []
        rules_snapshot = [engine.serialize_rule(rule) for rule in rules_snapshot]
        if rules_snapshot:
            rule_checking_data = ConfigurationNormalizer.normalize(snapshot=snapshot)
            rules_violation = engine.check(configuration=rule_checking_data, rules=rules_snapshot)
            if rules_violation:
                raise ValidationError(rules_violation)

        # the product is part of the hash : two products without configuration are two different lines
        config_hash = ConfigHashService.generate({"product": str(product.pk), "options": snapshot})
        # the configuration as sent is kept, so the line can be opened again in the configurator
        return {"options": snapshot, "configuration": configuration or {}}, total_price, config_hash

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
