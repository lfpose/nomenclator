import json


def test_seed_prompt_system_prompt_contains_spanish_keywords(conn):
    """System prompt contains required Spanish keywords."""
    cur = conn.cursor()
    cur.execute("SELECT system_prompt FROM task_templates WHERE id = 'job_titles_es'")
    row = cur.fetchone()
    assert row is not None
    system_prompt = row[0]

    # Check for required Spanish keywords
    assert "normalizar" in system_prompt
    assert "masculina" in system_prompt
    assert "femenina" in system_prompt


def test_seed_prompt_has_eight_few_shots(conn):
    """Few shots JSON array contains exactly 8 examples."""
    cur = conn.cursor()
    cur.execute("SELECT few_shots FROM task_templates WHERE id = 'job_titles_es'")
    row = cur.fetchone()
    assert row is not None
    few_shots_json = row[0]

    few_shots = json.loads(few_shots_json)
    assert len(few_shots) == 8


def test_seed_prompt_few_shots_have_required_fields(conn):
    """Every few-shot item has required fields: input, male_es, female_es, category."""
    cur = conn.cursor()
    cur.execute("SELECT few_shots FROM task_templates WHERE id = 'job_titles_es'")
    row = cur.fetchone()
    assert row is not None
    few_shots_json = row[0]

    few_shots = json.loads(few_shots_json)
    for shot in few_shots:
        assert "input" in shot
        assert "male_es" in shot
        assert "female_es" in shot
        assert "category" in shot
