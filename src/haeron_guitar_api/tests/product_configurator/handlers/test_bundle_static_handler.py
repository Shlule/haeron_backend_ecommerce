import pytest
from haeron_guitar_api.product_configurator.product_type_handlers.handlers.bundle_static_handler import (
    BundleStaticHandler,
)


@pytest.mark.django_db
def test_bundle_static_contains_fixed_component(product, fixed_component):
    handler = BundleStaticHandler()

    result, price = handler.resolve(product)

    assert len(result["items"]) == 1

    item = result["items"][0]
    assert item["component"] == fixed_component.key
    assert item["product_id"] == str(fixed_component.fixed_product.uuid)
