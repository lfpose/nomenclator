# Ralph Watch Extension - Fixes and Updates

## What Was Fixed

### Issue 1: `ctx.pi` Error ❌ → ✅

**Problem:**
```
Extension "command:ralph-watch" error:
Cannot read properties of undefined (reading 'appendEntry')
```

**Cause:** The code was trying to access `ctx.pi.appendEntry()`, but `ctx.pi` doesn't exist in `ExtensionContext`.

**Solution:** Changed to use `ctx.sessionManager.appendCustomEntry()` which is the correct API:

```typescript
// Before (broken):
ctx.pi.appendEntry("ralph-watch", {
  enabled: watchEnabled,
});

// After (fixed):
ctx.sessionManager.appendCustomEntry("ralph-watch", {
  enabled: watchEnabled,
});
```

---

### Issue 2: Widget Layout ❌ → ✅

**Problem:** The widget was shown inline with the main content, which conflicted with Pi's standard output.

**Solution:** Converted to use Pi's **overlay system** to create a dedicated **sidebar panel** on the right side:

```typescript
// Before: Inline widget above/below editor
ctx.ui.setWidget("ralph-watch", lines, { placement: "aboveEditor" });

// After: Sidebar overlay on the right
overlayHandle = ctx.ui.custom<boolean>(
  (tui, theme, _kb, done) => { /* sidebar component */ },
  {
    overlay: true,
    overlayOptions: {
      width: 35,
      minWidth: 30,
      maxWidth: 40,
      anchor: "right",
      margin: 0,
      visible: (termWidth, _termHeight) => termWidth >= 100,
    },
  },
);
```

---

## New Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Main Pi Content Area               │  Ralph Sidebar Panel (35 columns)      │
│                                     │                                        │
│  AI Messages and Tool Output        │   Ralph Status                         │
│                                     │   ─────────────                        │
│  [Assistant Response...]             │   Task:    P10-01                      │
│                                     │   Stuck:   0/5                         │
│  > Tool Call: read                  │   Failed:  0                           │
│                                     │   Last:    2m ago                      │
│  [Tool Output...]                  │                                        │
│                                     │   Total:   15                          │
│                                     │   Success: 15 (100%)                   │
│                                     │                                        │
│                                     │   Recent:                              │
│                                     │     ✓ Test passed                      │
│  ┌───────────────────────────────┐ │     ✓ Task started                     │
│  │ Type your message...          │ │                                        │
│  └───────────────────────────────┘ │                                        │
├─────────────────────────────────────┴────────────────────────────────────────┤
│ /workspaces/nomenclator | ✓ HEALTHY | session-123                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Improvements

### 1. Non-Intrusive Display
- Sidebar appears as a floating panel on the right
- Doesn't interfere with main content or editor
- Can be toggled on/off at any time

### 2. Responsive Design
- Only shows on terminals with 100+ columns
- Automatically hides on narrow terminals to save space
- Footer status indicator always visible regardless of terminal size

### 3. Proper State Management
- Fixed the `appendEntry` error
- State persists across session reloads
- Sidebar automatically shows/hides when enabled/disabled

### 4. Better Visual Separation
- Sidebar has its own bordered box
- Distinct from main Pi output
- Easy to read at a glance

---

## Usage

### Start with sidebar enabled
```bash
pi --ralph-watch
```

### Toggle during session
```bash
pi
/ralph-watch    # Toggle sidebar on/off
Ctrl+Alt+R      # Keyboard shortcut
```

### Resize terminal
- Sidebar shows on terminals ≥ 100 columns wide
- Automatically hides on smaller terminals
- Footer status always visible

---

## Terminal Width Guide

| Columns | Sidebar | Footer Status | Recommended |
|---------|---------|---------------|-------------|
| < 100   | ❌ No   | ✅ Yes        | Resize terminal |
| 100-120 | ✅ Yes  | ✅ Yes        | Works well |
| 120+    | ✅ Yes  | ✅ Yes        | Ideal |

To check your terminal width:
```bash
tput cols
```

To resize (in most terminals):
- **macOS/Terminal**: Drag window edge
- **iTerm2**: Cmd + Shift + ← / →
- **tmux**: `resize-pane -R` or `resize-pane -L`

---

## Files Modified

| File | Changes |
|------|---------|
| `.pi/extensions/ralph-watch.ts` | Fixed `ctx.pi` error, converted to overlay sidebar |
| `.pi/extensions/README.md` | Updated with sidebar documentation |
| `.pi/extensions/QUICKSTART.md` | Updated quick reference for sidebar |

---

## Testing

1. Make sure terminal is ≥ 100 columns wide:
   ```bash
   tput cols
   ```

2. Start Pi with watch enabled:
   ```bash
   pi --ralph-watch
   ```

3. You should see:
   - Sidebar panel on the right with Ralph stats
   - Footer status indicator showing loop health

4. Toggle on/off:
   ```bash
   /ralph-watch
   ```

---

## Next Steps

1. **Test the extension** with a wide terminal
2. **Customize sidebar width** if needed (edit `width: 35` in the file)
3. **Adjust terminal width threshold** (edit `termWidth >= 100`)
4. **Move sidebar to left** if preferred (change `anchor: "right"` to `"left"`)

---

## Support

If you encounter issues:

1. Check terminal width: `tput cols` (should be ≥ 100)
2. Check `.ralph-obs/` directory has data
3. Try `/reload` to reload the extension
4. Check for any error messages in Pi output
