import hashlib
import logging
from dataclasses import dataclass

from django.conf import settings

from .vault_client import VaultClient
from .vault_execptions import VaultSecretNotFound

logger = logging.getLogger(__name__)


def _domain_key_path(part_model_id: str) -> str:
    return f"domain-keys/part-model/{part_model_id}"


class VaultService:
    def __init__(self, client: VaultClient | None = None):
        self.client = client or VaultClient()

    def create_domain_key(self, part_model_id: str) -> str:
        path = _domain_key_path(part_model_id)

        import secrets

        domain_key = secrets.token_bytes(32)

        self.client.write_secret(
            path=path, secret={"domain_key": domain_key.hex(), "algorithm": "AES-256", "version": 1}
        )

        logger.info("Domain key created for PartModel %s", part_model_id)

        return path

    def get_domain_key(self, part_model_id: str) -> bytes:
        path = _domain_key_path(part_model_id)

        try:
            secret = self.client.read_secret(path)
        except VaultSecretNotFound:
            raise

        return bytes.fromhex(secret["domain_key"])

    def rotate_domain_key(self, part_model_id: str) -> str:
        """
        Rotate domain key for a PartModel.
        Old key is replaced (no history for now).
        """

        path = _domain_key_path(part_model_id)

        import secrets

        new_key = secrets.token_bytes(32)

        self.client.write_secret(
            path=path,
            secret={
                "domain_key": new_key.hex(),
                "algorithm": "AES-256",
                "version": self._get_next_version(part_model_id),
            },
        )

        logger.warning("Domain key rotated for %s", part_model_id)

        return path

    def _get_next_version(self, part_model_id: str) -> int:

        path = _domain_key_path(part_model_id)

        try:
            secret = self.client.read_secret(path)
            return int(secret.get("version", 1)) + 1
        except Exception:
            return 1

    def revoke_domain_key(self, part_model_id: str) -> None:
        path = _domain_key_path(part_model_id)

        self.client.delete_secret(path)

        logger.warning("Domain key revoked for %s", part_model_id)
