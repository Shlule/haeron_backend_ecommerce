import pytest


@pytest.fixture(autouse=True)
def vault_token(settings):
    """Outside Kubernetes there is no ServiceAccount token : the client logs in with a static token (hvac is mocked
    or never reached in these tests)."""
    settings.VAULT_TOKEN = "test-token"


@pytest.fixture(autouse=True)
def vault_roots(monkeypatch):
    """Vault paths are built from these settings (.env) : fixed here so the tests do not depend on the machine."""
    monkeypatch.setenv("VAULT_DOMAIN_ROOT", "part-model")
    monkeypatch.setenv("VAULT_BATCH_ROOT", "batch")
