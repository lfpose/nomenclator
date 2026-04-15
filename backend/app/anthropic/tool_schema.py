"""Tool schema builder for Anthropic's tool use API."""


def build_tool_schema(titles_per_request: int) -> dict:
    """Build the Anthropic tool definition dict for emit_standardized_titles.

    Args:
        titles_per_request: Number of titles to include in each batch request.
            This enforces exactly one result per input id.

    Returns:
        A dict conforming to Anthropic's tool schema format with
        minItems == maxItems == titles_per_request.
    """
    return {
        "name": "emit_standardized_titles",
        "description": "Emit standardized Spanish job titles for every input entry. Must include exactly one result per input id, with identical ids.",
        "input_schema": {
            "type": "object",
            "required": ["results"],
            "additionalProperties": False,
            "properties": {
                "results": {
                    "type": "array",
                    "minItems": titles_per_request,
                    "maxItems": titles_per_request,
                    "items": {
                        "type": "object",
                        "required": ["id", "male_es", "female_es", "category"],
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string", "pattern": "^t[0-9]+$"},
                            "male_es": {"type": "string", "minLength": 1},
                            "female_es": {"type": "string", "minLength": 1},
                            "category": {"type": "string", "minLength": 1},
                        },
                    },
                }
            },
        },
    }
