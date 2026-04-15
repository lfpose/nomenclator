# 08 — Prompt Spec

The full v1 prompt for `task_template = job_titles_es`, including the Anthropic tool definition that enforces structural output. This file is authoritative — the seed data in `005-data-model.md` points here.

## System prompt (default, operator-overridable)

```
Eres un asistente especializado en normalizar títulos laborales en español para una base de datos comercial.

Para cada título de entrada, debes producir tres salidas:

1. male_es — La forma masculina estandarizada del título en español.
2. female_es — La forma femenina estandarizada del título en español. Si la forma gramatical es idéntica a la masculina (por ejemplo, "Ingeniero en Sistemas"), repite exactamente el mismo valor.
3. category — La categoría funcional del rol, tomada EXACTAMENTE de la taxonomía proporcionada por el usuario. Si no se proporciona taxonomía, elige una categoría concisa en español que describa la función del rol.

Reglas estrictas:

- NO inventes títulos. Estandariza, no reinterpretes.
- Si el título está en inglés, tradúcelo al español antes de estandarizar.
- Elimina sufijos corporativos o de ubicación ("at Google", "| Remote", "en Chile"): no forman parte del título.
- Si un título es ambiguo o no se puede clasificar con confianza, elige la mejor aproximación y continúa — nunca omitas entradas.
- Mantén capitalización estándar (primera letra en mayúscula, resto en minúscula salvo nombres propios).
- Los valores de male_es y female_es NUNCA deben estar vacíos.

Responderás únicamente invocando la herramienta `emit_standardized_titles` con un array que contenga EXACTAMENTE un objeto por cada título de entrada, preservando los mismos `id`. No respondas en prosa.
```

## Few-shot examples (embedded in the system prompt)

Stored in `task_templates.few_shots` as JSON. Injected into the system prompt before the strict-rules section during every request.

```json
[
  { "input": "Senior Software Engineer at Google", "male_es": "Ingeniero de Software Senior", "female_es": "Ingeniera de Software Senior", "category": "Tecnología" },
  { "input": "jefe compras", "male_es": "Jefe de Compras", "female_es": "Jefa de Compras", "category": "Operaciones" },
  { "input": "Jefe de Compras", "male_es": "Jefe de Compras", "female_es": "Jefa de Compras", "category": "Operaciones" },
  { "input": "VP of Sales, LATAM", "male_es": "Vicepresidente de Ventas", "female_es": "Vicepresidenta de Ventas", "category": "Ventas" },
  { "input": "Contador General", "male_es": "Contador General", "female_es": "Contadora General", "category": "Finanzas" },
  { "input": "Product Manager", "male_es": "Gerente de Producto", "female_es": "Gerenta de Producto", "category": "Tecnología" },
  { "input": "Recepcionista", "male_es": "Recepcionista", "female_es": "Recepcionista", "category": "Operaciones" },
  { "input": "HR Business Partner", "male_es": "Socio de Negocios de RRHH", "female_es": "Socia de Negocios de RRHH", "category": "RRHH" }
]
```

These are deliberately cross the interesting cases: Spanish-from-English translation, dropped stop-words, existing good form, LATAM region suffix, gender-neutral form, function-to-category mapping.

## User message shape per request

Each batch request sends a single user message formatted as JSON in prose:

```
Taxonomía permitida para category (usa EXACTAMENTE uno de estos valores):
- Ventas
- Tecnología
- Operaciones
- Finanzas
- RRHH
- Otros

Títulos a estandarizar (responde llamando a `emit_standardized_titles`):

[
  { "id": "t001", "title": "Jefe Compras" },
  { "id": "t002", "title": "Senior Software Engineer" },
  ... exactly `titles_per_request` entries ...
]
```

The taxonomy block is omitted if the operator left taxonomy empty (freeform mode).

## Anthropic tool definition (the hard structural contract)

Sent as `tools` in every batch request. `tool_choice` is `{"type": "tool", "name": "emit_standardized_titles"}`.

```json
{
  "name": "emit_standardized_titles",
  "description": "Emit standardized Spanish job titles for every input entry. Must include exactly one result per input id, with identical ids.",
  "input_schema": {
    "type": "object",
    "required": ["results"],
    "additionalProperties": false,
    "properties": {
      "results": {
        "type": "array",
        "minItems": 25,
        "maxItems": 25,
        "items": {
          "type": "object",
          "required": ["id", "male_es", "female_es", "category"],
          "additionalProperties": false,
          "properties": {
            "id": { "type": "string", "pattern": "^t[0-9]+$" },
            "male_es": { "type": "string", "minLength": 1 },
            "female_es": { "type": "string", "minLength": 1 },
            "category": { "type": "string", "minLength": 1 }
          }
        }
      }
    }
  }
}
```

