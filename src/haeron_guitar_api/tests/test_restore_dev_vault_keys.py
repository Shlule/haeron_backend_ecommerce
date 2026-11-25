"""After the local dev Vault restarted (keys kept in memory only), the part models and batches get new keys."""

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings

from haeron_guitar_api.management.commands import restore_dev_vault_keys
from haeron_guitar_api.models import PartBatch, PartModel
from haeron_guitar_api.security.vault.vault_execptions import VaultSecretNotFound

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)


class EmptyVault:
    """A Vault that lost everything, then keeps what is written."""

    def __init__(self):
        self.secrets = {}

    def get_vault_path(self, kind, **ids):
        return f"{kind}/" + "/".join(str(value) for value in ids.values())

    def get_secret(self, path):
        if path not in self.secrets:
            raise VaultSecretNotFound(path)
        return self.secrets[path]

    def post_secret(self, kind, **ids):
        path = self.get_vault_path(kind, **ids)
        self.secrets[path] = b"k" * 32
        return path


@pytest.fixture
def vault(monkeypatch):
    fake = EmptyVault()
    monkeypatch.setattr(restore_dev_vault_keys, "get_vault_service", lambda: fake)
    return fake


@override_settings(VAULT_ADDR="http://127.0.0.1:8201")
def test_missing_keys_are_written_again(starlight, vault):  # noqa: F811
    part_model = PartModel.objects.get(code="BD")
    batch = PartBatch.objects.create(part_model=part_model, name="Lot 1", code="A1", status="active")

    call_command("restore_dev_vault_keys", "--dry-run")
    assert vault.secrets == {}  # dry run : nothing written

    call_command("restore_dev_vault_keys")
    assert f"domain/{part_model.uuid}" in vault.secrets
    batch.refresh_from_db()
    assert batch.vault_batch_key_path in vault.secrets
    written = dict(vault.secrets)
    call_command("restore_dev_vault_keys")  # second run : the keys are there, nothing changes
    assert vault.secrets == written


@override_settings(VAULT_ADDR="https://vault.haeron.fr")
def test_never_on_the_real_vault(starlight, vault):  # noqa: F811
    with pytest.raises(CommandError, match="pas le Vault local"):
        call_command("restore_dev_vault_keys")
    assert vault.secrets == {}
