# from django.forms import ValidationError


# class BundleConfigHandler:
#     def resolve(self, product_type, config):

#         components = product_type.product_components.all()
#         self.validate_structure(components, config)
#         for component in components:

#         snapshot = self.build_snapshot(components, config)
#         price = self.calculate_price(snapshot)

#         return snapshot, price

#     def validate_structure(self, components, config):
#         keys = set(config.keys())

#         expected = {component.key for component in components}

#         missing = expected - keys
#         unknown = keys - expected

#         if missing:
#             raise ValidationError(f"Missing: {missing}")

#         if unknown:
#             raise ValidationError(f"Unknown: {unknown}")

#     def resolve_component(self, component, data):

#         if component.source_type == "custom_piece":
#             return self.resolve_custom_piece(data)

#         if component.source_type == "product_choice":
#             return self.resolve_product_choice(component, data)

#         if component.source_type == "fixed":
#             return {"value": component.value}

#     def calculate_price(self):
#         total = base_product_price

#         for component in snapshot:
#             total += component["price_delta"]
from jsonschema import ValidationError
from ..product_type_registry import ProductTypeHandlerRegistry
from ...product_component.product_component_registry import ComponentHandlerRegistry


@ProductTypeHandlerRegistry.register("bundle_dynamique")
class BundleConfigHandler:
    def resolve(self, product, config):
        components = product.product_schema.compoments.all()

        self.validate_structure(components, config)
        snapshot = []
        total_price = product.price

        for component in components:
            data = config.get(component.key)
            handler = ComponentHandlerRegistry.get(component.source_type)

            if not handler:
                raise ValueError(f"No handler for {component.source_type}")
            result = handler.resolve(component, data, product)

            snapshot.append(result)
            total_price += result.get("price", 0)
        return snapshot, total_price

    def validate_structure(self, components, config):
        keys = set(config.keys())
        expected = {component.key for component in components if getattr(component, "required", True)}

        missing = expected - keys
        unknown = keys = {component.key for component in components}

        if missing:
            raise ValidationError(f"Missing fields: {missing}")

        if unknown:
            raise ValidationError(f"Unknow fields: {unknown}")
