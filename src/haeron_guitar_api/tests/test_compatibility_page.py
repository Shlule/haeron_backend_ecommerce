from haeron_guitar_api.models import ComponentCompatibility, PartModel, Product

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_storefront import run

QUERY = "{ shopCompatibility }"


def test_lists_the_parts_of_each_instrument_sold(starlight):  # noqa: F811
    body = PartModel.objects.get(code="BD")
    link = ComponentCompatibility.objects.get(part_model=body)
    old = PartModel.objects.create(name="old body", code="OB", part_type=body.part_type, status="service_only")
    proto = PartModel.objects.create(name="proto", code="PR", part_type=body.part_type, status="prototype")
    for model in (old, proto):
        ComponentCompatibility.objects.create(instrument_model=link.instrument_model, part_model=model, component=link.component)

    page = run(QUERY).data["shopCompatibility"]
    assert page == [
        {
            "instrumentModel": "starlight",
            "parts": [
                {
                    "type": "body",
                    "models": [
                        {"name": "body", "code": "BD", "serviceOnly": False},
                        {"name": "old body", "code": "OB", "serviceOnly": True},  # still made for repairs
                    ],
                }
            ],
        }
    ]


def test_hidden_instruments_are_not_shown(starlight):  # noqa: F811
    Product.objects.filter(instrument_model__isnull=False).update(is_visible=False)
    assert run(QUERY).data["shopCompatibility"] == []
