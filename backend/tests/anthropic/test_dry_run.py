from app.anthropic.dry_run import generate_dry_run_results
from app.anthropic.models import ToolOutput


def test_dry_run_returns_tool_output_with_correct_count():
    cluster_ids = [1, 2, 3]
    titles = ["Jefe de Compras", "Ingeniero de Software", "Director de Marketing"]
    result = generate_dry_run_results(cluster_ids, titles)
    assert isinstance(result, ToolOutput)
    assert len(result.results) == 3


def test_dry_run_male_es_has_m_suffix():
    cluster_ids = [1]
    titles = ["Gerente de Ventas"]
    result = generate_dry_run_results(cluster_ids, titles)
    assert result.results[0].male_es == "Gerente de Ventas (M)"


def test_dry_run_female_es_has_f_suffix():
    cluster_ids = [1]
    titles = ["Gerente de Ventas"]
    result = generate_dry_run_results(cluster_ids, titles)
    assert result.results[0].female_es == "Gerente de Ventas (F)"


def test_dry_run_category_is_dry_run():
    cluster_ids = [1, 2]
    titles = ["Analista de Datos", "Contador"]
    result = generate_dry_run_results(cluster_ids, titles)
    assert all(r.category == "DRY_RUN" for r in result.results)


def test_dry_run_ids_are_sequential_t_prefixed():
    cluster_ids = [10, 20, 30, 40]
    titles = ["Role1", "Role2", "Role3", "Role4"]
    result = generate_dry_run_results(cluster_ids, titles)
    assert [r.id for r in result.results] == ["t001", "t002", "t003", "t004"]


def test_dry_run_deterministic_same_input_same_output():
    cluster_ids = [5, 6, 7]
    titles = ["Doctor", "Abogado", "Ingeniero"]
    result1 = generate_dry_run_results(cluster_ids, titles)
    result2 = generate_dry_run_results(cluster_ids, titles)
    assert result1.results == result2.results
