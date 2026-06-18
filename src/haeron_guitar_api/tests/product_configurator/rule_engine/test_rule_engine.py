from pprint import pprint
import pytest
from django.test import TestCase

from haeron_guitar_api.models import (
    ConfigurationRule,
    ComponentCompatibility,
    ProductComponent,
    SelectableValue,
    ConfigurationCondition,
    ConfigurationResult,
    Option,
    PartModelOption,
)
from haeron_guitar_api.product_configurator.configuration_rule_engine import Product, RuleEngine

# from django_assert_num_queries import assert_num_queries
from decimal import Decimal

rule_engine = RuleEngine()


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
    opt3 = PartModelOption.objects.create(
        name="ebene", code="ebene", part_model=part_model, option=option_material, price_delta=Decimal("25.30")
    )

    return {"color": opt1, "material": opt2, "option_color": option_color, "option_material": option_material}


@pytest.fixture
def selectable_value(part_model_with_options):
    color = part_model_with_options["color"]
    material = part_model_with_options["material"]

    color_selectable = SelectableValue.objects.create(part_model_option=color)
    material_selectable = SelectableValue.objects.create(part_model_option=material)

    return {"color_selectable": color_selectable, "material_selectable": material_selectable}


@pytest.fixture
def collect_rule_setup(
    db,
    instrument_model,
    part_model,
    product_type,
    selectable_value,
    product_schema,
    product_component,
    part_model_with_options,
):
    print("!" * 50)
    pprint(product_component)
    product_component.product_schemas.add(product_schema)
    compat1 = ComponentCompatibility.objects.create(
        part_model=part_model, instrument_model=instrument_model, component=product_component
    )

    option_setup = part_model_with_options
    part_model_option_color = part_model_with_options["color"]
    part_model_option_material = part_model_with_options["material"]
    option_color = part_model_with_options["option_color"]
    option_material = part_model_with_options["option_material"]

    color_selectable = selectable_value["color_selectable"]
    material_selectable = selectable_value["material_selectable"]

    component_rule = ConfigurationRule.objects.create(target_component=product_component)
    schema_rule = ConfigurationRule.objects.create(target_schema=product_schema)
    part_model_rule = ConfigurationRule.objects.create(target_part_model=part_model)

    schema_rule_condition = ConfigurationCondition.objects.create(
        rule=component_rule,
        source_component=product_component,
        source_option=option_color,
        # source_values=part_model_option_color,
        operator="eq",
        # compare_values=part_model_option_color,
    )
    schema_rule_condition.compare_values.add(color_selectable)

    # component_rule_condition_un = ConfigurationCondition.objects.create(
    #     rule=component_rule,
    #     source_component=product_component,
    #     # source_values=part_model_option_material,
    #     operator="eq",
    #     # compare_values=part_model_option_material,
    # )

    component_rule_result_un = ConfigurationResult.objects.create(
        rule=component_rule,
        target_component=product_component,
        target_option=option_material,
        # target_values=part_model_option_color,
        # action="allow",
        # values=["vert", "jaune"],
    )
    component_rule_result_un.target_values.add(material_selectable)

    product = Product.objects.create(
        name="startLight_custom",
        price=0,
        product_type=product_type,
        product_schema=product_schema,
        instrument_model=instrument_model,
    )

    return {
        "product": product,
        "compat1": compat1,
        "component_rule": component_rule,
        "schema_rule": schema_rule,
        "part_model_rule": part_model_rule,
    }


@pytest.mark.django_db
def test_collect_rules_and_serialize_integration(collect_rule_setup, django_assert_num_queries):
    product = collect_rule_setup["product"]

    engine = RuleEngine()

    with django_assert_num_queries(7):  # ajuste selon ton optimisation
        snapshot = engine.collect_rules(product)

    rules = snapshot["rules"]

    assert len(rules) > 0

    serialized = [engine.serialize_rule(rule) for rule in rules]

    print("+" * 50)
    pprint(serialized)

    assert isinstance(serialized, list)
    assert getattr(serialized[0], "conditions")
    assert getattr(serialized[0], "results")

    # --- conditions existent
    assert len(serialized[0].conditions) > 0

    # --- results existent
    assert len(serialized[0].results) > 0


# @pytest.mark.django_db
# def test_collect_rules_includes_schema_rules(collect_rule_setup, django_assert_num_queries):
#     with django_assert_num_queries(999):
#         product = collect_rule_setup["product"]
#         component = product.product_schema.product_components.first()

#         component_rule = collect_rule_setup["component_rule"]
#         schema_rule = collect_rule_setup["schema_rule"]
#         part_model_rule = collect_rule_setup["part_model_rule"]
#         rule = [component_rule, schema_rule, part_model_rule]

#         rules = rule_engine.collect_rules(product)

# assert set(rule) == set(rules)


# @pytest.mark.django_db
# def test_serialize_rules(collect_rule_setup, django_assert_num_queries):
#     with django_assert_num_queries(999):
#         component_rule = collect_rule_setup["component_rule"]
#         print(rule_engine.serialize_rules(component_rule))
