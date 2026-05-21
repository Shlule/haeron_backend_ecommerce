import pytest
from decimal import Decimal
from django.apps import apps

from ..models import (
    Product,
    ProductComponent,
    ProductComponentChoice,
    ProductSchema,
    InstrumentType,
    PartType,
    InstrumentModel,
    PartModel,
    ComponentCompatibility,
    ProductType,
)


@pytest.fixture
def instrument_type(db):
    return InstrumentType.objects.create(name="Guitar", code="GTR")


@pytest.fixture
def part_type(db, instrument_type):
    part_type = PartType.objects.create(name="Pickup", code="PCK")
    part_type.instrument_types.add(instrument_type)
    return part_type


@pytest.fixture
def instrument_model(db, instrument_type):
    return InstrumentModel.objects.create(name="StartLight", instrument_type=instrument_type)


@pytest.fixture
def product(db, instrument_model, product_type, schema):
    return Product.objects.create(
        name="Custom Guitar",
        price=Decimal("100.00"),
        product_type=product_type,
        product_schema=schema,
        instrument_model=instrument_model,
    )


@pytest.fixture
def product_type(db):
    return ProductType.objects.create(code="custom_piece")


@pytest.fixture
def schema(db):
    return ProductSchema.objects.create(name="Guitar Schema", code="GTS")


@pytest.fixture
def custom_component(db, schema):
    return ProductComponent.objects.create(product_schema=schema, key="neck", source_type="custom_piece")


@pytest.fixture
def choice_component(db, schema):
    return ProductComponent.objects.create(product_schema=schema, key="pickup", source_type="product_choice")


@pytest.fixture
def fixed_component(db, schema, product):
    return ProductComponent.objects.create(
        product_schema=schema, key="case", source_type="fixed", fixed_product=product
    )


@pytest.fixture
def part_model(db, part_type):
    return PartModel.objects.create(
        name="Body sup StarLight", code="BSST", part_type=part_type, price=Decimal("150.00")
    )


@pytest.fixture
def compatibility(db, instrument_model, part_model, custom_component):
    return ComponentCompatibility.objects.create(
        instrument_model=instrument_model, component=custom_component, part_model=part_model
    )


@pytest.fixture
def part_model_factory(db):
    def create(**kwargs):
        if not kwargs:
            raise ValueError("no argument given")
        return PartModel.objects.create(**kwargs)

    return create
