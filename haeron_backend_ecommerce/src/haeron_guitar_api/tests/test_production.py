from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from haeron_guitar_api.models import Factory, Instrument, InstrumentHistory, Part, PartBatch, PartHistory, PartModel

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helper and fixture)
from .test_backoffice_orders import order  # noqa: F401  (fixture)

FORM = "{ backoffice { productionForm } }"
BUILD_INSTRUMENT = "mutation ($data: BoBuildInstrumentInput!) { backoffice { buildInstrument(data: $data) } }"
BUILD_PART = "mutation ($data: BoBuildPartInput!) { backoffice { buildPart(data: $data) } }"
ADD_EVENT = "mutation ($data: BoHistoryEventInput!) { backoffice { addHistoryEvent(data: $data) } }"
BATCH = "mutation ($pm: UUID!, $name: String!, $code: String!) { backoffice { createPartBatch(partModelId: $pm, name: $name, code: $code) } }"


@pytest.fixture
def workshop(starlight):  # noqa: F811
    s = starlight
    part_model = PartModel.objects.get(code="BD")
    batch = PartBatch.objects.create(part_model=part_model, name="Lot 1", code="A1", status="active")
    factory = Factory.objects.create(code="HAE", name="Haeron Lyon")
    return {**s, "part_model": part_model, "batch": batch, "factory": factory}


def test_form_gives_everything_in_one_call(staff, workshop, order):  # noqa: F811
    form = run(FORM, staff).data["backoffice"]["productionForm"]
    body = next(pm for pm in form["partModels"] if pm["code"] == "BD")
    assert body["activeBatch"]["code"] == "A1"
    assert {group["name"] for group in body["options"]} == {"color", "material"}
    assert form["factories"][0]["code"] == "HAE"
    # an order line gives the pieces to make with their option values
    parts = form["orders"][0]["items"][0]["parts"]
    assert parts[0]["partModelId"] == str(workshop["part_model"].uuid)
    assert set(parts[0]["optionIds"]) == {str(workshop["alu"].uuid), str(workshop["blue"].uuid)}


def test_build_a_part_with_its_options(staff, workshop):  # noqa: F811
    w = workshop
    data = {
        "partModelId": str(w["part_model"].uuid),
        "factoryId": str(w["factory"].uuid),
        "instrumentTypeId": str(w["product"].instrument_model.instrument_type_id),
        "optionIds": [str(w["alu"].uuid), str(w["blue"].uuid)],
        "description": "  Corps en alu brossé  ",
    }
    result = run(BUILD_PART, staff, data=data)
    assert result.errors is None
    sheet = result.data["backoffice"]["buildPart"]
    assert sheet["serialNumber"].startswith("HAEG-BD")
    assert sheet["description"] == "Corps en alu brossé"
    assert {(o["option"], o["value"]) for o in sheet["options"]} == {("material", "alu"), ("color", "blue")}
    assert sheet["history"][0]["eventType"] == "fabrication"
    assert Part.objects.get().created_by == staff
    # each part has its own number
    second = run(BUILD_PART, staff, data=data).data["backoffice"]["buildPart"]
    assert second["serialNumber"] != sheet["serialNumber"]


def test_build_a_part_refuses_bad_options_and_missing_batch(staff, workshop):  # noqa: F811
    w = workshop
    data = {
        "partModelId": str(w["part_model"].uuid),
        "factoryId": str(w["factory"].uuid),
        "instrumentTypeId": str(w["product"].instrument_model.instrument_type_id),
        "optionIds": [str(w["red"].uuid), str(w["blue"].uuid)],
    }
    assert "une seule valeur" in run(BUILD_PART, staff, data=data).errors[0].message
    w["batch"].status = "revoked"
    w["batch"].save()
    data["optionIds"] = []
    assert "Aucun lot actif" in run(BUILD_PART, staff, data=data).errors[0].message
    assert not Part.objects.exists()


