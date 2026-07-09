from functools import lru_cache
from .vault_client import VaultClient

from .vault_service import VaultService


@lru_cache(maxsize=1)
def get_vault_client():
    return VaultClient()


@lru_cache(maxsize=1)
def get_vault_service():
    return VaultService()
