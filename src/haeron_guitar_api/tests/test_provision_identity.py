from unittest import mock

import pytest
from rest_framework.test import APIClient

from haeron_guitar_api.models import Part, PartNFCIdentity
from provisionning_agent.models import ProvisionningAgent

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run, staff  # noqa: F401  (helper and fixture)
from .test_production import BUILD_PART, workshop  # noqa: F401  (fixture)

URL = "/agents/provision-identity/"


@pytest.fixture
def agent(staff):  # noqa: F811
    token, key_hash = ProvisionningAgent.generate_token()
    ProvisionningAgent.objects.create(name="Poste 1", key_hash=key_hash, is_active=True, created_by=staff)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def part(staff, workshop):  # noqa: F811
    data = {
        "partModelId": str(workshop["part_model"].uuid),
        "factoryId": str(workshop["factory"].uuid),
        "instrumentTypeId": str(workshop["product"].instrument_model.instrument_type_id),
    }
    run(BUILD_PART, staff, data=data)
    return Part.objects.get()


def ask(agent, part, **changes):
    body = {"serial_number": part.serial_number, "part_uuid": str(part.uuid), "nfc_uid": "04aabbccddeeff", "initial_counter": 0}
    return agent.post(URL, {**body, **changes}, format="json")


def test_refusals_say_why_instead_of_a_500(agent, part):
    response = ask(agent, part, serial_number="NOPE-0001")
    assert response.status_code == 404 and "NOPE-0001" in response.json()["detail"]

    response = ask(agent, part, part_uuid="0caa2e49-a0e9-4804-bcc1-dbf537623ed5")
    assert response.status_code == 400 and "même pièce" in response.json()["detail"]

    PartNFCIdentity.objects.create(part=part, batch=part.batch, nfc_uid="04aa", status="active")
    response = ask(agent, part)
    assert response.status_code == 409 and "révoque" in response.json()["detail"]


def test_vault_failure_is_reported(agent, part):
    with mock.patch("provisionning_agent.views.PartService.provideNFCIdentity", side_effect=ConnectionError("down")):
        response = ask(agent, part)
    assert response.status_code == 500 and "Vault" in response.json()["detail"]


def test_key_is_given_for_a_free_part(agent, part):
    keys = {"tag_key": bytes(range(16)), "old_tag_key": bytes(16), "version": 1}
    with mock.patch("provisionning_agent.views.PartService.provideNFCIdentity", return_value=keys):
        response = ask(agent, part)
    assert response.status_code == 200
    assert response.json() == {"tag_key": bytes(range(16)).hex(), "old_tag_key": "00" * 16, "version": 1, "is_rewrite": False}
