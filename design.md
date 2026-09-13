# design.md — UI/UX

## 1. Principles
1. **Show your work.** Every grounded answer displays its sources inline (collapsed by default,
   expandable) — the user should never have to wonder whether an answer is made up.
2. **Never hide system state.** Active model/provider, retrieval hit count, and tool used are
   always visible, not just in a settings screen nobody opens.
3. **Artifacts live beside the conversation, not instead of it.** Split-pane rather than a modal or
   a new tab — the user can keep asking follow-ups while looking at the doc.
4. **Fail loudly and specifically.** "Ollama isn't running" beats a spinner that never resolves.

## 2. Information architecture
```
┌─────────────────────────────────────────────────────────────────┐
│ Header: "Lenny Growth Assistant"      [Provider: Ollama ▾] [New] │
├───────────────────────────────┬───────────────────────────────────┤
│  Chat pane (left, ~55%)        │  Artifact Viewer (right, ~45%)     │
│  - message list                 │  - empty state until an artifact   │
│  - user bubble / assistant       │    exists                         │
│    bubble w/ collapsible          │  - tabs if multiple artifacts      │
│    "Sources (3)" list             │    generated in the session        │
│  - composer + send                │  - Markdown / sandboxed HTML view  │
└───────────────────────────────┴───────────────────────────────────┘
```
On narrow viewports the Artifact Viewer collapses to a slide-over panel triggered by a badge on
the message that produced it ("View artifact →"), so mobile stays single-column.

## 3. Key interaction states
- **Empty state:** short explainer + 3 example prompts (one grounded Q&A, one Ship 30 for 30, one
  artifact) so the evaluator doesn't stare at a blank box.
- **Retrieving / generating:** composer disables, an inline status line cycles
  "Searching transcripts…" → "Drafting answer…" rather than a generic spinner, since latency can be
  real (esp. local models) and users tolerate waits better when they know what's happening.
- **Grounded answer:** assistant bubble + "Sources (n)" disclosure listing guest, episode title
  (linked to YouTube), and timestamp per cited chunk.
- **No coverage:** a visually distinct (not red/error, just muted) bubble: "I couldn't find this in
  Lenny's transcripts," with a suggestion to rephrase — this is a valid, expected outcome, not a
  failure state, and should never be styled like one.
- **Artifact produced:** chat shows a compact card ("📄 Ship 30 for 30 draft — 1,240 words") that
  opens/updates the Artifact Viewer; the full content is not duplicated into the chat bubble.
- **Provider unavailable:** a dismissible banner at the top of the chat pane, not just a failed
  toast, since it affects every subsequent turn: "Ollama not reachable at localhost:11434 — start
  it and retry, or switch provider."
- **Error on a single turn:** inline error bubble with a retry button; history above it is
  untouched (no full-page error state for a single failed message).

## 4. Responsive behavior
- ≥1024px: two-pane layout as above.
- 640–1024px: panes stack with the Artifact Viewer as a bottom sheet you can expand.
- <640px: single column chat; artifacts open as a full-screen view with a back button.

## 5. Accessibility
- Semantic structure: chat log is a `role="log" aria-live="polite"` region so new assistant
  messages are announced without re-reading the whole history.
- All interactive elements (composer, send, provider switch, source disclosures, artifact tabs)
  are keyboard reachable and have visible focus states; disclosure triangles use
  `aria-expanded`.
- Color is never the only signal — the "no coverage" and "error" states differ in icon + copy, not
  just hue, for color-blind users.
- Sandboxed HTML artifacts are explicitly labeled ("Preview — sandboxed, no network access") so
  screen reader users aren't surprised by embedded interactive content.
- Minimum text contrast follows WCAG AA; composer and buttons have a minimum 44px touch target for
  mobile.

## 6. Visual design decisions
- Deliberately plain, content-forward styling (system font stack, generous line-height, restrained
  color palette: one accent color for interactive elements, neutral grays otherwise) — this is an
  internal tool for reading dense text, not a marketing surface, so typography legibility is
  prioritized over decoration.
- Citations and metadata (timestamps, provider badge) are visually de-emphasized (smaller, muted
  color) relative to the answer text itself, so the primary content stays scannable.
