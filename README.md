# Citadel

> A cryptographically-secured firewall and grammar-strict proxy that sits in front of your LLM APIs.

GuardRail-AI is a high-throughput security middleware layer that intercepts every prompt headed to a downstream LLM, screens it for prompt-injection and jailbreak attempts, cryptographically signs the payload, and **structurally validates the model's output** against a formal grammar before it ever reaches your application. Malformed or unsafe traffic is rejected fail-closed — the proxy never guesses, repairs, or forwards data it cannot verify.

---

## Why

LLM integrations have two soft underbellies:

1. **Inbound** — untrusted user prompts can carry injection / jailbreak payloads that hijack the model.
2. **Outbound** — model output is free-form text. When you parse it as a tool call or JSON, a single malformed token can crash a downstream handler or trigger an unintended action.

GuardRail-AI hardens both edges with a single proxy hop, designed to add **< 200 ms** of round-trip overhead and to lean on the standard library rather than heavy external dependencies.

---

## Architecture

```
                       ┌─────────────────────── GuardRail-AI Proxy ───────────────────────┐
                       │                                                                   │
  Client / User  ──►   │  FirewallMiddleware ──►  HMAC Signer ──►  LLM Call ──►  CFG Parser │ ──►  Validated
   (raw prompt)        │  (injection scan)        (SHA-256)       (downstream)  (structural)│      tool call
                       │        │                                       │            │       │
                       │        ▼ 400                                   │            ▼ 502   │
                       │   reject inbound                               │     reject output  │
                       └────────────────────────────────────────────────────────────────────┘
```

### Request pipeline (`POST /api/v1/gateway`)

1. **Firewall** — ASGI middleware scans the inbound prompt against configurable jailbreak rules and an ML classifier; rejects with `400` before any work is done.
2. **Canonicalize & sign** — the JSON body is canonicalized (sorted keys, compact form) and signed with **HMAC-SHA256**. Canonical form makes the signature independent of client key ordering.
3. **LLM call** — the signed prompt is forwarded to the target LLM (currently a deterministic mock; pluggable real HTTP client).
4. **Grammar validation** — raw model output is parsed against a formal **Context-Free Grammar** (Lark LALR(1)) and then deserialized. Any structural violation raises an error and returns `502` — no repair, no guessing.
5. **Response** — the validated tool-call dict is returned with an `X-GuardRail-Signature` header so downstream verifiers can confirm provenance.

### Fail-closed status codes

| Code | Meaning |
|------|---------|
| `400` | Non-JSON body, or missing / invalid `prompt` field, or firewall rejection |
| `502` | LLM output failed CFG grammar validation |
| `503` | Secret key absent — crypto subsystem cannot operate |

---

## Tech stack

| Layer | Choice |
|-------|--------|
| API framework | Python 3.11+, FastAPI, Uvicorn |
| Validation | Pydantic v2 |
| Crypto | stdlib `hmac` + `hashlib` (HMAC-SHA256), `cryptography` |
| Parser engine | Lark (EBNF / LALR(1) CFG) |
| Content classifier | scikit-learn (TF-IDF + Logistic Regression) |
| Frontend | Next.js 14, React 18, Tailwind CSS, Framer Motion |
| Deployment | Docker, docker-compose |
| Tooling | pytest, black, ruff, mypy |

---

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 18+ (only for the frontend dashboard)
- Docker (optional, for containerized runs)

### Backend

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
#    Set GUARDRAIL_SECRET_KEY to a value >= 32 bytes — the app fails fast without it.

# 4. (Optional) train the content classifier
python scripts/train_classifier.py

# 5. Run the proxy
uvicorn app.main:app --reload --port 8000
```

Interactive API docs are then available at `http://localhost:8000/docs`, and a liveness probe at `http://localhost:8000/health`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local          # point NEXT_PUBLIC_API_URL at the proxy
npm run dev                          # http://localhost:3000
```

### Docker

```bash
docker compose up --build
```

---

## Usage

```bash
curl -X POST http://localhost:8000/api/v1/gateway \
  -H "Content-Type: application/json" \
  -d '{"prompt": "search for recent AI papers"}'
```

```jsonc
// 200 OK
{
  "status": "ok",
  "tool_call": {
    "tool_name": "search",
    "arguments": { "query": "search for recent AI papers", "limit": 10 }
  },
  "signature_preview": "a1b2c3d4...ef01"
}
```

The signed payload digest is also returned on the `X-GuardRail-Signature` response header.

---

## Project layout

```
app/
  api/v1/proxy.py        # /api/v1/gateway pipeline
  middleware/firewall.py # inbound injection / jailbreak screening
  crypto/ , utils/crypto.py   # HMAC-SHA256 canonicalize + sign
  parser/                # Lark grammar + engine + transformer (output validation)
  ml/classifier.py       # TF-IDF + LogReg harmful-content classifier
  handlers/fallback.py   # fail-closed handlers
  main.py                # FastAPI app + middleware wiring + lifespan checks
config/
  config.yaml            # runtime config
  jailbreak_rules.yaml   # firewall rule set
grammar/ , app/parser/*.lark   # CFG definitions
scripts/
  train_classifier.py    # build app/ml/model.pkl
  benchmark.py           # latency benchmark
frontend/                # Next.js dashboard
tests/                   # pytest suite (firewall, parser, signer, ml, api)
```

---

## Testing

```bash
pytest                  # full suite
pytest --cov=app        # with coverage
```

---

## Configuration

Set via environment variables (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `GUARDRAIL_SECRET_KEY` | HMAC signing key — must be ≥ 32 bytes (required) |
| `LOG_LEVEL` | Logging verbosity (default `INFO`) |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `HOST` / `PORT` | Bind address (default `0.0.0.0:8000`) |

Both the HMAC key and the CFG grammar are validated at startup — misconfiguration surfaces at boot, not on the first live request.


