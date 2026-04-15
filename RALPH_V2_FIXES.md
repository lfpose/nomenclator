# Ralph Loop v2 - Fixed Version

## What Was Fixed

### Issue 1: "No such file or directory" Error
**Problem:** Script tried to read `.ralph-obs/state.json` before it was created.

**Fix:**
- `get_state()` function now returns default values if file doesn't exist
- `init_obs()` properly creates state.json with default values before running
- All state operations use safe defaults with `2>/dev/null` error handling

### Issue 2: No Progress During Execution
**Problem:** Output was buffered, so nothing showed until the loop finished.

**Fix:**
- Output is now printed immediately after each iteration
- Agent command runs and captures output, then prints right away
- Dashboard shows before each iteration
- No silent runs - you see everything as it happens

### Issue 3: Unexpected Stops
**Problem:** Script would exit on first error or stuck task.

**Fix:**
- `set +e` at start of main loop - won't exit on errors
- Stuck detection warns but doesn't stop the loop
- Only stops on `<promise>COMPLETE</promise>` or max iterations reached
- Agent errors are logged and counted, but loop continues

## Key Changes

### Safe State Management
```bash
# Before (would fail if file missing)
state=$(cat "$STATE_LOG" | jq '.')

# After (safe with defaults)
state=$(get_state)  # Returns defaults if file missing
```

### Error-Resilient Loop
```bash
# Before (exits on error)
set -e
for i in ...; do
  result=$($AGENT_CMD ...)  # Would exit if agent fails
done

# After (continues on error)
set +e  # Don't exit on errors
for i in ...; do
  result=$($AGENT_CMD ...)
  agent_exit_code=$?
  # Handle error but continue loop
done
```

### Immediate Output
```bash
# Before (might be buffered)
result=$($AGENT_CMD ...)

# After (print immediately)
result=$($AGENT_CMD ...)
echo "$result"  # Print right away
echo ""         # Add separator
```

## Usage

```bash
# Run with 50 iterations
./ralph-v2.sh 50

# Monitor in another terminal (optional)
./ralph-watch.sh

# Check status anytime
./ralph-status.sh

# Analyze after run
./ralph-analyze.sh summary
./ralph-analyze.sh failed
./ralph-analyze.sh report
```

## What You'll See Now

1. **Startup:**
   ```
   ═════════════════════════════════════════════════════════════════════
      Nomenclator — Ralph Loop v2
   ═════════════════════════════════════════════════════════════════════

   Max iterations: 50
   Completion signal: <promise>COMPLETE</promise>
   Observability: .ralph-obs

   Starting in 3 seconds... Press Ctrl+C to abort
   ```

2. **Per-Iteration Dashboard:**
   ```
   ═════════════════════════════════════════════════════════════════════
      Ralph Loop v2 — Progress Dashboard
   ═════════════════════════════════════════════════════════════════════
     Iteration:   1 / 50 (2.0%)
     Current Task: none
     Stuck Count: 0 / 5
     Obs Data:    .ralph-obs
   ═════════════════════════════════════════════════════════════════════

   Running iteration 1...
   ```

3. **Agent Output:**
   - All agent output printed immediately
   - No buffering - you see it as it happens

4. **Iteration Summary:**
   ```
   ✓ Task P08-07 completed in 15.3s
      Test result: PASS
      Iteration: 1

   --- End of iteration 1 ---
   ```

5. **Final Report:**
   ```
   ═════════════════════════════════════════════════════════════════════
      MAX ITERATIONS REACHED
   ═════════════════════════════════════════════════════════════════════

   Final Statistics:
     Successful: 10
     Failed: 2
     Total iterations: 50
   ```

## Stuck Detection

When a task fails repeatedly:

```
✗ Task P08-07 tests failed
   Test result: FAIL
   Iteration: 3

--- End of iteration 3 ---
```

Dashboard shows stuck count:
```
  Current Task: P08-07
  Stuck Count:  2 / 5  ← Increasing
```

After 5 failures:
```
╔═════════════════════════════════════════════════════════════════════╗
║   STUCK ON TASK P08-07                                               ║
╚═════════════════════════════════════════════════════════════════════╝

Failed 5 times in a row on the same task.
Consider: 1) Checking the test for bugs, 2) Reviewing the plan, 3) Manual intervention
```

**Important:** The loop continues running - it doesn't stop!

## Observability Data

All data in `.ralph-obs/`:
- `iterations.jsonl` - One line per iteration
- `health.log` - Health events
- `state.json` - Current loop state (created safely with defaults)

## Requirements

- `bash` (version 4+)
- `jq` (optional - for some advanced analysis)

If jq is missing, basic features still work. Only advanced filtering requires jq.

## Troubleshooting

### Script exits immediately
Check that PROMPT.md and prd.md exist:
```bash
ls -la PROMPT.md prd.md
```

### No output showing
Run with verbose mode or check the agent is installed:
```bash
pi --version
```

### State.json errors
The script creates state.json with defaults automatically. If there are issues:
```bash
rm -rf .ralph-obs
./ralph-v2.sh 10  # Will recreate everything
```

### Stuck on same task
The loop will continue running. Check:
```bash
./ralph-status.sh
./ralph-analyze.sh failed
```

Then manually fix the failing test or task.

---

**The loop now:**
✅ Doesn't fail on missing files
✅ Shows progress immediately
✅ Doesn't stop on errors
✅ Only stops on COMPLETE or max iterations
✅ Recovers from agent errors
