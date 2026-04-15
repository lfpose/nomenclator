# 15 — Frontend About and Docs Pages

Reference: `spec/10-ui-spec.md`, `spec/15-docs-content.md`.

---

### P15-01 — About page

**Deps:** P13-05
**Files:** `frontend/src/routes/about.tsx`, `frontend/tests/about-page.test.tsx`
**Goal:** Replace placeholder with the two-paragraph content from `spec/10-ui-spec.md` section "About page".

**Implementation:** literally paste the two paragraphs from the spec into JSX with `<article>` + `<p>`. Center the text with wide line-height using Tailwind utilities. Serif typeface for the etymology line via the `font-serif` Tailwind class.

**Test:** `cd frontend && pnpm test --run tests/about-page.test.tsx`

Required assertions:
- `test("renders etymology heading", ...)` — asserts "nomenclator" + "Latin" both present.
- `test("renders the whispering paragraph", ...)` — asserts "whispered the right name" present.
- `test("uses serif font family", ...)` — asserts the element has the `font-serif` Tailwind class or equivalent.

**Done when:**
- [ ] All 3 tests pass.

---

### P15-02 — Mermaid lazy loader

**Deps:** P13-01
**Files:** `frontend/src/lib/mermaid.ts`, `frontend/tests/mermaid-loader.test.ts`
**Goal:** Helper that dynamically imports `mermaid` and renders a diagram string to SVG, respecting current theme.

**Implementation:**
```ts
let loaded: Promise<typeof import("mermaid")> | null = null;

function loadMermaid() {
  if (!loaded) loaded = import("mermaid");
  return loaded;
}

export async function renderDiagram(source: string, theme: "light" | "dark"): Promise<string> {
  const mod = await loadMermaid();
  const mermaid = mod.default;
  mermaid.initialize({
    startOnLoad: false,
    theme: theme === "dark" ? "dark" : "default",
    securityLevel: "strict",
  });
  const id = `mmd-${Math.random().toString(36).slice(2)}`;
  const { svg } = await mermaid.render(id, source);
  return svg;
}
```

**Test:** `cd frontend && pnpm test --run tests/mermaid-loader.test.ts`

Required assertions (mock `mermaid`):
- `test("dynamic import happens on first call", ...)`
- `test("second call reuses the promise", ...)`
- `test("respects dark theme flag", ...)`

**Done when:**
- [ ] All 3 pass.

---

### P15-03 — Mermaid component

**Deps:** P15-02, P13-02
**Files:** `frontend/src/components/Mermaid.tsx`, `frontend/tests/mermaid-component.test.tsx`
**Goal:** React component that takes a `source` prop and renders the SVG, re-rendering when theme changes.

**Implementation:**
```tsx
import { useEffect, useRef, useState } from "react";
import { renderDiagram } from "../lib/mermaid";

export function Mermaid({ source }: { source: string }) {
  const [svg, setSvg] = useState<string>("");
  const theme = (document.documentElement.classList.contains("dark") ? "dark" : "light") as "light" | "dark";
  useEffect(() => {
    renderDiagram(source, theme).then(setSvg);
  }, [source, theme]);
  return <div dangerouslySetInnerHTML={{ __html: svg }} />;
}
```

**Test:** `cd frontend && pnpm test --run tests/mermaid-component.test.tsx`

Required assertions:
- `test("renders svg after mount", ...)` — mock renderDiagram, assert html contains mock svg.
- `test("re-renders when source changes", ...)`

**Done when:**
- [ ] Both pass.

---

### P15-04 — Docs page layout with sidebar

**Deps:** P13-05
**Files:** `frontend/src/routes/docs.tsx`, `frontend/src/components/DocsSidebar.tsx`, `frontend/tests/docs-layout.test.tsx`
**Goal:** Docs page with sticky left sidebar listing all sections (anchors) and a scrolling content area.

**Test:** `cd frontend && pnpm test --run tests/docs-layout.test.tsx`

Required assertions:
- `test("sidebar has 8 section links", ...)` — matches `spec/15-docs-content.md` section count.
- `test("clicking sidebar link scrolls to anchor", ...)` — assert hash change.
- `test("sidebar is sticky via CSS class", ...)`

**Done when:**
- [ ] All 3 pass.

---

### P15-05 — Docs content sections + mermaid embeds + error codes table

**Deps:** P15-03, P15-04
**Files:** `frontend/src/routes/docs.tsx` (extend), `frontend/src/data/mermaid-sources.ts`, `frontend/src/data/error-codes.ts`, `frontend/tests/docs-content.test.tsx`
**Goal:** Embed the real content from `spec/15-docs-content.md`: 8 sections, mermaid embeds from `solution-overview.md` (#1, #5, #6, #12), and the error codes table.

**Implementation:**
- `mermaid-sources.ts` exports a map of `name → source string`, with the 4 mermaid sources copied verbatim from `solution-overview.md`.
- `error-codes.ts` exports an array of error code descriptions.
- The Docs route imports these and lays them out.

**Test:** `cd frontend && pnpm test --run tests/docs-content.test.tsx`

Required assertions:
- `test("renders What this does section", ...)`
- `test("renders Quickstart section", ...)`
- `test("renders How it works section with 3 mermaid embeds", ...)` — assert 3 `<Mermaid>` components.
- `test("renders Architecture section", ...)`
- `test("renders error codes table with at least 10 rows", ...)`
- `test("renders FAQ section with at least 5 questions", ...)`
- `test("renders Troubleshooting section", ...)`

**Done when:**
- [ ] All 7 pass.
- [ ] `pnpm build` chunks mermaid into a separate file (verify dist size report).
