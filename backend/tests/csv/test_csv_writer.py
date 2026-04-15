import pytest
from backend.app.csv_io.exporter import write_csv_bytes, ExportRow


def test_output_starts_with_bom():
    """Verifies output starts with UTF-8 BOM bytes."""
    rows = [ExportRow("test", "male", "female", "category", "")]
    output = write_csv_bytes(rows)
    assert output.startswith(b"\xef\xbb\xbf")


def test_output_has_header_row():
    """Verifies output has a header row."""
    rows = [ExportRow("test", "male", "female", "category", "")]
    output = write_csv_bytes(rows)
    # BOM is 3 bytes, then the header row
    output_str = output[3:].decode("utf-8")
    lines = output_str.split("\r\n")
    # First line should be the header
    assert "original,male_es,female_es,category,error" in lines[0]


def test_output_has_5_columns_in_correct_order():
    """Verifies output has 5 columns in the correct order."""
    rows = [ExportRow("original_val", "male_val", "female_val", "category_val", "error_val")]
    output = write_csv_bytes(rows)
    output_str = output[3:].decode("utf-8")  # Skip BOM
    lines = output_str.split("\r\n")
    # Second line (first data row) should have values in correct order
    assert "original_val,male_val,female_val,category_val,error_val" in lines[1]


def test_output_uses_crlf_line_endings():
    """Verifies output uses CRLF line endings."""
    rows = [
        ExportRow("row1", "m1", "f1", "c1", ""),
        ExportRow("row2", "m2", "f2", "c2", ""),
    ]
    output = write_csv_bytes(rows)
    # Check that lines end with \r\n
    output_str = output[3:].decode("utf-8")  # Skip BOM
    assert "\r\n" in output_str
    # Verify there are no standalone \n line endings (not followed by \r)
    lines = output_str.split("\r\n")
    for line in lines:
        assert "\n" not in line  # Should have no bare newlines


def test_special_characters_quoted_correctly():
    """Verifies titles containing commas, quotes, newlines are quoted correctly."""
    rows = [
        ExportRow('title with "quotes"', "male", "female", "category", ""),
        ExportRow("title with, comma", "male", "female", "category", ""),
        ExportRow("title\nwith\nnewlines", "male", "female", "category", ""),
    ]
    output = write_csv_bytes(rows)
    output_str = output[3:].decode("utf-8")  # Skip BOM

    # Quotes should be escaped by doubling
    assert '""quotes""' in output_str

    # Fields with commas should be quoted
    assert '"title with, comma"' in output_str

    # Fields with newlines should be quoted
    assert '"title\nwith\nnewlines"' in output_str


def test_unicode_accents_preserved():
    """Verifies unicode accents are preserved in output."""
    rows = [
        ExportRow("Jefe de Compras", "Jefe de Compras", "Jefa de Compras", "Abastecimiento", ""),
        ExportRow("Ingeniero de Software", "Ingeniero de Software", "Ingeniera de Software", "Tecnología", ""),
    ]
    output = write_csv_bytes(rows)
    output_str = output.decode("utf-8")

    # Check that unicode characters are present
    assert "Jefe de Compras" in output_str
    assert "Jefa de Compras" in output_str
    assert "Abastecimiento" in output_str
    assert "Ingeniero de Software" in output_str
    assert "Ingeniera de Software" in output_str
    assert "Tecnología" in output_str
