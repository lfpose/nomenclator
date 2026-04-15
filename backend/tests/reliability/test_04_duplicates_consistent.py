from app.csv_io.exporter import export_job_to_csv


def test_all_duplicate_originals_have_same_male_es(conn, fake_anthropic, run_e2e):
    """If the same original appears multiple times in input, all output rows have identical male_es."""
    # Input has 10 × "Jefe de Compras" + 5 other distinct titles
    titles = ["Jefe de Compras"] * 10 + [
        "Ingeniero de Software",
        "Director de Marketing",
        "Analista de Datos",
        "Gerente de Ventas",
        "Coordinador de Proyectos",
    ]

    job_id = run_e2e(n_rows=15, conn=conn, fake=fake_anthropic, titles=titles)

    # Export CSV
    csv_bytes = export_job_to_csv(conn, job_id)
    csv_text = csv_bytes.decode("utf-8-sig")

    # Parse CSV, skip header
    lines = csv_text.splitlines()
    assert len(lines) == 16  # header + 15 data rows

    # Group rows by original title
    rows_by_original = {}
    for line in lines[1:]:  # Skip header
        # CSV format: original,male_es,female_es,category,error
        parts = line.split(",")
        original = parts[0]
        male_es = parts[1]
        rows_by_original.setdefault(original, []).append(male_es)

    # Verify all 10 "Jefe de Compras" rows have identical male_es
    jefe_male_es_values = rows_by_original["Jefe de Compras"]
    assert len(jefe_male_es_values) == 10, "Expected 10 Jefe de Compras rows"
    assert all(
        male == jefe_male_es_values[0] for male in jefe_male_es_values
    ), "All Jefe de Compras rows should have identical male_es"


def test_all_duplicate_originals_have_same_female_es(conn, fake_anthropic, run_e2e):
    """If the same original appears multiple times in input, all output rows have identical female_es."""
    # Input has 10 × "Jefe de Compras" + 5 other distinct titles
    titles = ["Jefe de Compras"] * 10 + [
        "Ingeniero de Software",
        "Director de Marketing",
        "Analista de Datos",
        "Gerente de Ventas",
        "Coordinador de Proyectos",
    ]

    job_id = run_e2e(n_rows=15, conn=conn, fake=fake_anthropic, titles=titles)

    # Export CSV
    csv_bytes = export_job_to_csv(conn, job_id)
    csv_text = csv_bytes.decode("utf-8-sig")

    # Parse CSV, skip header
    lines = csv_text.splitlines()
    assert len(lines) == 16  # header + 15 data rows

    # Group rows by original title
    rows_by_original = {}
    for line in lines[1:]:  # Skip header
        # CSV format: original,male_es,female_es,category,error
        parts = line.split(",")
        original = parts[0]
        female_es = parts[2]
        rows_by_original.setdefault(original, []).append(female_es)

    # Verify all 10 "Jefe de Compras" rows have identical female_es
    jefe_female_es_values = rows_by_original["Jefe de Compras"]
    assert len(jefe_female_es_values) == 10, "Expected 10 Jefe de Compras rows"
    assert all(
        female == jefe_female_es_values[0] for female in jefe_female_es_values
    ), "All Jefe de Compras rows should have identical female_es"


def test_all_duplicate_originals_have_same_category(conn, fake_anthropic, run_e2e):
    """If the same original appears multiple times in input, all output rows have identical category."""
    # Input has 10 × "Jefe de Compras" + 5 other distinct titles
    titles = ["Jefe de Compras"] * 10 + [
        "Ingeniero de Software",
        "Director de Marketing",
        "Analista de Datos",
        "Gerente de Ventas",
        "Coordinador de Proyectos",
    ]

    job_id = run_e2e(n_rows=15, conn=conn, fake=fake_anthropic, titles=titles)

    # Export CSV
    csv_bytes = export_job_to_csv(conn, job_id)
    csv_text = csv_bytes.decode("utf-8-sig")

    # Parse CSV, skip header
    lines = csv_text.splitlines()
    assert len(lines) == 16  # header + 15 data rows

    # Group rows by original title
    rows_by_original = {}
    for line in lines[1:]:  # Skip header
        # CSV format: original,male_es,female_es,category,error
        parts = line.split(",")
        original = parts[0]
        category = parts[3]
        rows_by_original.setdefault(original, []).append(category)

    # Verify all 10 "Jefe de Compras" rows have identical category
    jefe_category_values = rows_by_original["Jefe de Compras"]
    assert len(jefe_category_values) == 10, "Expected 10 Jefe de Compras rows"
    assert all(
        cat == jefe_category_values[0] for cat in jefe_category_values
    ), "All Jefe de Compras rows should have identical category"
