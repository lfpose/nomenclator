# 05 — Anthropic Client and Tool Use

Reference: `spec/08-prompt-spec.md`, `spec/18-reliability-contract.md` layer 1–4.

All tasks here are testable against a mocked Anthropic API using `pytest-httpx` or by injecting a fake client. The real Anthropic client is only ever called from one module (`client.py`); everything else is pure logic.

---

### P05-01 — Pricing constants module

**Deps:** P01-02
**Files:** `backend/app/pricing.py`, `backend/tests/test_pricing.py`
**Goal:** A module of constants + a cost estimation function.

**Implementation:**
```python
HAIKU_BATCH_IN_USD_PER_MTOK = 0.40
HAIKU_BATCH_OUT_USD_PER_MTOK = 2.00

SYSTEM_PROMPT_TOKENS = 1300
USER_PREAMBLE_TOKENS = 200
IN_TOKENS_PER_TITLE = 10
OUT_TOKENS_PER_TITLE = 50
OUTPUT_OVERHEAD_TOKENS = 50

MONTHLY_SPEND_CAP_USD = 20.0

import math

def estimate_cost(cluster_count: int, titles_per_request: int) -> float:
    if cluster_count <= 0 or titles_per_request <= 0:
        return 0.0
    request_count = math.ceil(cluster_count / titles_per_request)
    tokens_in_per_req = SYSTEM_PROMPT_TOKENS + USER_PREAMBLE_TOKENS + titles_per_request * IN_TOKENS_PER_TITLE
    tokens_out_per_req = titles_per_request * OUT_TOKENS_PER_TITLE + OUTPUT_OVERHEAD_TOKENS
    total_in = request_count * tokens_in_per_req
    total_out = request_count * tokens_out_per_req
    return (
        total_in / 1_000_000 * HAIKU_BATCH_IN_USD_PER_MTOK
        + total_out / 1_000_000 * HAIKU_BATCH_OUT_USD_PER_MTOK
    )
```

**Test:** `cd backend && uv run pytest tests/test_pricing.py -v`

Required assertions:
- `test_estimate_cost_zero_clusters_returns_zero`
- `test_estimate_cost_2500_clusters_25_tpr_within_range` — 0.25 ≤ cost ≤ 0.50.
- `test_estimate_cost_monotonic_in_cluster_count`
- `test_estimate_cost_decreases_when_tpr_increases` — fixed cluster count, larger TPR → lower cost.

**Done when:**
- [ ] All 4 tests pass.

---

### P05-02 — Tool schema builder

**Deps:** P01-02
**Files:** `backend/app/anthropic/tool_schema.py`, `backend/tests/anthropic/test_tool_schema.py`
**Goal:** Pure function that returns the Anthropic tool definition dict with `minItems == maxItems == titles_per_request`.

**Implementation:**
```python
def build_tool_schema(titles_per_request: int) -> dict:
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
```

**Test:** `cd backend && uv run pytest tests/anthropic/test_tool_schema.py -v`

Required assertions:
- `test_schema_has_correct_name`
- `test_schema_minitems_equals_titles_per_request`
- `test_schema_maxitems_equals_titles_per_request`
- `test_schema_requires_four_fields_per_item`
- `test_schema_id_pattern_matches_t_prefix_numeric`

**Done when:**
- [ ] All 5 tests pass.

---

### P05-03 — System prompt content

**Deps:** P02-02
**Files:** `backend/app/migrations/002_seed_prompt.sql`, `backend/tests/test_seed_prompt.py`
**Goal:** Replace the `PLACEHOLDER` system_prompt and `[]` few_shots from migration 001 with the real content from `spec/08-prompt-spec.md`.

**Implementation:**
Create `002_seed_prompt.sql` with an `UPDATE` statement containing the full Spanish system prompt and the JSON array of 8 few-shot examples from `spec/08-prompt-spec.md`.

```sql
UPDATE task_templates
SET system_prompt = 'Eres un asistente especializado...<full prompt>',
    few_shots = '[...8 examples...]'
WHERE id = 'job_titles_es';
```

**Test:** `cd backend && uv run pytest tests/test_seed_prompt.py -v`

Required assertions:
- `test_seed_prompt_system_prompt_contains_spanish_keywords` — contains `"normalizar"`, `"masculina"`, `"femenina"`.
- `test_seed_prompt_has_eight_few_shots`
- `test_seed_prompt_few_shots_have_required_fields` — every item has `input`, `male_es`, `female_es`, `category`.

**Done when:**
- [ ] All 3 tests pass.

---

### P05-04 — Request builder

**Deps:** P02-04, P05-02, P05-03
**Files:** `backend/app/anthropic/request_builder.py`, `backend/tests/anthropic/test_request_builder.py`
**Goal:** Pure function that builds the full request body for one batch request, given the titles and the task template.

**Implementation:**
```python
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
```

**Test:** `cd backend && uv run pytest tests/anthropic/test_request_builder.py -v`