def test_build_an_instrument_from_an_order_line(staff, workshop, order):  # noqa: F811
    w = workshop
    customer = get_user_model().objects.create_user(username="jean", email="jean@example.com", password="x")
    loose = Part.objects.create(serial_number="OLD-1", part_model=w["part_model"], batch=w["batch"])
    data = {
        "instrumentModelId": str(w["product"].instrument_model_id),
        "factoryId": str(w["factory"].uuid),
        "description": "Starlight de Jean",
        "ownerEmail": "JEAN@example.com",
        "orderId": str(order.uuid),
        "orderItemIndex": 0,
        "masterIndex": 0,
        "parts": [
            {"partModelId": str(w["part_model"].uuid), "optionIds": [str(w["alu"].uuid), str(w["blue"].uuid)]},
            {"existingPartId": str(loose.uuid)},
        ],
    }
    result = run(BUILD_INSTRUMENT, staff, data=data)
    assert result.errors is None
    sheet = result.data["backoffice"]["buildInstrument"]
    instrument = Instrument.objects.get()
    assert (instrument.owner, instrument.description) == (customer, "Starlight de Jean")
    assert instrument.configuration["source"] == "order"
    assert instrument.configuration["snapshot"]["options"]
    assert instrument.master_part.is_master
    assert set(Part.objects.filter(instrument=instrument).values_list("owner", flat=True)) == {customer.pk}
    assert len(sheet["parts"]) == 2 and sheet["parts"][0]["isMaster"]
    # assembly event on the instrument and on each part, shown together on the sheet
    assert set(InstrumentHistory.objects.values_list("event_type", flat=True)) == {"assemblage", "vente"}
    assert PartHistory.objects.filter(event_type="assemblage").count() == 2
    assert {e["eventType"] for e in sheet["history"]} == {"assemblage", "fabrication", "vente"}
    # made for an order : sold to the customer
    assert sheet["status"] == "sold"

    # a part already on an instrument cannot be used again
    data["parts"] = [{"existingPartId": str(loose.uuid)}]
    data["orderId"] = None
    assert "déjà montée" in run(BUILD_INSTRUMENT, staff, data=data).errors[0].message


def test_unknown_owner_cancels_everything(staff, workshop):  # noqa: F811
    w = workshop
    data = {
        "instrumentModelId": str(w["product"].instrument_model_id),
        "factoryId": str(w["factory"].uuid),
        "ownerEmail": "nobody@example.com",
        "parts": [{"partModelId": str(w["part_model"].uuid)}],
    }
    assert "Aucun compte" in run(BUILD_INSTRUMENT, staff, data=data).errors[0].message
    assert not Part.objects.exists() and not Instrument.objects.exists()


def test_history_events(staff, workshop):  # noqa: F811
    w = workshop
    part = Part.objects.create(serial_number="P-1", part_model=w["part_model"], batch=w["batch"], is_master=True)
    instrument = Instrument.objects.create(instrument_model=w["product"].instrument_model, master_part=part)
    Part.objects.update(instrument=instrument)
    event = run(
        ADD_EVENT,
        staff,
        data={"target": "instrument", "targetId": str(instrument.uuid), "eventType": "reglage", "description": "Action baissée"},
    ).data["backoffice"]["addHistoryEvent"]
    assert (event["title"], event["eventLabel"], event["author"]) == ("Réglage", "Réglage", "staff@example.com")
    run(ADD_EVENT, staff, data={"target": "part", "targetId": str(part.uuid), "eventType": "reparation", "title": "Frette"})
    assert PartHistory.objects.get().title == "Frette"
    assert run(ADD_EVENT, staff, data={"target": "part", "targetId": str(part.uuid), "eventType": "boom"}).errors

    sheet = run("query ($id: UUID!) { backoffice { instrumentSheet(instrumentId: $id) } }", staff, id=str(instrument.uuid))
    assert [e["title"] for e in sheet.data["backoffice"]["instrumentSheet"]["history"]] == ["Frette", "Réglage"]

    deleted = run("mutation ($id: UUID!) { backoffice { deleteHistoryEvent(eventId: $id) } }", staff, id=event["id"])
    assert deleted.data["backoffice"]["deleteHistoryEvent"] is True
    assert not InstrumentHistory.objects.exists()


def test_create_batch_provisions_its_key(staff, workshop):  # noqa: F811
    with mock.patch("haeron_guitar_api.partBatch.partBatch_service.get_vault_service") as vault:
        vault.return_value.post_secret.return_value = "batch/path"
        result = run(BATCH, staff, pm=str(workshop["part_model"].uuid), name="Lot 2", code="b2")
    assert result.data["backoffice"]["createPartBatch"]["code"] == "B2"
    assert PartBatch.objects.get(code="B2").vault_batch_key_path == "batch/path"


