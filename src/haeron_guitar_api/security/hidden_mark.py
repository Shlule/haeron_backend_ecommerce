"""Hidden mark : a short code micro-engraved at a place of the part that cannot be seen.

The code comes from the serial number and the secret key of the part model in Vault (the same key as the NFC tags,
through a separate derivation). It is never stored : the engraving agent gets it when it engraves, and the
back-office only says whether a code read on a part is the right one. A counterfeiter can copy the visible serial
number, but cannot compute the code without the key ; so when the NFC tag no longer works, this code still proves
that the part comes from the workshop.
"""

import hashlib
import hmac

from .vault.vault_factory import get_vault_service

# Crockford base 32 : no I, L, O or U, letters easily mistaken for digits when read under a magnifier
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LENGTH = 8  # 40 bits : one chance in a thousand billion to guess it
VERSION = b"haeron-hidden-mark-v1"


def code_from_key(serial_number: str, domain_key: bytes) -> str:
    digest = hmac.new(domain_key, VERSION + b":" + serial_number.encode(), hashlib.sha256).digest()
    number = int.from_bytes(digest[:5], "big")
    chars = "".join(ALPHABET[(number >> (5 * i)) & 31] for i in reversed(range(LENGTH)))
    return f"{chars[:4]}-{chars[4:]}"


def domain_key(part_model_id, vault=None) -> bytes:
    vault = vault or get_vault_service()
    return vault.get_secret(vault.get_vault_path("domain", part_model_id=part_model_id))


def code_for(part, vault=None) -> str:
    return code_from_key(part.serial_number, domain_key(part.part_model_id, vault))


def normalize(code: str) -> str:
    """What was read on the part, written as the alphabet : spaces and dashes dropped, O read as 0, I and L as 1."""
    code = "".join(code.upper().split()).replace("-", "")
    return code.translate(str.maketrans({"O": "0", "I": "1", "L": "1"}))


def matches(part, typed: str, vault=None) -> bool:
    return hmac.compare_digest(normalize(typed), normalize(code_for(part, vault)))
