# Demo video — script & checklist

Target length: 3-4 minutes, camera on, uploaded to YouTube (per assignment §6.8). This is a
speaking outline, not a word-for-word script — say it in your own words.

## Before recording
- [ ] `docker compose up --build` running cleanly (or your local `uvicorn` + static server setup).
- [ ] Confirm `ollama serve` is running and the model is pulled — you must demo the **local**
      path live, not just cloud.
- [ ] Have one grounded question, one Ship 30 for 30 request, and one artifact request ready to
      type (see examples below) so you're not thinking of prompts on camera.
- [ ] Open `/docs` (FastAPI Swagger) in a second tab in case you want to show the API contract.

## Beat-by-beat outline (~2:30)

**0:00–0:25 — The problem (camera on, talking head)**
"A product/growth team wants their team to get reliable answers from Lenny's Podcast without
reading hundreds of transcripts by hand, and to be able to turn a good answer into something
shareable — without touching prompts or infrastructure." (One sentence on who the user is, one on
the pain removed — pull straight from PRD §1 if you go blank.)

**0:25–1:10 — Product walkthrough**
- Show the chat UI. Ask: *"What do guests say about finding product-market fit?"*
- Point at the citations disclosure — click it open, click through to a source. Say why this
  matters: "answers are grounded, not just generated, and you can verify it in one click."
- Ask a natural follow-up to show session context is preserved.
- Ask something clearly not covered (e.g. "what's the weather today") to show the abstention
  behavior — call out that this is deliberate, not a failure.

**1:10–1:40 — Ship 30 for 30 + artifact viewer**
- Type: *"Turn what you found on product-market fit into a Ship 30 for 30 essay."*
- While it generates, narrate: "this is a distinct skill with its own encoded writing rules, not
  a one-off prompt tacked onto chat."
- Show the artifact opening in the split-pane viewer. Scroll it. Mention the word count is close
  to the ~1,250-word target.
- Optionally: ask for an HTML artifact and briefly show it rendering, mentioning it's sandboxed.

**1:40–2:10 — Local Ollama demonstration (required)**
- Show the provider badge reading "ollama".
- Either: stop Ollama live and show the clear error/banner, then restart it and show recovery —
  OR, if time is tight, just point at the badge and say "this whole demo has been running against
  a local model, no cloud API key involved," and briefly show `.env` / `LLM_PROVIDER=ollama`.

**2:10–2:40 — One technical trade-off (required)**
Pick ONE and explain the reasoning out loud in ~20–30 seconds. Strongest candidates, ranked:
1. **BM25/FTS5 over vector embeddings** — "I chose keyword-based retrieval over embeddings so the
   fully-local demo path has zero extra ML dependencies and stays fast and reliable on a laptop;
   the trade-off is weaker performance on purely semantic paraphrase queries. The retriever sits
   behind an interface so a vector store is a drop-in swap later."
2. **Non-silent provider fallback** — "If Ollama isn't running, the app fails with a clear error
   instead of silently answering from a different model — because a user shouldn't get an answer
   from a model they didn't choose without being told."
3. **Iframe sandboxing for HTML artifacts** — "Generated HTML is treated as fully untrusted: it
   renders in an iframe with no same-origin access and a CSP blocking all network calls, so even a
   malicious artifact can't read cookies or exfiltrate data."

**2:40–end — Close**
One sentence on what you'd build next if this went past a take-home (e.g. vector retrieval,
streaming responses, auth) — shows forward-looking judgment without over-promising.

## After recording
- [ ] Upload to YouTube (unlisted is fine unless the form asks for public).
- [ ] Add the link to your README and/or the submission form.
