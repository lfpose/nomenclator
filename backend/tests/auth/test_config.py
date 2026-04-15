import pytest

from app.auth.config import get_password_hash
from app.auth.passwords import hash_password


def test_valid_hash_returned():
    """Verify that a valid argon2 hash is returned."""
    # Generate a real argon2 hash
    valid_hash = hash_password("test_password")
    # Monkeypatch settings to use this hash
    from app import settings
    original_hash = settings.settings.auth_password_hash
    try:
        settings.settings.auth_password_hash = valid_hash
        result = get_password_hash()
        assert result == valid_hash
        assert result.startswith("$argon2")
    finally:
        settings.settings.auth_password_hash = original_hash


def test_missing_hash_raises():
    """Verify that an empty/missing hash raises RuntimeError."""
    from app import settings
    original_hash = settings.settings.auth_password_hash
    try:
        settings.settings.auth_password_hash = ""
        with pytest.raises(RuntimeError, match="AUTH_PASSWORD_HASH is not set or not an argon2 hash"):
            get_password_hash()
    finally:
        settings.settings.auth_password_hash = original_hash


def test_non_argon2_hash_raises():
    """Verify that a non-argon2 hash raises RuntimeError."""
    from app import settings
    original_hash = settings.settings.auth_password_hash
    try:
        settings.settings.auth_password_hash = "not_an_argon2_hash"
        with pytest.raises(RuntimeError, match="AUTH_PASSWORD_HASH is not set or not an argon2 hash"):
            get_password_hash()
    finally:
        settings.settings.auth_password_hash = original_hash
