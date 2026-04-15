from app.csv_io.ingest import ingest
from app.csv_io.parser import CSVError
import pytest


def test_ingest_csv_bytes_returns_indexed_triples():
    csv_content = b"title\nJefe de Compras\nGerente de Ventas\nTecnico de Soporte"
    result = ingest(file_bytes=csv_content)
    assert len(result) == 3
    assert result[0] == (0, "Jefe de Compras", "jefe de compras")
    assert result[1] == (1, "Gerente de Ventas", "gerente de ventas")
    assert result[2] == (2, "Tecnico de Soporte", "tecnico de soporte")


def test_ingest_text_returns_indexed_triples():
    text_content = "Ingeniero de Software\nAnalista de Datos\nDiseñador UX"
    result = ingest(text=text_content)
    assert len(result) == 3
    assert result[0] == (0, "Ingeniero de Software", "ingeniero de software")
    assert result[1] == (1, "Analista de Datos", "analista de datos")
    assert result[2] == (2, "Diseñador UX", "disenador ux")


def test_ingest_blank_row_raises_input_contains_blank_rows():
    # Row 1 is just punctuation which normalizes to empty
    csv_content = b"title\nJefe de Compras\n!!!\nGerente de Ventas"
    with pytest.raises(CSVError) as exc_info:
        ingest(file_bytes=csv_content)
    assert exc_info.value.code == "input_contains_blank_rows"
    assert "Row 1" in exc_info.value.message
    assert "!!!" in exc_info.value.message


def test_ingest_preserves_original_untouched():
    csv_content = b"title\n  JEFE  DE  COMPRAS  \n  Gerente  de  Ventas  "
    result = ingest(file_bytes=csv_content)
    assert len(result) == 2
    # Original should preserve whitespace and case
    assert result[0][1] == "  JEFE  DE  COMPRAS  "
    assert result[1][1] == "  Gerente  de  Ventas  "
    # Normalized should be cleaned
    assert result[0][2] == "jefe de compras"
    assert result[1][2] == "gerente de ventas"


def test_ingest_both_sources_raises_input_malformed():
    csv_content = b"Jefe de Compras"
    text_content = "Gerente de Ventas"
    with pytest.raises(CSVError) as exc_info:
        ingest(file_bytes=csv_content, text=text_content)
    assert exc_info.value.code == "input_malformed"
    assert "Exactly one" in exc_info.value.message


def test_ingest_neither_source_raises_input_malformed():
    with pytest.raises(CSVError) as exc_info:
        ingest()
    assert exc_info.value.code == "input_malformed"
    assert "Exactly one" in exc_info.value.message