**Important:** `minItems` and `maxItems` are set to the current `titles_per_request` dynamically — they are **not** hard-coded at 25. When retries halve the size to 12, the tool schema passed in that retry batch has `minItems: 12, maxItems: 12`.

## Parameters

| Parameter | Value |
|---|---|
| `model` | `claude-haiku-4-5` |
| `max_tokens` | `titles_per_request * 80 + 200` (headroom for JSON overhead) |
| `temperature` | `0` (we want determinism) |
| `tool_choice` | `{"type": "tool", "name": "emit_standardized_titles"}` |

## Validation pipeline (on response)

For each batch_request result:

1. Parse the raw response. If not valid JSON or not a tool call, mark `batch_request.status = failed`, error `tool_call_missing`.
2. Load the tool-call input into a Pydantic model matching the `input_schema`. Validation errors → `failed`, error `schema_violation`.
3. Extract `ids_returned = set(r['id'] for r in results)`.
4. Compare with `ids_expected = set(expected)`. If they differ:
   - Missing IDs → stragglers (will be retried in next round).
   - Extra IDs → log warning, drop them.
5. For each present and valid result, write `male_es`, `female_es`, `category` onto the cluster (joining via the `id → cluster_id` map stored in `batch_requests.cluster_ids`).

## Operator override rules

The operator can pass `prompt_override` on `/commit`. If set, it **replaces** the entire system prompt (including few-shots) verbatim. No merging, no templating. Advanced escape hatch only; the default is strong.

Taxonomy is always appended by the server as a user message prefix and not part of the override.

## Prompt review meta-prompt

Used by `POST /jobs/review-prompt`. A single non-batch call to Claude Haiku that evaluates the operator's prompt and few-shot examples.

### System prompt for the review call

```
You are an expert prompt engineer reviewing a prompt that will be used to standardize job titles via an AI batch processing system.

You will receive:
1. A system prompt that the operator wants to use
2. A set of few-shot examples (may be empty)

Evaluate the prompt on these criteria:
- **Safety**: Is the prompt asking the model to do legitimate standardization work? Flag if it asks for anything unrelated (creative writing, code generation, hacking, etc.)
- **Clarity**: Is the prompt clear about what output format is expected?
- **Completeness**: Does it cover edge cases (English→Spanish translation, gender-neutral titles, ambiguous titles)?
- **Few-shot quality**: Do the examples demonstrate the expected input→output mapping correctly? Are there enough varied examples?

Respond by calling the `review_prompt` tool with your assessment.
```

### Tool definition for the review call

```json
{
  "name": "review_prompt",
  "description": "Submit the structured review of the operator's prompt and few-shot examples.",
  "input_schema": {
    "type": "object",
    "required": ["safe", "quality_score", "issues", "suggestions", "summary"],
    "additionalProperties": false,
    "properties": {
      "safe": { "type": "boolean", "description": "true if the prompt is asking for legitimate standardization work" },
      "quality_score": { "type": "string", "enum": ["good", "needs_work", "poor"] },
      "issues": { "type": "array", "items": { "type": "string" }, "description": "Specific problems found" },
      "suggestions": { "type": "array", "items": { "type": "string" }, "description": "Improvement suggestions" },
      "summary": { "type": "string", "description": "1-2 sentence overall assessment" }
    }
  }
}
```

### User message shape for the review call

```
Prompt to review:

{operator_prompt}

Few-shot examples:

{few_shots_json}
```

### Parameters

| Parameter | Value |
|---|---|
| `model` | `claude-haiku-4-5` |
| `max_tokens` | 1000 |
| `temperature` | 0 |
| `tool_choice` | `{"type": "tool", "name": "review_prompt"}` |

### Important notes
- This is a standard (non-batch) API call, not a batch submission.
- Cost is ~$0.001 per review — negligible.
- This call does NOT go through the batch client or the monthly spend cap.
- If the call fails (network error, API error), return a 500 `prompt_review_failed` with a user-friendly message. The operator can still proceed without a review.
