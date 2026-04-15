from app.csv_io.parser import CSVError, parse_text


def test_parse_text_one_per_line():
    """Test that parse_text returns one title per line."""
    raw = "Jefe de Compras\nTécnico\nSeñor Administrativo"
    result = parse_text(raw)
    assert result == ["Jefe de Compras", "Técnico", "Señor Administrativo"]


def test_parse_text_skips_blank_lines():
    """Test that parse_text skips blank lines."""
    raw = "Jefe de Compras\n\n\nTécnico\n\nSeñor Administrativo"
    result = parse_text(raw)
    assert result == ["Jefe de Compras", "Técnico", "Señor Administrativo"]


def test_parse_text_strips_whitespace():
    """Test that parse_text strips whitespace from each line."""
    raw = "  Jefe de Compras  \n\tTécnico\t\n  Señor Administrativo  "
    result = parse_text(raw)
    assert result == ["Jefe de Compras", "Técnico", "Señor Administrativo"]


def test_parse_text_empty_raises_input_empty():
    """Test that parse_text raises input_empty for empty input."""
    raw = ""
    try:
        parse_text(raw)
        assert False, "Expected CSVError"
    except CSVError as e:
        assert e.code == "input_empty"


def test_parse_text_too_large_raises():
    """Test that parse_text raises input_too_large for > 50,000 lines."""
    raw = "Title\n" * 50_001
    try:
        parse_text(raw)
        assert False, "Expected CSVError"
    except CSVError as e:
        assert e.code == "input_too_large"
