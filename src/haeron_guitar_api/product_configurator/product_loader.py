from django.db.models import Prefetch

from ..models import Product, ProductComponent, ProductComponentChoice


def products_with_schema():
    """Products with everything the configurator reads : type, schema, components, their fixed product,
    compatibilities and allowed choices. About 6 queries whatever the size of the schema,
    instead of a few queries per component."""
    components = ProductComponent.objects.select_related("fixed_product").prefetch_related(
        "component_compatibilities",
        Prefetch("product_component_choices", queryset=ProductComponentChoice.objects.select_related("product")),
    )
    return Product.objects.select_related("product_type", "product_schema", "instrument_model").prefetch_related(
        Prefetch("product_schema__product_components", queryset=components)
    )


def load_product(product_id):
    return products_with_schema().get(pk=product_id)


def is_loaded(product):
    """True when the components of the product were read with products_with_schema()."""
    schema = product.product_schema if product.product_schema_id else None
    return schema is None or "product_components" in getattr(schema, "_prefetched_objects_cache", {})
