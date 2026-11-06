import secrets

from django.core.exceptions import ValidationError

from ..cartItem.cartItem_dto import createCartItemDTO
from ..cartItem.cartItem_service import CartItemService
from ..models import Cart, Product


class StorefrontService:
    """Public shop : product list and the visitor cart, identified by a random key kept by the browser."""

    @staticmethod
    def products():
        products = Product.objects.select_related("product_type").order_by("name")
        return [
            {
                "id": str(product.uuid),
                "name": product.name,
                "price": float(product.price),
                "type": product.product_type.code,
                # a product with a schema goes through the configurator, the others are added to the cart as they are
                "configurable": product.product_schema_id is not None,
                "image": product.image,
                "model3d": product.model_3d,
            }
            for product in products
        ]

    @staticmethod
    def find_cart(user=None, cart_key=None):
        carts = Cart.objects.filter(is_active=True)
        if user is not None and user.is_authenticated:
            return carts.filter(user=user).first()
        if cart_key:
            return carts.filter(session_key=cart_key, user__isnull=True).first()
        return None

    @staticmethod
    def add(product_id, configuration, quantity, user=None, cart_key=None):
        logged_in = user is not None and user.is_authenticated
        # an unknown key is replaced : the browser never chooses the key of a new cart
        if not logged_in and not StorefrontService.find_cart(cart_key=cart_key):
            cart_key = secrets.token_urlsafe(32)

        dto = createCartItemDTO(product_id=product_id, configuration=configuration or None, quantity=quantity)
        CartItemService.add_item(dto, user=user if logged_in else None, session_key=None if logged_in else cart_key)
        return StorefrontService.find_cart(user=user, cart_key=cart_key), cart_key

    @staticmethod
    def remove(item_id, user=None, cart_key=None):
        cart = StorefrontService.find_cart(user=user, cart_key=cart_key)
        if cart is None or not cart.cart_items.filter(pk=item_id).exists():
            raise ValidationError("Cet article n'est pas dans votre panier.")
        CartItemService.delete_item(item_id)
        return cart

    @staticmethod
    def serialize(cart, cart_key=None):
        if cart is None:
            return {"cartKey": cart_key, "count": 0, "total": 0, "items": []}
        items = []
        total = 0
        for item in cart.cart_items.select_related("product").order_by("created_at", "uuid"):
            line_total = item.unit_price * item.quantity
            total += line_total
            items.append(
                {
                    "id": str(item.uuid),
                    "productId": str(item.product_id) if item.product_id else None,
                    "name": item.product.name if item.product else "",
                    "quantity": item.quantity,
                    "unitPrice": float(item.unit_price),
                    "total": float(line_total),
                    "details": StorefrontService._details((item.config_snapshot or {}).get("options")),
                }
            )
        return {
            "cartKey": cart_key,
            "count": sum(item["quantity"] for item in items),
            "total": float(total),
            "items": items,
        }

    @staticmethod
    def _details(snapshot):
        """Choices of a configured item, per component : [{component, values: [{option, value}], product}]"""
        if not snapshot:
            return []
        components = snapshot if isinstance(snapshot, list) else [snapshot]
        details = []
        for component in components:
            if not isinstance(component, dict):
                continue
            details.append(
                {
                    "component": component.get("component", ""),
                    "values": [
                        {"option": option.get("name"), "value": option.get("value")}
                        for option in component.get("options", [])
                    ],
                    # part model of a custom piece, product of a chosen or fixed component
                    "product": component.get("part_model") or component.get("name"),
                }
            )
        return details
