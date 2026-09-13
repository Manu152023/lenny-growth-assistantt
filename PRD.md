# PRD — The Lenny Growth Assistant

## 1. Discovery Brief

### User & problem
**Primary user:** a startup product manager or growth lead inside the client's org who wants
tactical, credible product/growth advice without reading (or re-listening to) hundreds of hours
of podcast transcripts.

**Job to be done:** "When I'm about to make a product or growth decision (e.g. how to structure
onboarding, how to run a pricing experiment, how to build a PM career narrative), I want to pull
in what a credible operator has already said about this, get a straight answer with a source I
can go verify, and — if it's useful — turn that answer into something I can publish or share
(a Slack post, a one-pager, an internal memo) without opening a separate editor."

**Pain removed:** today that person either (a) guesses, (b) searches YouTube/Google and skims
transcripts by hand, or (c) asks a generic LLM that hallucinates specifics or can't cite Lenny's
guests directly. The assistant collapses "search transcripts → synthesize → draft something
shareable" into one conversational flow, grounded in a fixed corpus.

**Non-user / out of scope:** this is not a general podcast-summary tool, not a public-facing
product, and not a system of record for the podcast itself.

### Success metric
Primary (product): **≥ 80% of answered questions include at least one correctly attributed
transcript citation (guest + episode), verified against a manual eval set of ~30 representative
questions**, with the remainder correctly abstaining ("not covered in the transcripts") rather
than fabricating.

Secondary (operational): **local (Ollama) demo path boots and answers a question end-to-end in
under 60s on a laptop with no cloud credentials configured**, since the brief makes local-first a
hard requirement for the evaluator.

These are the two metrics an FDE would actually be graded on in the field: is it *right*, and can
someone *run it*.

### Assumptions
The brief was intentionally incomplete in several places. Recorded assumptions, made explicit so
the evaluator can challenge them:

1. **"Users" are internal, trusted employees**, not the public — so we do not need
   authentication/authorization, multi-tenant isolation, or rate limiting beyond basic sanity
   checks. (If this were truly external-facing, auth would move from "excluded" to "required.")
2. **"Grounded strictly from Lenny's transcripts"** means the assistant should not answer general
   knowledge questions unrelated to product/growth even if the base model could — it should say so
   and stay in its lane, but it's acceptable (and expected) for the model to phrase retrieved
   material in its own words rather than only quoting.
3. **Vector-embedding retrieval is not treated as a mandatory ingredient of "RAG."** The brief asks
   for grounded, cited retrieval — not a specific retrieval algorithm. Given the corpus (303 long
   transcripts, static, updated infrequently) and the constraint that everything must also work
   fully offline against a local model with no external embedding API, we default to **SQLite
   FTS5 (BM25) full-text retrieval over transcript chunks**, with a `Retriever` interface designed
   so a vector backend (pgvector, Chroma, etc.) can be swapped in without touching the agent layer.
   This is called out as a deliberate, documented trade-off, not an oversight.
4. **"Claude Agent SDK or Pi Coding Agent"** — we use the **Anthropic Messages API directly** via a
   thin agent/tool-router layer that mirrors the Agent SDK's shape (tools for retrieval and for the
   Ship 30 for 30 skill, a session/turn loop), rather than taking a hard dependency on the (still
   young) Agent SDK package for the *local* model path — Ollama models are called through the same
   abstraction. This keeps provider-swapping trivial and avoids a two-tier codebase where cloud
   gets "real" agent tooling and local gets a hand-rolled shim. Documented in `architecture.md`.
5. **PostgreSQL is used for persistence**, with SQLite as a zero-config local fallback (`DATABASE_URL`
   controls which). Supabase/Railway are not provisioned for this take-home; docker-compose ships
   its own Postgres container so the evaluator doesn't need a cloud account.
