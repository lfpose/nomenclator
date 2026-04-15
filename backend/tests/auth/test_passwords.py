from app.auth.passwords import hash_password, verify_password


def test_hash_is_not_plaintext():
    plain = "mypassword"
    hashed = hash_password(plain)
    assert hashed != plain
    assert hashed.startswith("$argon2")


def test_verify_correct_password_returns_true():
    plain = "mypassword"
    hashed = hash_password(plain)
    assert verify_password(hashed, plain) is True


def test_verify_wrong_password_returns_false():
    plain = "mypassword"
    hashed = hash_password(plain)
    assert verify_password(hashed, "wrongpassword") is False


def test_verify_malformed_hash_returns_false():
    malformed_hash = "not-a-real-hash"
    assert verify_password(malformed_hash, "anypassword") is False


def test_hash_twice_produces_different_hashes():
    plain = "mypassword"
    hash1 = hash_password(plain)
    hash2 = hash_password(plain)
    assert hash1 != hash2
    assert hash1.startswith("$argon2")
    assert hash2.startswith("$argon2")
