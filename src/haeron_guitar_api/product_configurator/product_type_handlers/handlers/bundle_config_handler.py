from decimal import Decimal
from pprint import pprint
from jsonschema import ValidationError
from ..product_type_registry import ProductTypeHandlerRegistry
from ...product_component_handlers.product_component_registry import ComponentHandlerRegistry


@ProductTypeHandlerRegistry.register("bundle_dynamique")
class BundleConfigHandler:
    def resolve(self, product, config):
        components = product.product_schema.product_components.all()

        self.validate_structure(components, config)
        snapshot = []
        total_price = product.price

        for component in components:
            data = config.get(component.key)
            handler = ComponentHandlerRegistry.get_handler(component.source_type)

            if not handler:
                raise ValueError(f"No handler for {component.source_type}")
            result = handler.resolve(component, data, product)
            print("&" * 50)
            pprint(result)
            total_price += Decimal(result.get("price", 0))

            snapshot.append(result)
        return snapshot, total_price

    def validate_structure(self, components, config):
        # TODO - corriger cet partie
        keys = set(config.keys())
        expected = {component.key for component in components if getattr(component, "required", True)}

        missing = expected - keys
        unknown = keys - {component.key for component in components}

        if missing:
            raise ValidationError(f"Missing fields: {missing}")

        if unknown:
            raise ValidationError(f"Unknow fields: {unknown}")