6. **"Users want rendered artifacts"** is interpreted as: Markdown documents and self-contained
   HTML/CSS snippets, explicitly requested or clearly implied ("write this up as a doc", "make a
   one-pager"), rendered in a split-pane viewer — not arbitrary JS execution or multi-file web apps.
7. Given a take-home time budget, **evaluation of RAG quality is a small fixed test set**, not a
   full offline eval harness (e.g. RAGAS) — noted as a risk/future-work item.

### Scope choices

**In scope**
- FastAPI backend: sessions, chat, artifact generation, health/readiness endpoints.
- Transcript ingestion (clone/pull the public repo, parse frontmatter + speaker-turn transcript,
  chunk, index into SQLite FTS5, store chunk provenance for citation).
- Retrieval-grounded chat with citations, multi-turn session memory, explicit "not covered"
  behavior when retrieval is empty/weak.
- Ship 30 for 30 essay skill as a distinct, documented tool with its own prompt/spec, not an
  ad-hoc instruction stapled onto the chat prompt.
- Artifact generation (Markdown + sandboxed HTML/CSS) with an in-app viewer.
- Pluggable LLM layer: Anthropic (cloud) + Ollama (local, mandatory for the demo), selected via
  config and visible in the UI, with fallback behavior when a provider is unavailable.
- Postgres/SQLite persistence for sessions, messages, and artifacts.
- Docker Compose one-command startup, `.env.example`, structured logging, basic resilience.
- Automated tests for ingestion/retrieval, the chat API, and provider fallback; manual UI test plan.

**Explicitly excluded (and why)**
- **User accounts/auth** — internal trusted-user assumption above; would be the first thing added
  for a real deployment.
- **Vector database / embeddings** — see assumption 3. Swappable via the `Retriever` interface but
  not implemented, to keep the offline/local path dependency-light and reliable within scope.
- **Streaming token-by-token UI** — the API supports it structurally (provider layer returns full
  text today) but the take-home ships request/response chat, not SSE streaming, to keep the surface
  area testable in the time available. Called out as the top "next" item.
- **Automatic re-ingestion / scheduled refresh** — ingestion is an explicit CLI/admin action, not a
  background cron, since the corpus is static for the exercise.
- **Multi-user real-time collaboration, notifications, billing, analytics dashboards.**

### Risks & trade-offs
| Risk | Mitigation in this build |
|---|---|
| **Hallucination** | Retrieval-first prompt contract: system prompt instructs the model to answer only from provided chunks and to say "the transcripts don't cover this" when retrieval is empty or low-scoring; citations are rendered from actual retrieved chunk metadata (not model-generated), so a citation can't be fabricated even if the model tries. |
| **Local model quality (Ollama)** | Small local models are weaker at instruction-following and citation formatting than Claude. We keep the retrieval/citation logic outside the model (deterministic, code-driven) so answer *grounding* doesn't depend on the local model behaving perfectly — only fluency does. Documented as a known quality gap in README. |
| **Latency** | Local models on a laptop CPU can be slow (10–60s+). UI shows explicit loading/streaming-style states and the backend enforces a request timeout with a clear error rather than hanging silently. |
| **Cost** | Cloud path only used for the chosen provider on demand; retrieval (the expensive-to-get-wrong part) never calls an LLM, so cost scales with conversation volume, not corpus size. |
| **Data leakage** | Transcripts are public podcast content; no PII/secrets are ingested. Session data stored per-session with a generated ID, not tied to any identity system in this build. |
| **Unsafe artifact rendering** | Generated HTML is treated as untrusted: rendered inside a sandboxed `<iframe>` with `sandbox="allow-scripts"` only (no `allow-same-origin`), `srcdoc` (never same-origin src), a strict inline CSP, and no access to postMessage back to the parent beyond a resize ping. Full detail in `design.md` / `architecture.md`. |
| **Retrieval quality ceiling of BM25 vs. embeddings** | Acceptable for keyword-rich PM/growth queries (people ask about named frameworks, guests, companies), weaker for purely semantic paraphrase queries. Flagged as the top scalability item if this graduated beyond a take-home. |

## 2. Flows

1. **New session** → user opens app → frontend calls `POST /sessions` → gets `session_id` → empty
   chat state.
2. **Ask a question** → `POST /sessions/{id}/messages` → backend retrieves top-k transcript chunks
   → agent generates an answer with inline citations → response + citations + provider used are
   persisted and returned → rendered in chat with expandable source list.
3. **Follow-up question** → same endpoint; backend loads prior turns from Postgres/SQLite to keep
   context; retrieval re-runs per turn (not just the first turn).
4. **"Turn this into a Ship 30 for 30 post"** → agent routes to the `ship30_essay` tool/skill →
   skill re-grounds against the same retrieval layer for the topic → returns a Markdown artifact.
5. **Artifact request** ("make this a one-pager", "give me an HTML card for this") → agent emits a
   structured artifact block (type + content) → backend stores it → frontend renders it in the
   Artifact Viewer pane, sandboxed if HTML.
6. **Provider toggle** → evaluator sets `LLM_PROVIDER=anthropic|ollama` (env) or per-session
   override in the UI → visible badge shows active provider → if the selected provider is
   unreachable, backend falls back per documented policy and surfaces that in the UI, it does not
   silently swap without telling the user.

## 3. Acceptance criteria

- [ ] Fresh clone + `docker compose up` (with a filled `.env`) serves a working chat UI without
      manual DB setup.
- [ ] Ingestion command populates the transcript index from the public repo and reports counts.
- [ ] A question with topical coverage in the transcripts returns an answer with ≥1 citation
      naming a specific guest/episode.
- [ ] A question with no coverage returns an explicit "not covered" response, not a fabricated one.
- [ ] Switching `LLM_PROVIDER` to `ollama` with no Anthropic key set still works end-to-end.
- [ ] Killing Ollama mid-session produces a clear error, not a hang or 500 with no message.
- [ ] "Write this as a Ship 30 for 30 post" produces a ~1,250-word Markdown artifact with a hook,
      headings/bullets, and a stated takeaway, viewable in the Artifact Viewer.
- [ ] A requested HTML artifact renders inside the sandboxed viewer and cannot execute a
      `postMessage`-based break-out or access `document.cookie` of the parent app.
- [ ] `pytest` passes for retrieval, chat API, and provider-fallback tests.

## 4. Implementation plan (as executed)
1. Ingestion + retrieval core (parse → chunk → FTS5 index → retriever interface).
2. LLM provider abstraction (Anthropic + Ollama) + config/toggle.
3. Agent/tool-routing layer (chat tool = retrieval, skill tool = Ship 30 for 30, artifact tool).
4. FastAPI routers + Postgres/SQLite persistence models.
5. Frontend chat UI + Artifact Viewer (sandboxed).
6. Docker Compose, `.env.example`, logging, resilience/error handling.
7. Tests + manual test plan + docs (`design.md`, `architecture.md`, `README.md`).
