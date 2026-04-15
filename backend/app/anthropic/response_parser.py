from .models import ToolOutput


class ParseError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


def parse_tool_call(message: dict) -> ToolOutput:
    content = message.get("content", [])
    tool_use_block = next(
        (
            block
            for block in content
            if block.get("type") == "tool_use" and block.get("name") == "emit_standardized_titles"
        ),
        None,
    )
    if tool_use_block is None:
        raise ParseError("tool_call_missing", "Response did not contain the expected tool call.")
    stop_reason = message.get("stop_reason")
    if stop_reason == "max_tokens":
        raise ParseError("truncated", "Response was truncated by max_tokens.")
    try:
        return ToolOutput.model_validate(tool_use_block.get("input", {}))
    except Exception as e:
        raise ParseError("schema_violation", f"Tool output schema violation: {e}")
