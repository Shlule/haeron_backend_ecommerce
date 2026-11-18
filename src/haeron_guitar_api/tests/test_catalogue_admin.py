from haeron_guitar_api.models import ComponentCompatibility, Option, PartModel, PartModelOption, PartType

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run as run_backoffice, staff  # noqa: F401  (helper and fixture)
from .test_piece_products import TEMPLATE, VALIDATE
from .test_storefront import run as run_shop

OVERVIEW = "{ backoffice { catalogueOverview } }"
PART_MODEL = "query ($id: UUID!) { backoffice { cataloguePartModel(partModelId: $id) } }"
INSTRUMENT_MODEL = "query ($id: UUID!) { backoffice { catalogueInstrumentModel(instrumentModelId: $id) } }"
SAVE_TYPE = "mutation ($data: BoCodeNameInput!) { backoffice { catalogueSaveInstrumentType(data: $data) } }"
SAVE_MODEL = "mutation ($data: BoInstrumentModelInput!) { backoffice { catalogueSaveInstrumentModel(data: $data) } }"
SAVE_PART_TYPE = "mutation ($data: BoCodeNameInput!) { backoffice { catalogueSavePartType(data: $data) } }"
SAVE_OPTION = "mutation ($data: BoOptionInput!) { backoffice { catalogueSaveOption(data: $data) } }"
DELETE_OPTION = "mutation ($id: UUID!) { backoffice { catalogueDeleteOption(optionId: $id) } }"
SAVE_PART_MODEL = "mutation ($id: UUID!, $data: BoPartModelInput!) { backoffice { catalogueSavePartModel(partModelId: $id, data: $data) } }"
SAVE_VALUE = "mutation ($id: UUID!, $data: BoPartModelValueInput!) { backoffice { catalogueSaveValue(partModelId: $id, data: $data) } }"
DELETE_VALUE = "mutation ($id: UUID!) { backoffice { catalogueDeleteValue(valueId: $id) } }"
LINK = (
    "mutation ($pm: UUID!, $im: UUID!, $step: UUID!) "
    "{ backoffice { catalogueLink(partModelId: $pm, instrumentModelId: $im, componentId: $step) } }"
)
UNLINK = LINK.replace("catalogueLink", "catalogueUnlink")


def _ok(result, field):
    assert result.errors is None, result.errors
    return result.data["backoffice"][field]


def _error(result):
    assert result.errors, "an error was expected"
    return result.errors[0].message


def test_overview_lists_the_business_data(staff, starlight):  # noqa: F811
    overview = _ok(run_backoffice(OVERVIEW, staff), "catalogueOverview")
    model = next(m for m in overview["instrumentModels"] if m["name"] == "starlight")
    assert (model["productCount"], model["partModelCount"]) == (1, 1)
    body = next(pm for pm in overview["partModels"] if pm["code"] == "BD")
    assert body["valueCount"] == 4 and body["instrumentModels"] == ["starlight"]
    color = next(o for o in overview["options"] if o["name"] == "color")
    assert (color["valueCount"], color["partModelCount"]) == (2, 1)


def test_new_instrument_model_and_a_part_model_offered_on_it(staff, starlight):  # noqa: F811
    s = starlight
    bass = _ok(run_backoffice(SAVE_TYPE, staff, data={"name": "basse", "code": "b1"}), "catalogueSaveInstrumentType")
    assert bass["code"] == "B1"
    assert "2 lettres" in _error(run_backoffice(SAVE_TYPE, staff, data={"name": "x", "code": "ABC"}))
    nova = _ok(run_backoffice(SAVE_MODEL, staff, data={"name": "nova", "instrumentTypeId": bass["id"]}), "catalogueSaveInstrumentModel")
    assert "existe déjà" in _error(run_backoffice(SAVE_MODEL, staff, data={"name": "Nova", "instrumentTypeId": bass["id"]}))

    # the body step of the Starlight is offered to the body part model for the starlight only
    sheet = _ok(run_backoffice(PART_MODEL, staff, id=str(PartModel.objects.get(code="BD").uuid)), "cataloguePartModel")
    assert [(o["instrumentModel"]["name"], o["step"]["key"], o["step"]["products"]) for o in sheet["offeredIn"]] == [
        ("starlight", "body", ["Starlight"])
    ]
    body_step = sheet["offeredIn"][0]["step"]["id"]

    # a second body, offered on the starlight body step : the configurator shows it
    second = PartModel.objects.create(name="body 2", code="BD2", price=200, part_type=PartType.objects.get(code="BDY"))
    model_id = str(s["product"].instrument_model_id)
    _ok(run_backoffice(LINK, staff, pm=str(second.uuid), im=model_id, step=body_step), "catalogueLink")
    _ok(run_backoffice(LINK, staff, pm=str(second.uuid), im=model_id, step=body_step), "catalogueLink")  # twice : once
    assert ComponentCompatibility.objects.filter(part_model=second).count() == 1
    template = run_shop(TEMPLATE, id=str(s["product"].uuid)).data["configuratorTemplate"]
    body = next(c for c in template["components"] if c["key"] == "body")
    assert {pm["name"] for pm in body["part_models"]} == {"body", "body 2"}

    instrument = _ok(run_backoffice(INSTRUMENT_MODEL, staff, id=model_id), "catalogueInstrumentModel")
    step = next(st for st in instrument["steps"] if st["key"] == "body")
    assert {pm["code"] for pm in step["partModels"]} == {"BD", "BD2"}
    assert step["products"] == [{"id": str(s["product"].uuid), "name": "Starlight"}]
    # the mic step is a product choice : not a step of pieces
    assert [st["key"] for st in instrument["steps"]] == ["body"]
    # the new model has no step yet
    assert _ok(run_backoffice(INSTRUMENT_MODEL, staff, id=nova["id"]), "catalogueInstrumentModel")["steps"] == []

    _ok(run_backoffice(UNLINK, staff, pm=str(second.uuid), im=model_id, step=body_step), "catalogueUnlink")
    template = run_shop(TEMPLATE, id=str(s["product"].uuid)).data["configuratorTemplate"]
    assert {pm["name"] for pm in next(c for c in template["components"] if c["key"] == "body")["part_models"]} == {"body"}


