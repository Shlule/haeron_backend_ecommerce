import logging
import secrets
import threading
import time
from typing import Any

import hvac
import hvac.exceptions
import requests
from django.conf import settings

from .vault_execptions import (
    VaultSecretNotFound,
    VaultAuthenticationError,
    VaultConnectionError,
    VaultError,
    VaultReadError,
    VaultWriteError,
)


logger = logging.getLogger(__name__)

SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
RENEW_MARGIN_SECONDS = 60


class VaultClient:
    def __init__(self):
        self._client = hvac.Client(url=settings.VAULT_ADDR, timeout=settings.VAULT_TIMEOUT)
        self.mount_point = getattr(settings, "VAULT_MOUNT_POINT", "secret")
        self._lock = threading.Lock()
        self._expires_at = 0.0  # horloge monotonic
        self._login()
        self._check_connection()

    @property
    def client(self) -> hvac.Client:
        """Client hvac, reconnecté automatiquement quand le token approche de l'expiration."""
        if time.monotonic() >= self._expires_at - RENEW_MARGIN_SECONDS:
            with self._lock:
                if time.monotonic() >= self._expires_at - RENEW_MARGIN_SECONDS:
                    self._login()
        return self._client

    def _login(self):
        # Mode développement : token statique fourni explicitement
        static_token = getattr(settings, "VAULT_TOKEN", None)
        if static_token:
            self._client.token = static_token
            self._expires_at = float("inf")
            return

        # Mode Kubernetes : authentification par ServiceAccount
        role = getattr(settings, "VAULT_K8S_ROLE", "haeron-backend")
        try:
            with open(SA_TOKEN_PATH) as f:
                jwt = f.read().strip()
            resp = self._client.auth.kubernetes.login(role=role, jwt=jwt)
        except FileNotFoundError as e:
            raise VaultAuthenticationError(f"Token ServiceAccount introuvable : {SA_TOKEN_PATH}") from e
        except requests.exceptions.RequestException as e:
            raise VaultConnectionError(f"Login Vault impossible : {type(e).__name__}: {e}") from e
        except hvac.exceptions.VaultError as e:
            raise VaultAuthenticationError(f"Login Kubernetes refusé (rôle {role}) : {e}") from e

        lease = resp["auth"]["lease_duration"]
        self._expires_at = time.monotonic() + lease
        logger.info("Vault: login Kubernetes OK (rôle %s, durée %ss)", role, lease)

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
        try:
            response = self.client.secrets.kv.v2.read_secret_version(path=path, mount_point=self.mount_point)
            return response.get("data", {}).get("data", {})
        except hvac.exceptions.InvalidPath:
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