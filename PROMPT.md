@prd.md @activity.md

We are building Nomenclator — a web tool that standardizes messy job titles into canonical Spanish forms. The full spec is in `spec/` and detailed task instructions are in `plan/`.

First read activity.md to see what was recently accomplished.

## Project Structure

- **Backend:** Python 3.12 + FastAPI, in `backend/`
- **Frontend:** React + Vite + TypeScript + TanStack Router + shadcn/ui, in `frontend/`
- **Specs:** `spec/` directory (authoritative requirements)
- **Plan:** `plan/` directory (detailed implementation guides per task)

## Work on Tasks

Open prd.md and find the single highest priority task where `"passes": false`.

Work on exactly ONE task:

1. **Read the plan file** referenced in the task steps (e.g., `plan/01-scaffolding.md` section P01-01). Follow the implementation guidance closely.
2. **Read the relevant spec file** if the task mentions one (e.g., `spec/05-data-model.md`). The spec is authoritative — if the plan contradicts the spec, the spec wins.
3. **Implement** exactly what the task describes. Do not add features, refactor surrounding code, or make improvements beyond the task scope.
4. **Run the test** specified in the task. The task is done ONLY when the test passes.

## Verify Your Work

After implementing, run the verification commands:

**For backend tasks:**
```bash
cd backend && uv run pytest <test_file> -v
```

**For frontend tasks:**
```bash
cd frontend && pnpm test --run <test_file>
```

**General checks (run if available):**
```bash
cd backend && uv run ruff check .
cd frontend && pnpm tsc --noEmit
```

If a test fails, fix the implementation (not the test) until it passes. If the test itself is wrong per the spec, fix the test THEN fix the implementation.

## Log Progress

Append a dated progress entry to activity.md describing:
- Task ID and description
- What you changed (files created/modified)
- Test command and result (pass/fail)
- Any issues encountered and how you resolved them

## Update Task Status

When the test passes, update that task's `"passes"` field in prd.md from `false` to `true`.

## Commit Changes

Make one git commit for that task only:
```bash
git add -A
git commit -m "P01-01: create directory structure"
```

Use the task ID as the commit prefix. Do NOT push.

## Important Rules

- ONLY work on a SINGLE task per iteration
- Always read the plan file for implementation details before coding
- Always run the specified test before marking a task as passing
- If a task depends on other tasks (listed in the plan as "Deps"), verify those are already passing
- Always log your progress in activity.md
- Always commit after completing a task
- Do not skip tests — if the test is wrong, fix it first
- The spec (`spec/`) always wins over the plan (`plan/`) on conflicts

## Completion

When ALL tasks have `"passes": true`, output:

<promise>COMPLETE</promise>
