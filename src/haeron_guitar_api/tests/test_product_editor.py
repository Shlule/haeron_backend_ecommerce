from haeron_guitar_api.models import PartModel, PartType, Product, ProductComponent

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run as run_backoffice, staff  # noqa: F401  (helper and fixture)
from .test_piece_products import CREATE as CREATE_PIECES, TEMPLATE, VALIDATE
from .test_storefront import run as run_shop

EDITOR = "query ($id: UUID!) { backoffice { productEditor(productId: $id) } }"
CATALOG = "{ backoffice { productEditorCatalog } }"
CREATE = "mutation ($data: BoProductInput!) { backoffice { createConfigurableProduct(data: $data) } }"
UPDATE = "mutation ($id: UUID!, $data: BoProductInput!) { backoffice { saveProduct(productId: $id, data: $data) } }"
ADD_STEP = (
    "mutation ($id: UUID!, $key: String!, $type: String!, $fixed: UUID) "
    "{ backoffice { addTemplateStep(productId: $id, key: $key, sourceType: $type, fixedProductId: $fixed) } }"
)
UPDATE_STEP = (
    "mutation ($id: UUID!, $step: UUID!, $data: BoProductComponentInput!) "
    "{ backoffice { saveTemplateStep(productId: $id, componentId: $step, data: $data) } }"
)
REMOVE_STEP = "mutation ($id: UUID!, $step: UUID!) { backoffice { removeTemplateStep(productId: $id, componentId: $step) } }"


def _ok(result, field):
    assert result.errors is None, result.errors
    return result.data["backoffice"][field]


def test_editor_shows_the_template_of_the_existing_guitar(staff, starlight):  # noqa: F811
    editor = _ok(run_backoffice(EDITOR, staff, id=str(starlight["product"].uuid)), "productEditor")
    steps = {c["key"]: c for c in editor["components"]}
    assert steps["body"]["sourceType"] == "custom_piece"
    assert steps["body"]["partModelIds"] == [str(PartModel.objects.get(code="BD").uuid)]
    assert steps["body"]["rules"][0]["name"] == "alu -> blue"
    assert len(steps["mic"]["choiceProductIds"]) == 1
    catalog = _ok(run_backoffice(CATALOG, staff), "productEditorCatalog")
    body = next(pm for pm in catalog["partModels"] if pm["code"] == "BD")
    assert {g["option"] for g in body["options"]} == {"color", "material"}


def test_new_guitar_from_scratch_works_in_the_configurator(staff, starlight):  # noqa: F811
    s = starlight
    model_id = str(s["product"].instrument_model_id)
    nova = _ok(run_backoffice(CREATE, staff, data={"name": "Nova", "price": "500", "instrumentModelId": model_id}), "createConfigurableProduct")
    product_id = nova["product"]["id"]
    assert nova["product"]["visible"] is False and nova["components"] == []

    step = _ok(run_backoffice(ADD_STEP, staff, id=product_id, key="corps", type="custom_piece"), "addTemplateStep")["components"][0]
    body_model = str(PartModel.objects.get(code="BD").uuid)
    _ok(run_backoffice(UPDATE_STEP, staff, id=product_id, step=step["id"], data={"partModelIds": [body_model]}), "saveTemplateStep")
    strings = Product.objects.get(name="mic A")
    # a fixed step needs its product
    assert run_backoffice(ADD_STEP, staff, id=product_id, key="cordes", type="fixed").errors
    _ok(run_backoffice(ADD_STEP, staff, id=product_id, key="cordes", type="fixed", fixed=str(strings.uuid)), "addTemplateStep")
    # same key twice, or a bad key
    assert "déjà" in run_backoffice(ADD_STEP, staff, id=product_id, key="corps", type="custom_piece").errors[0].message
    assert run_backoffice(ADD_STEP, staff, id=product_id, key="Corps Sup", type="custom_piece").errors

    template = run_shop(TEMPLATE, id=product_id).data["configuratorTemplate"]
    assert {c["key"] for c in template["components"]} == {"corps", "cordes"}
    config = {"corps": {"part_model_id": body_model, "part_model_option_ids": [str(s["wood"].uuid)]}, "cordes": {}}
    result = run_shop(VALIDATE, id=product_id, config=config).data["validateConfiguration"]
    assert result["valid"], result
    assert result["total_price"] == 500 + 100 + 30  # base + body + strings
    # hidden until shown
    assert "Nova" not in {p["name"] for p in run_shop("{ shopProducts }").data["shopProducts"]}
    shown = _ok(run_backoffice(UPDATE, staff, id=product_id, data={"name": "Nova", "price": "500", "instrumentModelId": model_id, "visible": True}), "saveProduct")
    assert shown["product"]["visible"] is True
    assert "Nova" in {p["name"] for p in run_shop("{ shopProducts }").data["shopProducts"]}


