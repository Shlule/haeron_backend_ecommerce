import pytest
from decimal import Decimal

from django.core.exceptions import ValidationError

from haeron_guitar_api.models import Product
from haeron_guitar_api.product_type.handlers.simple_product_handler import SimpleProductHandler


@pytest.mark.django_db
def test_simple_product_handler(product_type, instrument_model):
    product = Product.objects.create(
        name="Cable Jack",
        price=Decimal("10.00"),
        product_type=product_type,
        instrument_model=instrument_model,
    )

    handler = SimpleProductHandler()

    snapshot, price = handler.resolve(product)

    assert snapshot["type"] == "simple"
    assert snapshot["product_id"] == str(product.uuid)
    assert price == 10.00


@pytest.mark.django_db
def test_simple_product_handler_without_instrument_model(product_type):
    product = Product.objects.create(
        name="Cable Jack",
        price=Decimal("10.00"),
        product_type=product_type,
    )

    handler = SimpleProductHandler()

    snapshot, price = handler.resolve(product)

    assert snapshot["type"] == "simple"
    assert snapshot["product_id"] == str(product.uuid)
    assert price == 10.00


@pytest.mark.django_db
def test_simple_product_with_config_should_fail(product):
    handler = SimpleProductHandler()

    with pytest.raises(ValidationError):
        handler.resolve(product, config={"foo": "bar"})
