from typing import TypedDict, Any


class VaultSecret(TypedDict, total=False):
    domain_key: str
    version: int
    metadata: dict[str, Any]
