import secrets
import pytest
from unittest.mock import MagicMock

from haeron_guitar_api.security.vault.vault_service import VaultService
from haeron_guitar_api.security.vault.vault_execptions import VaultSecretNotFound


@pytest.fixture
def vault_client():
    return MagicMock()


@pytest.fixture
def vault_service(vault_client):
    return VaultService(client=vault_client)


def test_create_domain_key(vault_service, vault_client):
    path = vault_service.create_domain_key("body-strat")

    assert path == "domain-keys/part-model/body-strat"

    vault_client.write_secret.assert_called_once()

    kwargs = vault_client.write_secret.call_args.kwargs

    assert kwargs["path"] == "domain-keys/part-model/body-strat"

    secret = kwargs["secret"]

    assert "domain_key" in secret
    assert secret["algorithm"] == "AES-256"
    assert secret["version"] == 1

    # 32 bytes -> 64 caractères hex
    assert len(secret["domain_key"]) == 64


def test_get_domain_key(vault_service, vault_client):
    key = secrets.token_bytes(32)

    vault_client.read_secret.return_value = {
        "domain_key": key.hex(),
        "algorithm": "AES-256",
        "version": 1,
    }

    result = vault_service.get_domain_key("body-strat")

    assert result == key

    vault_client.read_secret.assert_called_once_with("domain-keys/part-model/body-strat")


def test_get_domain_key_not_found(vault_service, vault_client):
    vault_client.read_secret.side_effect = VaultSecretNotFound()

    with pytest.raises(VaultSecretNotFound):
        vault_service.get_domain_key("body-strat")


def test_rotate_domain_key(vault_service, vault_client):
    vault_client.read_secret.return_value = {
        "domain_key": secrets.token_hex(32),
        "version": 3,
    }

    path = vault_service.rotate_domain_key("body-strat")

    assert path == "domain-keys/part-model/body-strat"

    vault_client.write_secret.assert_called_once()

    kwargs = vault_client.write_secret.call_args.kwargs

    assert kwargs["secret"]["version"] == 4


def test_revoke_domain_key(vault_service, vault_client):
    vault_service.revoke_domain_key("body-strat")

    vault_client.delete_secret.assert_called_once_with("domain-keys/part-model/body-strat")


def test_create_domain_key_generates_unique_keys(vault_service, vault_client):
    vault_service.create_domain_key("part-model-1")

    first_call = vault_client.write_secret.call_args.kwargs

    vault_client.write_secret.reset_mock()

    vault_service.create_domain_key("part-model-2")

    second_call = vault_client.write_secret.call_args.kwargs

    assert first_call["secret"]["domain_key"] != second_call["secret"]["domain_key"]


@pytest.mark.parametrize(
    "current_version,next_version",
    [
        (1, 2),
        (2, 3),
        (15, 16),
    ],
)
def test_rotate_increment_version(
    vault_service,
    vault_client,
    current_version,
    next_version,
):
    vault_client.read_secret.return_value = {
        "domain_key": secrets.token_hex(32),
        "version": current_version,
    }

    vault_service.rotate_domain_key("body-strat")

    kwargs = vault_client.write_secret.call_args.kwargs

    assert kwargs["secret"]["version"] == next_version
