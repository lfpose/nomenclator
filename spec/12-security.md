# 12 — Security

Threat model: one operator, one password, one server holding a paid Anthropic API key. The failure we are protecting against is "random person on the internet discovers the URL and burns the API key." We are not protecting against determined targeted attacks or sophisticated insiders — this is a private internal tool for a single person.

## Authentication

### Single shared password

- Exactly one password exists, shared by whoever uses the tool.
- The password is stored **only** as an argon2id hash in the Fly secret `AUTH_PASSWORD_HASH`. Never in the database. Never in source. Never in logs.
- Argon2id parameters: `time_cost=3, memory_cost=65536, parallelism=4` (the `argon2-cffi` library defaults are fine).
- Hash verification on every login attempt. Timing is naturally constant thanks to argon2.

### Sessions

- On successful login, generate `sid = secrets.token_hex(32)` (64 hex chars = 256 random bits).
- Hash the sid with SHA-256 and store the hash in `sessions.id`. The cookie carries the raw sid; the DB only stores the hash. This means a DB leak doesn't expose live session tokens.
- Cookie: `Set-Cookie: sid={raw}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000`.
- Session row: `id=sha256(raw)`, `created_at=now`, `expires_at=now+30d`.
- On every authenticated request: sha256 the incoming cookie value, look up the session row, check `expires_at > now`. Update `expires_at` lazily once a day per session (sliding expiration).
- Logout: delete the row, unset the cookie.

### Rate limiting

- `/auth`: 5 attempts per minute per IP. Implemented as an in-memory token bucket keyed by client IP. Exceeded attempts return 429 `rate_limited`. Lost on restart — fine, attacker has to start over.
- `/jobs/commit`: 10 per hour per session. Protects against someone who guessed the password running cost attacks against the Anthropic key.
- Everything else: 60 per minute per session. Prevents silly loops.
- All limits are enforced in-process with a `collections.deque` of timestamps. No Redis.

## API key protection

- `ANTHROPIC_API_KEY` lives in Fly secrets only.
- The key is loaded once into `settings.anthropic_api_key` on startup.
- The key never appears in any HTTP response body, never in error messages, never in logs. Log redaction is a simple regex replacement on any string that starts with `sk-ant-`.
- The key is only used from the backend to call Anthropic. The frontend has no knowledge of it.

## Spend cap as a security control

The $20/month cap is a cost-containment control, not just a budget. If the password is guessed:

- Logins are rate-limited (5/min/IP).
- Commits are rate-limited (10/hour/session).
- Every commit runs the spend cap check.
- Even in the worst case where an attacker gets logged in, the cap bounds total monthly damage to $20.

## CSRF

Threat model: one operator, single-domain, SameSite=Lax cookie. For the level of threat we're defending against, SameSite=Lax is sufficient and no CSRF token is needed.

Conditions that keep this true:

- All mutating endpoints require `Content-Type: application/json` or `multipart/form-data`, not `application/x-www-form-urlencoded`. This blocks naive form-based CSRF since a cross-site form can't set arbitrary content types.
- All state-changing endpoints use POST (never GET).
- No JSONP, no permissive CORS.

If v2 ever adds public exposure or multi-user, reopen this decision and add CSRF tokens.

## CORS

- Default deny. Same-origin only.
- No cross-origin requests are expected in v1.

## Content Security Policy

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data:;
  font-src 'self';
  connect-src 'self';
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
```

`'unsafe-inline'` on style-src is the one compromise — CSS-in-JS solutions and mermaid inline-style the SVGs. Revisit if/when we audit for tighter CSP.

## Transport

- Fly terminates TLS with its default certs. All traffic is HTTPS.
- HTTP → HTTPS redirect at the Fly edge.
- HSTS: `Strict-Transport-Security: max-age=31536000; includeSubDomains`.

## Input validation

- Request sizes: multipart upload capped at 50 MB. JSON bodies capped at 1 MB.
- CSV rows capped at 50,000 (see `FR-016`).
- Pydantic models validate every request body. Rejection returns 400 with the validation error.
- User-supplied `prompt_override` is passed verbatim to Anthropic as the system prompt. It is **not** interpolated into any templated message on our side, so prompt injection cannot escape into our code paths. The model itself is what absorbs the override — that's the operator's choice and their content.
- Taxonomy is interpolated into the user message as a bullet list. Newlines in the operator's taxonomy input are escaped by splitting on `\n` and re-joining with `- ` prefixes.

## Prompt review security

The prompt review endpoint (`POST /jobs/review-prompt`) sends the operator's prompt to Claude Haiku for evaluation. Security notes:
- The review prompt is a *meta-evaluation* — it asks the model to assess the operator's prompt, not to execute it.
- The meta-prompt is fixed server-side; the operator cannot modify it.
- Rate-limited to 10/min/session to prevent abuse.
- Does not expose raw model responses — only the structured tool-call output.

## Dry-run mode

Dry-run mode bypasses the Anthropic API entirely. Security implications:
- No API key usage during dry runs — the key is never sent.
- Dry-run jobs don't contribute to the spend cap.
- The dry-run toggle is visible in the UI; there is no risk of accidentally running a real job if the toggle is off (default).
- Fake responses are generated deterministically server-side with no external calls.

## Logging

Logs must never contain:

- The raw password.
- The argon2 hash.
- Any session cookie value (raw or hashed).
- The Anthropic API key.
- Operator-supplied CSV content (row samples are OK at DEBUG, capped at 3 rows and 200 chars each).

A redaction filter runs on every log line. The filter is a simple regex list and is part of the logging setup module.

## Operational

- Fly secrets are managed with `fly secrets set` and never committed.
- No `.env` file in the repo. Local dev uses `direnv` or the operator's choice; the committed `.env.example` lists required variable names only.
- Dependency audit: `pip-audit` on CI (when CI exists) or manually before each release.
