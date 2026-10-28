import pytest
from unittest.mock import MagicMock, patch

from haeron_guitar_api.security.vault.vault_client import VaultClient
from haeron_guitar_api.security.vault.vault_execptions import VaultAuthenticationError, VaultSecretNotFound


@pytest.fixture
def mock_hvac():
    with patch("haeron_guitar_api.security.vault.vault_client.hvac.Client") as mock:
        yield mock


def test_vault_client_init_success(mock_hvac):
    mock_instance = MagicMock()
    mock_instance.is_authenticated.return_value = True
    mock_hvac.return_value = mock_instance

    client = VaultClient()

    assert client.is_authenticated() is True


def test_write_secret(mock_hvac):
    mock_instance = MagicMock()
    mock_instance.is_authenticated.return_value = True
    mock_hvac.return_value = mock_instance

    client = VaultClient()

    client.write_secret(
        path="part-model/test",
        secret={"domain_key": "abc"},
    )

    mock_instance.secrets.kv.v2.create_or_update_secret.assert_called_once()


def test_read_secret(mock_hvac):
    mock_instance = MagicMock()
    mock_instance.is_authenticated.return_value = True

    mock_instance.secrets.kv.v2.read_secret_version.return_value = {"data": {"data": {"domain_key": "abc"}}}

    mock_hvac.return_value = mock_instance

    client = VaultClient()

    result = client.read_secret("part-model/test")

    assert result["domain_key"] == "abc"


def test_read_secret_not_found(mock_hvac):
    import hvac

    mock_instance = MagicMock()
    mock_instance.is_authenticated.return_value = True

    mock_instance.secrets.kv.v2.read_secret_version.side_effect = hvac.exceptions.InvalidPath

    mock_hvac.return_value = mock_instance

    client = VaultClient()

    with pytest.raises(VaultSecretNotFound):
        client.read_secret("missing/path")


def test_delete_secret(mock_hvac):
    mock_instance = MagicMock()
    mock_instance.is_authenticated.return_value = True
    mock_hvac.return_value = mock_instance

    client = VaultClient()

    client.delete_secret("part-model/test")

    mock_instance.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once()


def test_auth_failure(mock_hvac):
    mock_instance = MagicMock()
    mock_instance.is_authenticated.return_value = False
    mock_hvac.return_value = mock_instance

    with pytest.raises(VaultAuthenticationError):
        VaultClient()
