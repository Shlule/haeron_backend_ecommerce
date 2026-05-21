import pytest
from django.core.exceptions import ValidationError

from haeron_guitar_api.product_component.handlers.product_choice_handler import ProducChoiceHandler
from haeron_guitar_api.models import ProductComponentChoice


@pytest.mark.django_db
def test_product_choice_valid(product, choice_component):
    chosen = product.__class__.objects.create(
        name="Pickup A",
        price=50,
        product_type=product.product_type,
        product_schema=product.product_schema,
    )

    ProductComponentChoice.objects.create(component=choice_component, product=chosen)

    handler = ProducChoiceHandler()
    result = handler.resolve(choice_component, {"product_id": str(chosen.uuid)})

    assert result["product_id"] == str(chosen.uuid)
    assert result["price"] == float(chosen.price)


@pytest.mark.django_db
def test_product_choice_invalid(choice_component):
    handler = ProducChoiceHandler()

    with pytest.raises(ValidationError):
        handler.resolve(choice_component, {"product_id": "abcd"})
