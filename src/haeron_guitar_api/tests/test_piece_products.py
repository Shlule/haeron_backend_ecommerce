from haeron_guitar_api.models import Product

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run as run_backoffice, staff  # noqa: F401  (helper and fixture)
from .test_storefront import run as run_shop

FORM = "{ backoffice { pieceProductForm } }"
CREATE = "mutation ($data: BoPieceProductsInput!) { backoffice { createPieceProducts(data: $data) } }"
TEMPLATE = "query ($id: UUID!) { configuratorTemplate(productId: $id) }"
VALIDATE = "query ($id: UUID!, $config: JSON!) { validateConfiguration(productId: $id, configuration: $config) }"


def _body_piece(staff, starlight):  # noqa: F811
    form = run_backoffice(FORM, staff).data["backoffice"]["pieceProductForm"]
    model = form["instrumentModels"][0]
    return model, next(p for p in model["pieces"] if p["key"] == "body")


def test_form_lists_the_configurable_pieces_of_each_model(staff, starlight):  # noqa: F811
    starlight["product"].model_3d = "/models/starlight.glb"
    starlight["product"].save()
    model, body = _body_piece(staff, starlight)
    assert model["name"] == "starlight"
    assert model["model3d"] == "/models/starlight.glb"
    # only custom pieces : the mic (product choice) is not a piece to sell alone
    assert [p["key"] for p in model["pieces"]] == ["body"]
    assert body["partModels"][0]["code"] == "BD"
    assert body["product"] is None


def test_a_piece_sold_alone_keeps_its_options_prices_and_rules(staff, starlight):  # noqa: F811
    s = starlight
    model, body = _body_piece(staff, s)
    data = {"instrumentModelId": model["id"], "pieces": [{"componentId": body["componentId"], "name": "Corps Starlight", "model3d": "/models/starlight.glb"}]}
    result = run_backoffice(CREATE, staff, data=data)
    assert result.errors is None
    product = Product.objects.get(name="Corps Starlight")
    assert product.instrument_model == s["product"].instrument_model

    # the configurator shows the body only
    template = run_shop(TEMPLATE, id=str(product.uuid)).data["configuratorTemplate"]
    assert [c["key"] for c in template["components"]] == ["body"]
    assert template["product"]["model3d"] == "/models/starlight.glb"

    def configuration(*options):
        return {"body": s["configuration"](*options)["body"]}

    valid = run_shop(VALIDATE, id=str(product.uuid), config=configuration(s["alu"], s["blue"])).data["validateConfiguration"]
    assert valid["valid"] and valid["total_price"] == 160  # part model 100 + alu 50 + blue 10
    # the rule of the guitar body still applies : aluminium must be blue
    refused = run_shop(VALIDATE, id=str(product.uuid), config=configuration(s["alu"], s["red"])).data["validateConfiguration"]
    assert refused["valid"] is False and refused["violations"]

    # the guitar itself is unchanged
    guitar = run_shop(TEMPLATE, id=str(s["product"].uuid)).data["configuratorTemplate"]
    assert {c["key"] for c in guitar["components"]} == {"body", "mic"}

    shop = {p["name"]: p for p in run_shop("{ shopProducts }").data["shopProducts"]}
    assert shop["Corps Starlight"]["piece"] is True and shop["Starlight"]["piece"] is False

    # the form now shows the product, and the piece cannot be sold alone twice
    assert _body_piece(staff, s)[1]["product"]["name"] == "Corps Starlight"
    data["pieces"][0]["name"] = "Autre corps"
    assert "déjà vendue seule" in run_backoffice(CREATE, staff, data=data).errors[0].message


def test_bad_piece_or_name_creates_nothing(staff, starlight):  # noqa: F811
    model, body = _body_piece(staff, starlight)
    before = Product.objects.count()
    blank = {"instrumentModelId": model["id"], "pieces": [{"componentId": body["componentId"], "name": "  "}]}
    assert run_backoffice(CREATE, staff, data=blank).errors
    taken = {"instrumentModelId": model["id"], "pieces": [{"componentId": body["componentId"], "name": "starlight"}]}
    assert "déjà" in run_backoffice(CREATE, staff, data=taken).errors[0].message
    assert Product.objects.count() == before


PRODUCTS = "{ backoffice { catalogueProducts } }"
CREATE_PRODUCT = "mutation ($data: BoNewProductInput!) { backoffice { createShopProduct(data: $data) } }"
VISIBLE = "mutation ($id: UUID!, $visible: Boolean!) { backoffice { setProductVisible(productId: $id, visible: $visible) } }"
ADD = "mutation ($input: AddToCartInput!) { addToCart(input: $input) }"


def test_new_product_can_be_hidden_from_the_shop(staff, starlight):  # noqa: F811
    created = run_backoffice(CREATE_PRODUCT, staff, data={"name": "Sangle cuir", "price": "35", "visible": False})
    assert created.errors is None
    strap = created.data["backoffice"]["createShopProduct"]
    assert (strap["kind"], strap["visible"], strap["price"]) == ("simple", False, 35)
    kinds = {p["name"]: p["kind"] for p in run_backoffice(PRODUCTS, staff).data["backoffice"]["catalogueProducts"]}
    assert kinds["Starlight"] == "configurable" and kinds["Sangle cuir"] == "simple"

    # hidden : not in the shop and not addable, even with its id
    assert "Sangle cuir" not in {p["name"] for p in run_shop("{ shopProducts }").data["shopProducts"]}
    assert "plus en vente" in run_shop(ADD, input={"productId": strap["id"]}).errors[0].message

    shown = run_backoffice(VISIBLE, staff, id=strap["id"], visible=True).data["backoffice"]["setProductVisible"]
    assert shown["visible"] is True
    assert "Sangle cuir" in {p["name"] for p in run_shop("{ shopProducts }").data["shopProducts"]}
    assert run_shop(ADD, input={"productId": strap["id"]}).errors is None

    # a hidden configurable product can still be tried in the configurator
    run_backoffice(VISIBLE, staff, id=str(starlight["product"].uuid), visible=False)
    template = run_shop(TEMPLATE, id=str(starlight["product"].uuid)).data["configuratorTemplate"]
    assert template["product"]["visible"] is False
    assert "Starlight" not in {p["name"] for p in run_shop("{ shopProducts }").data["shopProducts"]}
    assert run_backoffice(CREATE_PRODUCT, staff, data={"name": "sangle CUIR"}).errors
