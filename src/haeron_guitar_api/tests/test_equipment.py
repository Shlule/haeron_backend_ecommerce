"""Equipment of an instrument : the bought hardware mounted on it (tuners, pickups...), written from its order,
mounted or replaced from the workshop stock, and shown on the public certificate."""

import json

from haeron_guitar_api.models import InstrumentEquipment, InstrumentHistory, Part, PartHistory, StockMovement
from haeron_guitar_api.production.equipment_service import from_snapshot, slot_of
from haeron_guitar_api.production.hidden_mark_service import CHECKED_TITLE
from provisionning_agent.selectors import (
    build_verification_response,
    get_part_for_verification,
    verification_response_to_dict,
)

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helper and fixture)
from .test_backoffice_orders import order  # noqa: F401  (fixture)
from .test_order_production import build_instrument
from .test_production import workshop  # noqa: F401  (fixture)
from .test_purchasing import CREATE, catalogue, invoice  # noqa: F401  (fixture)

SHEET = "query ($id: UUID!) { backoffice { instrumentSheet(instrumentId: $id) } }"
MOUNT = "mutation ($id: UUID!, $data: BoEquipmentInput!) { backoffice { mountEquipment(instrumentId: $id, data: $data) } }"
TAKE = (
    "mutation ($id: UUID!, $item: UUID!) { backoffice { takeEquipmentFromStock(equipmentId: $id, stockItemId: $item) } }"
)
REMOVE = "mutation ($id: UUID!, $note: String!) { backoffice { removeEquipment(equipmentId: $id, note: $note) } }"
FILL = "mutation ($id: UUID!) { backoffice { fillEquipmentFromOrder(instrumentId: $id) } }"


def mount(staff, instrument_id, **data):  # noqa: F811
    result = run(MOUNT, staff, id=instrument_id, data=data)
    return result.errors[0].message if result.errors else result.data["backoffice"]["mountEquipment"]


def test_the_place_is_read_from_the_component_or_the_name():
    assert slot_of("mecaniques") == "mecaniques"
    assert slot_of("micro_chevalet") == "micros"  # a bridge pickup is a pickup
    assert slot_of("", "Humbucker Seymour Duncan") == "micros"
    assert slot_of("Pots CTS 500k") == "potentiometres"
    assert slot_of("Sélecteur 3 positions") == "selecteur"
    assert slot_of("Jack Switchcraft") == "jack"
    assert slot_of("Vibrato Bigsby") == "chevalet"
    assert slot_of("sangle") == "autre"
    # custom pieces are made here (serial number) : only the bought pieces are equipment
    snapshot = {
        "options": [
            {"type": "custom_piece", "component": "body", "part_model_id": "x", "options": [{"id": "1", "name": "color"}]},
            {"type": "product_choice", "component": "mic", "product_id": "p", "name": "mic A"},
            {"type": "product_configurable", "component": "electronique", "snapshot": [
                {"type": "fixed", "component": "jack", "product_id": "j", "name": "Jack Switchcraft"},
            ]},
        ],
        "configuration": {"mic": {"product_id": "p"}},
    }
    assert [(e["slot"], e["name"]) for e in from_snapshot(snapshot)] == [("micros", "mic A"), ("jack", "Jack Switchcraft")]


def test_an_instrument_made_for_an_order_carries_its_bought_pieces(staff, workshop, order):  # noqa: F811
    sheet = build_instrument(staff, workshop, order).data["backoffice"]["buildInstrument"]
    current = sheet["equipment"]["current"]
    assert [(e["slot"], e["name"], e["fromOrder"]) for e in current] == [("micros", "mic A", True)]
    # asked again : nothing doubled
    again = run(FILL, staff, id=sheet["id"]).data["backoffice"]["fillEquipmentFromOrder"]
    assert len(again["equipment"]["current"]) == 1


