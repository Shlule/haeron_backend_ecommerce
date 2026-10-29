import pytest
from django.contrib.auth import get_user_model

from haeron_guitar_api.models import (
    ComponentCompatibility,
    ConfigurationCondition,
    ConfigurationResult,
    ConfigurationRule,
    InstrumentModel,
    InstrumentType,
    Option,
    PartModel,
    PartModelOption,
    PartType,
    Product,
    ProductComponent,
    ProductComponentChoice,
    ProductSchema,
    ProductType,
    SelectableValue,
)
from haeron_guitar_api.cartItem.cartItem_dto import createCartItemDTO
from haeron_guitar_api.cartItem.cartItem_service import CartItemService
from haeron_guitar_api.product_configurator.configuration_normalizer import ConfigurationNormalizer
from haeron_guitar_api.product_configurator.configurator_resolver import (
    build_configurator_template,
    validate_configuration,
)


@pytest.fixture
def starlight(db):
    """body (custom_piece with color + material) and mic (product_choice)
    rule : if body.material == alu then body.color must be blue"""
    bundle = ProductType.objects.create(code="bundle_dynamique")
    simple = ProductType.objects.create(code="simple")
    instrument_model = InstrumentModel.objects.create(
        name="starlight", instrument_type=InstrumentType.objects.create(name="guitar", code="G")
    )
    schema = ProductSchema.objects.create(name="starlight", code="starlight")
    product = Product.objects.create(
        name="Starlight", price=100, product_type=bundle, product_schema=schema, instrument_model=instrument_model
    )

    color = Option.objects.create(name="color")
    material = Option.objects.create(name="material")
    part_model = PartModel.objects.create(
        name="body", code="BD", price=100, part_type=PartType.objects.create(name="body", code="BDY")
    )
    blue = PartModelOption.objects.create(name="blue", code="blue", part_model=part_model, option=color, price_delta=10)
    red = PartModelOption.objects.create(name="red", code="red", part_model=part_model, option=color, price_delta=10)
    alu = PartModelOption.objects.create(name="alu", code="alu", part_model=part_model, option=material, price_delta=50)
    wood = PartModelOption.objects.create(name="wood", code="wood", part_model=part_model, option=material)

    body = ProductComponent.objects.create(key="body", source_type="custom_piece")
    body.product_schemas.add(schema)
    ComponentCompatibility.objects.create(instrument_model=instrument_model, part_model=part_model, component=body)

    mic = ProductComponent.objects.create(key="mic", source_type="product_choice")
    mic.product_schemas.add(schema)
    mic_product = Product.objects.create(name="mic A", price=30, product_type=simple)
    ProductComponentChoice.objects.create(component=mic, product=mic_product)

    rule = ConfigurationRule.objects.create(name="alu -> blue", target_component=body)
    condition = ConfigurationCondition.objects.create(rule=rule, source_component=body, source_option=material, operator="eq")
    condition.compare_values.add(SelectableValue.objects.create(part_model_option=alu))
    result = ConfigurationResult.objects.create(rule=rule, target_component=body, target_option=color)
    result.target_values.add(SelectableValue.objects.create(part_model_option=blue))

    def configuration(*options):
        return {
            "body": {"part_model_id": str(part_model.uuid), "part_model_option_ids": [str(o.uuid) for o in options]},
            "mic": {"product_id": str(mic_product.uuid)},
        }

    return {
        "product": product,
        "blue": blue,
        "red": red,
        "alu": alu,
        "wood": wood,
        "configuration": configuration,
        "user": get_user_model().objects.create_user(username="buyer"),
    }


def test_normalizer_flatten_options_and_products():
    snapshot = [
        {"type": "custom_piece", "component": "body", "options": [{"id": "x", "name": "color", "value": "red"}]},
        {"type": "product_choice", "component": "mic", "product_id": "p1"},
    ]
    assert ConfigurationNormalizer.normalize(snapshot) == {"body.color": "x", "mic": "p1"}


def test_validate_configuration_respecting_rule(starlight):
    s = starlight
    result = validate_configuration(s["product"], s["configuration"](s["alu"], s["blue"]))
    assert result["valid"] is True
    assert result["errors"] == []
    # 100 product + 100 body + 50 alu + 10 blue + 30 mic
    assert result["total_price"] == 290


