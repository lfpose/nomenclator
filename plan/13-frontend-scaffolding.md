# 13 — Frontend Scaffolding

Reference: `spec/10-ui-spec.md`, `spec/11-design-system.md`. All tests use `vitest` + `@testing-library/react` against jsdom.

The frontend uses shadcn/ui (Tailwind + Radix) for all interactive components. Custom CSS is minimal — only for the DropZone and a few layout classes.

---

### P13-01 — Tailwind + shadcn globals

**Deps:** P01-04, P01-09
**Files:** `frontend/src/styles/globals.css`, `frontend/tailwind.config.ts`, `frontend/tests/globals.test.ts`
**Goal:** Tailwind configured with the monochrome palette (HSL variables from spec/11-design-system.md), custom font families, and both light/dark mode variables.

**Implementation:**
- `globals.css` has the `:root` and `.dark` CSS variable blocks from spec/11-design-system.md.
- `tailwind.config.ts` extends the default theme with custom font families (Inter, Fraunces, JetBrains Mono).
- Import `globals.css` in `main.tsx`.

**Test:** `cd frontend && pnpm test --run tests/globals.test.ts`

Required assertions:
- `test("globals.css defines --background variable", ...)`
- `test("dark mode overrides --background", ...)`
- `test("tailwind config has custom font families", ...)`

**Done when:**
- [ ] All 3 tests pass.
- [ ] `pnpm build` succeeds.

---

### P13-02 — Theme provider and toggle

**Deps:** P13-01
**Files:** `frontend/src/lib/theme.ts`, `frontend/src/components/ThemeToggle.tsx`, `frontend/tests/theme.test.tsx`
**Goal:** Theme provider that reads `prefers-color-scheme`, persists to `localStorage`, toggles `dark` class on `<html>`.

**Implementation:**
```tsx
// theme.ts
export type Theme = "light" | "dark";

export function getInitialTheme(): Theme {
  const stored = localStorage.getItem("theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  localStorage.setItem("theme", theme);
}
```

ThemeToggle uses shadcn's `<Button>` with variant="ghost" and sun/moon icons.

**Test:** `cd frontend && pnpm test --run tests/theme.test.tsx`

Required assertions:
- `test("applies dark class on toggle", ...)`
- `test("persists to localStorage", ...)`
- `test("restores from localStorage on mount", ...)`

**Done when:**
- [ ] All 3 tests pass.

---

### P13-03 — Fetch client (with session cookie)

**Deps:** P01-04
**Files:** `frontend/src/lib/api.ts`, `frontend/tests/api.test.ts`
**Goal:** Typed `api` helper wrapping `fetch` with `credentials: "include"`, JSON content-type, error envelope parsing.

**Implementation:** Same as before — `api.get`, `api.post`, `api.postForm`. Uses `APIErrorResponse` class.

**Test:** `cd frontend && pnpm test --run tests/api.test.ts`

Required assertions:
- `test("get returns parsed JSON on 200", ...)`
- `test("get throws APIErrorResponse on 4xx", ...)`
- `test("error has code and status fields", ...)`
- `test("post sends JSON body", ...)`
- `test("credentials include is set", ...)`

**Done when:**
- [ ] All 5 tests pass.

---

### P13-04 — Auth gate component

**Deps:** P13-03
**Files:** `frontend/src/components/AuthGate.tsx`, `frontend/src/components/PasswordForm.tsx`, `frontend/tests/auth-gate.test.tsx`
**Goal:** AuthGate checks `GET /me`. If 401, renders `PasswordForm` (using shadcn Input + Button). Else renders children.

**Implementation:** PasswordForm uses `<Input>` and `<Button>` from shadcn/ui. Error shown with `role="alert"`.

**Test:** `cd frontend && pnpm test --run tests/auth-gate.test.tsx`

Required assertions:
- `test("renders password form when /me returns 401", ...)`
- `test("renders children when /me returns 200", ...)`
- `test("password form error shows on 401", ...)`
- `test("password form success transitions to children", ...)`

**Done when:**
- [ ] All 4 tests pass.

---

### P13-05 — Root layout

**Deps:** P13-02, P13-04
**Files:** `frontend/src/routes/__root.tsx`, `frontend/src/components/Header.tsx`, `frontend/src/components/Footer.tsx`, `frontend/tests/root-layout.test.tsx`
**Goal:** Root layout with header (wordmark + nav + theme toggle + logout), `<Outlet>`, footer. Styled with Tailwind utilities + shadcn Button for nav/logout.

**Implementation:**
- Header: sticky, `backdrop-blur`, flex layout.
- Wordmark "nomenclator" in serif font (`font-serif`).
- 3 nav links using TanStack Router `<Link>`.
- ThemeToggle + Logout button on the right.
- Footer: small centered text.

**Test:** `cd frontend && pnpm test --run tests/root-layout.test.tsx`

Required assertions:
- `test("header renders wordmark", ...)` — `/nomenclator/i` present.
- `test("header has 3 nav links", ...)`
- `test("header has theme toggle button", ...)`
- `test("header has logout button", ...)`
- `test("footer is rendered", ...)`

**Done when:**
- [ ] All 5 tests pass.

---

### P13-06 — DropZone component

**Deps:** P13-01
**Files:** `frontend/src/components/DropZone.tsx`, `frontend/tests/dropzone.test.tsx`
**Goal:** Custom file upload drop zone (no shadcn equivalent). Styled with Tailwind. Accepts drag-and-drop + click-to-browse.

**Implementation:**
```tsx
export function DropZone({ onFile, accept = ".csv" }: { onFile: (file: File) => void; accept?: string }) {
  // Tailwind-styled div with border-dashed, hover:border-primary, etc.
  // Hidden <input type="file">, click handler opens it, drag handlers manage state
}
```

**Test:** `cd frontend && pnpm test --run tests/dropzone.test.tsx`

Required assertions:
- `test("handles file drop event", ...)`
- `test("click opens file picker", ...)`
- `test("shows drag-over visual state", ...)`
- `test("calls onFile callback with dropped file", ...)`

**Done when:**
- [ ] All 4 tests pass.

---

### P13-07 — Spinner component

**Deps:** P13-01
**Files:** `frontend/src/components/Spinner.tsx`, `frontend/tests/spinner.test.tsx`
**Goal:** Simple loading spinner using Tailwind animate-spin.

**Implementation:**
```tsx
export function Spinner({ className }: { className?: string }) {
  return <div className={cn("animate-spin rounded-full border-2 border-muted border-t-primary h-4 w-4", className)} role="status" aria-label="Loading" />;
}
```

**Test:** `cd frontend && pnpm test --run tests/spinner.test.tsx`

Required assertions:
- `test("renders with aria-label", ...)`
- `test("applies custom className", ...)`

**Done when:**
- [ ] Both pass.
