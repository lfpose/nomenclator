# Ralph Watch Extension for Pi - Setup Complete

## Summary

I've created a **Ralph Watch extension for Pi** that integrates your Ralph loop monitoring directly into the Pi TUI. Now you can see Ralph's status in the same interface where you work with your AI coding agent, without needing a separate `ralph-watch.sh` terminal window.

## Files Created

| File | Description |
|------|-------------|
| `.pi/extensions/ralph-watch.ts` | Main extension code |
| `.pi/extensions/package.json` | Package metadata (for npm sharing) |
| `.pi/extensions/README.md` | Full documentation |
| `.pi/extensions/QUICKSTART.md` | Quick reference guide |
| `test-ralph-watch.sh` | Test script to create sample data |

## Key Features

### 1. Real-Time Status Widget
Shows Ralph loop status directly in Pi's TUI:
- Current task being executed
- Stuck count with /5 threshold
- Total failed attempts
- Last successful execution time
- Success rate and iteration stats
- Recent health events

### 2. Toggle On/Off
- Command: `/ralph-watch`
- Keyboard shortcut: `Ctrl+Alt+R`
- CLI flag: `pi --ralph-watch`

### 3. Smart Status Indicator
Footer shows color-coded status:
- 🟢 `✓ HEALTHY` - Normal operation
- 🟡 `⚠️ FAILURES` - Some failures but recovering
- 🟡 `⚠️ WARNING` - High stuck count
- 🔴 `🚫 STOPPED` - Loop stopped

### 4. State Persistence
Remembers enabled/disabled state across session reloads. When you run `/reload`, Ralph Watch restores its previous state.

## Usage Examples

### Start with watch enabled
```bash
pi --ralph-watch
```

### Toggle during session
```bash
pi
/ralph-watch    # Enable
/ralph-watch    # Disable
Ctrl+Alt+R      # Toggle via keyboard
```

### Working with Ralph
```bash
# Terminal 1: Run Ralph loop
./ralph-v2.sh

# Terminal 2: Monitor in Pi
pi --ralph-watch
```

## What It Monitors

The extension reads from your `.ralph-obs/` directory:

### state.json
```json
{
  "current_task": "P10-01",
  "stuck_count": 0,
  "last_successful": "2026-04-15T16:17:26+00:00",
  "total_failed": 0,
  "updated_at": "2026-04-15T16:17:26+00:00"
}
```

### iterations.jsonl
JSONL file with one entry per iteration:
```json
{"type":"iteration","status":"success","timestamp":"2026-04-15T16:17:26+00:00"}
```

### health.log
Log file with health events:
```
[2026-04-15T16:17:26+00:00] [INFO] Test passed
[2026-04-15T16:17:27+00:00] [WARN] Slow response
```

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    Pi TUI Interface                      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐   │
│  │  Ralph Loop Status         ← Widget              │   │
│  │  ─────────────────────────────────────────       │   │
│  │  Task:    P10-01                               │   │
│  │  Stuck:   0/5                                  │   │
│  │  Failed:  0                                    │   │
│  │  Last:    2m ago                              │   │
│  │                                                │   │
│  │  Total:   15                                   │   │
│  │  Success: 15 (100%)                            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Messages from AI agent...                     │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Type your message...        ← Editor            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  /workspaces/nomenclator | ✓ HEALTHY | session-123     │
│                          ↑ Footer status               │
└─────────────────────────────────────────────────────────┘
```

## Extension API Usage

The extension demonstrates several key Pi extension APIs:

- `pi.registerCommand()` - Register `/ralph-watch` command
- `pi.registerShortcut()` - Register `Ctrl+Alt+R` shortcut
- `pi.registerFlag()` - Register `--ralph-watch` CLI flag
- `ctx.ui.setStatus()` - Set footer status indicator
- `ctx.ui.setWidget()` - Show widget panel above/below editor
- `ctx.sessionManager.getBranch()` - Restore state from branch
- `pi.appendEntry()` - Persist state to session
- `pi.on("session_start")` - Initialize on session load
- `pi.on("session_shutdown")` - Cleanup on exit

## Testing

Run the test script to create sample data:
```bash
./test-ralph-watch.sh
```

Then start Pi:
```bash
pi
/ralph-watch
```

## Customization

Edit `.pi/extensions/ralph-watch.ts`:

```typescript
// Change update interval (default: 2000ms)
setInterval(() => updateRalphData(ctx), 2000)

// Move widget below editor
ctx.ui.setWidget("ralph-watch", lines, { placement: "belowEditor" })

// Add more stats to widget
lines.push(`${theme.fg("dim", "Custom:")} ${customData}`);
```

## Sharing as a Package

To share this extension with others via npm:

```bash
cd .pi/extensions
npm publish
```

Others can install:
```bash
pi install npm:pi-ralph-watch
```

## Documentation

- **README.md** - Full documentation with detailed explanations
- **QUICKSTART.md** - Quick reference guide for common tasks

## Next Steps

1. Try it out: `pi --ralph-watch`
2. Customize the widget display to your preferences
3. Add additional metrics if needed
4. Share with your team if they use Ralph + Pi

## Credits

Built using Pi's extension system:
- https://github.com/badlogic/pi-mono
- Based on Pi documentation examples
- Inspired by Armin Ronacher's blog post on Pi extensions
