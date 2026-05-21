from haeron_guitar_api.product_component.product_component_registry import ComponentHandlerRegistry
from ..types.product_configurator_types import ProductConfiguration
from ..models import Product

# THis is the the fonction that serve the forms of configuration to the fron end.
# after we call


def build_product_configuration(product):
    product = (
        Product.objects.select_related("product_schema")
        .prefetch_related("product_schema__product_components")
        .get(pk=product.pk)
    )

    components = list(product.product_schema.product_components.all())

    components_by_type = {}
    for c in components:
        components_by_type.setdefault(c.source_type, []).append(c)

    handlers = {source_type: ComponentHandlerRegistry.get_handler(source_type) for source_type in components_by_type}

    result_components = []

    for source_type, comps in components_by_type.items():
        handler = handlers[source_type]

        if hasattr(handler, "bulk_build_configuration"):
            result_components.extend(handler.bulk_build_configuration(comps, product))
        else:
            for c in comps:
                result_components.append(handler.build_configuration_component(c, product))

    return ProductConfiguration(product=product, components=result_components)
