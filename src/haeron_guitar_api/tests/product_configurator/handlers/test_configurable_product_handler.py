from decimal import Decimal
from pprint import pprint
import pytest
from haeron_guitar_api.models import InstrumentModel
from haeron_guitar_api.product_configurator.product_type_handlers.product_type_registry import (
    ProductTypeHandlerRegistry,
)
from haeron_guitar_api.product_configurator.product_component_handlers.product_component_registry import (
    ComponentHandlerRegistry,
)
from haeron_guitar_api.models import ProductComponent, Product, ProductComponentChoice
from haeron_guitar_api.product_type import handlers
from uuid import uuid4
from django.forms import ValidationError
from jsonschema import ValidationError as jsonValidationError

# @pytest.fixture
# def guitar_full_setup(instrument_type, part_model_factory, part_type):
#     neck = part_model_factory(name="neck A", code="NCKA", part_type=part_type, price=Decimal("150.00"))
#     body = part_model_factory(name="body B", code="BDYB", part_type=part_type, price=Decimal("120.00"))

#     instrument_model = InstrumentModel.objects.create(name="Strat", instrument_type=instrument_type)

#     return {
#         "instrument": instrument_model,
#         "parts": [neck, body],
#     }


class FakeHandler:
    def resolve(self, product, config):
        return {"ok": True}, 123.45


@pytest.mark.django_db
def test_guitar_scenario(product, custom_component, fixed_component, choice_component):

    handler = ComponentHandlerRegistry.get_handler("product_configurable")
    product = (
        Product.objects.select_related("product_schema")
        .prefetch_related("product_schema__product_components")
        .get(pk=product.uuid)
    )
    for component in product.product_schema.product_components.all():
        print(component.key)

    print(handler)


@pytest.mark.django_db
def test_product_configurable_success(
    product,
    custom_component,
    monkeypatch,
):
    handler = ComponentHandlerRegistry.get_handler("product_configurable")

    ProductComponentChoice.objects.create(component=custom_component, product=product)
    monkeypatch.setattr(ProductTypeHandlerRegistry, "get_handler", lambda code: FakeHandler())

    config = {"product_id": str(product.uuid), "configuration": {}}

    result = handler.resolve(custom_component, config)

    assert result["type"] == "product_configurable"
    assert result["product_id"] == str(product.uuid)
    assert result["price"] == 123.45


@pytest.mark.django_db
def test_product_configurable_missing_config(product, custom_component):
    handler = ComponentHandlerRegistry.get_handler("product_configurable")

    with pytest.raises(jsonValidationError):
        handler.resolve(custom_component, {}, product=product)


@pytest.mark.django_db
def test_product_configurable_invalid_product(product, custom_component):
    handler = ComponentHandlerRegistry.get_handler("product_configurable")

    config = {"product_id": str(uuid4()), "configuration": {}}

    with pytest.raises(Product.DoesNotExist):
        handler.resolve(custom_component, config, product=product)
