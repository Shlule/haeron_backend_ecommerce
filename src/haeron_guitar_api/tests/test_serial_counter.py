import importlib

from django.apps import apps

from haeron_guitar_api.models import Part, PartBatch, PartModel, SerialCounter

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helper and fixture)
from .test_production import BUILD_PART, workshop  # noqa: F401  (fixture)


def build(staff, w, part_model):  # noqa: F811
    data = {
        "partModelId": str(part_model.uuid),
        "factoryId": str(w["factory"].uuid),
        "instrumentTypeId": str(w["product"].instrument_model.instrument_type_id),
    }
    result = run(BUILD_PART, staff, data=data)
    assert result.errors is None, result.errors
    return result.data["backoffice"]["buildPart"]["serialNumber"]


def neck_model(w):
    body = w["part_model"]
    neck = PartModel.objects.create(code="NK", name="Neck", part_type=body.part_type)
    PartBatch.objects.create(part_model=neck, name="Lot 1", code="A1", status="active")
    return neck


def test_each_part_model_has_its_own_numbers(staff, workshop):  # noqa: F811
    body, neck = workshop["part_model"], neck_model(workshop)
    serials = [build(staff, workshop, body), build(staff, workshop, neck), build(staff, workshop, body)]
    # the bodies follow each other, the neck does not take a body number
    assert [s[-4:] for s in serials] == ["0001", "0001", "0002"]
    assert serials[1].startswith("HAEG-NK")
    counters = SerialCounter.objects.values_list("part_model__code", "last_value")
    assert sorted(counters) == [("BD", 2), ("NK", 1)]


def test_migration_starts_each_counter_after_the_numbers_given(staff, workshop):  # noqa: F811
    body = workshop["part_model"]
    for _ in range(3):
        build(staff, workshop, body)
    Part.objects.filter(serial_number__endswith="0002").delete()  # a gap : the highest number counts
    SerialCounter.objects.all().delete()  # as before the counter per part model
    migration = importlib.import_module("haeron_guitar_api.migrations.0022_serial_counter_per_part_model")
    migration.start_counters_after_existing_numbers(apps, None)
    assert SerialCounter.objects.get(part_model=body).last_value == 3
    assert build(staff, workshop, body).endswith("A10004")
