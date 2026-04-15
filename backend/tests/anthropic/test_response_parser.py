from app.anthropic.response_parser import ParseError, parse_tool_call


def test_parse_valid_tool_use_returns_tool_output():
    message = {
        "content": [
            {
                "type": "tool_use",
                "name": "emit_standardized_titles",
                "input": {
                    "results": [
                        {"id": "t001", "male_es": "Jefe de Compras", "female_es": "Jefa de Compras", "category": "Gerencia"}
                    ]
                },
            }
        ],
        "stop_reason": "end_turn",
    }
    output = parse_tool_call(message)
    assert len(output.results) == 1
    assert output.results[0].id == "t001"
    assert output.results[0].male_es == "Jefe de Compras"
    assert output.results[0].female_es == "Jefa de Compras"
    assert output.results[0].category == "Gerencia"


def test_parse_missing_tool_use_raises_tool_call_missing():
    message = {
        "content": [{"type": "text", "text": "Hello"}],
        "stop_reason": "end_turn",
    }
    try:
        parse_tool_call(message)
        assert False, "Expected ParseError"
    except ParseError as e:
        assert e.code == "tool_call_missing"
        assert "did not contain the expected tool call" in e.message


def test_parse_max_tokens_stop_reason_raises_truncated():
    message = {
        "content": [
            {
                "type": "tool_use",
                "name": "emit_standardized_titles",
                "input": {"results": []},
            }
        ],
        "stop_reason": "max_tokens",
    }
    try:
        parse_tool_call(message)
        assert False, "Expected ParseError"
    except ParseError as e:
        assert e.code == "truncated"
        assert "truncated by max_tokens" in e.message


def test_parse_invalid_schema_raises_schema_violation():
    message = {
        "content": [
            {
                "type": "tool_use",
                "name": "emit_standardized_titles",
                "input": {
                    "results": [
                        {"id": "t001", "male_es": "Jefe de Compras", "female_es": "Jefa de Compras"}
                        # Missing 'category' field
                    ]
                },
            }
        ],
        "stop_reason": "end_turn",
    }
    try:
        parse_tool_call(message)
        assert False, "Expected ParseError"
    except ParseError as e:
        assert e.code == "schema_violation"
        assert "schema violation" in e.message
