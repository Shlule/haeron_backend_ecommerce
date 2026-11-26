"""Replacing a manufactured part of an instrument : a free part of the same kind takes its place, the old one goes
back to stock, and both stay in the history (the master part, which carries the serial number, cannot be replaced)."""

from haeron_guitar_api.models import InstrumentHistory, Part, PartBatch, PartHistory, PartModel

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helper and fixture)
from .test_backoffice_orders import order  # noqa: F401  (fixture)
from .test_order_production import BUILD_INSTRUMENT, BUILD_PART, build_part
from .test_production import workshop  # noqa: F401  (fixture)

REPLACE = (
    "mutation ($id: UUID!, $part: UUID!, $new: UUID!, $note: String!) { backoffice { "
    "replaceInstrumentPart(instrumentId: $id, partId: $part, newPartId: $new, note: $note) } }"
)
CANDIDATES = "query ($part: UUID!) { backoffice { replacementParts(partId: $part) } }"


def two_part_instrument(staff, w, order=None):  # noqa: F811
    line = {"partModelId": str(w["part_model"].uuid), "optionIds": [str(w["alu"].uuid), str(w["blue"].uuid)]}
    data = {
        "instrumentModelId": str(w["product"].instrument_model_id),
        "factoryId": str(w["factory"].uuid),
        "parts": [line, line],
    }
    if order is not None:
        data.update(orderId=str(order.uuid), orderItemIndex=0)
    return run(BUILD_INSTRUMENT, staff, data=data).data["backoffice"]["buildInstrument"]


def test_a_part_is_replaced_by_a_free_one(staff, workshop, order):  # noqa: F811
    sheet = two_part_instrument(staff, workshop, order)  # made for the order : sold, owned by the customer
    master, old = sheet["parts"]
    spare = build_part(staff, workshop).data["backoffice"]["buildPart"]

    candidates = run(CANDIDATES, staff, part=old["id"]).data["backoffice"]["replacementParts"]
    assert candidates["checked"] is True  # the body is declared compatible with the model in the catalogue
    assert [(c["serialNumber"], c["sameModel"]) for c in candidates["parts"]] == [(spare["serialNumber"], True)]

    result = run(REPLACE, staff, id=sheet["id"], part=old["id"], new=spare["id"], note="Fissure au talon")
    assert result.errors is None
    after = result.data["backoffice"]["replaceInstrumentPart"]
    assert [p["serialNumber"] for p in after["parts"]] == [master["serialNumber"], spare["serialNumber"]]

    new, gone = Part.objects.get(pk=spare["id"]), Part.objects.get(pk=old["id"])
    assert (new.status, new.owner_id, new.sold_at is not None) == ("sold", sheet_owner(sheet), True)
    assert (gone.instrument_id, gone.owner_id, gone.status, gone.sold_at) == (None, None, "in_stock", None)
    event = InstrumentHistory.objects.get(title="Pièce remplacée")
    assert event.description == f"{old['partModel']['name']} : {old['serialNumber']} → {spare['serialNumber']}. Fissure au talon"
    assert PartHistory.objects.filter(part=gone, title=f"Démontée de l'instrument {sheet['serialNumber']}").exists()
    assert PartHistory.objects.get(part=new, title="Montée sur un instrument").description.endswith(
        f"(remplace {old['serialNumber']}). Fissure au talon"
    )
    # the old part is free again : it can replace the new one
    again = run(CANDIDATES, staff, part=spare["id"]).data["backoffice"]["replacementParts"]["parts"]
    assert [c["id"] for c in again] == [old["id"]]


def sheet_owner(sheet):
    return Part.objects.get(serial_number=sheet["serialNumber"]).owner_id


def test_what_cannot_be_replaced(staff, workshop):  # noqa: F811
    sheet = two_part_instrument(staff, workshop)
    master, part = sheet["parts"]
    other = two_part_instrument(staff, workshop)
    spare = build_part(staff, workshop).data["backoffice"]["buildPart"]

    def error(part_id, new_id):
        return run(REPLACE, staff, id=sheet["id"], part=part_id, new=new_id, note="").errors[0].message

    assert "pièce maîtresse" in error(master["id"], spare["id"])
    assert "déjà montée" in error(part["id"], other["parts"][1]["id"])  # mounted on another instrument
    assert "n'est plus montée" in error(other["parts"][1]["id"], spare["id"])  # not on this instrument


def test_only_the_models_compatible_with_the_instrument_are_proposed(staff, workshop):  # noqa: F811
    w = workshop
    sheet = two_part_instrument(staff, w)
    part = sheet["parts"][1]
    # another body, not declared for this instrument model in Compatibilité
    other = PartModel.objects.create(name="body XL", code="BX", part_type=w["part_model"].part_type)
    PartBatch.objects.create(part_model=other, name="Lot X", code="X1", status="active")
    stray = run(BUILD_PART, staff, data={
        "partModelId": str(other.uuid),
        "factoryId": str(w["factory"].uuid),
        "instrumentTypeId": str(w["product"].instrument_model.instrument_type_id),
    }).data["backoffice"]["buildPart"]
    spare = build_part(staff, w).data["backoffice"]["buildPart"]

    candidates = run(CANDIDATES, staff, part=part["id"]).data["backoffice"]["replacementParts"]
    assert [c["id"] for c in candidates["parts"]] == [spare["id"]]
    refused = run(REPLACE, staff, id=sheet["id"], part=part["id"], new=stray["id"], note="").errors[0].message
    assert "n'est pas compatible" in refused
