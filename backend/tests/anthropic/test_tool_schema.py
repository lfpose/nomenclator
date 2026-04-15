"""Tests for tool_schema.py build_tool_schema function."""

from app.anthropic.tool_schema import build_tool_schema


def test_schema_has_correct_name():
    """Verify the schema has the expected tool name."""
    schema = build_tool_schema(titles_per_request=10)
    assert schema["name"] == "emit_standardized_titles"


def test_schema_minitems_equals_titles_per_request():
    """Verify minItems in results array equals titles_per_request."""
    schema = build_tool_schema(titles_per_request=25)
    results_schema = schema["input_schema"]["properties"]["results"]
    assert results_schema["minItems"] == 25


def test_schema_maxitems_equals_titles_per_request():
    """Verify maxItems in results array equals titles_per_request."""
    schema = build_tool_schema(titles_per_request=50)
    results_schema = schema["input_schema"]["properties"]["results"]
    assert results_schema["maxItems"] == 50


def test_schema_requires_four_fields_per_item():
    """Verify each item in results requires exactly four fields."""
    schema = build_tool_schema(titles_per_request=10)
    item_schema = schema["input_schema"]["properties"]["results"]["items"]
    required = item_schema["required"]
    assert required == ["id", "male_es", "female_es", "category"]


def test_schema_id_pattern_matches_t_prefix_numeric():
    """Verify the id field pattern matches t-prefix followed by digits."""
    schema = build_tool_schema(titles_per_request=10)
    id_field = schema["input_schema"]["properties"]["results"]["items"]["properties"]["id"]
    assert id_field["pattern"] == "^t[0-9]+$"
