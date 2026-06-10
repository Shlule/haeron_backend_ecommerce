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

        user_choice = (
            ProductComponentChoice.objects.filter(component=component, product_id=product_id)
            .select_related("product")
            .first()
        )
        if not user_choice:
            raise ValidationError(f"Product {product_id} not allowed for component {component.key}")

        chosen_product = user_choice.product

        return {
            "type": "product_choice",
            "component": component.key,
            "product_id": str(chosen_product.uuid),
            "name": chosen_product.name,
            "price": float(chosen_product.price),
        }

    def bulk_build_configuration(self, components, product):
        choices = ProductComponentChoice.objects.filter(component__in=components).select_related("product", "component")

        choices_by_component = {}
        for choice in choices:
            choices_by_component.setdefault(choice.component_id, []).append(choice.product)

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
                        for p in choices_by_component.get(comp.id, [])
                    ],
                }
            )

        return result

    def build_configuration_component(self, component, product):

        choices = ProductComponentChoice.objects.filter(component=component).select_related("product")
        return ProductChoiceComponent(key=component.key, choices=[c.product for c in choices])
