from ..settings import settings


def get_password_hash() -> str:
    """Get the auth password hash from settings, validating it's an argon2 hash."""
    h = settings.auth_password_hash
    if not h or not h.startswith("$argon2"):
        raise RuntimeError("AUTH_PASSWORD_HASH is not set or not an argon2 hash")
    return h