def test_validate_configuration_rule_not_triggered(starlight):
    s = starlight
    assert validate_configuration(s["product"], s["configuration"](s["wood"], s["red"]))["valid"] is True


def test_validate_configuration_violating_rule(starlight):
    s = starlight
    result = validate_configuration(s["product"], s["configuration"](s["alu"], s["red"]))
    assert result["valid"] is False
    assert result["violations"][0]["component"] == "body.color"


def test_validate_configuration_missing_component(starlight):
    s = starlight
    configuration = s["configuration"](s["wood"])
    del configuration["mic"]
    result = validate_configuration(s["product"], configuration)
    assert result["valid"] is False
    assert result["errors"]


def test_cart_refuses_configuration_violating_rule(starlight):
    s = starlight
    dto = createCartItemDTO(product_id=s["product"].uuid, configuration=s["configuration"](s["alu"], s["red"]))
    with pytest.raises(Exception):
        CartItemService.add_item(dto, user=s["user"])


def test_inactive_value_hidden_from_template(starlight):
    s = starlight
    s["wood"].is_active = False
    s["wood"].save()
    template = build_configurator_template(s["product"])
    body = next(c for c in template["components"] if c["key"] == "body")
    values = [o["value"] for o in body["part_models"][0]["options"]]
    assert "wood" not in values
    assert "alu" in values


def test_inactive_value_refused(starlight):
    s = starlight
    s["wood"].is_active = False
    s["wood"].save()
    result = validate_configuration(s["product"], s["configuration"](s["wood"], s["red"]))
    assert result["valid"] is False
    assert result["errors"]


def test_template_contains_components_and_rules(starlight):
    template = build_configurator_template(starlight["product"])
    keys = {c["key"] for c in template["components"]}
    assert keys == {"body", "mic"}
    assert template["rules"][0]["conditions"][0] == {
        "component": "body",
        "option": "material",
        "operator": "eq",
        "values": [{"type": "option", "id": str(starlight["alu"].uuid), "code": "alu", "label": "alu"}],
    }


@pytest.fixture
def starlight_product(db):
    from haeron_guitar_api.setup_preconfig.starlight_product import handle_starlight_product

    InstrumentModel.objects.create(
        name="guitar_starlight", instrument_type=InstrumentType.objects.create(name="electric guitar", code="EG")
    )
    for code in ["BSSTR", "BSALP", "BISTR", "BIALP", "NORG", "NALP", "FBORG", "FBALP", "MCORG", "MCALP"]:
        PartModel.objects.create(name=code, code=code, part_type=PartType.objects.create(name=code, code=code))

    handle_starlight_product()
    handle_starlight_product()  # can be run twice
    return Product.objects.get(name="Starlight")


def _starlight_configuration(product, body):
    template = build_configurator_template(product)
    piece_options = {"fingerboard": {"radius": "radius_10"}, "mic_plate": {"post_treatment": "raw"}}
    configuration = {}
    for component in template["components"]:
        part_model = component["part_models"][0]
        wanted = body if component["key"].startswith("body") else piece_options.get(component["key"], {})
        configuration[component["key"]] = {
            "part_model_id": part_model["id"],
            "part_model_option_ids": [o["id"] for o in part_model["options"] if wanted.get(o["name"]) == o["value"]],
        }
    return configuration


@pytest.mark.parametrize(
    "body, valid",
    [
        ({"material": "wood", "finish": "painted", "color": "color_green"}, True),
        ({"material": "aluminium", "finish": "painted", "color": "color_red"}, True),
        ({"material": "wood", "finish": "raw", "wood_essence": "walnut"}, True),
        ({"material": "aluminium", "finish": "raw", "post_treatment": "anodised"}, True),
        ({"material": "wood", "finish": "raw", "color": "color_red"}, False),
        ({"material": "aluminium", "finish": "raw", "wood_essence": "pine"}, False),
        ({"material": "wood", "finish": "raw", "post_treatment": "chrome"}, False),
        ({"material": "aluminium", "finish": "painted", "color": "color_red", "post_treatment": "chrome"}, False),
    ],
)
def test_starlight_product_rules(starlight_product, body, valid):
    result = validate_configuration(starlight_product, _starlight_configuration(starlight_product, body))
    assert result["errors"] == []
    assert result["valid"] is valid
    assert ConfigurationRule.objects.count() == 10  # 5 rules on each Alpha body
