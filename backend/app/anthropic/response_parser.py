from dataclasses import dataclass

from .models import ToolOutput, TitleResult


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


@dataclass(frozen=True)
class StragglerAnalysis:
    present_ids: set[str]
    missing_ids: set[str]
    extra_ids: set[str]
    results_by_id: dict[str, TitleResult]


def analyze_stragglers(expected_ids: set[str], output: ToolOutput) -> StragglerAnalysis:
    """Analyze a ToolOutput to find missing, extra, and present IDs.

    Args:
        expected_ids: Set of IDs we expect to receive (e.g., {"t001", "t002"})
        output: ToolOutput from parse_tool_call

    Returns:
        StragglerAnalysis with sets of present, missing, and extra IDs,
        plus a dict mapping present IDs to their TitleResults.
    """
    returned = {r.id: r for r in output.results}
    returned_ids = set(returned.keys())
    return StragglerAnalysis(
        present_ids=expected_ids & returned_ids,
        missing_ids=expected_ids - returned_ids,
        extra_ids=returned_ids - expected_ids,
        results_by_id={k: v for k, v in returned.items() if k in expected_ids},
    )
