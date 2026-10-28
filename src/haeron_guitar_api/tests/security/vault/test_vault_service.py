import secrets

import pytest
from unittest.mock import MagicMock

from haeron_guitar_api.security.vault.vault_execptions import (
    VaultSecretNotFound,
)
from haeron_guitar_api.security.vault.vault_service import VaultService
from haeron_guitar_api.security.vault.vault_client import VaultClient


@pytest.fixture
def vault_client():
    client = VaultClient()

    return client


@pytest.fixture
def vault_service(vault_client):
    return VaultService(client=vault_client)


def test_should_build_domain_path(vault_service):
    path = vault_service.get_vault_path(
        secret_type="domain",
        part_model_id="body-strat",
    )

    assert path == "secret/domain/part-model/body-strat"


def test_should_build_batch_path(vault_service):
    path = vault_service.get_vault_path(
        secret_type="batch",
        part_model_id="body-strat",
        batch_id="batch-001",
    )

    assert path == ("secret/batch/part-batch/body-strat/batch/batch-001")


def test_should_raise_when_secret_type_is_unknown(vault_service):
    with pytest.raises(ValueError):
        vault_service.get_vault_path(
            secret_type="unknown",
        )


def test_create_domain_key(vault_client, vault_service):
    path = vault_service.post_secret("domain", part_model_id="body-strat")

    assert path == "secret/domain/part-model/body-strat"

    vault_client.write_secret.assert_called_once()

    kwargs = vault_client.write_secret.call_args.kwargs

    assert kwargs["path"] == "secret/domain/part-model/body-strat"

    secret = kwargs["secret"]

    assert "key" in secret

    # 32 bytes = 64 hex chars
    assert len(secret["key"]) == 64


def test_create_domain_key_should_generate_unique_keys(vault_client, vault_service):
    path_secret_1 = vault_service.post_secret("domain", part_model_id="part-model-1")

    path_secret_2 = vault_service.post_secret("domain", part_model_id="part-model-2")
    first_secret = vault_service.get_secret(path_secret_1)
    second_secret = vault_service.get_secret(path_secret_2)

    assert first_secret != second_secret
