from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


class HKDFService:
    @staticmethod
    def derive_tag_key(domain_key: bytes, batch_key: bytes, uid: str, length: int = 16) -> bytes:
        if not uid or not uid.strip():
            raise ValueError("UID cannot be empty")
        hkdf_service = HKDFService()
        info = f"ntag424:{uid}".encode()

        return hkdf_service._derive_key(
            key=domain_key,
            salt=batch_key,
            info=info,
            length=length,
        )

    def _derive_key(self, key: bytes, salt: bytes, info: bytes, length: int = 16) -> bytes:
        return HKDF(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            info=info,
        ).derive(key)
