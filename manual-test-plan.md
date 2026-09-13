# Manual test plan — UI

Automated tests (`backend/tests/`) cover the API/retrieval/routing/persistence layer. This is the
manual pass for the parts only a human eye/keyboard can verify: rendering, sandboxing, responsive
behavior, and accessibility.

## Prerequisites
- `docker compose up` running (or backend + frontend started manually per README).
- Ollama running locally with a model pulled (for the mandatory local-demo path).

## 1. First-load / empty state
- [ ] Loading the app creates a new session automatically (no manual "start" step).
- [ ] Empty state shows the three example prompts; clicking one sends it immediately.
- [ ] Provider badge in the header shows the active provider and a status dot.

## 2. Grounded Q&A
- [ ] Ask a question clearly covered in the transcripts (e.g. "What do guests say about
      product-market fit?"). Response appears with a "Sources (n)" disclosure.
- [ ] Expand "Sources" — each entry links to the correct YouTube video and shows a timestamp.
- [ ] Ask a follow-up ("What about for marketplaces specifically?") — answer reflects the new,
      re-retrieved context, not just a repeat of turn 1.
- [ ] Ask something unrelated to product/growth (e.g. "What's the weather in Tokyo?") — assistant
      states it isn't covered by the transcripts rather than answering from general knowledge.

## 3. Ship 30 for 30 skill
- [ ] Ask: "Turn what you found into a Ship 30 for 30 essay." A compact artifact card appears in
      chat; the Artifact Viewer opens automatically showing the full Markdown essay.
- [ ] Essay has a clear hook in the first sentence, headings/bullets, at least one **bold**
      emphasis, and a distinct takeaway at the end. Word count is roughly 1,250 (±250).

## 4. Artifact generation & viewer
- [ ] Ask for an HTML artifact (e.g. "Give me an HTML card summarizing this"). Confirm it renders
      inside the Artifact Viewer, not as raw code in the chat bubble.
- [ ] Open browser DevTools → Elements — confirm the artifact is inside an `<iframe sandbox=
      "allow-scripts">` with no `allow-same-origin`.
- [ ] With DevTools Network tab open, confirm the iframe issues no network requests (CSP blocks
      them) even if the generated HTML includes an `<img src="https://...">` or fetch call.
- [ ] Generate a second artifact in the same session — confirm a second tab appears in the
      Artifact Viewer and both remain switchable.

## 5. Provider toggle & failure handling
- [ ] With `LLM_PROVIDER=ollama` and Ollama stopped, badge shows the provider as unavailable and a
      banner explains why; sending a message returns a clear inline error, not a hang.
- [ ] Restart Ollama, wait for the next status poll (~15s) or send a message — badge/banner clear.
- [ ] Set `LLM_PROVIDER=anthropic` with no `ANTHROPIC_API_KEY` — same clear-failure behavior.

## 6. Responsive & accessibility
- [ ] Resize the window below ~900px — layout stacks (chat above, artifact panel below) instead of
      overlapping or clipping.
- [ ] Tab through the page using only the keyboard: composer → send → provider badge → new chat →
      example chips → source disclosures → artifact tabs, all reachable with visible focus rings.
- [ ] Use a screen reader (or DevTools accessibility tree) to confirm new assistant messages are
      announced via the `aria-live="polite"` log region without re-reading the whole history.
- [ ] Confirm the sandboxed-preview note ("no cookies, no network access...") is present and
      readable before any HTML artifact.

## 7. Persistence
- [ ] Refresh the page mid-conversation — note that (as scoped) history is per-session in memory
      client-side; hitting `GET /sessions/{id}` directly confirms the conversation *is* persisted
      server-side in Postgres/SQLite even though the demo UI doesn't auto-resume it (documented as
      a known scope cut in `PRD.md`).