def test_sheets_do_not_grow_with_parts(staff, workshop, django_assert_max_num_queries):  # noqa: F811
    w = workshop
    parts = [Part.objects.create(serial_number=f"P-{i}", part_model=w["part_model"], batch=w["batch"]) for i in range(6)]
    instrument = Instrument.objects.create(instrument_model=w["product"].instrument_model, master_part=parts[0])
    Part.objects.update(instrument=instrument)
    for part in parts:
        PartHistory.objects.create(part=part, event_type="fabrication", title="x", description="", created_by=staff)
    query = "query ($id: UUID!) { backoffice { instrumentSheet(instrumentId: $id) } }"
    with django_assert_max_num_queries(8):
        assert len(run(query, staff, id=str(instrument.uuid)).data["backoffice"]["instrumentSheet"]["parts"]) == 6
    with django_assert_max_num_queries(6):
        assert run("{ backoffice { producedParts } }", staff).data["backoffice"]["producedParts"]["totalCount"] == 6


def test_production_managers_can_read_but_not_build(staff, workshop):  # noqa: F811
    staff.groups.set([Group.objects.create(name="production_manager")])
    assert run(FORM, staff).errors is None
    assert run(BUILD_PART, staff, data={
        "partModelId": str(workshop["part_model"].uuid),
        "factoryId": str(workshop["factory"].uuid),
        "instrumentTypeId": str(workshop["product"].instrument_model.instrument_type_id),
    }).errors


STATUS = "mutation ($t: String!, $id: UUID!, $s: String!, $n: String!) { backoffice { setProductionStatus(target: $t, targetId: $id, status: $s, note: $n) } }"


def test_selling_an_instrument_sells_its_parts_and_writes_the_history(staff, workshop):  # noqa: F811
    w = workshop
    parts = [Part.objects.create(serial_number=f"P-{i}", part_model=w["part_model"], batch=w["batch"]) for i in range(2)]
    instrument = Instrument.objects.create(instrument_model=w["product"].instrument_model, master_part=parts[0])
    Part.objects.update(instrument=instrument)

    sheet = run(STATUS, staff, t="instrument", id=str(instrument.uuid), s="sold", n="Vendue au salon de Lyon").data[
        "backoffice"
    ]["setProductionStatus"]
    assert (sheet["status"], sheet["soldAt"] is not None) == ("sold", True)
    assert {p["status"] for p in sheet["parts"]} == {"sold"}
    assert sheet["history"][0]["title"] == "Vendu"
    assert InstrumentHistory.objects.get().description == "Vendue au salon de Lyon"
    assert PartHistory.objects.filter(event_type="vente").count() == 2
    # same status again : nothing new in the history
    run(STATUS, staff, t="instrument", id=str(instrument.uuid), s="sold", n="")
    assert InstrumentHistory.objects.count() == 1

    listed = run('{ backoffice { instruments(status: "sold") } }', staff).data["backoffice"]["instruments"]
    assert listed["totalCount"] == 1 and listed["results"][0]["status"] == "sold"
    assert run('{ backoffice { producedParts(status: "in_stock") } }', staff).data["backoffice"]["producedParts"]["totalCount"] == 0

    back = run(STATUS, staff, t="instrument", id=str(instrument.uuid), s="in_stock", n="").data["backoffice"]["setProductionStatus"]
    assert (back["status"], back["soldAt"], back["history"][0]["title"]) == ("in_stock", None, "Remis en stock")
    assert run(STATUS, staff, t="part", id=str(parts[1].uuid), s="lost", n="").errors


def test_instrument_made_for_an_order_is_sold(staff, workshop, order):  # noqa: F811
    w = workshop
    data = {
        "instrumentModelId": str(w["product"].instrument_model_id),
        "factoryId": str(w["factory"].uuid),
        "orderId": str(order.uuid),
        "orderItemIndex": 0,
        "parts": [{"partModelId": str(w["part_model"].uuid)}],
    }
    sheet = run(BUILD_INSTRUMENT, staff, data=data).data["backoffice"]["buildInstrument"]
    assert sheet["status"] == "sold" and sheet["parts"][0]["status"] == "sold"
    # a part made alone stays in stock unless told otherwise
    part = run(BUILD_PART, staff, data={
        "partModelId": str(w["part_model"].uuid),
        "factoryId": str(w["factory"].uuid),
        "instrumentTypeId": str(w["product"].instrument_model.instrument_type_id),
    }).data["backoffice"]["buildPart"]
    assert part["status"] == "in_stock"
