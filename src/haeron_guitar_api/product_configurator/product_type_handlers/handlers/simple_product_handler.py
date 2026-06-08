from decimal import Decimal
from django.core.exceptions import ValidationError

from ..product_type_registry import ProductTypeHandlerRegistry


@ProductTypeHandlerRegistry.register("simple")
class SimpleProductHandler:
    """Simple product just a snapshot"""

    def resolve(self, product, config=None, **kwargs):

        if config:
            raise ValidationError("Simple product does not accept configuration")

        return {
            "type": "simple",
            "product_id": str(product.uuid),
            "name": product.name,
            "price": float(product.price),
        }, float(product.price)
