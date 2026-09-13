# Architecture — The Lenny Growth Assistant

## 1. System overview

```
                        ┌─────────────────────────────┐
                        │        Frontend (SPA)        │
                        │  Chat pane │ Artifact Viewer  │
                        │  (vanilla HTML/CSS/JS)        │
                        └───────────────┬──────────────┘
                                        │ REST (JSON)
                        ┌───────────────▼──────────────┐
                        │           FastAPI             │
                        │  routers: sessions, chat,      │
                        │  artifacts, health              │
                        └───────┬───────────────┬───────┘
                                │               │
                    ┌───────────▼───┐   ┌───────▼─────────┐
                    │  Agent layer   │   │  Persistence     │
                    │  (tool router) │   │  (SQLAlchemy)     │
                    └──┬─────────┬──┘   │  Postgres/SQLite  │
                       │         │       └──────────────────┘
             ┌─────────▼──┐   ┌──▼─────────────┐
             │ Retriever   │   │  LLM Provider   │
             │ (FTS5/BM25) │   │  factory        │
             │ over        │   │  ┌────────────┐ │
             │ transcript  │   │  │ Anthropic  │ │
             │ chunks      │   │  ├────────────┤ │
             └─────────────┘   │  │ Ollama     │ │
                                 │  └────────────┘ │
                                 └─────────────────┘
```

Everything downstream of the router layer is provider-agnostic: the agent asks for "the current
LLM" and "the current retriever" through small interfaces (`LLMProvider`, `Retriever`), so cloud
vs. local and BM25 vs. a future vector store are config, not code, changes.

## 2. Ingestion & retrieval flow

1. `scripts/ingest_transcripts.py` clones/pulls
   `https://github.com/ChatPRD/lennys-podcast-transcripts` into `data/transcripts/` (shallow clone;
   re-run does a `git pull`, so refresh = re-run the command; not scheduled automatically).
2. For each `episodes/{guest}/transcript.md`:
   - Parse YAML frontmatter (guest, title, youtube_url, publish_date, keywords, …).
   - Parse the body into speaker turns `Speaker (HH:MM:SS): text`.
   - Group consecutive turns into ~800–1,200 character chunks (never splitting a speaker turn
     mid-sentence where avoidable), tagging each chunk with: `episode_slug`, `guest`, `title`,
     `youtube_url`, `start_timestamp` (of the first turn in the chunk), `chunk_index`.
3. Chunks are inserted into a SQLite **FTS5 virtual table** (`transcript_chunks`) for BM25-ranked
   full-text search, plus a plain table with the same rows for joins/metadata (FTS5 content tables
   keep the two in sync). This lives in its own SQLite file (`data/index.db`) — deliberately
   separate from the app's relational DB (Postgres/SQLite) that holds sessions/messages, since the
   index is a rebuildable derived artifact, not source-of-truth application data.
4. `Retriever.search(query, k)` runs an FTS5 `MATCH` query (query terms sanitized/escaped),
   returns top-k chunks ranked by BM25 with full provenance for citation. This is the seam where a
   pgvector/Chroma-backed `VectorRetriever` could be substituted later — same interface, same
   downstream consumers.
5. Citation string shown to the user is built **from retrieved-chunk metadata by code**, not
   asked of the LLM — the model narrates over the chunks, but "Guest X, *Episode Title*
   (youtube link)" is rendered deterministically. This is the main hallucination guardrail: even a
   confused local model cannot invent a citation that doesn't correspond to a real retrieved chunk.

## 3. Agent / tool routing

The agent layer (`app/services/agent.py`) is a small explicit router, not a black-box planner:

