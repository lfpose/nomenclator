"""Test determinism guarantees for run_clustering."""
import random

from app.cluster.pipeline import ClusterResult, run_clustering
from app.csv_io.normalize import normalize


def _generate_synthetic_spanish_titles(count: int = 500) -> list[tuple[int, str, str]]:
    """
    Generate synthetic Spanish job titles with realistic variants.

    Creates titles based on common Spanish job role patterns with various
    combinations of:
    - Role types (jefe, director, gerente, encargado, coordinador, supervisor)
    - Departments (compras, ventas, marketing, rrhh, it, operaciones, finanzas)
    - Variations in accent marks, case, whitespace, and word order
    - Gender variants
    """
    roles = [
        "jefe", "jefa",
        "director", "directora",
        "gerente",
        "encargado", "encargada",
        "coordinador", "coordinadora",
        "supervisor", "supervisora",
    ]
    departments = [
        "compras",
        "ventas",
        "marketing",
        "recursos humanos",
        "rh",
        "rrhh",
        "ti",
        "it",
        "informatica",
        "operaciones",
        "finanzas",
        "logistica",
        "produccion",
    ]
    connectors = ["de", "del", "de la", "en", "para"]

    titles = []
    for i in range(count):
        # Generate base title
        role = random.choice(roles)
        dept = random.choice(departments)
        connector = random.choice(connectors) if random.random() > 0.3 else ""

        base_parts = [role]
        if connector:
            base_parts.append(connector)
        base_parts.append(dept)

        base_title = " ".join(base_parts)

        # Apply variants (accent marks, case, whitespace)
        variants = [base_title]

        # Accent mark variants
        if "informatica" in base_title.lower():
            variants.append(base_title.replace("informatica", "informática"))
        if "rrhh" in base_title.lower():
            variants.append(base_title.replace("rrhh", "recursos humanos"))

        # Case variants
        variants.append(base_title.title())
        variants.append(base_title.upper())
        variants.append(base_title.lower())

        # Whitespace variants
        if "  " not in base_title:
            variants.append(base_title.replace(" ", "  "))
            variants.append(f" {base_title}")
            variants.append(f"{base_title} ")

        # Remove duplicates while preserving order
        seen = set()
        unique_variants = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                unique_variants.append(v)

        # Pick a random variant for this row
        original = random.choice(unique_variants)
        normalized = normalize(original)
        titles.append((i, original, normalized))

    return titles


def _clusters_are_equivalent(
    results1: list[ClusterResult],
    results2: list[ClusterResult],
) -> bool:
    """
    Check if two clustering results are equivalent.

    Two clusterings are equivalent if they have the same partition of rows,
    even if cluster_id assignments differ or members are in different order.
    """
    # Sort both results by cluster_id for consistent comparison
    sorted1 = sorted(results1, key=lambda cr: cr.cluster_id)
    sorted2 = sorted(results2, key=lambda cr: cr.cluster_id)

    # Must have same number of clusters
    if len(sorted1) != len(sorted2):
        return False

    # Build mapping from normalized representatives to member sets for result 1
    clusters1 = {cr.normalized_key: set(cr.member_row_indices) for cr in sorted1}

    # Check that each cluster in result 2 matches one in result 1
    for cr2 in sorted2:
        if cr2.normalized_key not in clusters1:
            return False
        if clusters1[cr2.normalized_key] != set(cr2.member_row_indices):
            return False

    return True


def _results_are_identical(
    results1: list[ClusterResult],
    results2: list[ClusterResult],
) -> bool:
    """
    Check if two clustering results are byte-identical.

    This is stricter than equivalence - it requires same cluster IDs,
    same representatives, same order, and same member order.
    """
    # Must have same number of clusters
    if len(results1) != len(results2):
        return False

    for cr1, cr2 in zip(results1, results2):
        if cr1.cluster_id != cr2.cluster_id:
            return False
        if cr1.representative_original != cr2.representative_original:
            return False
        if cr1.normalized_key != cr2.normalized_key:
            return False
        if cr1.member_row_indices != cr2.member_row_indices:
            return False
        if cr1.member_count != cr2.member_count:
            return False

    return True


def test_run_clustering_deterministic_same_input() -> None:
    """Run clustering twice on same input, results must be byte-identical."""
    titles = _generate_synthetic_spanish_titles(500)

    # Run clustering twice on same input
    results1 = run_clustering(titles, threshold=90)
    results2 = run_clustering(titles, threshold=90)

    # Results must be byte-identical
    assert _results_are_identical(results1, results2), (
        "Clustering results are not deterministic - running twice on same input "
        "produced different results"
    )


def test_run_clustering_deterministic_shuffled_input() -> None:
    """Run clustering on shuffled input, partition must be identical."""
    titles = _generate_synthetic_spanish_titles(500)

    # Run clustering on original order
    results1 = run_clustering(titles, threshold=90)

    # Shuffle rows while preserving row_index values
    shuffled_titles = list(titles)
    random.seed(42)
    random.shuffle(shuffled_titles)

    # Run clustering on shuffled input
    results2 = run_clustering(shuffled_titles, threshold=90)

    # Results must be equivalent (same partition of rows)
    assert _clusters_are_equivalent(results1, results2), (
        "Clustering results are not deterministic when input is shuffled - "
        "different partition of rows produced"
    )

    # Also verify total rows clustered is the same
    total_members1 = sum(cr.member_count for cr in results1)
    total_members2 = sum(cr.member_count for cr in results2)
    assert total_members1 == total_members2 == 500, (
        f"Expected 500 rows clustered, got {total_members1} and {total_members2}"
    )
