import uuid

import pytest
from django.contrib.auth.models import Group

from haeron_guitar_api.cartItem.cartItem_dto import createCartItemDTO
from haeron_guitar_api.cartItem.cartItem_service import CartItemService
from haeron_guitar_api.checkout.checkout_dto import CustomerDTO
from haeron_guitar_api.checkout.checkout_service import CheckoutService

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helpers and fixture)

LIST = "query ($status: String, $search: String) { backoffice { orders(status: $status, search: $search) } }"
SHEET = "query ($id: UUID!) { backoffice { orderSheet(orderId: $id) } }"
STATUS = "mutation ($id: UUID!, $status: String!) { backoffice { setOrderStatus(orderId: $id, status: $status) } }"


@pytest.fixture
def order(starlight):  # noqa: F811
    s = starlight
    dto = createCartItemDTO(product_id=s["product"].uuid, configuration=s["configuration"](s["alu"], s["blue"]))
    CartItemService.add_item(dto, session_key="guest")
    customer = CustomerDTO("jean@example.com", "Jean", "Dupont", "1 rue de la Paix", "75002", "Paris")
    return CheckoutService.checkout(uuid.uuid4(), customer, session_key="guest")


def test_orders_list_and_search(staff, order):  # noqa: F811
    listed = run(LIST, staff).data["backoffice"]["orders"]
    assert listed["totalCount"] == 1
    assert listed["results"][0]["reference"] == str(order.uuid)[:8].upper()
    assert listed["results"][0]["itemCount"] == 1
    assert run(LIST, staff, search="dupont").data["backoffice"]["orders"]["totalCount"] == 1
    assert run(LIST, staff, search=str(order.uuid)[:8].upper()).data["backoffice"]["orders"]["totalCount"] == 1
    assert run(LIST, staff, status="paid").data["backoffice"]["orders"]["totalCount"] == 0


def test_order_sheet_has_the_composition(staff, order, starlight):  # noqa: F811
    sheet = run(SHEET, staff, id=str(order.uuid)).data["backoffice"]["orderSheet"]
    assert (sheet["city"], sheet["total"]) == ("Paris", 290)
    components = {c["component"]: c for c in sheet["items"][0]["components"]}
    body = components["body"]
    assert (body["partModel"]["name"], body["partModel"]["code"]) == ("body", "BD")
    assert {(o["option"], o["value"], o["priceDelta"]) for o in body["options"]} == {("material", "alu", 50), ("color", "blue", 10)}
    assert components["mic"]["product"] == "mic A"


def test_set_order_status(staff, order):  # noqa: F811
    sheet = run(STATUS, staff, id=str(order.uuid), status="processing").data["backoffice"]["setOrderStatus"]
    assert sheet["status"] == "processing"
    assert run(STATUS, staff, id=str(order.uuid), status="lost").errors


def test_orders_need_a_staff_role(staff, order):  # noqa: F811
    staff.groups.set([Group.objects.create(name="customer")])
    assert run(LIST, staff).errors
