from anthropic import Anthropic
from dataclasses import dataclass

REVIEW_SYSTEM_PROMPT = """You are an expert prompt engineer reviewing a prompt that will be used to standardize job titles via an AI batch processing system.

You will receive:
1. A system prompt that the operator wants to use
2. A set of few-shot examples (may be empty)

Evaluate the prompt on these criteria:
- **Safety**: Is the prompt asking the model to do legitimate standardization work? Flag if it asks for anything unrelated.
- **Clarity**: Is the prompt clear about what output format is expected?
- **Completeness**: Does it cover edge cases (English→Spanish translation, gender-neutral titles, ambiguous titles)?
- **Few-shot quality**: Do the examples demonstrate the expected input→output mapping correctly?

Respond by calling the `review_prompt` tool with your assessment."""

REVIEW_TOOL = {
    "name": "review_prompt",
    "description": "Submit the structured review of the operator's prompt and few-shot examples.",
    "input_schema": {
        "type": "object",
        "required": ["safe", "quality_score", "issues", "suggestions", "summary"],
        "additionalProperties": False,
        "properties": {
            "safe": {"type": "boolean"},
            "quality_score": {"type": "string", "enum": ["good", "needs_work", "poor"]},
            "issues": {"type": "array", "items": {"type": "string"}},
            "suggestions": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
        },
    },
}


@dataclass(frozen=True)
class PromptReview:
    safe: bool
    quality_score: str
    issues: list[str]
    suggestions: list[str]
    summary: str


def review_prompt(api_key: str, prompt: str, few_shots: str) -> PromptReview:
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1000,
        temperature=0,
        system=REVIEW_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Prompt to review:\n\n{prompt}\n\nFew-shot examples:\n\n{few_shots}",
            }
        ],
        tools=[REVIEW_TOOL],
        tool_choice={"type": "tool", "name": "review_prompt"},
    )
    tool_block = next(b for b in message.content if b.type == "tool_use")
    inp = tool_block.input
    return PromptReview(
        safe=inp["safe"],
        quality_score=inp["quality_score"],
        issues=inp.get("issues", []),
        suggestions=inp.get("suggestions", []),
        summary=inp["summary"],
    )