Required assertions:
- `test_build_user_message_includes_taxonomy_when_present`
- `test_build_user_message_omits_taxonomy_when_none`
- `test_build_user_message_serializes_titles_as_json_array`
- `test_build_request_params_sets_tool_choice_to_forced`
- `test_build_request_params_temperature_is_zero`
- `test_build_request_params_max_tokens_scales_with_tpr`
- `test_build_request_params_assertion_on_mismatched_tpr`
- `test_build_system_prompt_embeds_few_shots`

**Done when:**
- [ ] All 8 tests pass.

---

### P05-05 — Pydantic response models

**Deps:** P01-02
**Files:** `backend/app/anthropic/models.py`, `backend/tests/anthropic/test_models.py`
**Goal:** Strict Pydantic models that validate the tool-call output shape.

**Implementation:**
```python
from pydantic import BaseModel, ConfigDict, Field

class TitleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^t[0-9]+$")
    male_es: str = Field(min_length=1)
    female_es: str = Field(min_length=1)
    category: str = Field(min_length=1)

class ToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[TitleResult]
```

**Test:** `cd backend && uv run pytest tests/anthropic/test_models.py -v`

Required assertions:
- `test_parse_valid_tool_output`
- `test_parse_missing_male_es_raises`
- `test_parse_empty_male_es_raises`
- `test_parse_bad_id_pattern_raises`
- `test_parse_extra_field_raises` — `extra="forbid"` enforcement.
- `test_parse_empty_results_array_allowed` — empty list is valid at Pydantic level; count enforcement happens elsewhere.

**Done when:**
- [ ] All 6 tests pass.

---

### P05-06 — Response parser

**Deps:** P05-05
**Files:** `backend/app/anthropic/response_parser.py`, `backend/tests/anthropic/test_response_parser.py`
**Goal:** Extract the tool call from an Anthropic message response, validate via Pydantic, return `ToolOutput` or raise a specific error.

**Implementation:**
```python
from .models import ToolOutput

class ParseError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

def parse_tool_call(message: dict) -> ToolOutput:
    content = message.get("content", [])
    tool_use_block = next(
        (block for block in content if block.get("type") == "tool_use" and block.get("name") == "emit_standardized_titles"),
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
```

**Test:** `cd backend && uv run pytest tests/anthropic/test_response_parser.py -v`

Required assertions:
- `test_parse_valid_tool_use_returns_tool_output`
- `test_parse_missing_tool_use_raises_tool_call_missing`
- `test_parse_max_tokens_stop_reason_raises_truncated`
- `test_parse_invalid_schema_raises_schema_violation`

**Done when:**
- [ ] All 4 tests pass.

---

### P05-07 — Straggler detection

**Deps:** P05-06
**Files:** `backend/app/anthropic/response_parser.py` (extend), `backend/tests/anthropic/test_stragglers.py`
**Goal:** Given expected IDs and a `ToolOutput`, return missing + extra + valid sets.

**Implementation:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class StragglerAnalysis:
    present_ids: set[str]
    missing_ids: set[str]
    extra_ids: set[str]
    results_by_id: dict[str, "TitleResult"]

def analyze_stragglers(expected_ids: set[str], output: ToolOutput) -> StragglerAnalysis:
    returned = {r.id: r for r in output.results}
    returned_ids = set(returned.keys())
    return StragglerAnalysis(
        present_ids=expected_ids & returned_ids,
        missing_ids=expected_ids - returned_ids,
        extra_ids=returned_ids - expected_ids,
        results_by_id={k: v for k, v in returned.items() if k in expected_ids},
    )
```

**Test:** `cd backend && uv run pytest tests/anthropic/test_stragglers.py -v`

Required assertions:
- `test_all_present_no_stragglers`
- `test_some_missing_reported`
- `test_extra_ids_reported`
- `test_results_by_id_excludes_extras`
- `test_empty_response_all_missing`

**Done when:**
- [ ] All 5 tests pass.

---

### P05-08 — Anthropic client wrapper

**Deps:** P05-04, P05-05, P05-06
**Files:** `backend/app/anthropic/client.py`, `backend/tests/anthropic/test_client.py`
**Goal:** Wrap the Anthropic SDK's batch operations in a tiny, testable interface. The real implementation uses `anthropic.Anthropic`; tests inject a fake.

**Implementation:**
```python
from typing import Protocol
from anthropic import Anthropic

class AnthropicBatchClient(Protocol):
    def submit_batch(self, requests: list[dict]) -> str: ...
    def get_batch_status(self, batch_id: str) -> dict: ...
    def get_batch_results(self, batch_id: str) -> list[dict]: ...
    def cancel_batch(self, batch_id: str) -> None: ...

class RealAnthropicClient:
    def __init__(self, api_key: str):
        self._anthropic = Anthropic(api_key=api_key)

    def submit_batch(self, requests: list[dict]) -> str:
        batch = self._anthropic.messages.batches.create(requests=requests)
        return batch.id

    def get_batch_status(self, batch_id: str) -> dict:
        batch = self._anthropic.messages.batches.retrieve(batch_id)
        return {"id": batch.id, "processing_status": batch.processing_status, "ended_at": batch.ended_at}

    def get_batch_results(self, batch_id: str) -> list[dict]:
        return list(self._anthropic.messages.batches.results(batch_id))

    def cancel_batch(self, batch_id: str) -> None:
        self._anthropic.messages.batches.cancel(batch_id)
