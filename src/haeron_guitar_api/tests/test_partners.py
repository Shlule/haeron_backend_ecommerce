import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from haeron_guitar_api.cartItem.cartItem_dto import createCartItemDTO
from haeron_guitar_api.cartItem.cartItem_service import CartItemService
from haeron_guitar_api.checkout.checkout_dto import CustomerDTO
from haeron_guitar_api.checkout.checkout_service import CheckoutService
from haeron_guitar_api.models import Partner, Payment
from haeron_guitar_api.payments.payment_service import PaymentService

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helper and fixture)
from .test_storefront import run as run_shop

SAVE = "mutation ($id: UUID, $data: BoPartnerInput!) { backoffice { savePartner(partnerId: $id, data: $data) } }"
PAYOUT = (
    "mutation ($id: UUID!, $data: BoPartnerPayoutInput!) { backoffice { recordPartnerPayout(partnerId: $id, data: $data) } }"
)
PARTNERS = "{ backoffice { partners } }"
PARTNER = "query ($id: UUID!) { backoffice { partner(partnerId: $id) } }"
FINANCES = "{ backoffice { finances } }"
CODE = "query ($code: String!) { shopPartnerCode(code: $code) }"


def place(s, code="", key="guest"):
    dto = createCartItemDTO(product_id=s["product"].uuid, configuration=s["configuration"](s["alu"], s["blue"]))
    CartItemService.add_item(dto, session_key=key)
    customer = CustomerDTO("jean@example.com", "Jean", "Dupont", "1 rue de la Paix", "75002", "Paris")
    return CheckoutService.checkout(uuid.uuid4(), customer, session_key=key, partner_code=code)


def pay(order, refunded=0):
    Payment.objects.create(
        order=order, provider="manual", status="partially_refunded" if refunded else "paid",
        amount=order.total_price, refunded_amount=refunded, paid_at=order.created_at,
        refunded_at=order.created_at if refunded else None,
    )
    order.status = "paid"
    order.save(update_fields=["status"])


def save(staff, **data):  # noqa: F811
    partner_id = data.pop("id", None)
    result = run(SAVE, staff, id=partner_id, data={"name": "Atelier Martin", "code": "martin", **data})
    return result.errors[0].message if result.errors else result.data["backoffice"]["savePartner"]


def test_a_partner_is_created_and_changed(staff):  # noqa: F811
    partner = save(staff, discountPercent="5", commissionPercent="10")
    assert (partner["code"], partner["discountPercent"], partner["commissionPercent"]) == ("MARTIN", 5, 10)
    assert partner["link"].endswith("/?ref=MARTIN")
    changed = save(staff, id=partner["id"], code="MARTIN-2026", discountPercent="7.5")
    assert (changed["code"], changed["discountPercent"]) == ("MARTIN-2026", 7.5)
    # a second partner cannot take the same code, and a code has no space or accent
    assert "déjà pris" in save(staff, name="Autre", code="martin-2026")
    assert "3 à 40 caractères" in save(staff, name="Autre", code="é")
    assert "entre 0 et 99" in save(staff, name="Autre", code="AUTRE", discountPercent="100")
    assert len(run(PARTNERS, staff).data["backoffice"]["partners"]["results"]) == 1


def test_the_code_gives_its_discount_at_checkout(staff, starlight):  # noqa: F811
    save(staff, discountPercent="5", commissionPercent="10")
    assert run_shop(CODE, code=" martin ").data["shopPartnerCode"] == {"code": "MARTIN", "discountPercent": 5.0}
    order = place(starlight, code="Martin")
    assert (order.total_price, order.discount_amount, order.partner_code) == (Decimal("275.50"), Decimal("14.50"), "MARTIN")
    # an unknown code is refused, not silently forgotten
    with pytest.raises(Exception, match="pas valide"):
        place(starlight, code="NOPE", key="other")


