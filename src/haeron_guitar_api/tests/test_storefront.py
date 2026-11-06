import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from haeron_backend.schema import schema
from haeron_guitar_api.models import Product, ProductType

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)

ADD = "mutation ($input: AddToCartInput!) { addToCart(input: $input) }"
REMOVE = "mutation ($id: UUID!, $key: String) { removeFromCart(itemId: $id, cartKey: $key) }"
CART = "query ($key: String) { shopCart(cartKey: $key) }"


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
