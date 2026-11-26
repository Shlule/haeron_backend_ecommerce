"""Pieces made by an outside factory and paid by a supplier invoice line : what each piece, and its instrument, cost."""

from haeron_guitar_api.models import Part, Supplier

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helper and fixture)
from .test_order_production import build_instrument, build_part
from .test_production import workshop  # noqa: F401  (fixture)
from .test_purchasing import CREATE, catalogue  # noqa: F401  (fixture)

INVOICE = "query ($id: UUID!) { backoffice { purchaseInvoice(invoiceId: $id) } }"
FREE = "query ($search: String) { backoffice { partsWithoutInvoice(search: $search) } }"
LINK = "mutation ($line: UUID!, $parts: [UUID!]!) { backoffice { linkPartsToInvoiceLine(lineId: $line, partIds: $parts) } }"
UNLINK = "mutation ($id: UUID!) { backoffice { unlinkPartInvoice(partId: $id) } }"
PART = "query ($id: UUID!) { backoffice { partSheet(partId: $id) } }"
INSTRUMENT = "query ($id: UUID!) { backoffice { instrumentSheet(instrumentId: $id) } }"


def factory_invoice(staff, catalogue):  # noqa: F811
    supplier = Supplier.objects.create(name="Usine Haeron")
    data = {
        "supplierId": str(supplier.uuid),
        "number": "U-001",
        "issuedOn": "2026-11-20",
        "lines": [
            {"label": "Corps Starlight", "category": "manufacturing", "quantity": "2", "unitPriceHt": "100", "vatRate": "20"},
            {"label": "", "category": "components", "stockItemId": str(catalogue["pickup"].uuid), "zone": "workshop",
             "quantity": "1", "unitPriceHt": "50"},
        ],
    }
    return run(CREATE, staff, data=data).data["backoffice"]["createPurchaseInvoice"]


def test_a_factory_invoice_pays_for_its_pieces(staff, workshop, catalogue):  # noqa: F811
    invoice = factory_invoice(staff, catalogue)
    line, stock_line = invoice["lines"]
    assert (line["canHoldParts"], stock_line["canHoldParts"]) == (True, False)
    ids = [build_part(staff, workshop).data["backoffice"]["buildPart"]["id"] for _ in range(3)]
    assert len(run(FREE, staff).data["backoffice"]["partsWithoutInvoice"]) == 3

    linked = run(LINK, staff, line=line["id"], parts=ids[:2]).data["backoffice"]["linkPartsToInvoiceLine"]
    assert len(linked["lines"][0]["parts"]) == 2
    # the line paid for 2 pieces, not 3 ; a stock line pays for no piece
    assert "paie 2 pièce(s)" in run(LINK, staff, line=line["id"], parts=[ids[2]]).errors[0].message
    assert "fait entrer un article en stock" in run(LINK, staff, line=stock_line["id"], parts=[ids[2]]).errors[0].message
    assert [p["id"] for p in run(FREE, staff).data["backoffice"]["partsWithoutInvoice"]] == [ids[2]]

    sheet = run(PART, staff, id=ids[0]).data["backoffice"]["partSheet"]
    assert sheet["purchase"] == {
        "invoiceId": invoice["id"], "supplier": "Usine Haeron", "number": "U-001", "issuedOn": "2026-11-20",
        "line": "Corps Starlight", "unitHt": 100.0, "unitTtc": 120.0,
    }
    sheet = run(UNLINK, staff, id=ids[0]).data["backoffice"]["unlinkPartInvoice"]
    assert sheet["purchase"] is None
    assert Part.objects.filter(purchase_line__isnull=False).count() == 1


def test_the_instrument_cost(staff, workshop, catalogue):  # noqa: F811
    invoice = factory_invoice(staff, catalogue)
    built = build_instrument(staff, workshop).data["backoffice"]["buildInstrument"]
    costs = built["costs"]
    assert (costs["partsHt"], costs["partsWithoutInvoice"], costs["totalHt"]) == (0, 1, 0)
    run(LINK, staff, line=invoice["lines"][0]["id"], parts=[built["parts"][0]["id"]])
    costs = run(INSTRUMENT, staff, id=built["id"]).data["backoffice"]["instrumentSheet"]["costs"]
    assert costs == {"partsHt": 100.0, "partsTtc": 120.0, "partsWithoutInvoice": 0, "stockHt": 0.0, "totalHt": 100.0}


def test_the_pieces_are_chosen_when_the_invoice_is_typed(staff, workshop, catalogue):  # noqa: F811
    ids = [build_part(staff, workshop).data["backoffice"]["buildPart"]["id"] for _ in range(2)]
    supplier = Supplier.objects.create(name="Usine Chine")
    data = {
        "supplierId": str(supplier.uuid), "number": "CN-7", "issuedOn": "2026-11-21",
        "lines": [{"label": "Corps", "category": "manufacturing", "quantity": "2", "unitPriceHt": "60", "partIds": ids}],
    }
    invoice = run(CREATE, staff, data=data).data["backoffice"]["createPurchaseInvoice"]
    assert sorted(p["id"] for p in invoice["lines"][0]["parts"]) == sorted(ids)
    # one piece too many : nothing is saved
    data.update(number="CN-8", lines=[{**data["lines"][0], "quantity": "1"}])
    assert run(CREATE, staff, data=data).errors
    assert not Part.objects.filter(purchase_line__invoice__number="CN-8").exists()
