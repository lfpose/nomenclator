import json
import pytest

from app.anthropic.request_builder import (
    TitleInput,
    build_system_prompt,
    build_user_message,
    build_request_params,
)


def test_build_user_message_includes_taxonomy_when_present():
    """Test that taxonomy is included in user message when provided."""
    titles = [TitleInput(id="t001", title="Jefe de Compras")]
    taxonomy = "Gerencia\nOperaciones\nVentas"
    message = build_user_message(titles, taxonomy)
    assert "Taxonomía permitida para category" in message
    assert "- Gerencia" in message
    assert "- Operaciones" in message
    assert "- Ventas" in message
    assert "Títulos a estandarizar" in message


def test_build_user_message_omits_taxonomy_when_none():
    """Test that taxonomy section is omitted when taxonomy is None."""
    titles = [TitleInput(id="t001", title="Jefe de Compras")]
    message = build_user_message(titles, None)
    assert "Taxonomía" not in message
    assert "Títulos a estandarizar" in message
    assert '"id": "t001"' in message
    assert '"title": "Jefe de Compras"' in message


def test_build_user_message_serializes_titles_as_json_array():
    """Test that titles are serialized as JSON array with proper formatting."""
    titles = [
        TitleInput(id="t001", title="Jefe de Compras"),
        TitleInput(id="t002", title="Ingeniero de Software"),
    ]
    message = build_user_message(titles, None)
    # Verify JSON structure is present
    expected_data = json.dumps([{"id": "t001", "title": "Jefe de Compras"}, {"id": "t002", "title": "Ingeniero de Software"}], ensure_ascii=False, indent=2)
    assert expected_data in message


def test_build_request_params_sets_tool_choice_to_forced():
    """Test that tool_choice is set to force the tool."""
    titles = [TitleInput(id="t001", title="Jefe de Compras")]
    params = build_request_params(
        titles=titles,
        system_prompt="Test prompt",
        taxonomy=None,
        titles_per_request=1,
    )
    assert params["tool_choice"] == {"type": "tool", "name": "emit_standardized_titles"}


def test_build_request_params_temperature_is_zero():
    """Test that temperature is set to 0 for deterministic output."""
    titles = [TitleInput(id="t001", title="Jefe de Compras")]
    params = build_request_params(
        titles=titles,
        system_prompt="Test prompt",
        taxonomy=None,
        titles_per_request=1,
    )
    assert params["temperature"] == 0


def test_build_request_params_max_tokens_scales_with_tpr():
    """Test that max_tokens scales with titles_per_request."""
    titles_5 = [TitleInput(id=f"t{i:03d}", title=f"Title {i}") for i in range(5)]
    params_5 = build_request_params(
        titles=titles_5,
        system_prompt="Test prompt",
        taxonomy=None,
        titles_per_request=5,
    )
    assert params_5["max_tokens"] == 5 * 80 + 200  # 600

    titles_10 = [TitleInput(id=f"t{i:03d}", title=f"Title {i}") for i in range(10)]
    params_10 = build_request_params(
        titles=titles_10,
        system_prompt="Test prompt",
        taxonomy=None,
        titles_per_request=10,
    )
    assert params_10["max_tokens"] == 10 * 80 + 200  # 1000


def test_build_request_params_assertion_on_mismatched_tpr():
    """Test that assertion fails when titles length doesn't match titles_per_request."""
    titles = [TitleInput(id="t001", title="Jefe de Compras")]
    with pytest.raises(AssertionError):
        build_request_params(
            titles=titles,
            system_prompt="Test prompt",
            taxonomy=None,
            titles_per_request=5,  # Mismatch: 1 title but TPR=5
        )


def test_build_system_prompt_embeds_few_shots():
    """Test that few_shots are embedded into the system prompt."""
    template_prompt = "Eres un asistente especializado..."
    few_shots = [
        {"input": "Software Engineer", "male_es": "Ingeniero de Software", "female_es": "Ingeniera de Software", "category": "Tecnología"},
        {"input": "Marketing Manager", "male_es": "Gerente de Marketing", "female_es": "Gerenta de Marketing", "category": "Marketing"},
    ]
    result = build_system_prompt(template_prompt, few_shots)
    assert template_prompt in result
    assert "Ejemplos:" in result
    assert '- "Software Engineer" → {"male_es": "Ingeniero de Software", "female_es": "Ingeniera de Software", "category": "Tecnología"}' in result
    assert '- "Marketing Manager" → {"male_es": "Gerente de Marketing", "female_es": "Gerenta de Marketing", "category": "Marketing"}' in result
