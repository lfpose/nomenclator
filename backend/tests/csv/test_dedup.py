from app.csv_io.dedup import unique_normalized


def test_dedup_removes_exact_duplicates():
    """Duplicate normalized values should be removed."""
    rows = [
        (0, "Jefe de Compras", "jefe de compras"),
        (1, "JEFE DE COMPRAS", "jefe de compras"),
        (2, "Técnico", "tecnico"),
        (3, "técnico", "tecnico"),
    ]
    result = unique_normalized(rows)
    assert result == ["jefe de compras", "tecnico"]


def test_dedup_preserves_first_occurrence_order():
    """First occurrence order should be preserved in output."""
    rows = [
        (0, "Jefe de Compras", "jefe de compras"),
        (1, "Técnico", "tecnico"),
        (2, "Vendedor", "vendedor"),
        (3, "JEFE DE COMPRAS", "jefe de compras"),  # duplicate
        (4, "técnico", "tecnico"),  # duplicate
    ]
    result = unique_normalized(rows)
    assert result == ["jefe de compras", "tecnico", "vendedor"]


def test_dedup_on_empty_returns_empty():
    """Empty input should return empty list."""
    rows = []
    result = unique_normalized(rows)
    assert result == []


def test_dedup_on_already_unique_returns_same_length():
    """Already unique rows should return same length."""
    rows = [
        (0, "Jefe de Compras", "jefe de compras"),
        (1, "Técnico", "tecnico"),
        (2, "Vendedor", "vendedor"),
        (3, "Gerente", "gerente"),
    ]
    result = unique_normalized(rows)
    assert len(result) == len(rows)
    assert result == ["jefe de compras", "tecnico", "vendedor", "gerente"]
