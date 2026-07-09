import logging

from typing import Dict, Callable
from decouple import config

from .vault_client import VaultClient
from .vault_factory import get_vault_client

logger = logging.getLogger(__name__)


class VaultService:
    def __init__(self, client: VaultClient | None = None):
        self.client = client or get_vault_client()

    def get_vault_path(self, secret_type: str, **scope_ids):
        if secret_type not in self._SCOPES:
            raise ValueError(f"Unknown secret type: {secret_type}")

        scope_path = self._SCOPES[secret_type](scope_ids)

        return f"secret/{secret_type}/{scope_path}"

    def post_secret(self, secret_type: str, **scope_ids) -> str:
        path = self.get_vault_path(secret_type, **scope_ids)

        key = self.client.generate_key()

        self.client.write_secret(
            path=path,
            secret={
                "key": key.hex(),
                "type": secret_type,
            },
        )

        return path

    def get_secret(self, path: str) -> bytes:
        data = self.client.read_secret(path)

        return bytes.fromhex(data["key"])

    def delete_secret(self, path: str) -> None:
        self.client.delete_secret(path)
