from jsonschema import ValidationError
from ..product_component_registry import ComponentHandlerRegistry
from ....types.product_configurator_types import FixedComponent


@ComponentHandlerRegistry.register("fixed")
class FixedHandler:
    def resolve(self, component, data=None, **kwargs):

        if not component.fixed_product:
            raise ValidationError(f"Fixed component {component.key} has no fixed_product")

        product = component.fixed_product

        return {
            "type": "fixed",
            "component": component.key,
            "product_id": str(product.uuid),
            "name": product.name,
            "price": float(product.price),
        }

    def bulk_build_configuration(self, components, product):
        return [
            {
                "key": comp.key,
                "type": "fixed",
                "product": {
                    "id": str(comp.fixed_product.uuid),
                    "name": comp.fixed_product.name,
                    "price": float(comp.fixed_product.price),
                },
            }
            for comp in components
        ]

    def build_configuration_component(self, component, product):

        fixed = component.fixed_product
        return FixedComponent(key=component.key, product_id=str(fixed.uuid), name=fixed.name, price=float(fixed.price))
