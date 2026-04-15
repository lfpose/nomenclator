"""P12-03: Test 3: Every input row is in output.

Verifies that the set of original values in output equals the set of input
values (accounting for duplicates).
"""

from app.csv_io.exporter import export_job_to_csv


def test_output_multiset_equals_input_multiset(conn, fake_anthropic, run_e2e):
    """Verify that output's original column has same multiset as input.

    Uses input with duplicates and unique values mixed. After export,
    assert Counter(input) == Counter(output[original]).
    """
    # Create input with duplicates and unique values mixed
    titles = [
        "Jefe de Compras",  # Will appear 3 times
        "Ingeniero de Software",
        "Jefe de Compras",  # Duplicate
        "Gerente de Ventas",
        "Jefe de Compras",  # Duplicate
        "Director de Marketing",
        "Analista de Datos",
        "Ingeniero de Software",  # Duplicate
        "Recursos Humanos",
        "Gerente de Proyectos",
    ]

    job_id = run_e2e(n_rows=len(titles), conn=conn, fake=fake_anthropic, titles=titles)

    # Export CSV and extract original column
    csv_bytes = export_job_to_csv(conn, job_id)
    csv_text = csv_bytes.decode("utf-8-sig")
    lines = csv_text.splitlines()

    # Skip header row
    data_lines = lines[1:]

    # Extract original column (first column)
    output_originals = []
    for line in data_lines:
        if line.strip():  # Skip empty lines
            columns = line.split(",")
            output_originals.append(columns[0])

    # Count occurrences
    from collections import Counter

    input_counter = Counter(titles)
    output_counter = Counter(output_originals)

    # Assert multiset equality
    assert input_counter == output_counter, (
        f"Input multiset {input_counter} does not match output multiset {output_counter}"
    )


def test_no_hallucinated_rows(conn, fake_anthropic, run_e2e):
    """Verify that no extra rows appear in output that weren't in input.

    Ensures the system doesn't hallucinate new job titles.
    """
    # Create input with distinct titles
    titles = [
        "Director Financiero",
        "Jefe de Operaciones",
        "Gerente de Calidad",
        "Ingeniero Civil",
        "Arquitecto de Software",
    ]

    job_id = run_e2e(n_rows=len(titles), conn=conn, fake=fake_anthropic, titles=titles)

    # Export CSV and extract original column
    csv_bytes = export_job_to_csv(conn, job_id)
    csv_text = csv_bytes.decode("utf-8-sig")
    lines = csv_text.splitlines()

    # Skip header row
    data_lines = lines[1:]

    # Extract original column (first column)
    output_originals = []
    for line in data_lines:
        if line.strip():  # Skip empty lines
            columns = line.split(",")
            output_originals.append(columns[0])

    # Convert to sets for comparison
    input_set = set(titles)
    output_set = set(output_originals)

    # Assert no extra rows (output is subset of input)
    assert output_set.issubset(input_set), (
        f"Output contains hallucinated rows not in input: {output_set - input_set}"
    )

    # Also assert no missing rows (input is subset of output)
    assert input_set.issubset(output_set), (
        f"Output is missing rows from input: {input_set - output_set}"
    )
