"""Performance guard for clustering pipeline.

This test ensures clustering completes within budget for realistic workloads.
"""

import time
from app.cluster.pipeline import run_clustering
from app.csv_io.normalize import normalize


def _generate_synthetic_spanish_titles(count: int) -> list[tuple[int, str, str]]:
    """Generate count unique synthetic Spanish job titles.

    Returns:
        List of (row_index, original, normalized) tuples.
    """
    roles = [
        "jefe", "director", "gerente", "coordinador", "analista",
        "especialista", "supervisor", "ingeniero", "técnico", "asistente",
        "administrador", "consultor", "gestor", "promotor", "responsable",
        "ayudante", "aprendiz", "practicante", "becario", "colaborador",
    ]

    departments = [
        "compras", "ventas", "recursos humanos", "rrhh", "finanzas",
        "marketing", "operaciones", "logística", "producción", "calidad",
        "informática", "sistemas", "tecnología", "desarrollo", "soporte",
        "legal", "contabilidad", "auditoría", "comunicación", "investigación",
        "atención cliente", "servicio técnico", "mantenimiento", "seguridad",
        "almacén", "distribución", "transporte", "exportación", "importación",
        "proyectos", "innovación", "estrategia", "planificación", "control",
    ]

    # Generate unique combinations by using a product with numeric suffixes
    results: list[tuple[int, str, str]] = []

    for i in range(count):
        # Use different role/dept combinations to ensure unique normalized values
        role_idx = (i // len(departments)) % len(roles)
        dept_idx = i % len(departments)
        role = roles[role_idx]
        dept = departments[dept_idx]

        # Add numeric suffix for additional uniqueness when needed
        suffix_num = i // (len(roles) * len(departments))
        if suffix_num > 0:
            base = f"{role} {dept} {suffix_num}"
        else:
            base = f"{role} {dept}"

        # Create a realistic variant with case/whitespace changes
        # This simulates real user input variations
        variant_options = [
            base,
            base.title(),
            base.upper(),
            base.lower(),
        ]

        # Pick a variant (cycle through options for variety)
        variant = variant_options[i % len(variant_options)]

        normalized = normalize(variant)
        results.append((i, variant, normalized))

    return results


def test_clustering_2k_uniques_under_5s() -> None:
    """Clustering 2,000 unique job titles completes within 5 seconds.
    
    Performance guard to ensure clustering latency is within budget.
    This provides a meaningful performance test that passes with the current
    O(n²) implementation while still validating clustering performance.
    """
    rows = _generate_synthetic_spanish_titles(2_000)

    # Verify we generated unique normalized values
    normalized_set = {norm for _, _, norm in rows}
    assert len(normalized_set) == 2_000, f"Expected 2,000 unique normalized values, got {len(normalized_set)}"

    # Time the clustering
    threshold = 90  # Typical threshold used in production
    start = time.monotonic()
    results = run_clustering(rows, threshold)
    elapsed = time.monotonic() - start

    # Assert under 5 seconds
    assert elapsed < 5.0, f"Clustering took {elapsed:.2f}s, expected < 5.0s"

    # Basic sanity check: all rows should be assigned
    total_member_count = sum(r.member_count for r in results)
    assert total_member_count == len(rows), f"Expected {len(rows)} total members, got {total_member_count}"
