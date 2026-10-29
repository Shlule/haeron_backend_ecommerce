from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from haeron_guitar_api.models import Option, PartModel, PartModelOption, PartType
from haeron_guitar_api.partModel_option.part_model_option_dto import (
    CreatePartModelOptionDTO,
    UpdatePartModelOptionActiveDTO,
)
from haeron_guitar_api.partModel_option.part_model_option_service import PartModelOptionService


@pytest.fixture
def body(db):
    part_model = PartModel.objects.create(
        name="body", code="BD", price=100, part_type=PartType.objects.create(name="body", code="BDY")
    )
    return part_model, Option.objects.create(name="color")


def test_create_several_values_for_one_option(body):
    part_model, color = body
    red = PartModelOptionService.create(
        CreatePartModelOptionDTO(name="", code="color_red", part_model=part_model.uuid, option=color.uuid)
    )
    blue = PartModelOptionService.create(
        CreatePartModelOptionDTO(
            name="color_blue", code="color_blue", part_model=part_model.uuid, option=color.uuid, price_delta=Decimal("20")
        )
    )
    assert (red.name, red.code, red.price_delta, red.is_active) == ("color_red", "color_red", 0, True)
    assert blue.price_delta == 20
    assert PartModelOption.objects.filter(part_model=part_model, option=color).count() == 2


def test_create_refuses_same_value_twice(body):
    part_model, color = body
    dto = CreatePartModelOptionDTO(name="", code="color_red", part_model=part_model.uuid, option=color.uuid)
    PartModelOptionService.create(dto)
    with pytest.raises(ValidationError):
        PartModelOptionService.create(dto)


def test_set_active(body):
    part_model, color = body
    red = PartModelOption.objects.create(name="red", code="red", part_model=part_model, option=color)
    PartModelOptionService.set_active(UpdatePartModelOptionActiveDTO(uuid=red.uuid, is_active=False))
    red.refresh_from_db()
    assert red.is_active is False
