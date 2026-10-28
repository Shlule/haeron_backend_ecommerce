import pytest
from haeron_guitar_api.tag.sdm import validate_plain_sun, InvalidMessage


@pytest.fixture
def zero_key() -> bytes:
    """Clé de test all-zero, utilisée dans les vecteurs de test AN12196 / sdm-backend."""
    return bytes(16)


def test_validate_plain_sun_reference_vector(zero_key):
    """
    Vecteur de référence connu (AN12196 / démo sdm-backend) :
    uid=041E3C8A2D6B80, ctr=000006, cmac=4B00064004B0B3D3
    """
    result = validate_plain_sun(
        uid=bytes.fromhex("041E3C8A2D6B80"),
        read_ctr=bytes.fromhex("000006"),
        sdmmac=bytes.fromhex("4B00064004B0B3D3"),
        sdm_file_read_key=zero_key,
    )

    assert result["read_ctr"] == 6
    assert result["uid"] == bytes.fromhex("041E3C8A2D6B80")


def test_validate_plain_sun_rejects_tampered_cmac(zero_key):
    """Un CMAC altéré (même d'un seul octet) doit être rejeté, pas juste 'ignoré'."""
    with pytest.raises(InvalidMessage):
        validate_plain_sun(
            uid=bytes.fromhex("041E3C8A2D6B80"),
            read_ctr=bytes.fromhex("000006"),
            sdmmac=bytes.fromhex("4B00064004B0B3D4"),  # dernier octet modifié
            sdm_file_read_key=zero_key,
        )


def test_validate_plain_sun_rejects_wrong_counter(zero_key):
    """Un compteur différent doit produire un CMAC différent -> rejeté avec la même signature attendue."""
    with pytest.raises(InvalidMessage):
        validate_plain_sun(
            uid=bytes.fromhex("041E3C8A2D6B80"),
            read_ctr=bytes.fromhex("000007"),  # counter différent du vecteur de référence
            sdmmac=bytes.fromhex("4B00064004B0B3D3"),  # cmac du counter=6, pas 7
            sdm_file_read_key=zero_key,
        )