from dataclasses import dataclass


@dataclass(frozen=True)
class TitleInput:
    id: str  # "t001", "t002", ...
    title: str


def build_system_prompt(template_system_prompt: str, few_shots: list) -> str:
    # Embed few-shots into the system prompt before strict rules
    shots_block = "\n".join(
        f'- "{s["input"]}" → {{"male_es": "{s["male_es"]}", "female_es": "{s["female_es"]}", "category": "{s["category"]}"}}'
        for s in few_shots
    )
    return f"{template_system_prompt}\n\nEjemplos:\n{shots_block}"


def build_user_message(titles: list[TitleInput], taxonomy: str | None) -> str:
    lines = []
    if taxonomy:
        lines.append("Taxonomía permitida para category (usa EXACTAMENTE uno de estos valores):")
        for t in taxonomy.strip().splitlines():
            if t.strip():
                lines.append(f"- {t.strip()}")
        lines.append("")
    lines.append("Títulos a estandarizar (responde llamando a `emit_standardized_titles`):")
    lines.append("")
    import json

    lines.append(json.dumps([{"id": t.id, "title": t.title} for t in titles], ensure_ascii=False, indent=2))
    return "\n".join(lines)


def build_request_params(
    *, titles: list[TitleInput], system_prompt: str, taxonomy: str | None, titles_per_request: int
) -> dict:
    assert len(titles) == titles_per_request
    from .tool_schema import build_tool_schema

    return {
        "model": "claude-haiku-4-5",
        "max_tokens": titles_per_request * 80 + 200,
        "temperature": 0,
        "system": system_prompt,
        "messages": [{"role": "user", "content": build_user_message(titles, taxonomy)}],
        "tools": [build_tool_schema(titles_per_request)],
        "tool_choice": {"type": "tool", "name": "emit_standardized_titles"},
    }
