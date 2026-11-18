import secrets

from django.core.exceptions import ValidationError

from ..cartItem.cartItem_dto import createCartItemDTO
from ..cartItem.cartItem_service import CartItemService
from ..checkout.checkout_dto import CustomerDTO
from ..checkout.checkout_service import CheckoutService
from django.db.models import Prefetch

from ..models import Cart, CartItem, Order, OrderItem, Product


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
        item = CartItemService.add_item(dto, user=user if logged_in else None, session_key=None if logged_in else cart_key)
        # the cart of the new line is the visitor cart : no need to look it up again
        return item.cart, cart_key

    @staticmethod
    def remove(item_id, user=None, cart_key=None):
        cart, _ = StorefrontService._own_item(item_id, user, cart_key)
        CartItemService.delete_item(item_id)
        return cart

    @staticmethod
    def update(item_id, quantity=None, configuration=None, user=None, cart_key=None):
        cart, item = StorefrontService._own_item(item_id, user, cart_key)
        if configuration is not None:
            item = CartItemService.reconfigure_item(item, configuration)
        if quantity is not None:
            if quantity < 1 or quantity > 20:
                raise ValidationError("La quantité doit être comprise entre 1 et 20.")
            # the line was just checked as belonging to this cart : one update is enough
            CartItem.objects.filter(pk=item.pk).update(quantity=quantity)
        return cart

    @staticmethod
    def checkout(idempotency_key, customer: CustomerDTO, user=None, cart_key=None):
        logged_in = user is not None and user.is_authenticated
        if not logged_in and not cart_key:
            raise ValidationError("Votre panier est vide.")
        return CheckoutService.checkout(
            idempotency_key,
            customer,
            user=user if logged_in else None,
            session_key=None if logged_in else cart_key,
        )

    @staticmethod
    def _own_item(item_id, user, cart_key):
        """The visitor cart and one of its lines, refused when the line belongs to another cart."""
        cart = StorefrontService.find_cart(user=user, cart_key=cart_key)
        item = cart.cart_items.select_related("product").filter(pk=item_id).first() if cart else None
        if item is None:
            raise ValidationError("Cet article n'est pas dans votre panier.")
        return cart, item

    @staticmethod
    def find_order(order_uuid):
        # the uuid is only known by the customer (returned at checkout) : it is enough to show the confirmation
        lines = Prefetch("order_items", queryset=OrderItem.objects.order_by("pk"))
        return Order.objects.prefetch_related(lines).filter(uuid=order_uuid).first()

    @staticmethod
    def serialize_order(order):
        return {
            "id": str(order.uuid),
            "reference": str(order.uuid)[:8].upper(),
            "status": order.status,
            "createdAt": order.created_at.isoformat(),
            "email": order.email,
            "firstName": order.first_name,
            "lastName": order.last_name,
            "address": order.address,
            "postalCode": order.postal_code,
            "city": order.city,
            "country": order.country,
            "total": float(order.total_price or 0),
            "items": [
                {
                    "name": item.product_name,
                    "quantity": item.quantity,
                    "unitPrice": float(item.unit_price),
                    "total": float(item.unit_price * item.quantity),
                    "details": StorefrontService._details((item.config_snapshot or {}).get("options")),
                }
                for item in order.order_items.all()  # prefetched in order (see find_order)
            ],
        }

    @staticmethod
    def serialize(cart, cart_key=None):
        if cart is None:
            return {"cartKey": cart_key, "count": 0, "total": 0, "items": []}
        items = []
        total = 0
        for item in cart.cart_items.select_related("product").order_by("created_at", "uuid"):
            snapshot = item.config_snapshot or {}
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
                    "details": StorefrontService._details(snapshot.get("options")),
                    # configuration as sent by the configurator, to open the line again
                    "configurable": bool(item.product and item.product.product_schema_id),
                    "configuration": snapshot.get("configuration") or None,
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
