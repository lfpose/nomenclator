import pytest

from app.anthropic.models import ToolOutput


def test_parse_valid_tool_output():
    data = {
        "results": [
            {
                "id": "t001",
                "male_es": "Jefe de Compras",
                "female_es": "Jefa de Compras",
                "category": "management",
            },
            {
                "id": "t002",
                "male_es": "Ingeniero de Software",
                "female_es": "Ingeniera de Software",
                "category": "technology",
            },
        ]
    }
    output = ToolOutput.model_validate(data)
    assert len(output.results) == 2
    assert output.results[0].id == "t001"
    assert output.results[0].male_es == "Jefe de Compras"
    assert output.results[1].id == "t002"


def test_parse_missing_male_es_raises():
    data = {
        "results": [
            {
                "id": "t001",
                "female_es": "Jefa de Compras",
                "category": "management",
            }
        ]
    }
    with pytest.raises(ValueError) as exc_info:
        ToolOutput.model_validate(data)
    assert "male_es" in str(exc_info.value).lower()


def test_parse_empty_male_es_raises():
    data = {
        "results": [
            {
                "id": "t001",
                "male_es": "",
                "female_es": "Jefa de Compras",
                "category": "management",
            }
        ]
    }
    with pytest.raises(ValueError) as exc_info:
        ToolOutput.model_validate(data)
    assert "male_es" in str(exc_info.value).lower() or "at least 1" in str(exc_info.value).lower()


def test_parse_bad_id_pattern_raises():
    data = {
        "results": [
            {
                "id": "invalid",
                "male_es": "Jefe de Compras",
                "female_es": "Jefa de Compras",
                "category": "management",
            }
        ]
    }
    with pytest.raises(ValueError) as exc_info:
        ToolOutput.model_validate(data)
    assert "id" in str(exc_info.value).lower() or "pattern" in str(exc_info.value).lower()


def test_parse_extra_field_raises():
    data = {
        "results": [
            {
                "id": "t001",
                "male_es": "Jefe de Compras",
                "female_es": "Jefa de Compras",
                "category": "management",
                "unexpected_field": "should not be here",
            }
        ]
    }
    with pytest.raises(ValueError) as exc_info:
        ToolOutput.model_validate(data)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()


def test_parse_empty_results_array_allowed():
    data = {"results": []}
    output = ToolOutput.model_validate(data)
    assert output.results == []
    assert len(output.results) == 0