```

`Protocol` matters — the tests provide a fake class with the same methods; the service layer depends only on the protocol.

**Test:** `cd backend && uv run pytest tests/anthropic/test_client.py -v`

Required assertions (using a `FakeAnthropicBatchClient` stub):
- `test_protocol_accepts_fake_client` — structural typing works.
- `test_real_client_initializes_with_api_key` — no exceptions, doesn't call API.
- A fake-based sanity test: submit, get status, get results, cancel, each with expected shapes.

**Done when:**
- [ ] Tests pass without any real Anthropic call.
- [ ] No module imports `RealAnthropicClient` outside `client.py` and `main.py`.

---

### P05-09 — Fake Anthropic client fixture

**Deps:** P05-08
**Files:** `backend/tests/conftest.py` (extend), `backend/tests/anthropic/fake_client.py`
**Goal:** A shared pytest fixture providing a `FakeAnthropicBatchClient` with configurable responses, used by every downstream test (worker, api, reliability).

**Implementation:**
```python
# backend/tests/anthropic/fake_client.py
from dataclasses import dataclass, field

@dataclass
class FakeBatch:
    id: str
    requests: list[dict]
    processing_status: str = "in_progress"
    result_rows: list[dict] = field(default_factory=list)

class FakeAnthropicBatchClient:
    def __init__(self) -> None:
        self.batches: dict[str, FakeBatch] = {}
        self._next_id = 0

    def submit_batch(self, requests: list[dict]) -> str:
        self._next_id += 1
        batch_id = f"batch_fake_{self._next_id}"
        self.batches[batch_id] = FakeBatch(id=batch_id, requests=requests)
        return batch_id

    def get_batch_status(self, batch_id: str) -> dict:
        b = self.batches[batch_id]
        return {"id": b.id, "processing_status": b.processing_status, "ended_at": None}

    def get_batch_results(self, batch_id: str) -> list[dict]:
        return self.batches[batch_id].result_rows

    def cancel_batch(self, batch_id: str) -> None:
        self.batches[batch_id].processing_status = "canceled"

    # test helpers
    def complete_batch(self, batch_id: str, results: list[dict]) -> None:
        self.batches[batch_id].processing_status = "ended"
        self.batches[batch_id].result_rows = results
```

Add a `fake_anthropic` fixture to `conftest.py`.

**Test:** `cd backend && uv run pytest tests/anthropic/test_fake_client.py -v`

Required assertions:
- `test_fake_submit_returns_batch_id`
- `test_fake_complete_batch_sets_status_and_results`
- `test_fake_cancel_sets_canceled_status`

**Done when:**
- [ ] All 3 tests pass.
- [ ] The fixture is importable from `conftest.py`.

---

### P05-10 — Prompt review client

**Deps:** P01-02
**Files:** `backend/app/anthropic/review.py`, `backend/tests/anthropic/test_review.py`
**Goal:** A function that sends the operator's prompt + few-shots to Claude Haiku (non-batch) for quality/safety review.

**Implementation:**
```python
from anthropic import Anthropic

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

from dataclasses import dataclass

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
        messages=[{"role": "user", "content": f"Prompt to review:\n\n{prompt}\n\nFew-shot examples:\n\n{few_shots}"}],
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
```

**Test:** `cd backend && uv run pytest tests/anthropic/test_review.py -v`

Required assertions (mock the Anthropic client):
- `test_review_prompt_returns_prompt_review_dataclass`
- `test_review_prompt_calls_haiku_with_tool_choice`
- `test_review_prompt_handles_good_quality_score`
- `test_review_prompt_handles_poor_quality_score`
- `test_review_prompt_raises_on_api_error`

**Done when:**
- [ ] All 5 tests pass without real API calls.

---

### P05-11 — Dry-run response generator

**Deps:** P05-05
**Files:** `backend/app/anthropic/dry_run.py`, `backend/tests/anthropic/test_dry_run.py`
**Goal:** Generate fake deterministic responses for dry-run jobs, matching the same ToolOutput shape as real responses.

**Implementation:**
```python
from .models import ToolOutput, TitleResult

def generate_dry_run_results(
    cluster_ids: list[int],
    titles: list[str],  # representative titles, one per cluster_id
) -> ToolOutput:
    results = []
    for i, (cid, title) in enumerate(zip(cluster_ids, titles)):
        results.append(TitleResult(
            id=f"t{i+1:03d}",
            male_es=f"{title} (M)",
            female_es=f"{title} (F)",
            category="DRY_RUN",
        ))
    return ToolOutput(results=results)
```

**Test:** `cd backend && uv run pytest tests/anthropic/test_dry_run.py -v`

Required assertions:
- `test_dry_run_returns_tool_output_with_correct_count`
- `test_dry_run_male_es_has_m_suffix`
- `test_dry_run_female_es_has_f_suffix`
- `test_dry_run_category_is_dry_run`
- `test_dry_run_ids_are_sequential_t_prefixed`
- `test_dry_run_deterministic_same_input_same_output`

**Done when:**
- [ ] All 6 tests pass.
