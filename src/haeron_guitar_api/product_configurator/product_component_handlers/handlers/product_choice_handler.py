from decimal import Decimal
from django.forms import ValidationError
from ....models import ProductComponentChoice
from ..product_component_registry import ComponentHandlerRegistry
from ....types.product_configurator_types import ProductChoiceComponent


@ComponentHandlerRegistry.register("product_choice")
class ProducChoiceHandler:
    def resolve(self, component, data, product=None, **kwargs):
        if not data or "product_id" not in data:
            raise ValidationError(f"{component.key}, requires product_id")

        product_id = data.get("product_id")

        # choices are loaded with the product (see product_loader) : no query here
        user_choice = next(
            (choice for choice in component.product_component_choices.all() if str(choice.product_id) == str(product_id)),
            None,
        )
        if not user_choice:
            raise ValidationError(f"Product {product_id} not allowed for component {component.key}")

        chosen_product = user_choice.product

        return {
            "type": "product_choice",
            "component": component.key,
            "product_id": str(chosen_product.uuid),
            "name": chosen_product.name,
            "price": str(chosen_product.price),
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
                    "type": "product_choice",
                    "choices": [
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
        return ProductChoiceComponent(key=component.key, choices=[c.product for c in choices])
