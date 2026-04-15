from argon2 import PasswordHasher, exceptions

_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(hash_str: str, plain: str) -> bool:
    try:
        _ph.verify(hash_str, plain)
        return True
    except exceptions.VerifyMismatchError:
        return False
    except exceptions.InvalidHashError:
        return False
