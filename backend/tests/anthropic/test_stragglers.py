from app.anthropic.models import TitleResult, ToolOutput
from app.anthropic.response_parser import analyze_stragglers


def test_all_present_no_stragglers():
    """When all expected IDs are present, missing and extra are empty."""
    output = ToolOutput(
        results=[
            TitleResult(id="t001", male_es="Jefe de Compras", female_es="Jefa de Compras", category="Management"),
            TitleResult(id="t002", male_es="Ingeniero de Software", female_es="Ingeniera de Software", category="Engineering"),
            TitleResult(id="t003", male_es="Contador", female_es="Contadora", category="Finance"),
        ]
    )
    expected_ids = {"t001", "t002", "t003"}
    analysis = analyze_stragglers(expected_ids, output)

    assert analysis.present_ids == expected_ids
    assert analysis.missing_ids == set()
    assert analysis.extra_ids == set()
    assert len(analysis.results_by_id) == 3


def test_some_missing_reported():
    """When some expected IDs are missing, they appear in missing_ids."""
    output = ToolOutput(
        results=[
            TitleResult(id="t001", male_es="Jefe de Compras", female_es="Jefa de Compras", category="Management"),
            # t002 is missing
            TitleResult(id="t003", male_es="Contador", female_es="Contadora", category="Finance"),
        ]
    )
    expected_ids = {"t001", "t002", "t003"}
    analysis = analyze_stragglers(expected_ids, output)

    assert analysis.present_ids == {"t001", "t003"}
    assert analysis.missing_ids == {"t002"}
    assert analysis.extra_ids == set()
    assert len(analysis.results_by_id) == 2
    assert "t002" not in analysis.results_by_id


def test_extra_ids_reported():
    """When extra unexpected IDs are present, they appear in extra_ids."""
    output = ToolOutput(
        results=[
            TitleResult(id="t001", male_es="Jefe de Compras", female_es="Jefa de Compras", category="Management"),
            TitleResult(id="t002", male_es="Ingeniero de Software", female_es="Ingeniera de Software", category="Engineering"),
            TitleResult(id="t099", male_es="Extra Title", female_es="Extra Title (F)", category="Other"),
        ]
    )
    expected_ids = {"t001", "t002"}
    analysis = analyze_stragglers(expected_ids, output)

    assert analysis.present_ids == {"t001", "t002"}
    assert analysis.missing_ids == set()
    assert analysis.extra_ids == {"t099"}
    assert len(analysis.results_by_id) == 2
    assert "t099" not in analysis.results_by_id


def test_results_by_id_excludes_extras():
    """results_by_id only contains entries for expected IDs."""
    output = ToolOutput(
        results=[
            TitleResult(id="t001", male_es="Jefe de Compras", female_es="Jefa de Compras", category="Management"),
            TitleResult(id="t002", male_es="Ingeniero de Software", female_es="Ingeniera de Software", category="Engineering"),
            TitleResult(id="t099", male_es="Extra Title", female_es="Extra Title (F)", category="Other"),
        ]
    )
    expected_ids = {"t001", "t002"}
    analysis = analyze_stragglers(expected_ids, output)

    # results_by_id should only have the two expected IDs
    assert set(analysis.results_by_id.keys()) == {"t001", "t002"}

    # Verify the values are correct
    assert analysis.results_by_id["t001"].male_es == "Jefe de Compras"
    assert analysis.results_by_id["t002"].male_es == "Ingeniero de Software"

    # Extra ID should not be in results_by_id
    assert "t099" not in analysis.results_by_id


def test_empty_response_all_missing():
    """When response is empty, all expected IDs are reported as missing."""
    output = ToolOutput(results=[])
    expected_ids = {"t001", "t002", "t003"}
    analysis = analyze_stragglers(expected_ids, output)

    assert analysis.present_ids == set()
    assert analysis.missing_ids == expected_ids
    assert analysis.extra_ids == set()
    assert len(analysis.results_by_id) == 0
