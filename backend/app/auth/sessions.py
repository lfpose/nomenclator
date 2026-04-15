import hashlib
import secrets

from ..dao import sessions as sessions_dao


def create_session(conn, ttl_seconds: int = 2592000) -> str:
    """Returns the raw session id to set on the cookie."""
    raw = secrets.token_hex(32)  # 64 chars, 256 bits
    id_hash = hashlib.sha256(raw.encode()).hexdigest()
    sessions_dao.create_session(conn, session_id_hash=id_hash, ttl_seconds=ttl_seconds)
    return raw


def validate_session(conn, raw_sid: str | None) -> bool:
    if not raw_sid:
        return False
    id_hash = hashlib.sha256(raw_sid.encode()).hexdigest()
    return sessions_dao.get_valid_session(conn, id_hash) is not None


def destroy_session(conn, raw_sid: str) -> None:
    id_hash = hashlib.sha256(raw_sid.encode()).hexdigest()
    sessions_dao.delete_session(conn, id_hash)
