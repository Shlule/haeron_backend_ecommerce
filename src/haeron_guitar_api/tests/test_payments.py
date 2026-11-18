import json
from datetime import date
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.test import Client

from haeron_guitar_api.models import Payment

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run as run_staff, staff  # noqa: F401  (helper and fixture)
from .test_backoffice_orders import order  # noqa: F401  (fixture)
from .test_storefront import run as run_shop

PAY = "mutation ($id: UUID!) { payOrder(orderId: $id) }"
CONFIRM = "mutation ($id: UUID!, $session: String!) { confirmOrderPayment(orderId: $id, sessionId: $session) }"
FINANCES = "query ($from: Date, $to: Date) { backoffice { finances(dateFrom: $from, dateTo: $to) } }"
STATUS = "mutation ($id: UUID!, $status: String!) { backoffice { setOrderStatus(orderId: $id, status: $status) } }"


def session(paid_order, paid=True, session_id="cs_test_1"):
    return {
        "id": session_id,
        "url": "https://checkout.stripe.com/c/pay/cs_test_1",
        "payment_status": "paid" if paid else "unpaid",
        "amount_total": int(paid_order.total_price * 100),
        "currency": "eur",
        "payment_intent": "pi_test_1",
        "livemode": False,
        "metadata": {"order_id": str(paid_order.uuid)},
    }


@pytest.fixture
def stripe_api():
    with (
        mock.patch("stripe.checkout.Session.create") as create,
        mock.patch("stripe.checkout.Session.retrieve") as retrieve,
        mock.patch("stripe.PaymentIntent.retrieve") as intent,
    ):
        intent.return_value = {"latest_charge": {"balance_transaction": {"fee": 450}}}
        yield {"create": create, "retrieve": retrieve, "intent": intent}


def test_pay_order_opens_a_stripe_page(order, stripe_api):  # noqa: F811
    stripe_api["create"].return_value = session(order, paid=False)
    result = run_shop(PAY, id=str(order.uuid))
    assert result.errors is None
    assert result.data["payOrder"].startswith("https://checkout.stripe.com/")
    sent = stripe_api["create"].call_args.kwargs
    assert sent["metadata"] == {"order_id": str(order.uuid)}
    assert sum(line["price_data"]["unit_amount"] * line["quantity"] for line in sent["line_items"]) == 29000
    assert f"/commande/{order.uuid}" in sent["success_url"]
    payment = Payment.objects.get()
    assert (payment.status, payment.amount, payment.stripe_session_id) == ("pending", 290, "cs_test_1")
    order.refresh_from_db()
    assert order.status == "pending"


def test_customer_back_from_stripe_marks_the_order_paid(order, stripe_api):  # noqa: F811
    stripe_api["create"].return_value = session(order, paid=False)
    run_shop(PAY, id=str(order.uuid))
    # the browser only gives the session id : the payment is read again from Stripe
    stripe_api["retrieve"].return_value = session(order)
    result = run_shop(CONFIRM, id=str(order.uuid), session="cs_test_1")
    assert result.errors is None
    assert result.data["confirmOrderPayment"]["status"] == "paid"
    payment = Payment.objects.get()
    assert (payment.status, payment.fee, payment.stripe_payment_intent_id) == ("paid", 4.5, "pi_test_1")
    # a second confirmation (webhook arriving after) changes nothing
    run_shop(CONFIRM, id=str(order.uuid), session="cs_test_1")
    assert Payment.objects.count() == 1


def test_unpaid_session_leaves_the_order_pending(order, stripe_api):  # noqa: F811
    stripe_api["create"].return_value = session(order, paid=False)
    run_shop(PAY, id=str(order.uuid))
    stripe_api["retrieve"].return_value = session(order, paid=False)
    assert run_shop(CONFIRM, id=str(order.uuid), session="cs_test_1").data["confirmOrderPayment"]["status"] == "pending"


def test_paid_order_cannot_be_paid_again(order, stripe_api):  # noqa: F811
    order.status = "paid"
    order.save()
    assert "déjà payée" in run_shop(PAY, id=str(order.uuid)).errors[0].message
    stripe_api["create"].assert_not_called()


def post_event(event):
    with mock.patch("stripe.Webhook.construct_event", return_value=event):
        return Client().post(
            "/api/payments/stripe/webhook/", data=json.dumps(event), content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1"
        )


def test_webhook_marks_paid_then_refund(order, stripe_api):  # noqa: F811
    stripe_api["create"].return_value = session(order, paid=False)
    run_shop(PAY, id=str(order.uuid))

    assert post_event({"type": "checkout.session.completed", "data": {"object": session(order)}}).status_code == 200
    order.refresh_from_db()
    assert order.status == "paid"

    charge = {"payment_intent": "pi_test_1", "amount_refunded": 9000}
    post_event({"type": "charge.refunded", "data": {"object": charge}})
    payment = Payment.objects.get()
    assert (payment.status, payment.refunded_amount) == ("partially_refunded", 90)


def test_webhook_refuses_a_bad_signature(db):
    response = Client().post("/api/payments/stripe/webhook/", data="{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="bad")
    assert response.status_code == 400


def test_finances(staff, order, stripe_api):  # noqa: F811
    stripe_api["create"].return_value = session(order, paid=False)
    run_shop(PAY, id=str(order.uuid))
    finances = run_staff(FINANCES, staff).data["backoffice"]["finances"]
    assert (finances["received"], finances["unpaid"]["count"], finances["unpaid"]["total"]) == (0, 1, 290)
    assert finances["unpaid"]["orders"][0]["triedToPay"] is True

    post_event({"type": "checkout.session.completed", "data": {"object": session(order)}})
    post_event({"type": "charge.refunded", "data": {"object": {"payment_intent": "pi_test_1", "amount_refunded": 9000}}})
    today = date.today().isoformat()
    finances = run_staff(FINANCES, staff, **{"from": today, "to": today}).data["backoffice"]["finances"]
    assert (finances["received"], finances["refunded"], finances["fees"], finances["net"]) == (290, 90, 4.5, 195.5)
    assert finances["unpaid"]["count"] == 0
    assert sorted(m["amount"] for m in finances["movements"]) == [-90, -4.5, 290]
    assert finances["months"][0]["net"] == 195.5
    # nothing before the period
    assert run_staff(FINANCES, staff, **{"from": "2000-01-01", "to": "2000-12-31"}).data["backoffice"]["finances"]["received"] == 0


def test_order_marked_paid_by_hand_counts_in_finances(staff, order):  # noqa: F811
    run_staff(STATUS, staff, id=str(order.uuid), status="paid")
    payment = Payment.objects.get()
    assert (payment.provider, payment.amount) == ("manual", 290)
    finances = run_staff(FINANCES, staff).data["backoffice"]["finances"]
    assert finances["byProvider"] == {"manual": 290}
    sheet = run_staff("query ($id: UUID!) { backoffice { orderSheet(orderId: $id) } }", staff, id=str(order.uuid))
    assert sheet.data["backoffice"]["orderSheet"]["payments"][0]["provider"] == "manual"


def test_finances_are_for_managers_only(staff, order):  # noqa: F811
    staff.groups.set([Group.objects.create(name="rnd")])
    assert run_staff(FINANCES, staff).errors