def test_a_switched_off_or_ended_code_does_not_work(staff, starlight):  # noqa: F811
    partner = save(staff)
    save(staff, id=partner["id"], isActive=False)
    assert run_shop(CODE, code="MARTIN").data["shopPartnerCode"] is None
    save(staff, id=partner["id"], isActive=True, validUntil=(date.today() - timedelta(days=1)).isoformat())
    assert run_shop(CODE, code="MARTIN").data["shopPartnerCode"] is None
    save(staff, id=partner["id"], validUntil=date.today().isoformat())
    assert run_shop(CODE, code="MARTIN").data["shopPartnerCode"] is not None


def test_changing_the_rates_keeps_past_orders(staff, starlight):  # noqa: F811
    partner = save(staff, discountPercent="5", commissionPercent="10")
    first = place(starlight, code="MARTIN")
    save(staff, id=partner["id"], discountPercent="10", commissionPercent="20")
    second = place(starlight, code="MARTIN", key="other")
    assert (first.discount_percent, first.commission_percent) == (5, 10)
    assert (second.discount_percent, second.commission_percent, second.total_price) == (10, 20, Decimal("261.00"))


def test_commissions_payouts_and_statement(staff, starlight):  # noqa: F811
    partner = save(staff, discountPercent="5", commissionPercent="10")
    paid, refunded, unpaid = (place(starlight, "MARTIN", key) for key in ("a", "b", "c"))
    pay(paid)
    pay(refunded, refunded=Decimal("75.50"))  # 200 kept
    # not paid yet : no commission
    sheet = run(PARTNER, staff, id=partner["id"]).data["backoffice"]["partner"]
    assert (sheet["orderCount"], sheet["sales"], sheet["earned"]) == (2, 475.5, 47.55)
    assert {o["reference"]: o["commission"] for o in sheet["orders"]}[str(unpaid.uuid)[:8].upper()] == 0

    result = run(PAYOUT, staff, id=partner["id"], data={"amount": "40", "paidOn": date.today().isoformat(), "paymentMethod": "transfer"})
    sheet = result.data["backoffice"]["recordPartnerPayout"]
    assert (sheet["paidOut"], sheet["due"]) == (40, 7.55)
    month = date.today().strftime("%Y-%m")
    assert sheet["months"][0] == {"month": month, "orders": 2, "sales": 475.5, "earned": 47.55, "paidOut": 40}
    assert sheet["years"][0]["das2"] is False

    # a cancelled order earns nothing
    paid.status = "cancelled"
    paid.save(update_fields=["status"])
    assert run(PARTNER, staff, id=partner["id"]).data["backoffice"]["partner"]["earned"] == 20

    # the payout is an expense of the finances
    finances = run(FINANCES, staff).data["backoffice"]["finances"]
    assert {c["category"]: c["ttc"] for c in finances["expenses"]["byCategory"]}["partners"] == 40
    assert any(m["kind"] == "commission" and m["amount"] == -40 for m in finances["movements"])


def test_das2_above_1200_euros_a_year(staff):  # noqa: F811
    partner = save(staff)
    run(PAYOUT, staff, id=partner["id"], data={"amount": "1200.01", "paidOn": date.today().isoformat()})
    assert run(PARTNER, staff, id=partner["id"]).data["backoffice"]["partner"]["years"][0]["das2"] is True


def test_stripe_takes_the_discount_off(staff, starlight):  # noqa: F811
    save(staff, discountPercent="5")
    order = place(starlight, code="MARTIN")
    with (
        mock.patch("stripe.checkout.Session.create") as create,
        mock.patch("stripe.Coupon.create", return_value={"id": "coupon_1"}) as coupon,
    ):
        create.return_value = {"id": "cs_1", "url": "https://checkout.stripe.com/x", "amount_total": 27550}
        PaymentService.start_checkout(order.uuid)
    assert coupon.call_args.kwargs["amount_off"] == 1450
    assert create.call_args.kwargs["discounts"] == [{"coupon": "coupon_1"}]
    assert Payment.objects.get().amount == Decimal("275.50")


def test_partners_are_for_managers_only(db):
    user = get_user_model().objects.create_user(username="rnd", email="rnd@example.com", password="x")
    user.groups.add(Group.objects.create(name="rnd"))
    assert run(PARTNERS, user).errors
    assert not Partner.objects.exists()
