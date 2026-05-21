import pytest
from haeron_guitar_api.product_component.product_component_registry import ComponentHandlerRegistry
from haeron_guitar_api.product_configurator.builder import build_product_configuration
from haeron_guitar_api.models import Option, ComponentCompatibility, PartModelOption


@pytest.mark.django_db
def test_build_product_configuration_basic(product, custom_component, monkeypatch):
    class FakeHandler:
        def build_configuration_component(self, component, product):
            return {
                "key": component.key,
                "type": component.source_type,
            }

    monkeypatch.setattr(ComponentHandlerRegistry, "get_handler", lambda source_type: FakeHandler())

    result = build_product_configuration(product)
    print("#" * 50)
    print(result)

    assert result.product == product
    assert len(result.components) == 1
    assert result.components[0]["key"] == custom_component.key
    assert result.components[0]["type"] == custom_component.source_type


@pytest.mark.django_db
def test_build_product_configuration_multiple_components(
    product,
    custom_component,
    choice_component,
    fixed_component,
    monkeypatch,
):
    class FakeHandler:
        def build_configuration_component(self, component, product):
            return {"key": component.key}

    monkeypatch.setattr(ComponentHandlerRegistry, "get_handler", lambda source_type: FakeHandler())

    result = build_product_configuration(product)
    print("@" * 50)
    print(result)

    assert len(result.components) == 3

    keys = {c["key"] for c in result.components}
    assert keys == {"neck", "pickup", "case"}


@pytest.mark.django_db
def test_build_configuration_with_custom_piece_real(
    product,
    custom_component,
    instrument_model,
    part_model,
):
    ComponentCompatibility.objects.create(
        instrument_model=instrument_model,
        component=custom_component,
        part_model=part_model,
    )

    option_color = Option.objects.create(name="color")
    option_mat = Option.objects.create(name="mat")
    opt_color_val1 = PartModelOption.objects.create(
        name="blue",
        code="blue",
        part_model=part_model,
        option=option_color,
        price_delta=10,
    )
    opt_color_val2 = PartModelOption.objects.create(
        name="red",
        code="red",
        part_model=part_model,
        option=option_color,
        price_delta=15,
    )
    opt_color_val3 = PartModelOption.objects.create(
        name="green",
        code="green",
        part_model=part_model,
        option=option_color,
        price_delta=20,
    )

    result = build_product_configuration(product)

    assert len(result.components) == 1

    comp = result.components[0]

    assert comp["key"] == "neck"
    assert comp["type"] == "custom_piece"

    assert len(comp["part_models"]) == 1

    pm = comp["part_models"][0]

    assert pm["id"] == str(part_model.uuid)
    assert pm["price"] == float(part_model.price)

    assert len(pm["options"]) == 1
    assert pm["options"][0]["name"] == "color"
    assert pm["options"][0]["value"] == "blue"


@pytest.mark.django_db
def test_build_product_configuration_missing_handler(product, custom_component, monkeypatch):

    monkeypatch.setattr(ComponentHandlerRegistry, "get_handler", lambda source_type: None)

    with pytest.raises(Exception):
        build_product_configuration(product)


@pytest.mark.django_db
def test_handler_called_for_each_component(product, custom_component, monkeypatch):
    calls = []

    class FakeHandler:
        def build_configuration_component(self, component, product):
            calls.append(component.key)
            return {"key": component.key}

    monkeypatch.setattr(ComponentHandlerRegistry, "get_handler", lambda source_type: FakeHandler())

    build_product_configuration(product)

    assert calls == [custom_component.key]


# @pytest.mark.django_db
# def test_configuration_output_structure(product, custom_component, monkeypatch):
#     class FakeHandler:
#         def build_configuration_component(self, component, product):
#             return {"key": component.key, "type": "custom_piece", "options": []}

#     monkeypatch.setattr(ComponentHandlerRegistry, "get_handler", lambda source_type: FakeHandler())

#     result = build_product_configuration(product)

#     component = result.components[0]

#     assert "key" in component
#     assert "type" in component
#     assert isinstance(component["options"], list)


# from django.test.utils import CaptureQueriesContext
# from django.db import connection


# @pytest.mark.django_db
# def test_no_n_plus_one(product, custom_component, monkeypatch):

#     class FakeHandler:
#         def build_configuration_component(self, component, product):
#             return {"key": component.key}

#     monkeypatch.setattr(ComponentHandlerRegistry, "get_handler", lambda source_type: FakeHandler())

#     with CaptureQueriesContext(connection) as ctx:
#         build_product_configuration(product)

#     assert len(ctx.captured_queries) < 10  # seuil raisonnable
