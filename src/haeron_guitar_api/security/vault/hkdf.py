from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


class HKDFService:
    @staticmethod
    def derive_tag_key(domain_key: bytes, batch_key: bytes, uid: str, key_version:int, length: int = 16) -> bytes:
        if not uid :
            ("l'id nest pas fournie")
            raise ValueError("UID cannot be empty")
        info = f"ntag424:{uid}{key_version}".encode()
        return HKDF(
                    algorithm=hashes.SHA256(),
                    length=length,
                    salt=batch_key,
                    info=info,
                ).derive(domain_key)
        