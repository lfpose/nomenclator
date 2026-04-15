# Ralph Watch Extension for Pi

A Pi extension that monitors Ralph loop state and displays it directly in the Pi TUI.

## Features

- **Toggle on/off** with `/ralph-watch` command or `Ctrl+Alt+R` shortcut
- **Footer status** shows overall loop health (Healthy/Warning/Stopped)
- **Widget panel** displays detailed stats:
  - Current task being executed
  - Stuck count (with /5 threshold indicator)
  - Total failed attempts
  - Last successful execution time
  - Iteration statistics (total, success rate, failed, errors)
  - Recent health events (last 3)

## Installation

### Local installation (project-specific)

```bash
# Already installed in .pi/extensions/
pi
/ralph-watch
```

### As a standalone package (to share)

```bash
# From within this directory
pi install .

# Or install from npm
pi install npm:pi-ralph-watch
```

## Usage

### Start with watch enabled

```bash
pi --ralph-watch
```

### Toggle during session

```bash
pi
/ralph-watch    # Toggle on/off
Ctrl+Alt+R      # Keyboard shortcut
```

### What it monitors

The extension reads from `.ralph-obs/` directory:

- **state.json** - Current loop state
  - `current_task` - Task ID currently executing
  - `stuck_count` - Number of consecutive failures (stops at 5)
  - `last_successful` - Timestamp of last successful iteration
  - `total_failed` - Total failed iterations
  - `updated_at` - Last update timestamp

- **iterations.jsonl** - Iteration history
  - One JSON line per iteration
  - `status` can be: `success`, `test_failed`, `agent_error`

- **health.log** - Health event log
  - Format: `[timestamp] [LEVEL] message`
  - Levels: INFO, WARN, ERROR

## State persistence

The extension remembers its enabled/disabled state across session reloads. When you reload Pi with `/reload`, Ralph Watch will restore its previous state.

## Example output

### Footer (status indicator)

```
✓ HEALTHY    ← Normal operation
⚠️ FAILURES  ← Some failures but recovering
⚠️ WARNING   ← High stuck count
🚫 STOPPED   ← Loop stopped (stuck_count >= 5)
```

### Widget (detailed stats)

```
 Ralph Loop Status
─────────────────────────
Task:    P10-01
Stuck:   0/5
Failed:  0
Last:    2m ago

Total:   15
Success: 15 (100%)

Recent:
  ✓ Test passed for P10-01
  ✓ Task P10-01 started
  ✓ Iteration 15 complete
```

## How it works

1. **Polling**: Updates every 2 seconds by reading the `.ralph-obs/` files
2. **TUI Integration**:
   - Uses `ctx.ui.setStatus()` for footer indicator
   - Uses `ctx.ui.setWidget()` for detailed panel
3. **State persistence**: Saves enabled/disabled state to session via `pi.appendEntry()`

## Extending

You can customize the extension by modifying:

- **Update interval**: Change `setInterval(() => updateRalphData(ctx), 2000)` to adjust polling frequency
- **Widget placement**: Change `{ placement: "aboveEditor" }` to `"belowEditor"`
- **Status thresholds**: Modify the `if (stuck_count >= X)` conditions
- **Widget content**: Add more fields to the `lines` array in `updateWidget()`

## Troubleshooting

### No data showing

1. Check that `.ralph-obs/` directory exists in your working directory
2. Verify files contain valid JSON:
   ```bash
   cat .ralph-obs/state.json | jq .
   ```

### Extension not loading

1. Make sure it's in `~/.pi/agent/extensions/` or `.pi/extensions/`
2. Check for TypeScript errors (Pi uses jiti for on-the-fly compilation)
3. Try `/reload` to reload all extensions

### Widget not updating

1. Check that files are being written by the Ralph loop
2. Try toggling the extension off and on: `/ralph-watch` twice
3. Check Pi logs for any errors

## License

MIT