def test_values_of_an_option_on_a_part_model(staff, starlight):  # noqa: F811
    s = starlight
    body = PartModel.objects.get(code="BD")
    color = Option.objects.get(name="color")
    sheet = _ok(
        run_backoffice(SAVE_VALUE, staff, id=str(body.uuid), data={"optionId": str(color.uuid), "code": "green", "name": "Vert", "priceDelta": "15"}),
        "catalogueSaveValue",
    )
    green = next(v for g in sheet["options"] if g["name"] == "color" for v in g["values"] if v["code"] == "green")
    assert (green["name"], green["priceDelta"], green["active"]) == ("Vert", 15, True)
    assert "déjà la valeur" in _error(run_backoffice(SAVE_VALUE, staff, id=str(body.uuid), data={"optionId": str(color.uuid), "code": "GREEN"}))

    # the new value is offered in the configurator, with its price
    config = s["configuration"](s["wood"], PartModelOption.objects.get(pk=green["id"]))
    result = run_shop(VALIDATE, id=str(s["product"].uuid), config=config).data["validateConfiguration"]
    assert result["valid"] and result["total_price"] == 100 + 100 + 15 + 30

    # a new option typed by name
    sheet = _ok(run_backoffice(SAVE_VALUE, staff, id=str(body.uuid), data={"newOptionName": "inlay", "code": "dots"}), "catalogueSaveValue")
    assert "inlay" in {g["name"] for g in sheet["options"]}

    # deactivated : kept, no longer offered
    _ok(run_backoffice(SAVE_VALUE, staff, id=str(body.uuid), data={"id": green["id"], "code": "green", "name": "Vert", "priceDelta": "20", "active": False}), "catalogueSaveValue")
    green_value = PartModelOption.objects.get(pk=green["id"])
    assert (green_value.is_active, green_value.price_delta) == (False, 20)

    # a value used by a rule is not deleted ; an unused one is
    blue = next(v for g in sheet["options"] if g["name"] == "color" for v in g["values"] if v["code"] == "blue")
    assert blue["rules"] == ["alu -> blue"]
    assert "désactive-la" in _error(run_backoffice(DELETE_VALUE, staff, id=blue["id"]))
    _ok(run_backoffice(DELETE_VALUE, staff, id=green["id"]), "catalogueDeleteValue")
    assert not PartModelOption.objects.filter(pk=green["id"]).exists()


def test_part_model_and_options_are_edited(staff, starlight):  # noqa: F811
    body = PartModel.objects.get(code="BD")
    body_type = PartType.objects.get(code="BDY")
    data = {"name": "Corps", "code": "bdx", "price": "120", "status": "discontinued", "partTypeId": str(body_type.uuid)}
    sheet = _ok(run_backoffice(SAVE_PART_MODEL, staff, id=str(body.uuid), data=data), "catalogueSavePartModel")
    assert (sheet["partModel"]["name"], sheet["partModel"]["code"], sheet["partModel"]["price"]) == ("Corps", "BDX", 120)
    assert sheet["partModel"]["discontinuedAt"]

    neck = _ok(run_backoffice(SAVE_PART_TYPE, staff, data={"name": "neck", "code": "nck"}), "catalogueSavePartType")
    assert "existe déjà" in _error(run_backoffice(SAVE_PART_TYPE, staff, data={"name": "Neck", "code": "N2"}))
    assert neck["code"] == "NCK"

    option = _ok(run_backoffice(SAVE_OPTION, staff, data={"name": "radius", "category": "manche"}), "catalogueSaveOption")
    _ok(run_backoffice(SAVE_OPTION, staff, data={"id": option["id"], "name": "radius", "description": "Rayon de la touche"}), "catalogueSaveOption")
    assert Option.objects.get(pk=option["id"]).description == "Rayon de la touche"
    # an option with values is not deleted, an unused one is
    assert "retire-les" in _error(run_backoffice(DELETE_OPTION, staff, id=str(Option.objects.get(name="color").uuid)))
    _ok(run_backoffice(DELETE_OPTION, staff, id=option["id"]), "catalogueDeleteOption")


def test_catalogue_mutations_keep_the_generic_ones():
    from haeron_backend.schema import schema

    names = {field.python_name for field in schema.get_type_by_name("BackofficeMutations").fields}
    assert {"create_option", "update_option", "delete_option", "create_instrument_model", "catalogue_save_option"} <= names
