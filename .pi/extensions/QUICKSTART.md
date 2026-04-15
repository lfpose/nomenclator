# Ralph Watch Extension - Quick Reference

## What is it?

A Pi extension that monitors your Ralph loop and displays it as a **sidebar panel** on the right side of the Pi TUI.

## Quick Start

### Option 1: Start with watch enabled
```bash
pi --ralph-watch
```

### Option 2: Toggle during session
```bash
pi
/ralph-watch    # Toggle on/off
Ctrl+Alt+R      # Keyboard shortcut
```

## Requirements

- **Terminal width**: 100+ columns (sidebar only shows on wide terminals)
- On smaller terminals, you'll only see the footer status indicator

## What You'll See

```
┌──────────────────────────────────────────┬──────────────────────┐
│  Main Pi Content Area                    │  Ralph Sidebar        │
│                                          │                      │
│  AI messages and tool output             │  Ralph Status         │
│                                          │  ─────────            │
│                                          │  Task:    P10-01      │
│                                          │  Stuck:   0/5         │
│  Your editor...                          │  Failed:  0           │
│                                          │  Last:    2m ago      │
│                                          │                      │
│                                          │  Total:   15          │
│                                          │  Success: 15 (100%)   │
├──────────────────────────────────────────┴──────────────────────┤
│ /workspaces/nomenclator | ✓ HEALTHY | session-123             │
└─────────────────────────────────────────────────────────────────┘
```

### Footer Status (always visible when enabled)
- `✓ HEALTHY` - Loop running normally
- `⚠️ FAILURES` - Some failures but recovering
- `⚠️ WARNING` - High stuck count
- `🚫 STOPPED` - Loop stopped (stuck_count >= 5)

### Sidebar Panel (right side, 35 cols, on wide terminals)
- Current task being executed
- Stuck count with /5 threshold
- Total failed attempts
- Last successful execution time
- Success rate and iteration statistics
- Recent health events

## Commands

| Command | Description |
|---------|-------------|
| `/ralph-watch` | Toggle Ralph watch sidebar on/off |
| `/reload` | Reload extensions (restores sidebar state) |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Alt+R` | Toggle Ralph watch sidebar |

## Troubleshooting

### No sidebar showing

Check your terminal width:
```bash
tput cols  # Must be >= 100
```

If it's < 100, resize your terminal or the sidebar won't show (footer status will still work).

### Check data exists

```bash
ls -la .ralph-obs/
cat .ralph-obs/state.json | jq .
```

## Example Workflow

```bash
# Terminal 1: Run Ralph loop
./ralph-v2.sh

# Terminal 2: Monitor in Pi (sidebar appears on right)
pi --ralph-watch

# Work normally - sidebar updates in real-time
# No separate ralph-watch.sh terminal needed!
```

## Customization

Edit `.pi/extensions/ralph-watch.ts`:

```typescript
// Change sidebar width (default: 35)
width: 35,

// Change minimum terminal width (default: 100)
visible: (termWidth, _termHeight) => termWidth >= 100,

// Move to left side
anchor: "left",

// Change update interval (default: 2000ms = 2s)
setInterval(() => updateRalphData(ctx), 2000)
```
