import logging

from typing import Dict, Callable
from decouple import config

from .vault_client import VaultClient

logger = logging.getLogger(__name__)


class VaultService:
    def __init__(self, client: VaultClient | None = None):
        self.client = client or VaultClient()

    _SCOPES = {
        "domain": lambda p: f"{config('VAULT_DOMAIN_ROOT')}/{p['part_model_id']}",
        "batch": lambda p: f"{config('VAULT_BATCH_ROOT')}/{p['part_model_id']}/batch/{p['batch_id']}",
        "tag": lambda p: f"part/{p['part_id']}/uid/{p['uid']}",
    }

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
        self.client.delete(path)
