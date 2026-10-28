import pytest

from haeron_guitar_api.tag.sdm import validate_plain_sun


def test_validate_plain_sun_valid():
    uid = bytes.fromhex("048D8D322B1690")
    read_ctr = bytes.fromhex("000001")
    sdmmac = bytes.fromhex("AF8F6EF041FD5B9C")
    key = bytes(16)

    assert validate_plain_sun(
        uid=uid,
        read_ctr=read_ctr,
        sdmmac=sdmmac,
        sdm_file_read_key=key,
    )