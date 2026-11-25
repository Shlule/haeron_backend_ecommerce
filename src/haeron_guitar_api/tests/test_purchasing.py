"""Purchases and stock of the parts bought from suppliers (pickups, tuners...) : supplier invoices, stock by zone,
parts mounted on an instrument, and the expenses on the finances page."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from haeron_guitar_api.models import Instrument, Part, StockItem, StockMovement, Supplier

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helper and fixture)
from .test_production import workshop  # noqa: F401  (fixture)

CREATE = "mutation ($data: BoPurchaseInvoiceInput!) { backoffice { createPurchaseInvoice(data: $data) } }"
UPDATE = "mutation ($id: UUID!, $data: BoPurchaseInvoiceUpdateInput!) { backoffice { updatePurchaseInvoice(invoiceId: $id, data: $data) } }"
DELETE = "mutation ($id: UUID!) { backoffice { deletePurchaseInvoice(invoiceId: $id) } }"
MOVE = "mutation ($data: BoStockMoveInput!) { backoffice { moveStock(data: $data) } }"
STOCK = "{ backoffice { stock } }"
FINANCES = "query ($from: Date, $to: Date) { backoffice { finances(dateFrom: $from, dateTo: $to) } }"


@pytest.fixture
def catalogue(db):
    supplier = Supplier.objects.create(name="Seymour Duncan")
    pickup = StockItem.objects.create(name="Micro SH-4", reference="SH4", family="Micros", supplier=supplier, alert_quantity=2)
    tuners = StockItem.objects.create(name="Mécaniques Gotoh", family="Mécaniques")
    return {"supplier": supplier, "pickup": pickup, "tuners": tuners}


def invoice(c, number="F-001", **extra):
    return {
        "supplierId": str(c["supplier"].uuid),
        "number": number,
        "issuedOn": "2026-11-10",
        "lines": [
            {"label": "", "category": "components", "stockItemId": str(c["pickup"].uuid), "zone": "workshop",
             "quantity": "4", "unitPriceHt": "50"},
            {"label": "", "category": "components", "stockItemId": str(c["pickup"].uuid), "zone": "shop",
             "quantity": "2", "unitPriceHt": "62"},
            {"label": "Frais de port", "category": "shipping", "unitPriceHt": "15"},
        ],
        **extra,
    }


def item(stock, name):
    return next(row for row in stock["items"] if row["name"] == name)


def test_an_invoice_brings_its_parts_into_stock(staff, catalogue):  # noqa: F811
    result = run(CREATE, staff, data=invoice(catalogue))
    assert result.errors is None
    sheet = result.data["backoffice"]["createPurchaseInvoice"]
    # 4 x 50 + 2 x 62 + 15 = 339 HT, 20 % VAT
    assert (sheet["totalHt"], sheet["totalVat"], sheet["totalTtc"]) == (339.0, 67.8, 406.8)
    assert sheet["lines"][0]["label"] == "Micro SH-4 (SH4)"  # the item name when the line has no label
    assert sheet["paidOn"] is None

    stock = run(STOCK, staff).data["backoffice"]["stock"]
    pickup = item(stock, "Micro SH-4")
    assert (pickup["workshop"], pickup["shop"], pickup["quantity"]) == (4.0, 2.0, 6.0)
    assert pickup["averageCost"] == pytest.approx(54.0)  # (200 + 124) / 6
    assert pickup["value"] == 324.0
    assert stock["value"]["total"] == 324.0
    # the same invoice twice is refused
    assert "déjà enregistrée" in run(CREATE, staff, data=invoice(catalogue)).errors[0].message


def test_stock_goes_out_through_movements(staff, catalogue, workshop):  # noqa: F811
    run(CREATE, staff, data=invoice(catalogue))
    pickup = catalogue["pickup"]
    master = Part.objects.create(serial_number="HAE-1", part_model=workshop["part_model"], batch=workshop["batch"], is_master=True)
    instrument = Instrument.objects.create(master_part=master, instrument_model=workshop["product"].instrument_model)

    def move(**data):
        return run(MOVE, staff, data={"stockItemId": str(pickup.uuid), **data})

    assert "Choisis l'instrument" in move(kind="use", quantity="1").errors[0].message
    sheet = move(kind="use", quantity="2", instrumentId=str(instrument.uuid)).data["backoffice"]["moveStock"]
    assert sheet["workshop"] == 2.0
    assert sheet["movements"][0]["instrument"] == "HAE-1"
    assert "Stock insuffisant" in move(kind="use", quantity="3", instrumentId=str(instrument.uuid)).errors[0].message

    sheet = move(kind="transfer", zone="shop", quantity="1").data["backoffice"]["moveStock"]
    assert (sheet["workshop"], sheet["shop"]) == (3.0, 1.0)
    sheet = move(kind="sale", zone="shop", quantity="1", note="Vendu au salon").data["backoffice"]["moveStock"]
    assert sheet["shop"] == 0.0
    sheet = move(kind="adjustment", quantity="-1", note="Micro abîmé").data["backoffice"]["moveStock"]
    assert (sheet["workshop"], sheet["quantity"], sheet["low"]) == (2.0, 2.0, True)  # alert at 2

    # cost of the instrument : the 2 pickups at the average cost of the day
    parts = run("query ($id: UUID!) { backoffice { instrumentStockParts(instrumentId: $id) } }", staff, id=str(instrument.uuid))
    assert parts.data["backoffice"]["instrumentStockParts"] == {
        "parts": [{"item": "Micro SH-4 (SH4)", "quantity": 2.0, "cost": 108.0}],
        "total": 108.0,
    }


def test_an_invoice_is_deleted_only_while_its_stock_is_there(staff, catalogue):  # noqa: F811
    created = run(CREATE, staff, data=invoice(catalogue)).data["backoffice"]["createPurchaseInvoice"]
    run(MOVE, staff, data={"stockItemId": str(catalogue["pickup"].uuid), "kind": "sale", "zone": "shop", "quantity": "1"})
    assert "déjà sortie du stock" in run(DELETE, staff, id=created["id"]).errors[0].message

    other = run(CREATE, staff, data=invoice(catalogue, number="F-002")).data["backoffice"]["createPurchaseInvoice"]
    assert run(DELETE, staff, id=other["id"]).data["backoffice"]["deletePurchaseInvoice"] is True
    assert StockMovement.objects.filter(kind="purchase").count() == 2  # the 2 lines of the first invoice


def test_paying_an_invoice_and_the_finances(staff, catalogue):  # noqa: F811
    created = run(CREATE, staff, data=invoice(catalogue)).data["backoffice"]["createPurchaseInvoice"]
    finances = run(FINANCES, staff, **{"from": "2026-11-01", "to": "2026-11-30"}).data["backoffice"]["finances"]
    assert finances["expenses"]["totalTtc"] == 406.8
    assert {row["category"]: row["ht"] for row in finances["expenses"]["byCategory"]} == {"components": 324.0, "shipping": 15.0}
    assert finances["balance"] == -406.8
    assert finances["toPay"]["count"] == 1
    assert finances["months"][-1]["expenses"] == 406.8
    assert finances["movements"][0]["kind"] == "expense"
    # outside the period : not counted
    october = run(FINANCES, staff, **{"from": "2026-10-01", "to": "2026-10-31"}).data["backoffice"]["finances"]
    assert october["expenses"]["totalTtc"] == 0

    header = {"number": "F-001", "issuedOn": "2026-11-10", "paidOn": "2026-11-20", "paymentMethod": "transfer"}
    paid = run(UPDATE, staff, id=created["id"], data=header).data["backoffice"]["updatePurchaseInvoice"]
    assert paid["paidOn"] == "2026-11-20"
    finances = run(FINANCES, staff).data["backoffice"]["finances"]
    assert finances["toPay"]["count"] == 0


def test_invoices_are_for_managers_only(catalogue):
    clerk = get_user_model().objects.create_user(username="rnd", email="rnd@example.com", password="x")
    clerk.groups.add(Group.objects.create(name="rnd"))
    assert run("{ backoffice { purchaseInvoices } }", clerk).errors
    assert run(STOCK, clerk).errors is None  # the stock is not money : readable by the workshop


def test_the_invoice_file(staff, catalogue):  # noqa: F811
    created = run(CREATE, staff, data=invoice(catalogue)).data["backoffice"]["createPurchaseInvoice"]
    url = f"/api/backoffice/purchase-invoices/{created['id']}/file/"
    client = APIClient()
    assert client.get(url).status_code == 401
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(staff)}")
    assert client.get(url).status_code == 404

    bad = client.post(url, {"file": SimpleUploadedFile("a.exe", b"MZ", content_type="application/x-msdownload")})
    assert bad.status_code == 400
    pdf = SimpleUploadedFile("facture.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    assert client.post(url, {"file": pdf}).status_code == 200
    response = client.get(url)
    assert (response.status_code, response["Content-Type"], response.content) == (200, "application/pdf", b"%PDF-1.4 test")
    detail = run("query ($id: UUID!) { backoffice { purchaseInvoice(invoiceId: $id) } }", staff, id=created["id"])
    assert detail.data["backoffice"]["purchaseInvoice"]["fileName"] == "facture.pdf"


def test_a_new_supplier_is_typed_in_the_invoice(staff, catalogue):  # noqa: F811
    data = {**invoice(catalogue), "supplierId": None, "supplierName": "  Gotoh   Europe "}
    sheet = run(CREATE, staff, data=data).data["backoffice"]["createPurchaseInvoice"]
    assert sheet["supplier"] == "Gotoh Europe"
    # the same name again (any case) : the same supplier, not a second one
    again = run(CREATE, staff, data={**data, "number": "F-002", "supplierName": "gotoh europe"}).data["backoffice"]["createPurchaseInvoice"]
    assert again["supplierId"] == sheet["supplierId"]
    assert Supplier.objects.filter(name__iexact="gotoh europe").count() == 1
    missing = {**data, "supplierName": " "}
    assert "tape son nom" in run(CREATE, staff, data=missing).errors[0].message
