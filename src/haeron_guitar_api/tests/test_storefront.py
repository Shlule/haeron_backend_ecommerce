import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from haeron_backend.schema import schema
from haeron_guitar_api.models import Order, Product, ProductType

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)

ADD = "mutation ($input: AddToCartInput!) { addToCart(input: $input) }"
REMOVE = "mutation ($id: UUID!, $key: String) { removeFromCart(itemId: $id, cartKey: $key) }"
CART = "query ($key: String) { shopCart(cartKey: $key) }"
UPDATE = "mutation ($input: UpdateCartItemInput!) { updateCartItem(input: $input) }"
ORDER = "mutation ($input: PlaceOrderInput!) { placeOrder(input: $input) }"
CUSTOMER = {
    "email": "jean@example.com",
    "firstName": "Jean",
    "lastName": "Dupont",
    "address": "1 rue de la Paix",
    "postalCode": "75002",
    "city": "Paris",
    "acceptedTerms": True,
    "acceptedColourTerms": True,
}


def run(query, **variables):
    request = RequestFactory().post("/graphql/")
    request.user = AnonymousUser()
    return schema.execute_sync(query, variable_values=variables, context_value={"request": request})


@pytest.fixture
def case(starlight):  # noqa: F811
    product = starlight["product"]
    product.model_3d = "/models/starlight.glb"
    product.save()
    simple = ProductType.objects.get(code="simple")
    starlight["strings"] = Product.objects.create(name="Strings", price=15, product_type=simple)
    return starlight


def test_shop_products_split_configurable(case):
    products = {p["name"]: p for p in run("{ shopProducts }").data["shopProducts"]}
    assert products["Starlight"]["configurable"] is True
    assert products["Starlight"]["model3d"] == "/models/starlight.glb"
    assert products["Strings"]["configurable"] is False


def test_add_without_key_creates_cart_and_accumulates(case):
    first = run(ADD, input={"productId": str(case["strings"].uuid)}).data["addToCart"]
    key = first["cartKey"]
    assert key and first["count"] == 1
    second = run(ADD, input={"productId": str(case["strings"].uuid), "quantity": 2, "cartKey": key}).data["addToCart"]
    assert second["cartKey"] == key
    assert len(second["items"]) == 1
    assert (second["count"], second["total"]) == (3, 45)
    assert run(CART, key=key).data["shopCart"]["count"] == 3


def test_add_configured_product_with_details(case):
    s = case
    cart = run(ADD, input={"productId": str(s["product"].uuid), "configuration": s["configuration"](s["alu"], s["blue"])})
    item = cart.data["addToCart"]["items"][0]
    assert item["total"] == 290
    body = next(d for d in item["details"] if d["component"] == "body")
    assert body["product"] == "body"
    assert {"option": "color", "value": "blue"} in body["values"]


def test_add_refuses_configuration_violating_rule(case):
    s = case
    result = run(ADD, input={"productId": str(s["product"].uuid), "configuration": s["configuration"](s["alu"], s["red"])})
    assert result.errors
    assert result.data is None


def test_add_refuses_bad_quantity(case):
    assert run(ADD, input={"productId": str(case["strings"].uuid), "quantity": 0}).errors


def test_unknown_key_is_replaced(case):
    cart = run(ADD, input={"productId": str(case["strings"].uuid), "cartKey": "chosen-by-client"}).data["addToCart"]
    assert cart["cartKey"] != "chosen-by-client"


def test_remove_needs_the_cart_key(case):
    cart = run(ADD, input={"productId": str(case["strings"].uuid)}).data["addToCart"]
    item_id = cart["items"][0]["id"]
    refused = run(REMOVE, id=item_id, key="someone-else")
    assert refused.errors[0].message == "Cet article n'est pas dans votre panier."
    emptied = run(REMOVE, id=item_id, key=cart["cartKey"]).data["removeFromCart"]
    assert emptied["count"] == 0


def test_unknown_cart_is_empty(case):
    assert run(CART, key="nothing").data["shopCart"] == {"cartKey": None, "count": 0, "total": 0, "items": []}


def test_two_products_without_configuration_are_two_lines(case):
    s = case
    key = run(ADD, input={"productId": str(s["strings"].uuid)}).data["addToCart"]["cartKey"]
    simple = Product.objects.create(name="Cover", price=120, product_type=s["strings"].product_type)
    cart = run(ADD, input={"productId": str(simple.uuid), "cartKey": key}).data["addToCart"]
    assert sorted((i["name"], i["quantity"]) for i in cart["items"]) == [("Cover", 1), ("Strings", 1)]


