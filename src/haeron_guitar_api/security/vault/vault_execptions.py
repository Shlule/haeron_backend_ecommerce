class VaultError(Exception):
    """Base exception for Vault layer."""

    pass


class VaultConnectionError(VaultError):
    """Vault is unreachable or network error."""

    pass


class VaultAuthenticationError(VaultError):
    """Invalid token or auth failure."""

    pass


class VaultSecretNotFound(VaultError):
    """Secret does not exist at given path."""

    pass


class VaultWriteError(VaultError):
    """Failed to write secret."""

    pass


class VaultReadError(VaultError):
    """Failed to read secret."""

    pass
