import pytest
from app.csv_io.parser import CSVError, parse_csv


def test_parse_comma_csv_returns_list():
    """Test parsing a comma-delimited CSV returns list of first column values."""
    with open("tests/fixtures/csv/basic_comma.csv", "rb") as f:
        result = parse_csv(f.read())
    assert result == [
        "Jefe de Compras",
        "Técnico en Ventas",
        "Gerente de Marketing",
        "Analista de Datos",
        "Director de Operaciones",
    ]


def test_parse_semicolon_csv_returns_list():
    """Test parsing a semicolon-delimited CSV returns list of first column values."""
    with open("tests/fixtures/csv/basic_semicolon.csv", "rb") as f:
        result = parse_csv(f.read())
    assert result == [
        "Jefe de Compras",
        "Técnico en Ventas",
        "Gerente de Marketing",
        "Analista de Datos",
        "Director de Operaciones",
    ]


def test_parse_strips_bom():
    """Test that UTF-8 BOM is stripped correctly."""
    with open("tests/fixtures/csv/with_bom.csv", "rb") as f:
        result = parse_csv(f.read())
    assert result == [
        "Ingeniero de Software",
        "Diseñador UX",
        "Product Manager",
    ]


def test_parse_multi_column_reads_only_first():
    """Test that only the first column is read from multi-column CSV."""
    with open("tests/fixtures/csv/multi_column.csv", "rb") as f:
        result = parse_csv(f.read())
    assert result == [
        "Jefe de Compras",
        "Técnico en Ventas",
        "Gerente de Marketing",
        "Analista de Datos",
        "Director de Operaciones",
    ]


def test_parse_empty_raises_input_empty():
    """Test that CSV with header only raises input_empty error."""
    with open("tests/fixtures/csv/empty_data.csv", "rb") as f:
        with pytest.raises(CSVError) as exc_info:
            parse_csv(f.read())
    assert exc_info.value.code == "input_empty"


def test_parse_non_utf8_raises_encoding_invalid():
    """Test that non-UTF8 encoded file raises encoding_invalid error."""
    with open("tests/fixtures/csv/non_utf8.csv", "rb") as f:
        with pytest.raises(CSVError) as exc_info:
            parse_csv(f.read())
    assert exc_info.value.code == "encoding_invalid"


def test_parse_huge_raises_input_too_large():
    """Test that CSV with > 50,000 rows raises input_too_large error."""
    # Generate a CSV with 50,001 rows
    lines = ["title"] + [f"Title {i}" for i in range(1, 50002)]
    csv_bytes = "\n".join(lines).encode("utf-8")
    with pytest.raises(CSVError) as exc_info:
        parse_csv(csv_bytes)
    assert exc_info.value.code == "input_too_large"
    assert "50001" in exc_info.value.message


def test_parse_unknown_delimiter_raises_delimiter_unknown():
    """Test that CSV with unknown delimiter raises delimiter_unknown error."""
    # CSV with pipe delimiter (not comma or semicolon)
    csv_bytes = "title|department\nJefe de Compras|Compras".encode("utf-8")
    with pytest.raises(CSVError) as exc_info:
        parse_csv(csv_bytes)
    assert exc_info.value.code == "delimiter_unknown"
