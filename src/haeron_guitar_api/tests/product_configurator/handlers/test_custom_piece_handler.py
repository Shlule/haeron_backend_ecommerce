from decimal import Decimal
from django.forms import ValidationError
import pytest

from haeron_guitar_api.product_component.handlers.custom_piece_handler import CustomPieceHandler
from haeron_guitar_api.models import ComponentCompatibility, PartModelOption, Option


@pytest.fixture
def part_model_with_options(part_model):
    option_color = Option.objects.create(name="color")
    option_material = Option.objects.create(name="material")

    opt1 = PartModelOption.objects.create(
        name="bleu", code="bleu", part_model=part_model, option=option_color, price_delta=Decimal("12.00")
    )

    opt2 = PartModelOption.objects.create(
        name="mapple", code="mapple", part_model=part_model, option=option_material, price_delta=Decimal("15.50")
    )

    return {"color": opt1, "material": opt2, "option_color": option_color, "option_material": option_material}


@pytest.mark.django_db
def test_custompiece_valid(product, custom_component, part_model):
    ComponentCompatibility.objects.create(
        instrument_model=product.instrument_model, component=custom_component, part_model=part_model
    )
    handler = CustomPieceHandler()
    configuration = {"part_model_id": str(part_model.uuid)}
    result = handler.resolve(custom_component, configuration, product=product)
    assert result["price"] == float(part_model.price)


@pytest.mark.django_db
def test_custompiece_valid_with_options(product, custom_component, part_model, part_model_with_options):
    ComponentCompatibility.objects.create(
        instrument_model=product.instrument_model, component=custom_component, part_model=part_model
    )
    handler = CustomPieceHandler()
    options = part_model_with_options
    selected_option_color = options["color"]
    selected_option_materiaux = options["material"]
    # putting in str fait json validation
    configuration = {
        "part_model_id": str(part_model.uuid),
        "part_model_option_ids": [str(selected_option_color.uuid), str(selected_option_materiaux.uuid)],
    }
    result = handler.resolve(custom_component, configuration, product=product)

    assert {o["id"] for o in result["options"]} == {
        str(selected_option_color.uuid),
        str(selected_option_materiaux.uuid),
    }

    assert result["price"] == float(
        part_model.price + selected_option_color.price_delta + selected_option_materiaux.price_delta
    )


@pytest.mark.django_db
def test_custom_piece_invalid_options(product, custom_component, part_model, part_model_with_options):
    ComponentCompatibility.objects.create(
        instrument_model=product.instrument_model, component=custom_component, part_model=part_model
    )
    handler = CustomPieceHandler()
    # putting in str fait json validation
    options = part_model_with_options
    selected_option_color = options["color"]
    option_color = options["option_color"]
    selected_option_color_deux = PartModelOption.objects.create(
        name="red", code="red", part_model=part_model, option=option_color, price_delta=Decimal("15.50")
    )
    configuration = {
        "part_model_id": str(part_model.uuid),
        "part_model_option_ids": [str(selected_option_color.uuid), str(selected_option_color_deux.uuid)],
    }

    with pytest.raises(ValidationError):
        handler.resolve(custom_component, configuration, product=product)


@pytest.mark.django_db
def test_custom_piece_invalid(product, custom_component, part_model):

    handler = CustomPieceHandler()

    with pytest.raises(ValidationError):
        handler.resolve(custom_component, {"part_model_id": str(part_model.uuid)}, product=product)
