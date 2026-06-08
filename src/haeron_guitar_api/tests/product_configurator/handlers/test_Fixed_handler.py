import pytest

from haeron_guitar_api.product_configurator.product_component_handlers.handlers.fixed_handlers import FixedHandler


@pytest.mark.django_db
def test_fixed_handler(fixed_component):
    handler = FixedHandler()

    result = handler.resolve(fixed_component, data=None)

    assert result["type"] == "fixed"
    assert result["component"] == fixed_component.key