def test_replacing_a_piece_from_the_stock_keeps_what_was_there(staff, workshop, order, catalogue):  # noqa: F811
    run(CREATE, staff, data=invoice(catalogue))  # 4 pickups in the workshop
    sheet = build_instrument(staff, workshop, order).data["backoffice"]["buildInstrument"]
    mic = sheet["equipment"]["current"][0]

    sheet = mount(staff, sheet["id"], stockItemId=str(catalogue["pickup"].uuid), replacesId=mic["id"], note="Client voulait plus de sortie")
    current, removed = sheet["equipment"]["current"], sheet["equipment"]["removed"]
    assert [(e["slot"], e["name"], e["stockItem"]) for e in current] == [("micros", "Micro SH-4", "Micro SH-4 (SH4)")]
    assert current[0]["cost"] == 54.0  # average cost of the stock
    assert [(e["name"], e["removalNote"]) for e in removed] == [("mic A", "Remplacé par Micro SH-4")]
    event = InstrumentHistory.objects.get(title="Micros : pièce remplacée")
    assert event.description == "mic A → Micro SH-4 (Client voulait plus de sortie)."
    # out of the workshop stock, on this instrument
    assert StockMovement.objects.get(kind="use").instrument_id == InstrumentEquipment.objects.get(removed_at=None).instrument_id

    # the order is asked again : the replaced pickup does not come back
    again = run(FILL, staff, id=sheet["id"]).data["backoffice"]["fillEquipmentFromOrder"]
    assert [e["name"] for e in again["equipment"]["current"]] == ["Micro SH-4"]


def test_a_piece_of_the_order_is_taken_out_of_the_stock(staff, workshop, order, catalogue):  # noqa: F811
    run(CREATE, staff, data=invoice(catalogue))
    sheet = build_instrument(staff, workshop, order).data["backoffice"]["buildInstrument"]
    mic = sheet["equipment"]["current"][0]
    taken = run(TAKE, staff, id=mic["id"], item=str(catalogue["pickup"].uuid)).data["backoffice"]["takeEquipmentFromStock"]
    row = taken["equipment"]["current"][0]
    assert (row["name"], row["stockItem"], row["cost"]) == ("mic A", "Micro SH-4 (SH4)", 54.0)
    assert "déjà sorti du stock" in run(TAKE, staff, id=mic["id"], item=str(catalogue["pickup"].uuid)).errors[0].message


def test_typed_pieces_are_mounted_and_removed(staff, workshop):  # noqa: F811
    sheet = build_instrument(staff, workshop).data["backoffice"]["buildInstrument"]
    assert "emplacement" in mount(staff, sheet["id"], slot="nope", name="X")
    assert "Indique ce qui est monté" in mount(staff, sheet["id"], slot="jack")
    sheet = mount(staff, sheet["id"], slot="jack", name="Jack Switchcraft")
    sheet = mount(staff, sheet["id"], slot="mecaniques", name="Gotoh SG381")
    assert [e["slot"] for e in sheet["equipment"]["current"]] == ["mecaniques", "jack"]  # by place
    jack = sheet["equipment"]["current"][1]
    sheet = run(REMOVE, staff, id=jack["id"], note="Jack cassé").data["backoffice"]["removeEquipment"]
    assert [e["name"] for e in sheet["equipment"]["current"]] == ["Gotoh SG381"]
    assert InstrumentHistory.objects.filter(title="Jack : pièce retirée", description="Jack Switchcraft (Jack cassé).").exists()
    assert "n'est plus monté" in run(REMOVE, staff, id=jack["id"], note="").errors[0].message


def test_the_certificate_shows_the_equipment_but_not_the_hidden_code(staff, workshop, order):  # noqa: F811
    sheet = build_instrument(staff, workshop, order).data["backoffice"]["buildInstrument"]
    part = Part.objects.get()
    PartHistory.objects.create(
        part=part, event_type="controle", title=CHECKED_TITLE, description="Emplacement : sous la plaque de jack."
    )
    PartHistory.objects.create(part=part, event_type="reglage", title="Réglage", description="Action abaissée.")

    found = get_part_for_verification(part.serial_number)
    response = verification_response_to_dict(build_verification_response(found))
    text = json.dumps(response, ensure_ascii=False)
    assert "sous la plaque" not in text and "security_marks" not in text
    assert [h["title"] for h in response["part"]["history"] if h["title"] == "Réglage"] == ["Réglage"]
    instrument = response["instrument"]
    assert instrument["serial_number"] == sheet["serialNumber"]
    assert [p["serial_number"] for p in instrument["parts"]] == [part.serial_number]
    assert instrument["equipment"] == [{"slot": "micros", "label": "Micros", "name": "mic A"}]
