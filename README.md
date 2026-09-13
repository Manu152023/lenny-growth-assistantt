# The Lenny Growth Assistant

A grounded conversational assistant over [Lenny's Podcast transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts),
with a Ship 30 for 30 essay skill and an in-app Markdown/HTML artifact viewer. Built as a Forward
Deployed Engineer take-home — see `PRD.md`, `design.md`, and `architecture.md` for the full
discovery brief, UX rationale, and system design.

## Architecture at a glance

```
frontend (static HTML/CSS/JS)  →  FastAPI backend  →  Postgres/SQLite (sessions, messages, artifacts)
                                        │
                                        ├─ Retriever (SQLite FTS5/BM25 over transcript chunks)
                                        └─ LLM provider factory (Anthropic | Ollama, config-toggled)
```

Full detail: [`architecture.md`](architecture.md). UX rationale: [`design.md`](design.md).
Product framing, assumptions, and scope cuts: [`PRD.md`](PRD.md).

## Prerequisites

- Docker + Docker Compose (recommended path), **or** Python 3.12 + Node not required (frontend is
  plain HTML/JS, no build step).
- [Ollama](https://ollama.com/) installed and running **on your host machine** (mandatory for the
  local-model demo path — see PRD for why it isn't containerized by default):
  ```bash
  ollama serve
  ollama pull llama3.1:8b   # or any model that runs comfortably on your machine
  ```
- Optional: an Anthropic API key if you want to exercise the cloud provider path.
- `git` (used by the ingestion script to fetch the public transcript repo).

## Quickstart (Docker Compose — one command)

```bash
cp .env.example .env
# edit .env only if you want to change the Ollama model or add ANTHROPIC_API_KEY
docker compose up --build
```

- Backend API: http://localhost:8000 (docs at `/docs`, health at `/health`, `/health/ready`)
- Frontend: http://localhost:3000
- Postgres: localhost:5432 (credentials from `.env`)

On first boot, the backend container automatically clones the transcript repo and builds the
retrieval index if one doesn't already exist (`data/index.db`) — this takes roughly a minute the
first time and is skipped on subsequent restarts. Watch `docker compose logs -f backend` to see
ingestion progress.

## Running without Docker (local dev)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env    # DATABASE_URL defaults to a local SQLite file — no Postgres needed

python scripts/ingest_transcripts.py     # clones the transcript repo + builds the index (~1 min)
uvicorn app.main:app --reload --port 8000
```

In another terminal, serve the frontend (any static file server works):
```bash
cd frontend
python -m http.server 3000
```
Open http://localhost:3000. The frontend defaults to talking to `http://localhost:8000`; override
by setting `window.LGA_API_BASE` (e.g. add a small inline `<script>` in `index.html` before
`app.js`, or serve behind a reverse proxy that rewrites `/api`).

## Environment variables

See [`.env.example`](.env.example) for the full list with defaults and comments. The ones you're
most likely to touch:

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `ollama` (default, mandatory for the demo) or `anthropic` |
| `LLM_FALLBACK_PROVIDER` | Optional — auto-fallback target if the primary is unreachable (default: none, fails loudly instead) |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Cloud provider config |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | Local provider config |
| `DATABASE_URL` | Postgres (compose) or SQLite (bare `uvicorn`) connection string |

**Never commit a filled-in `.env`** — it's gitignored; `.env.example` only contains safe defaults
and empty placeholders for secrets.

## Switching the model provider

The active provider is config-driven (`LLM_PROVIDER`) and shown live in the UI's provider badge —
this satisfies the "flexible LLM configuration" requirement without touching application code.
Per-request overrides are also supported: `POST /sessions/{id}/messages` accepts an optional
`provider_override` field.

**Fallback policy:** if the selected provider is unavailable (missing API key, Ollama not
running), the API returns a clear `503` rather than silently answering from a different model —
see `architecture.md` §6. Set `LLM_FALLBACK_PROVIDER` if you want opt-in automatic fallback instead
(the response will be tagged with the provider actually used).

## Running tests

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

17 tests cover: health/readiness, transcript parsing + retrieval quality (against a fixture
transcript, no network required), the full chat API (grounded citations, "not covered" abstention,
Ship 30 for 30 routing + length validation, artifact generation, session persistence, error
handling), and LLM provider fallback behavior. Tests never require a live Ollama instance or a
real Anthropic key — the chat/agent paths are tested against a fake in-process provider; the
provider-factory tests intentionally point at an unroutable host to assert the "fail loudly, don't
silently swap" contract.

A manual UI test plan (rendering, artifact sandboxing, responsiveness, accessibility — things an
automated API test can't verify) is in [`manual-test-plan.md`](manual-test-plan.md).

## Re-running / refreshing ingestion

Ingestion is an explicit action, not a background job (see PRD scope cuts):
```bash
python scripts/ingest_transcripts.py            # git pull + full re-index
python scripts/ingest_transcripts.py --skip-clone  # re-index files already on disk
```

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `docker compose up` backend keeps restarting | Check `docker compose logs backend` — usually ingestion failed (no network to GitHub) or Postgres wasn't ready yet (compose waits on a healthcheck, but a slow first boot can still race). |
| `/health/ready` returns `"llm_provider_reachable": false` | If `LLM_PROVIDER=ollama`: is `ollama serve` running on the **host**, and did you `ollama pull` the configured model? Docker containers reach it via `host.docker.internal` — confirm `OLLAMA_HOST` matches. If `anthropic`: is `ANTHROPIC_API_KEY` set? |
| Chat requests return `503 provider_unavailable` | Same as above — this is the intended "fail loudly" behavior, not a bug. Check the message body for the specific cause. |
| Chat requests return `502 llm_error` | The provider was reachable but the request itself failed (timeout, model error). Check backend logs for the `llm_provider_error` structured log entry. |
| Retrieval returns nothing for a clearly-covered topic | Confirm the index actually built: `GET /config` → `index_chunk_count` should be in the tens of thousands. If it's `0`, re-run `scripts/ingest_transcripts.py`. |
| Frontend shows "Cannot reach the backend API" | Confirm the backend is actually running on the port `app.js`'s `API_BASE` expects, and that CORS isn't blocking it (`CORS_ORIGINS` defaults to `*`). |

## Security notes

- Generated HTML artifacts render inside a sandboxed `<iframe sandbox="allow-scripts">` via
  `srcdoc`, with no `allow-same-origin`, and a strict injected CSP blocking all network access.
  Full rationale in `architecture.md` §7.
- Citations are built from retrieved-chunk metadata in code, not asked of the LLM, so a citation
  can't be fabricated even by a confused local model — see `architecture.md` §2.
- This build assumes internal/trusted users and does not implement authentication — see
  `PRD.md`'s assumptions for why, and what would change for a public deployment.

## Project layout

```
PRD.md                    Discovery brief, assumptions, scope, acceptance criteria
design.md                 UI/UX principles and interaction states
architecture.md            System design, data model, API contract, security
manual-test-plan.md        Human-verified UI/accessibility/sandboxing checks
docker-compose.yml         db + backend + frontend orchestration
.env.example                Configuration template
backend/
  app/                     FastAPI app (routers, services, models)
  scripts/ingest_transcripts.py   Ingestion CLI
  tests/                   pytest suite
frontend/
  index.html, app.js, styles.css   Chat UI + Artifact Viewer (no build step)
agent-transcripts/          AI-assisted build process log (see its own README)
```
## Video Demo
https://youtu.be/4-9N_tJHK80?si=cBE0tKTP1gbYKXLI