def test_a_shared_step_is_changed_everywhere_and_removed_only_here(staff, starlight):  # noqa: F811
    s = starlight
    guitar_id = str(s["product"].uuid)
    form = run_backoffice("{ backoffice { pieceProductForm } }", staff).data["backoffice"]["pieceProductForm"]
    model = form["instrumentModels"][0]
    body = next(p for p in model["pieces"] if p["key"] == "body")
    run_backoffice(CREATE_PIECES, staff, data={"instrumentModelId": model["id"], "pieces": [{"componentId": body["componentId"], "name": "Corps seul"}]})
    piece = Product.objects.get(name="Corps seul")

    editor = _ok(run_backoffice(EDITOR, staff, id=guitar_id), "productEditor")
    step = next(c for c in editor["components"] if c["key"] == "body")
    assert step["sharedWith"] == [{"id": str(piece.uuid), "name": "Corps seul"}]

    # a second body model offered on the guitar is offered on the piece too
    other = PartModel.objects.create(name="body 2", code="BD2", price=200, part_type=PartType.objects.get(code="BDY"))
    ids = step["partModelIds"] + [str(other.uuid)]
    _ok(run_backoffice(UPDATE_STEP, staff, id=guitar_id, step=step["id"], data={"partModelIds": ids}), "saveTemplateStep")
    piece_template = run_shop(TEMPLATE, id=str(piece.uuid)).data["configuratorTemplate"]
    assert {pm["name"] for pm in piece_template["components"][0]["part_models"]} == {"body", "body 2"}

    # taken out of the piece : the guitar keeps it
    _ok(run_backoffice(REMOVE_STEP, staff, id=str(piece.uuid), step=step["id"]), "removeTemplateStep")
    assert ProductComponent.objects.filter(pk=step["id"]).exists()
    guitar = run_shop(TEMPLATE, id=guitar_id).data["configuratorTemplate"]
    assert {c["key"] for c in guitar["components"]} == {"body", "mic"}


def test_instrument_model_cannot_change_under_chosen_pieces(staff, starlight):  # noqa: F811
    product = starlight["product"]
    data = {"name": "Starlight", "price": "100", "instrumentModelId": None}
    assert "Retire d'abord" in run_backoffice(UPDATE, staff, id=str(product.uuid), data=data).errors[0].message
    # renaming and pricing keep the template
    data["instrumentModelId"] = str(product.instrument_model_id)
    data["price"] = "120"
    _ok(run_backoffice(UPDATE, staff, id=str(product.uuid), data=data), "saveProduct")
    product.refresh_from_db()
    assert product.price == 120 and product.product_schema_id


def test_generic_product_pages_keep_their_own_mutations():
    from haeron_backend.schema import schema

    # « Données » : createProduct / updateProduct / updateProductComponent stay the generic ones
    mutations = schema.get_type_by_name("BackofficeMutations").fields
    names = {field.python_name: field for field in mutations}
    assert {"create_product", "update_product", "update_product_component", "save_product", "create_shop_product"} <= set(names)
    assert schema.get_type_by_name("BoProductCreateInput") is not None