- **Intent classification** is rule/keyword based first (cheap, deterministic, no extra LLM call):
  if the message matches Ship-30-for-30 trigger phrases ("ship 30", "turn this into a post",
  "write an essay") → `ship30_essay` tool. If it looks like an artifact request ("make this a
  doc", "give me an HTML page/card", "one-pager") → `artifact` tool. Otherwise → default grounded
  `chat` tool.
- Each tool independently calls the `Retriever` for the current query (follow-ups re-retrieve,
  they don't just reuse turn 1's chunks) and then calls the configured `LLMProvider` with a tool-
  specific system prompt.
- This mirrors the shape of the Anthropic Agent SDK (tools + a loop over them) without taking a
  hard runtime dependency on it, so the exact same router works against Ollama. See PRD assumption
  4 for why.

### Ship 30 for 30 skill
`app/services/skills/ship30.py` encodes the writing rules extracted from the linked guide as a
structured spec (not a one-off prompt string): hook requirement, ~1,250-word target, heading/bullet
skimmability, one specific takeaway, and a rule that every non-obvious claim must trace back to a
retrieved chunk. The skill first retrieves chunks for the requested topic, then renders a prompt
that embeds the spec + chunks + guest attributions, and validates the output length/structure
before returning it (regenerates once if word count is far off target).

## 4. Data model (SQLAlchemy, works on Postgres and SQLite)

```
sessions
  id            UUID / str PK
  created_at    timestamptz
  metadata_json JSON            -- free-form client metadata (e.g. user-agent), no PII required

messages
  id            PK
  session_id    FK -> sessions.id
  role          enum(user, assistant, system)
  content       text
  provider      str null        -- "anthropic" | "ollama", set on assistant messages
  citations     JSON null       -- [{guest, title, youtube_url, start_timestamp, chunk_index}]
  tool_used     str null        -- "chat" | "ship30_essay" | "artifact"
  created_at    timestamptz

artifacts
  id            PK
  session_id    FK -> sessions.id
  message_id    FK -> messages.id
  kind          enum(markdown, html)
  title         str
  content       text
  created_at    timestamptz
```

`transcript_chunks` (SQLite FTS5, separate index DB — see §2) is treated as a derived cache, not
part of this relational schema, and is rebuilt by the ingestion script rather than migrated.

## 5. API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/health/ready` | readiness: checks DB connection, checks index DB exists/non-empty, checks configured LLM provider is reachable |
| POST | `/sessions` | create a new session, returns `session_id` |
| GET | `/sessions/{id}` | fetch session + message history |
| POST | `/sessions/{id}/messages` | send a user message; returns assistant message with citations/artifact refs |
| GET | `/sessions/{id}/artifacts` | list artifacts generated in a session |
| GET | `/artifacts/{id}` | fetch one artifact's content |
| GET | `/config` | returns active provider, available providers, retrieval index stats — drives the UI's provider badge |

Requests/responses are Pydantic models (`app/schemas.py`) with validation; errors return a
consistent JSON shape `{"error": {"code": ..., "message": ...}}` with appropriate HTTP status
(400 validation, 404 not found, 502 upstream LLM/provider failure, 503 dependency not ready).

## 6. LLM provider layer & toggle

`app/services/llm/base.py` defines:

```python
class LLMProvider(Protocol):
    name: str
    def generate(self, *, system: str, messages: list[dict], max_tokens: int) -> LLMResult: ...
    def is_available(self) -> bool: ...
```

- `AnthropicProvider` — wraps the Messages API (`claude-sonnet-4-6` by default, configurable),
  reads `ANTHROPIC_API_KEY`.
- `OllamaProvider` — calls the local Ollama HTTP API (`OLLAMA_HOST`, default
  `http://localhost:11434`), model configurable via `OLLAMA_MODEL` (default `llama3.1:8b`, chosen
  for running comfortably on a modern laptop; documented as swappable).
- `factory.get_provider(name)` reads `LLM_PROVIDER` (`anthropic` | `ollama`) from config/session
  override. `/config` and a UI badge expose the active provider.
- **Fallback policy (explicit, not silent):** if the selected provider's `is_available()` check
  fails at request time, the API returns a 503 with a clear message ("Ollama is not reachable at
  <host>; is it running?") rather than silently switching providers — a growth PM asking a
  question should never get an answer from a different, potentially lower-quality model than the
  one shown in the UI without being told. An explicit `LLM_FALLBACK_PROVIDER` env var can opt into
  auto-fallback for the demo, in which case the response is tagged with the provider actually used
  so the UI can show "answered via fallback (ollama unreachable)".

## 7. Artifact rendering & security

- The agent returns artifacts as a structured JSON block (`kind`, `title`, `content`), never as
  raw text the frontend regex-parses out of a chat bubble.
- **Markdown** artifacts are rendered client-side with a markdown library into sanitized DOM
  (no `dangerouslySetInnerHTML`-style raw injection; markdown renderer configured with HTML
  disabled).
- **HTML** artifacts are rendered inside an `<iframe>` with:
  - `sandbox="allow-scripts"` only — explicitly **no** `allow-same-origin`, `allow-forms`,
    `allow-popups`, or `allow-top-navigation`. This means any script inside runs in a unique opaque
    origin: it cannot read cookies/localStorage of the app, cannot navigate the parent, cannot
    submit forms anywhere.
  - Content passed via `srcdoc`, never a same-origin `src`, so it never shares origin with app
    assets.
  - A strict inline `Content-Security-Policy` meta tag injected into the srcdoc
    (`default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'`) — scripts can run
    (for interactive artifacts like a small calculator) but cannot fetch network resources or
    load external scripts.
  - No `postMessage` bridge is wired up beyond an optional height-report ping the parent validates
    by origin (`event.origin === 'null'` from the sandboxed iframe) and by a fixed message shape —
    the parent never `eval`s or trusts arbitrary iframe messages.
  - This is documented for the evaluator explicitly in the viewer UI ("this preview runs
    sandboxed: no cookies, no network, no access to the rest of the app") — see `design.md`.

## 8. Observability & resilience

- Structured JSON logging (`app/logging_config.py`) with a request-id per call, log fields for:
  provider used, retrieval hit count, latency per stage (retrieval / LLM / total), and tool routed
  to. Logs are what an FDE would tail in the field to diagnose "why did this answer look wrong."
- Explicit handling for: missing API key (clear 503 at provider construction, not a stack trace),
  Ollama unreachable (connection-error caught, mapped to 503 with actionable message), empty
  retrieval (returns a "not covered" answer rather than calling the LLM with no context — saves a
  cost/latency round-trip and prevents ungrounded guessing), DB connection failure at startup
  (readiness probe fails loudly instead of the app half-starting).

## 9. Deployment topology

`docker-compose.yml` runs: `db` (Postgres), `backend` (FastAPI, builds the index on first boot if
missing), `frontend` (static file server). Ollama is **not** containerized by default — the brief
asks for a model that runs comfortably on the evaluator's machine, and bundling a multi-GB model in
Compose would fight that goal — instead the backend connects to Ollama running natively on the
host (`OLLAMA_HOST=http://host.docker.internal:11434`), documented in the README with the one
`ollama pull <model>` prerequisite. A commented-out Ollama service is included in the compose file
for evaluators who prefer everything containerized.
