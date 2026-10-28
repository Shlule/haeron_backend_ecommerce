from functools import lru_cache
from .vault_client import VaultClient


@lru_cache(maxsize=1)
def get_vault_client():
    return VaultClient()


@lru_cache(maxsize=1)
def get_vault_service():
    from .vault_service import VaultService

    return VaultService()
