from unittest import mock

import pytest
from rest_framework.test import APIClient

from haeron_guitar_api.models import EngravingTemplate, PartEngravingMark
from haeron_guitar_api.security import hidden_mark
from provisionning_agent.models import AgentType, ProvisionningAgent

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helper and fixture)
from .test_production import workshop  # noqa: F401  (fixture)
from .test_provision_identity import part  # noqa: F401  (fixture)

CHECK = "query ($id: UUID!, $code: String!) { backoffice { checkHiddenMark(partId: $id, code: $code) } }"
SHEET = "query ($id: UUID!) { backoffice { partSheet(partId: $id) } }"


class FakeVault:
    def get_vault_path(self, kind, **ids):
        return f"{kind}/{ids['part_model_id']}"

    def get_secret(self, path):
        return path.encode().ljust(32, b"0")[:32]


@pytest.fixture(autouse=True)
def no_hidden_code_template(db):
    # migration 0024 adds a "security" template for all models : these tests choose their own
    EngravingTemplate.objects.filter(mark_type="security").delete()


@pytest.fixture
def vault():
    with mock.patch("haeron_guitar_api.security.hidden_mark.get_vault_service", return_value=FakeVault()):
        yield


def test_the_code_depends_on_the_serial_and_the_key():
    code = hidden_mark.code_from_key("HAEG-BD-0001", b"k" * 32)
    assert len(code) == 9 and code[4] == "-" and code == hidden_mark.code_from_key("HAEG-BD-0001", b"k" * 32)
    assert code != hidden_mark.code_from_key("HAEG-BD-0002", b"k" * 32)
    assert code != hidden_mark.code_from_key("HAEG-BD-0001", b"x" * 32)  # without the key, no code
    assert not set(code) & set("ILOU")


def test_a_code_read_by_hand_is_understood():
    assert hidden_mark.normalize(" 0a1b-c2d3 ") == "0A1BC2D3"
    assert hidden_mark.normalize("oilL") == "0111"


def test_the_back_office_checks_a_code_without_showing_it(staff, part, vault):  # noqa: F811
    right = hidden_mark.code_for(part)
    assert run(CHECK, staff, id=str(part.uuid), code=right.lower()).data["backoffice"]["checkHiddenMark"]["match"]
    wrong = run(CHECK, staff, id=str(part.uuid), code="0000-0000").data["backoffice"]["checkHiddenMark"]
    assert wrong["match"] is False
    sheet = run(SHEET, staff, id=str(part.uuid)).data["backoffice"]["partSheet"]
    assert sheet["hiddenMarks"] == [] and right not in str(sheet)


def test_the_engraving_agent_gets_the_code_but_it_is_not_stored(staff, part, vault):  # noqa: F811
    EngravingTemplate.objects.create(
        name="code caché", mark_type="security", location="cavité du manche", lightburn_project_path="c.lbrn2"
    )
    token, key_hash = ProvisionningAgent.generate_token()
    ProvisionningAgent.objects.create(
        name="Laser", key_hash=key_hash, is_active=True, created_by=staff, agent_type=AgentType.ENGRAVING
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    marks = client.post("/agents/engraving/fetch/", {"mark_type": "security"}, format="json").json()["templates"][0]["marks"]
    assert [m["value"] for m in marks] == [hidden_mark.code_for(part)]
    assert PartEngravingMark.objects.get().value == ""  # the database never holds the code


SHOW = "mutation ($id: UUID!) { backoffice { hiddenMarkToEngrave(partId: $id) } }"
CONFIRM = (
    "mutation ($id: UUID!, $code: String!, $location: String!) "
    "{ backoffice { confirmHiddenMark(partId: $id, code: $code, location: $location) } }"
)


def test_engraved_from_the_back_office_then_checked(staff, part, vault):  # noqa: F811
    # no "security" template : the code is shown all the same
    shown = run(SHOW, staff, id=str(part.uuid)).data["backoffice"]["hiddenMarkToEngrave"]
    assert shown == {"code": hidden_mark.code_for(part), "location": ""}
    assert run(SHOW, staff, id=str(part.uuid)).data  # shown again while not engraved : still one mark
    assert PartEngravingMark.objects.get().status == "pending"

    where = "  sous la plaque,   côté gauche "
    assert "Indique où" in run(CONFIRM, staff, id=str(part.uuid), code=shown["code"], location=" ").errors[0].message
    wrong = run(CONFIRM, staff, id=str(part.uuid), code="0000-0000", location=where)
    assert "ne correspond pas" in wrong.errors[0].message

    sheet = run(CONFIRM, staff, id=str(part.uuid), code=shown["code"], location=where).data["backoffice"]["confirmHiddenMark"]
    assert sheet["hiddenMarks"][0] == {**sheet["hiddenMarks"][0], "status": "confirmed", "location": "sous la plaque, côté gauche"}
    assert "Code caché gravé et contrôlé" in [event["title"] for event in sheet["history"]]
    # the place is written by hand : the code stays the one of the serial number and the key
    assert run(CHECK, staff, id=str(part.uuid), code=shown["code"]).data["backoffice"]["checkHiddenMark"]["match"]
    # engraved and checked : the code is no longer shown
    assert "déjà gravé" in run(SHOW, staff, id=str(part.uuid)).errors[0].message


def test_the_template_places_are_only_suggestions(staff, part, vault):  # noqa: F811
    EngravingTemplate.objects.create(
        name="code caché", mark_type="security", location="talon ; cavité ; sous la plaque", lightburn_project_path="-"
    )
    sheet = run(SHEET, staff, id=str(part.uuid)).data["backoffice"]["partSheet"]
    assert (sheet["hiddenMarkLocation"], sheet["hiddenMarkSuggestions"]) == (None, ["talon", "cavité", "sous la plaque"])
    code = run(SHOW, staff, id=str(part.uuid)).data["backoffice"]["hiddenMarkToEngrave"]["code"]
    sheet = run(CONFIRM, staff, id=str(part.uuid), code=code, location="dans le logement du micro").data["backoffice"]["confirmHiddenMark"]
    assert sheet["hiddenMarks"][0]["location"] == "dans le logement du micro"


def test_the_engraving_agent_gets_hidden_codes_only_when_asked(staff, part, vault):  # noqa: F811
    EngravingTemplate.objects.create(
        name="code caché", mark_type="security", location="talon ; cavité", lightburn_project_path="c.lbrn2"
    )
    token, key_hash = ProvisionningAgent.generate_token()
    ProvisionningAgent.objects.create(
        name="Laser", key_hash=key_hash, is_active=True, created_by=staff, agent_type=AgentType.ENGRAVING
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    everything = client.post("/agents/engraving/fetch/", {}, format="json").json()["templates"]
    assert "security" not in [template["mark_type"] for template in everything]
    marks = client.post("/agents/engraving/fetch/", {"mark_type": "security"}, format="json").json()["templates"][0]["marks"]
    assert marks[0]["location"] in {"talon", "cavité"}
    # fetched again : the same mark, not a second one at another place
    again = client.post("/agents/engraving/fetch/", {"mark_type": "security"}, format="json").json()["templates"][0]["marks"]
    assert [m["mark_uuid"] for m in again] == [marks[0]["mark_uuid"]]
