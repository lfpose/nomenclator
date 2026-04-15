# Ralph Watch Extension for Pi

A Pi extension that monitors Ralph loop state and displays it as a **sidebar panel** on the right side of the Pi TUI.

## Features

- **Toggle on/off** with `/ralph-watch` command or `Ctrl+Alt+R` shortcut
- **Sidebar panel** on the right side showing detailed stats (current task, stuck count, success rate, etc.)
- **Status indicator** in footer showing loop health
- **Real-time updates** from `.ralph-obs/state.json`, `health.log`, and `iterations.jsonl`
- **Responsive** - only shows on wide terminals (100+ columns)

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

## What You'll See

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Main Pi Content Area                    │  Ralph Sidebar (35 cols)  │
│                                            │                            │
│  Messages from AI...                      │  Ralph Status              │
│                                            │  ─────────                 │
│  [Assistant response...]                  │  Task:    P10-01           │
│                                            │  Stuck:   0/5              │
│  > Tool calls...                          │  Failed:  0                │
│                                            │  Last:    2m ago           │
│  [Tool output...]                         │                            │
│                                            │  Total:   15               │
│                                            │  Success: 15 (100%)        │
│                                            │                            │
│                                            │  Recent:                   │
│                                            │    ✓ Test passed           │
│                                            │    ✓ Task started          │
│                                            │                            │
│  Type your message...                     │                            │
├────────────────────────────────────────────┴────────────────────────────┤
│ /workspaces/nomenclator | ✓ HEALTHY | session-123                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Footer (status indicator)

```
✓ HEALTHY    ← Normal operation
⚠️ FAILURES  ← Some failures but recovering
⚠️ WARNING   ← High stuck count
🚫 STOPPED   ← Loop stopped (stuck_count >= 5)
```

### Sidebar Panel (right side)

```
 Ralph Status
─────────────────────
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

## Sidebar Behavior

- **Width**: 35 columns (adjusts between 30-40 based on terminal width)
- **Position**: Right side of terminal
- **Visibility**: Only shows on terminals with 100+ columns
- **Updates**: Refreshes every 2 seconds
- **Non-intrusive**: Doesn't interfere with main content or editor

## What it monitors

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

The extension remembers its enabled/disabled state across session reloads. When you reload Pi with `/reload`, Ralph Watch will restore its previous state and show the sidebar.

## Requirements

- Terminal width: **100+ columns** for sidebar to appear
- On smaller terminals, only the footer status indicator will show
- Ralph loop must be writing to `.ralph-obs/` directory

## Example workflow

```bash
# Terminal 1: Run Ralph loop
./ralph-v2.sh

# Terminal 2: Start Pi with Ralph watch
pi --ralph-watch

# Work normally - sidebar shows real-time status
# Type your prompts, see AI responses
# Ralph status updates automatically in sidebar

# Toggle sidebar off if needed
/ralph-watch

# Toggle back on later
/ralph-watch
```

## Troubleshooting

### No sidebar showing

1. Check terminal width - must be 100+ columns:
   ```bash
   tput cols  # Should be >= 100
   ```

2. Check extension is enabled:
   ```bash
   # Footer should show "✓ HEALTHY" or similar
   ```

3. Check `.ralph-obs/` directory has data:
   ```bash
   ls -la .ralph-obs/
   cat .ralph-obs/state.json | jq .
   ```

### Footer status but no sidebar

This is expected on narrow terminals (< 100 columns). The sidebar is automatically hidden to preserve space for main content.

### Extension error loading

1. Make sure it's in `~/.pi/agent/extensions/` or `.pi/extensions/`
2. Try `/reload` to reload all extensions
3. Check for TypeScript errors in the file

## Extending

You can customize the extension by modifying `.pi/extensions/ralph-watch.ts`:

```typescript
// Change sidebar width (default: 35 columns)
width: 35,
minWidth: 30,
maxWidth: 40,

// Change minimum terminal width (default: 100 columns)
visible: (termWidth, _termHeight) => termWidth >= 100,

// Change update interval (default: 2000ms)
setInterval(() => updateRalphData(ctx), 2000)

// Add more fields to sidebar
lines.push(`${th.fg("dim", "Custom:")} ${customData}`);

// Move sidebar to left side
anchor: "left",  // instead of "right"
```

## License

MIT
