import importlib

from django.apps import apps
from django.contrib.auth import get_user_model

from haeron_guitar_api.models import Instrument, InstrumentHistory, Part

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helper and fixture)
from .test_backoffice_orders import SHEET, STATUS, order  # noqa: F401  (fixture)
from .test_production import BUILD_INSTRUMENT, BUILD_PART, FORM, workshop  # noqa: F401  (fixture)

LINK = (
    "mutation ($target: String!, $id: UUID!, $order: UUID, $index: Int) "
    "{ backoffice { linkProductionOrder(target: $target, targetId: $id, orderId: $order, orderItemIndex: $index) } }"
)


def build_instrument(staff, w, order=None):  # noqa: F811
    data = {
        "instrumentModelId": str(w["product"].instrument_model_id),
        "factoryId": str(w["factory"].uuid),
        "parts": [{"partModelId": str(w["part_model"].uuid), "optionIds": [str(w["alu"].uuid), str(w["blue"].uuid)]}],
    }
    if order is not None:
        data.update(orderId=str(order.uuid), orderItemIndex=0)
    return run(BUILD_INSTRUMENT, staff, data=data)


def build_part(staff, w, order=None):  # noqa: F811
    data = {
        "partModelId": str(w["part_model"].uuid),
        "factoryId": str(w["factory"].uuid),
        "instrumentTypeId": str(w["product"].instrument_model.instrument_type_id),
    }
    if order is not None:
        data.update(orderId=str(order.uuid), orderItemIndex=0)
    return run(BUILD_PART, staff, data=data)


def sheet_line(staff, order):  # noqa: F811
    return run(SHEET, staff, id=str(order.uuid)).data["backoffice"]["orderSheet"]["items"][0]["production"]


def test_instrument_made_for_an_order_line_is_linked_to_it(staff, workshop, order):  # noqa: F811
    # before : the line needs one instrument
    assert sheet_line(staff, order) == {"kind": "instrument", "expected": 1, "made": []}
    line = run(FORM, staff).data["backoffice"]["productionForm"]["orders"][0]["items"][0]
    assert (line["kind"], line["quantity"], line["linked"]) == ("instrument", 1, 0)

    sheet = build_instrument(staff, workshop, order).data["backoffice"]["buildInstrument"]
    instrument = Instrument.objects.get()
    assert instrument.order_item == order.order_items.get()
    assert sheet["order"]["reference"] == str(order.uuid)[:8].upper() and sheet["order"]["item"] == "Starlight"
    assert sheet["status"] == "sold"

    made = sheet_line(staff, order)["made"]
    assert [(m["kind"], m["serialNumber"]) for m in made] == [("instrument", sheet["serialNumber"])]
    # one instrument ordered : not a second one
    assert "a déjà tout" in build_instrument(staff, workshop, order).errors[0].message
    assert Instrument.objects.count() == 1


def test_stock_instrument_given_to_an_order_then_taken_back(staff, workshop, order):  # noqa: F811
    customer = get_user_model().objects.create_user(username="jean", email="jean@example.com", password="x")
    order.user = customer
    order.save()
    sheet = build_instrument(staff, workshop).data["backoffice"]["buildInstrument"]
    assert (sheet["status"], sheet["order"]) == ("in_stock", None)

    linked = run(LINK, staff, target="instrument", id=sheet["id"], order=str(order.uuid), index=0)
    assert linked.errors is None
    linked = linked.data["backoffice"]["linkProductionOrder"]
    assert (linked["status"], linked["owner"], linked["order"]["id"]) == ("sold", "jean@example.com", str(order.uuid))
    assert set(Part.objects.values_list("owner__email", flat=True)) == {"jean@example.com"}

    back = run(LINK, staff, target="instrument", id=sheet["id"]).data["backoffice"]["linkProductionOrder"]
    assert (back["status"], back["owner"], back["order"]) == ("in_stock", None, None)
    assert InstrumentHistory.objects.filter(description__startswith="Retiré de la commande").exists()


def test_cancelled_order_puts_its_instrument_back_in_stock(staff, workshop, order):  # noqa: F811
    build_instrument(staff, workshop, order)
    assert run(STATUS, staff, id=str(order.uuid), status="cancelled").errors is None
    instrument = Instrument.objects.get()
    assert (instrument.order_item, instrument.status) == (None, "in_stock")
    assert InstrumentHistory.objects.filter(description__endswith="annulée.").exists()
    assert set(Part.objects.values_list("status", flat=True)) == {"in_stock"}
    # a cancelled order takes nothing any more
    assert "annulée" in build_instrument(staff, workshop, order).errors[0].message


def test_piece_sold_alone_is_linked_but_a_mounted_part_follows_its_instrument(staff, workshop, order):  # noqa: F811
    piece = build_part(staff, workshop, order).data["backoffice"]["buildPart"]
    assert (piece["status"], piece["order"]["reference"]) == ("sold", str(order.uuid)[:8].upper())
    assert sheet_line(staff, order)["made"][0]["kind"] == "part"
    # sold alone : it cannot be mounted on an instrument
    data = {
        "instrumentModelId": str(workshop["product"].instrument_model_id),
        "factoryId": str(workshop["factory"].uuid),
        "parts": [{"existingPartId": piece["id"]}],
    }
    assert "vendue seule" in run(BUILD_INSTRUMENT, staff, data=data).errors[0].message

    instrument = build_instrument(staff, workshop).data["backoffice"]["buildInstrument"]
    mounted = instrument["parts"][0]["id"]
    result = run(LINK, staff, target="part", id=mounted, order=str(order.uuid), index=0)
    assert "montée sur un instrument" in result.errors[0].message


def test_old_instruments_are_linked_by_the_migration(staff, workshop, order):  # noqa: F811
    build_instrument(staff, workshop, order)
    instrument = Instrument.objects.get()
    Instrument.objects.update(order_item=None)  # as before the link existed : only the order id in the configuration
    migration = importlib.import_module("haeron_guitar_api.migrations.0020_order_item_link")
    migration.link_existing_instruments(apps, None)
    instrument.refresh_from_db()
    assert instrument.order_item == order.order_items.get()


def test_production_form_only_lists_orders_still_waiting(staff, workshop, order):  # noqa: F811
    def listed():
        return [o["id"] for o in run(FORM, staff).data["backoffice"]["productionForm"]["orders"]]

    assert listed() == [str(order.uuid)]
    build_instrument(staff, workshop, order)
    # its only line has its instrument : nothing left to make for it
    assert listed() == []
