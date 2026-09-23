import logging
import secrets
from typing import Any

import hvac
from django.conf import settings
import hvac.exceptions

from .vault_execptions import (
    VaultSecretNotFound,
    VaultAuthenticationError,
    VaultConnectionError,
    VaultError,
    VaultReadError,
    VaultWriteError,
)


logger = logging.getLogger(__name__)


class VaultClient:
    def __init__(self):
        self.client = hvac.Client(url=settings.VAULT_ADDR, token=settings.VAULT_TOKEN, timeout=settings.VAULT_TIMEOUT)

        self.mount_point = getattr(settings, "VAULT_MOUNT_POINT", "secret")
        self._check_connection()

    def _check_connection(self):
        try:
            authenticated = self.client.is_authenticated()

        except Exception as e:

            raise VaultConnectionError(
                f"is_authenticated() a échoué : "
                f"{type(e).__name__}: {str(e)}"
            ) from e

        if not authenticated:
            raise VaultAuthenticationError("Invalid Vault Token")

    def health(self) -> dict[str, Any]:
        return self.client.sys.read_health_status()

    def is_authenticated(self) -> bool:
        return self.client.is_authenticated()

    def read_secret(self, path: str) -> dict[str, Any]:
        print("je suis dans le readsecret")
        try:
            print("jai trouver le path")
            print(path)
            response = self.client.secrets.kv.v2.read_secret_version(path=path, mount_point=self.mount_point)
            return response.get("data", {}).get("data", {})
        except hvac.exceptions.InvalidPath:
            print("je n'ai pas trouver le path")
            print(path)
            raise VaultSecretNotFound(path)

    def generate_key(self):
        return secrets.token_bytes(32)

    def write_secret(self, path: str, secret: dict[str, Any]) -> None:
        try:
            secret = self.client.secrets.kv.v2.create_or_update_secret(
                path=path, mount_point=self.mount_point, secret=secret
            )

            logger.info("Vault secret written at %s", path)
        except Exception as e:
            raise VaultWriteError(str(e))

    def delete_secret(self, path: str) -> None:
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=self.mount_point,
            )
            logger.info("Vault secret deleted at %s", path)

        except Exception as e:
            raise VaultWriteError(str(e))

    def list(self, path: str) -> list[str]:
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=self.mount_point,
            )
            return response.get("data", {}).get("keys", [])

        except Exception as e:
            raise VaultReadError(str(e))
