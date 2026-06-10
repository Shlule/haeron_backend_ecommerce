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

            snapshot.append(result)
            print("@" * 50)
            print(type(product.price))
            print(type(result.get("price")))
            print(result.get("price"))
            total_price += result.get("price", 0)
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
