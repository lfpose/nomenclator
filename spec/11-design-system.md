# 11 — Design System

Tailwind CSS + shadcn/ui. Monochrome, modern-minimal, both modes. The visual identity is defined by the shadcn theme configuration plus custom font choices.

## Stack

- **Tailwind CSS v4** — utility-first CSS framework. Configured via `tailwind.config.ts`.
- **shadcn/ui** — pre-built Radix + Tailwind components. Installed via `npx shadcn@latest init` with the "neutral" color palette.
- **CSS variables** — shadcn uses HSL-based CSS variables for theming. We override them to match our monochrome palette.

## Color palette

shadcn's "neutral" base, customized for pure monochrome. Configured in `globals.css`:

### Light mode
```css
:root {
  --background: 0 0% 98%;       /* #fafafa */
  --foreground: 0 0% 4%;        /* #0a0a0a */
  --card: 0 0% 100%;            /* #ffffff */
  --card-foreground: 0 0% 4%;
  --popover: 0 0% 100%;
  --popover-foreground: 0 0% 4%;
  --primary: 0 0% 4%;           /* #0a0a0a */
  --primary-foreground: 0 0% 98%;
  --secondary: 0 0% 96%;        /* #f5f5f5 */
  --secondary-foreground: 0 0% 10%;
  --muted: 0 0% 96%;
  --muted-foreground: 0 0% 45%;
  --accent: 0 0% 96%;
  --accent-foreground: 0 0% 10%;
  --destructive: 0 84% 60%;
  --destructive-foreground: 0 0% 98%;
  --border: 0 0% 90%;
  --input: 0 0% 90%;
  --ring: 0 0% 4%;
  --radius: 0.375rem;
}
```

### Dark mode
```css
.dark {
  --background: 0 0% 4%;        /* #0a0a0a */
  --foreground: 0 0% 98%;       /* #fafafa */
  --card: 0 0% 8%;              /* #141414 */
  --card-foreground: 0 0% 98%;
  --popover: 0 0% 8%;
  --popover-foreground: 0 0% 98%;
  --primary: 0 0% 98%;          /* #fafafa */
  --primary-foreground: 0 0% 4%;
  --secondary: 0 0% 15%;
  --secondary-foreground: 0 0% 98%;
  --muted: 0 0% 15%;
  --muted-foreground: 0 0% 64%;
  --accent: 0 0% 15%;
  --accent-foreground: 0 0% 98%;
  --destructive: 0 62% 50%;
  --destructive-foreground: 0 0% 98%;
  --border: 0 0% 15%;
  --input: 0 0% 15%;
  --ring: 0 0% 83%;
}
```

## Typography

| Token | Font | Fallback stack |
|---|---|---|
| Sans (body, UI) | **Inter Variable** | `system-ui, -apple-system, sans-serif` |
| Serif (display: wordmark + About page) | **Fraunces Variable** | `Georgia, serif` |
| Mono (code in Docs) | **JetBrains Mono** | `ui-monospace, monospace` |

Loaded via `@fontsource-variable/*` packages, self-hosted.

Tailwind font config:
```ts
fontFamily: {
  sans: ['Inter Variable', 'system-ui', '-apple-system', 'sans-serif'],
  serif: ['Fraunces Variable', 'Georgia', 'serif'],
  mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
}
```

## shadcn/ui components used (v1)

Installed via `npx shadcn@latest add <component>`:

- `button` — variants: default, secondary, ghost, destructive, outline. Sizes: sm, default, lg.
- `input` — text and number inputs with label integration.
- `textarea` — auto-grow variant available.
- `slider` — range slider for threshold.
- `card` — container with header/content/footer slots.
- `badge` — status variants: default, secondary, destructive, outline.
- `dialog` — modal for confirmations (cancel job).
- `table` — for clusters list and job history.
- `collapsible` — replaces custom Disclosure for Advanced section.
- `switch` — for dry-run toggle.
- `tooltip` — for parameter explanations.
- `select` — for row subset mode picker.
- `label` — form field labels.
- `separator` — visual dividers.
- `scroll-area` — for cluster members overflow.
- `dropdown-menu` — if needed for header actions.
- `toast` — via sonner, for transient notifications.

## Dark mode toggle

Uses shadcn's recommended approach:
- `next-themes` pattern adapted for TanStack Router (no Next.js dependency).
- A `ThemeProvider` component wraps the app.
- Toggle button in the header switches between "light", "dark", and "system".
- Theme class applied to `<html>` element.
- `localStorage` persists the choice.

## Spacing and layout

Tailwind's default spacing scale (based on 0.25rem = 4px increments). No custom spacing tokens needed.

Main content area: `max-w-3xl mx-auto` (~860px, matches the original spec).

## Motion

Tailwind's `transition-*` utilities. Respect `prefers-reduced-motion` via `motion-reduce:` variant.

- Button hover: `duration-100`
- Collapsible expand: `duration-200`
- Panel swap: `duration-300`

## Contrast

All shadcn components meet WCAG 2.1 AA contrast ratios out of the box with the neutral palette.

## Focus handling

shadcn components use Radix's built-in focus management:
- Focus-visible rings via `ring-ring` utility.
- Skip-to-content link hidden until focused.