def test_update_quantity(case):
    cart = run(ADD, input={"productId": str(case["strings"].uuid)}).data["addToCart"]
    item, key = cart["items"][0], cart["cartKey"]
    updated = run(UPDATE, input={"itemId": item["id"], "quantity": 4, "cartKey": key}).data["updateCartItem"]
    assert (updated["count"], updated["total"]) == (4, 60)
    assert run(UPDATE, input={"itemId": item["id"], "quantity": 0, "cartKey": key}).errors
    assert run(UPDATE, input={"itemId": item["id"], "quantity": 2, "cartKey": "other"}).errors


def test_reconfigure_line(case):
    s = case
    cart = run(ADD, input={"productId": str(s["product"].uuid), "configuration": s["configuration"](s["wood"], s["red"])}).data["addToCart"]
    item, key = cart["items"][0], cart["cartKey"]
    assert item["configurable"] is True
    assert item["configuration"] == s["configuration"](s["wood"], s["red"])

    new = s["configuration"](s["alu"], s["blue"])
    updated = run(UPDATE, input={"itemId": item["id"], "configuration": new, "cartKey": key}).data["updateCartItem"]
    assert updated["items"][0]["configuration"] == new
    assert updated["total"] == 290

    refused = run(UPDATE, input={"itemId": item["id"], "configuration": s["configuration"](s["alu"], s["red"]), "cartKey": key})
    assert refused.errors


def test_reconfigure_to_an_existing_line_merges_them(case):
    s = case
    first = run(ADD, input={"productId": str(s["product"].uuid), "configuration": s["configuration"](s["alu"], s["blue"])}).data["addToCart"]
    key = first["cartKey"]
    second = run(
        ADD, input={"productId": str(s["product"].uuid), "configuration": s["configuration"](s["wood"], s["red"]), "cartKey": key}
    ).data["addToCart"]
    other = next(i for i in second["items"] if i["id"] != first["items"][0]["id"])
    merged = run(UPDATE, input={"itemId": other["id"], "configuration": s["configuration"](s["alu"], s["blue"]), "cartKey": key})
    items = merged.data["updateCartItem"]["items"]
    assert [(i["id"], i["quantity"]) for i in items] == [(first["items"][0]["id"], 2)]


def test_place_order_closes_the_cart(case):
    cart = run(ADD, input={"productId": str(case["strings"].uuid), "quantity": 2}).data["addToCart"]
    key = cart["cartKey"]
    idempotency = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
    order = run(ORDER, input={**CUSTOMER, "idempotencyKey": idempotency, "cartKey": key}).data["placeOrder"]
    assert (order["status"], order["total"], order["items"][0]["quantity"]) == ("pending", 30, 2)
    assert len(order["reference"]) == 8
    # same key : same order, the cart is now empty
    again = run(ORDER, input={**CUSTOMER, "idempotencyKey": idempotency, "cartKey": key}).data["placeOrder"]
    assert again["id"] == order["id"]
    assert run(CART, key=key).data["shopCart"]["count"] == 0
    shown = run("query ($id: UUID!) { shopOrder(orderId: $id) }", id=order["id"]).data["shopOrder"]
    assert shown["city"] == "Paris"
    saved = Order.objects.get(uuid=order["id"])
    assert saved.terms_accepted_at and saved.colour_terms_accepted_at


@pytest.mark.parametrize("box", ["acceptedTerms", "acceptedColourTerms"])
def test_place_order_needs_both_boxes(case, box):
    key = run(ADD, input={"productId": str(case["strings"].uuid)}).data["addToCart"]["cartKey"]
    result = run(ORDER, input={**CUSTOMER, box: False, "idempotencyKey": "3f2504e0-4f89-11d3-9a0c-0305e82c3303", "cartKey": key})
    assert "accepter" in result.errors[0].message
    assert not Order.objects.exists()
    assert run(CART, key=key).data["shopCart"]["count"] == 1  # the cart is kept


def test_place_order_refuses_invalid_contact(case):
    key = run(ADD, input={"productId": str(case["strings"].uuid)}).data["addToCart"]["cartKey"]
    result = run(ORDER, input={**CUSTOMER, "email": "pas-un-mail", "idempotencyKey": "3f2504e0-4f89-11d3-9a0c-0305e82c3302", "cartKey": key})
    assert result.errors[0].message == "Cette adresse e-mail n'est pas valide."
