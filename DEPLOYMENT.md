# Deployment

Live URL: **https://nomenclator.fly.dev**  
Platform: Fly.io, region `gru` (São Paulo, Brazil)  
flyctl binary: `~/.fly/bin/flyctl` (not on PATH by default in this codespace)

---

## Infrastructure

| Resource | Value |
|---|---|
| App name | `nomenclator` |
| Volume | `nomenclator_data` — 1 GB, mounted at `/data` |
| Database | `/data/nomenclator.db` (SQLite, persisted on volume) |
| VM | 512 MB RAM, 1 shared CPU (256 MB causes OOM — do not downgrade) |
| Static files | `/app/static` (frontend dist copied in during Docker build) |

---

## Secrets

Set via `flyctl secrets set`, never in `fly.toml` or committed files.

| Secret | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `AUTH_PASSWORD_HASH` | argon2id hash of the app password |

To update a secret:
```bash
~/.fly/bin/flyctl secrets set KEY=value --app nomenclator
```

### Regenerating the password hash

The app **requires an argon2id hash** — bcrypt will be rejected with a RuntimeError at startup (`auth_password_hash must start with $argon2`).

```bash
cd backend
uv run python -c "from app.auth.passwords import hash_password; print(hash_password('your-password'))"
```

Then set the result:
```bash
~/.fly/bin/flyctl secrets set AUTH_PASSWORD_HASH='$argon2id$...' --app nomenclator
```

---

## Deploy

```bash
# Standard deploy (uses Docker layer cache)
~/.fly/bin/flyctl deploy --app nomenclator

# Force clean build (use when .venv or dependency issues are suspected)
~/.fly/bin/flyctl deploy --app nomenclator --no-cache
```

The `fly.toml` at the repo root drives all config. The Dockerfile is a two-stage build:
1. **`fe-build`** — Node 22 + pnpm 10 builds the frontend into `/fe/dist`
2. **`runtime`** — Python 3.12-slim + uv installs backend deps, then frontend dist is copied in

---

## Critical `.dockerignore` rule

`.dockerignore` must use `**/.venv` (glob), not `.venv` (root-only). The codespace has a local `backend/.venv` whose uvicorn script has a shebang pointing to the codespace's Python path. If that directory leaks into the Docker build context it overwrites the container's uvicorn and the app fails to start with "No such file or directory".

Current `.dockerignore` (correct):
```
node_modules
**/__pycache__
*.pyc
**/.venv
.git
```

---

## Post-deploy verification

```bash
# Health check (DB + worker heartbeat)
curl https://nomenclator.fly.dev/health

# Frontend served
curl -o /dev/null -w "%{http_code}\n" https://nomenclator.fly.dev/

# Auth — correct password → 200
curl -X POST https://nomenclator.fly.dev/auth \
  -H "Content-Type: application/json" \
  -d '{"password":"<password>"}'

# Auth — wrong password → 401
curl -X POST https://nomenclator.fly.dev/auth \
  -H "Content-Type: application/json" \
  -d '{"password":"wrong"}'
```

---

## Logs and monitoring

```bash
~/.fly/bin/flyctl logs --app nomenclator
~/.fly/bin/flyctl status --app nomenclator
~/.fly/bin/flyctl ssh console --app nomenclator   # interactive shell
```

Health checks run every 30 s at `GET /health`. Grace period is 10 s after deploy.

---

## pnpm version pin

The Dockerfile pins `pnpm@10` explicitly (`npm install -g pnpm@10`). Do not upgrade to pnpm 11 without also moving `onlyBuiltDependencies` out of `package.json#pnpm` into a `pnpm-workspace.yaml` — pnpm 11 changed that config location and will error on install.
