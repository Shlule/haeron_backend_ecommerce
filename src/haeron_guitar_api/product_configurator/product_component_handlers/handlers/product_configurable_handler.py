from django.forms import ValidationError
from ....models import Product, ProductComponentChoice

from ..product_component_registry import ComponentHandlerRegistry
from ...product_type_handlers.product_type_registry import ProductTypeHandlerRegistry
from ..handlers.base_component_handler import BaseComponentHandler
from ...product_loader import load_product
from ....types.product_configurator_types import ProductConfigurableComponent


@ComponentHandlerRegistry.register("product_configurable")
class ProductConfigurableHandler(BaseComponentHandler):
    CONFIG_SCHEMA = {
        "type": "object",
        "required": ["product_id"],
        "properties": {
            "product_id": {"type": "string", "format": "uuid"},
            "configuration": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def _validate_business(self, component, config, product=None, **kwargs):
        product_id = config.get("product_id")

        if not product_id:
            raise ValidationError("product_id is required")

        try:
            # loaded with its own schema : the nested configuration is resolved without extra queries
            nested_product = load_product(product_id)
        except Product.DoesNotExist:
            raise Product.DoesNotExist("Product does not exist")

        if not any(choice.product_id == nested_product.pk for choice in component.product_component_choices.all()):
            raise ValidationError(f"Product {product_id} not allowed for component {component.key}")

        handler = ProductTypeHandlerRegistry.get_handler(nested_product.product_type.code)

        if not handler:
            raise ValidationError("No handler for this product type")

        return {"nested_product": nested_product, "handler": handler, "nested_config": config.get("configuration", {})}

    def _resolve(self, component, config, product=None, validated=None, **kwargs):
        validated = validated or self._validate_business(component, config, product)
        nested_product = validated["nested_product"]
        config = config.get("configuration", {})
        handler = validated["handler"]

        snapshot, price = handler.resolve(nested_product, config)

        return {
            "type": "product_configurable",
            "component": component.key,
            "product_id": str(nested_product.uuid),
            "snapshot": snapshot,
            "price": price,
        }

    def bulk_build_configuration(self, components, product):
        choices_by_component = {
            comp.uuid: [choice.product for choice in comp.product_component_choices.all()] for comp in components
        }

        result = []

        for comp in components:
            result.append(
                {
                    "key": comp.key,
                    "type": "product_configurable",
                    "products": [
                        {
                            "id": str(p.uuid),
                            "name": p.name,
                            "price": float(p.price),
                        }
                        for p in choices_by_component.get(comp.uuid, [])
                    ],
                }
            )

        return result

    def build_configuration_component(self, component, product):

        choices = ProductComponentChoice.objects.filter(component=component).select_related("product")
        return ProductConfigurableComponent(key=component.key, products=[c.product for c in choices])


# JSON attendu côté front
# {
#   "guitar": {
#     "product_id": "uuid",
#     "configuration": {
#       "body": { "part_model_id": "uuid" },
#       "neck": { "part_model_id": "uuid" }
#     }
#   },
#   "case": { "product_id": "uuid" }
# }
