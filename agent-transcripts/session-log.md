# Agent session log (condensed)

## 1. Discovery
- Parsed the take-home brief (docx) to extract requirements: FastAPI + Postgres + Claude Agent
  SDK/Pi + Ollama toggle + RAG over a named public transcript repo + Ship 30 for 30 skill +
  sandboxed artifact viewer + full deliverable set.
- Wrote `PRD.md` first, including explicit assumptions where the brief was ambiguous (see
  "Assumptions" section) — notably the decision to use FTS5/BM25 retrieval instead of a vector
  store, and to implement an Agent-SDK-shaped tool router directly against the Anthropic Messages
  API + Ollama rather than taking a hard dependency on the (young) Agent SDK package for a path
  that also has to run against a local model.

## 2. Ground the design in the real data (before writing ingestion code)
- Cloned the actual transcript repo (`git clone --depth 1
  https://github.com/ChatPRD/lennys-podcast-transcripts`) instead of guessing its structure.
- Inspected `README.md`, `CLAUDE.md`, and one full episode file (`episodes/boz/transcript.md`) to
  confirm: YAML frontmatter fields, `## Transcript` heading, and the exact
  `Speaker (HH:MM:SS):` turn format — this shaped `ingest.py`'s regex and chunking logic directly
  from real data rather than an assumed format.

## 3. Backend build, verified incrementally
- Built config → db → models → schemas → retrieval (ingest + FTS5 retriever) → LLM provider layer
  (Anthropic + Ollama + factory/fallback) → Ship 30 skill → artifact service → agent router →
  routers → `main.py`, in that order — each layer only depends on layers already built and tested.
- After writing the retrever, ran ingestion against the full real corpus (not a stub): 301 of 303
  episodes indexed, 22,903 chunks, 2 episodes skipped (files that didn't parse as expected
  frontmatter — logged, not silently ignored). Spot-checked retrieval quality with real queries
  ("product market fit", "pricing experiments", "onboarding activation") and confirmed the
  top hits were substantively on-topic and attributed to the right guest before trusting the
  retriever in the agent layer.

## 4. Failures hit and how they were corrected
1. **Ingestion path mismatch.** First attempt at copying the cloned transcripts into `data/`
   silently nested them one directory too deep (`cp -r src ../data/transcripts` copied *into* an
   already-existing target dir instead of populating it), and separately the default
   `transcripts_dir` config value (`./data/transcripts`) was relative to the process's working
   directory, which didn't match where the data actually ended up when running the script from
   `backend/`. Fixed by moving the data directory under `backend/data/` (matching where the
   process actually runs, both locally and in the Docker image) and re-verifying with a fresh
   ingestion run rather than assuming the fix worked.
2. **FastAPI `TestClient` didn't run startup logic.** First end-to-end smoke test hit
   `sqlite3.OperationalError: no such table: sessions` even though `Base.metadata.create_all()`
   was wired to the startup event — `TestClient` only fires FastAPI lifespan/startup hooks when
   used as a context manager (`with TestClient(app) as client:`), not on ad-hoc instantiation.
   Fixed the test invocations, and separately migrated `main.py` off the deprecated `@app.on_event`
   decorator to an explicit `lifespan` context manager while addressing this, removing a
   deprecation warning at the same time instead of leaving it for later.
3. **Missing ORM relationship.** `sessions.py`'s response builder assumed `Message.artifacts`
   existed to look up an artifact tied to a message, but the initial `models.py` only defined the
   FK column on `Artifact`, not the back-reference on `Message`. Caught by re-reading the router
   against the model before running it (not by a runtime crash) and added the missing
   `relationship()` on both sides.

## 5. What was verified by actually running it, not just written
- Full ingestion against the real 303-episode corpus (counts logged above).
- Retrieval spot checks against real queries with real results inspected.
- A live end-to-end HTTP flow through `TestClient` covering: session creation → grounded chat with
  citations → Ship 30 for 30 routing → artifact creation → artifact fetch → session history —
  using a fake LLM provider so no API key or local Ollama instance was required to validate the
  wiring.
- The full `pytest` suite (17 tests: health, retrieval unit tests against a fixture transcript,
  chat API integration tests, provider-fallback tests) — run to green, including a deliberate test
  that an ungrounded/unrelated query gets a "not covered" response with zero citations rather than
  a fabricated one.

## 6. Known gaps left for the evaluator (see PRD.md §Scope choices for the full list)
- No automated browser/UI test (Playwright etc.) — the manual test plan in
  `manual-test-plan.md` covers rendering, sandboxing, and accessibility, which weren't practical
  to verify headlessly in the time available.
- Frontend does not persist/resume a session across a page refresh (a new session is created on
  each load); server-side persistence works and is directly verifiable via `GET /sessions/{id}`,
  but the UI doesn't yet surface a "resume last session" affordance.
