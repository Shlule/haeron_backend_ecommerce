from cryptography.hazmat.primitives import cmac
from cryptography.hazmat.primitives.ciphers import algorithms
import struct


class InvalidMessage(RuntimeError):
    pass


def _cmac(key: bytes, data: bytes) -> bytes:
    c = cmac.CMAC(algorithms.AES(key))
    c.update(data)
    return c.finalize()


def calculate_sdmmac(sdm_file_read_key: bytes, picc_data: bytes) -> bytes:
    """
    Port de libsdm/sdm.py::calculate_sdmmac, mode AES uniquement,
    sans SDMEncFileData (mirroring UID+compteur en clair seulement).
    """
    sv2 = bytearray(b"\x3C\xC3\x00\x01\x00\x80")
    sv2 += picc_data
    while len(sv2) % 16 != 0:
        sv2 += b"\x00"

    ses_sdm_file_read_key = _cmac(sdm_file_read_key, bytes(sv2))
    mac_digest = _cmac(ses_sdm_file_read_key, b"")  # message vide, pas de fichier chiffré

    return bytes(mac_digest[i] for i in range(16) if i % 2 == 1)


def validate_plain_sun(uid: bytes, read_ctr: bytes, sdmmac: bytes, sdm_file_read_key: bytes) -> dict:
    """
    Port de libsdm/sdm.py::validate_plain_sun.
    Valide UID + compteur en clair + CMAC, tel que reçu dans l'URL générée par le tag.
    Lève InvalidMessage si le CMAC ne correspond pas.
    """
    read_ctr_ba = bytearray(read_ctr)
    read_ctr_ba.reverse()

    data = uid + bytes(read_ctr_ba)
    proper_sdmmac = calculate_sdmmac(sdm_file_read_key, data)

    if sdmmac != proper_sdmmac:
        raise InvalidMessage("CMAC invalide")

    read_ctr_num = struct.unpack(">I", b"\x00" + read_ctr)[0]
    return {"uid": uid, "read_ctr": read_ctr_num}