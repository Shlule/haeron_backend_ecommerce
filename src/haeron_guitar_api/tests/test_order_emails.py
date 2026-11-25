from unittest import mock

import pytest

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run as run_staff, staff  # noqa: F401  (helper and fixture)
from .test_backoffice_orders import order  # noqa: F401  (fixture)
from .test_payments import CONFIRM, PAY, STATUS, session, stripe_api  # noqa: F401  (fixture)
from .test_storefront import run as run_shop

SHIP = (
    "mutation ($id: UUID!, $carrier: String!, $number: String!, $url: String!, $notify: Boolean!) "
    "{ backoffice { shipOrder(orderId: $id, carrier: $carrier, trackingNumber: $number, trackingUrl: $url, notify: $notify) } }"
)
SHOP_ORDER = "query ($id: UUID!) { shopOrder(orderId: $id) }"


@pytest.fixture
def emails(mailoutbox):
    """Sent e-mails. They leave once the change is committed : a test never commits, so they leave right away."""
    with mock.patch("haeron_guitar_api.order.order_emails.transaction.on_commit", side_effect=lambda send: send()):
        yield mailoutbox


def ship(staff, order, carrier="colissimo", number="6A12345678901", url="", notify=True):  # noqa: F811
    return run_staff(SHIP, staff, id=str(order.uuid), carrier=carrier, number=number, url=url, notify=notify)


def test_stripe_payment_sends_one_confirmation(order, stripe_api, emails):  # noqa: F811
    stripe_api["create"].return_value = session(order, paid=False)
    run_shop(PAY, id=str(order.uuid))
    # the Stripe page shows the choices made
    product = stripe_api["create"].call_args.kwargs["line_items"][0]["price_data"]["product_data"]
    assert product["name"] == "Starlight" and "Matière alu · Couleur blue" in product["description"]
    assert "images" not in product  # no public picture in the tests

    stripe_api["retrieve"].return_value = session(order)
    run_shop(CONFIRM, id=str(order.uuid), session="cs_test_1")
    run_shop(CONFIRM, id=str(order.uuid), session="cs_test_1")  # webhook arriving after the customer
    assert len(emails) == 1
    mail = emails[0]
    reference = str(order.uuid)[:8].upper()
    assert mail.to == ["jean@example.com"] and mail.subject == f"Haeron Guitar : commande {reference} confirmée"
    assert f"/commande/{order.uuid}" in mail.body and "290,00 €" in mail.body and "Couleur blue" in mail.body
    html = mail.alternatives[0][0]
    assert "Suivre ma commande" in html and "1 rue de la Paix" in html
    assert "Conditions générales de vente" in mail.body and "/cgv" in html


def test_unpaid_order_gets_no_confirmation(order, stripe_api, emails):  # noqa: F811
    stripe_api["create"].return_value = session(order, paid=False)
    run_shop(PAY, id=str(order.uuid))
    stripe_api["retrieve"].return_value = session(order, paid=False)
    run_shop(CONFIRM, id=str(order.uuid), session="cs_test_1")
    assert emails == []


def test_order_paid_by_hand_gets_the_confirmation(staff, order, emails):  # noqa: F811
    run_staff(STATUS, staff, id=str(order.uuid), status="paid")
    run_staff(STATUS, staff, id=str(order.uuid), status="processing")
    run_staff(STATUS, staff, id=str(order.uuid), status="paid")  # back and forth : not sent again
    assert [mail.subject.endswith("confirmée") for mail in emails] == [True]


def test_shipping_sends_the_tracking_link(staff, order, emails):  # noqa: F811
    run_staff(STATUS, staff, id=str(order.uuid), status="paid")
    result = ship(staff, order)
    assert result.errors is None
    sheet = result.data["backoffice"]["shipOrder"]
    assert sheet["status"] == "shipped"
    shipment = sheet["shipment"]
    assert (shipment["carrierName"], shipment["trackingNumber"]) == ("Colissimo", "6A12345678901")
    assert shipment["trackingUrl"] == "https://www.laposte.fr/outils/suivre-vos-envois?code=6A12345678901"
    assert {"value": "colissimo", "label": "Colissimo"} in sheet["carriers"]

    mail = emails[-1]
    assert mail.subject.endswith("est expédiée")
    assert shipment["trackingUrl"] in mail.body and "Colissimo" in mail.body and f"/commande/{order.uuid}" in mail.body

    # the customer follows the parcel from the order page of the shop
    shop = run_shop(SHOP_ORDER, id=str(order.uuid)).data["shopOrder"]
    assert shop["status"] == "shipped" and shop["shipment"]["trackingUrl"] == shipment["trackingUrl"]


def test_tracking_number_corrected_without_e_mail(staff, order, emails):  # noqa: F811
    run_staff(STATUS, staff, id=str(order.uuid), status="paid")
    ship(staff, order)
    sheet = ship(staff, order, carrier="other", number="", url="https://suivi.example.com/42", notify=False)
    shipment = sheet.data["backoffice"]["shipOrder"]["shipment"]
    assert (shipment["carrierName"], shipment["trackingUrl"]) == ("Autre", "https://suivi.example.com/42")
    assert len(emails) == 2  # confirmation, first shipping e-mail


def test_shipping_is_checked(staff, order, emails):  # noqa: F811
    assert "pas payée" in ship(staff, order).errors[0].message
    run_staff(STATUS, staff, id=str(order.uuid), status="paid")
    assert "Transporteur inconnu" in ship(staff, order, carrier="pigeon").errors[0].message
    assert "adresse web" in ship(staff, order, carrier="other", url="pas un lien").errors[0].message
    assert run_shop(SHOP_ORDER, id=str(order.uuid)).data["shopOrder"]["shipment"] is None
