import secrets
import pytest


from haeron_guitar_api.security.vault.hkdf import HKDFService


def test_should_generate_same_key_for_same_inputs():
    domain_key = secrets.token_bytes(32)
    batch_key = secrets.token_bytes(32)
    uid = "049A12BC34DE56"

    key1 = HKDFService.derive_tag_key(
        domain_key=domain_key,
        batch_key=batch_key,
        uid=uid,
    )

    key2 = HKDFService.derive_tag_key(
        domain_key=domain_key,
        batch_key=batch_key,
        uid=uid,
    )

    assert key1 == key2


def test_should_generate_different_key_when_uid_changes():
    domain_key = secrets.token_bytes(32)
    batch_key = secrets.token_bytes(32)

    key1 = HKDFService.derive_tag_key(
        domain_key=domain_key,
        batch_key=batch_key,
        uid="UID_001",
    )

    key2 = HKDFService.derive_tag_key(
        domain_key=domain_key,
        batch_key=batch_key,
        uid="UID_002",
    )

    assert key1 != key2


def test_should_generate_different_key_when_domain_key_changes():
    batch_key = secrets.token_bytes(32)

    key1 = HKDFService.derive_tag_key(
        domain_key=secrets.token_bytes(32),
        batch_key=batch_key,
        uid="UID",
    )

    key2 = HKDFService.derive_tag_key(
        domain_key=secrets.token_bytes(32),
        batch_key=batch_key,
        uid="UID",
    )

    assert key1 != key2


def test_should_generate_different_key_when_batch_key_changes():
    domain_key = secrets.token_bytes(32)

    key1 = HKDFService.derive_tag_key(
        domain_key=domain_key,
        batch_key=secrets.token_bytes(32),
        uid="UID",
    )

    key2 = HKDFService.derive_tag_key(
        domain_key=domain_key,
        batch_key=secrets.token_bytes(32),
        uid="UID",
    )

    assert key1 != key2


def test_should_generate_16_bytes_key():
    key = HKDFService.derive_tag_key(
        domain_key=secrets.token_bytes(32),
        batch_key=secrets.token_bytes(32),
        uid="UID",
    )

    assert len(key) == 16


def test_should_generate_custom_length():
    key = HKDFService.derive_tag_key(
        domain_key=secrets.token_bytes(32),
        batch_key=secrets.token_bytes(32),
        uid="UID",
        length=32,
    )

    assert len(key) == 32


def test_should_return_bytes():
    key = HKDFService.derive_tag_key(
        domain_key=secrets.token_bytes(32),
        batch_key=secrets.token_bytes(32),
        uid="UID",
    )

    assert isinstance(key, bytes)


def test_should_not_return_domain_key():
    domain_key = secrets.token_bytes(32)

    key = HKDFService.derive_tag_key(
        domain_key=domain_key,
        batch_key=secrets.token_bytes(32),
        uid="UID",
    )

    assert key != domain_key


def test_should_raise_when_uid_is_empty():
    with pytest.raises(ValueError):
        HKDFService.derive_tag_key(
            domain_key=secrets.token_bytes(32),
            batch_key=secrets.token_bytes(32),
            uid="",
        )


def test_should_match_expected_vector():
    domain_key = b"\x00" * 32
    batch_key = b"\x11" * 32

    key = HKDFService.derive_tag_key(
        domain_key=domain_key,
        batch_key=batch_key,
        uid="TESTUID",
    )

    expected = HKDFService.derive_tag_key(
        domain_key=domain_key,
        batch_key=batch_key,
        uid="TESTUID",
    )

    assert key == expected
