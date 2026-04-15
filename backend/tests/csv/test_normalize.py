from app.csv_io.normalize import normalize


def test_normalize_strips_accents():
    assert normalize("Señor Técnico") == "senor tecnico"


def test_normalize_lowercases():
    assert normalize("JEFE COMPRAS") == "jefe compras"


def test_normalize_collapses_whitespace():
    assert normalize("  jefe    compras  ") == "jefe compras"


def test_normalize_drops_punctuation():
    assert normalize("jefe, de compras!") == "jefe de compras"


def test_normalize_preserves_inner_hyphen():
    assert normalize("co-founder") == "co-founder"


def test_normalize_empty_string_returns_empty():
    assert normalize("") == ""


def test_normalize_only_punctuation_returns_empty():
    assert normalize("!!!") == ""


def test_normalize_idempotent():
    import random
    import string

    for _ in range(20):
        # Generate random strings with letters, spaces, punctuation
        chars = string.ascii_letters + string.digits + " .,;!-¿¡áéíóúñ"
        random_string = "".join(random.choice(chars) for _ in range(30))
        result1 = normalize(random_string)
        result2 = normalize(result1)
        assert result1 == result2
