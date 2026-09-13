const API_BASE = window.LGA_API_BASE || "http://localhost:8000";

const md = window.markdownit({ html: false, linkify: true, breaks: true });

const els = {
  chatLog: document.getElementById("chatLog"),
  emptyState: document.getElementById("emptyState"),
  composerForm: document.getElementById("composerForm"),
  composerInput: document.getElementById("composerInput"),
  sendBtn: document.getElementById("sendBtn"),
  newSessionBtn: document.getElementById("newSessionBtn"),
  providerBadge: document.getElementById("providerBadge"),
  providerDot: document.getElementById("providerDot"),
  providerLabel: document.getElementById("providerLabel"),
  providerBanner: document.getElementById("providerBanner"),
  artifactEmpty: document.getElementById("artifactEmpty"),
  artifactContent: document.getElementById("artifactContent"),
  artifactTabs: document.getElementById("artifactTabs"),
  artifactBody: document.getElementById("artifactBody"),
};

let sessionId = null;
const artifacts = []; // { id, kind, title, content }

// ---------------------------------------------------------------------
// Session lifecycle
// ---------------------------------------------------------------------
async function startNewSession() {
  els.chatLog.innerHTML = "";
  els.chatLog.appendChild(els.emptyState);
  els.emptyState.classList.remove("hidden");
  artifacts.length = 0;
  renderArtifactTabs();
  showArtifactEmpty();

  const resp = await fetch(`${API_BASE}/sessions`, { method: "POST" });
  const body = await resp.json();
  sessionId = body.session_id;
}

// ---------------------------------------------------------------------
// Provider status
// ---------------------------------------------------------------------
async function refreshProviderStatus() {
  try {
    const resp = await fetch(`${API_BASE}/config`);
    const cfg = await resp.json();
    els.providerLabel.textContent = cfg.active_provider;
    const active = cfg.available_providers.includes(cfg.active_provider);
    els.providerDot.className = "dot " + (active ? "ok" : "down");
    if (!active) {
      const hint =
        cfg.active_provider === "ollama"
          ? "Ollama is not reachable. Start it locally (`ollama serve`) and ensure the model is pulled."
          : "Anthropic is not configured. Set ANTHROPIC_API_KEY.";
      showBanner(`Active provider "${cfg.active_provider}" is unavailable. ${hint}`);
    } else {
      hideBanner();
    }
  } catch (e) {
    els.providerLabel.textContent = "unreachable";
    els.providerDot.className = "dot down";
    showBanner("Cannot reach the backend API. Is it running?");
  }
}

function showBanner(text) {
  els.providerBanner.textContent = text;
  els.providerBanner.classList.remove("hidden");
}
function hideBanner() {
  els.providerBanner.classList.add("hidden");
}

// ---------------------------------------------------------------------
// Chat rendering
// ---------------------------------------------------------------------
function scrollToBottom() {
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

function addUserMessage(text) {
  els.emptyState.classList.add("hidden");
  const el = document.createElement("div");
  el.className = "msg user";
  el.innerHTML = `<div class="msg-role">You</div><div class="msg-bubble"></div>`;
  el.querySelector(".msg-bubble").textContent = text;
  els.chatLog.appendChild(el);
  scrollToBottom();
}

function addPendingMessage() {
  const el = document.createElement("div");
  el.className = "msg assistant pending";
  el.innerHTML = `<div class="msg-role">Assistant</div><div class="msg-bubble">Searching transcripts…</div>`;
  els.chatLog.appendChild(el);
  scrollToBottom();
  return el;
}

function renderAssistantMessage(el, data) {
  el.classList.remove("pending");
  const noCoverage = /couldn't find this in lenny's transcripts/i.test(data.content);
  if (noCoverage) el.classList.add("no-coverage");

  const bubble = el.querySelector(".msg-bubble");
  bubble.textContent = data.content;

  if (data.citations && data.citations.length) {
    const details = document.createElement("details");
    details.className = "sources";
    const summary = document.createElement("summary");
    summary.textContent = `Sources (${data.citations.length})`;
    details.appendChild(summary);
    data.citations.forEach((c) => {
      const item = document.createElement("div");
      item.className = "source-item";
      item.innerHTML = `<div><a href="${c.youtube_url}" target="_blank" rel="noopener">${escapeHtml(
        c.guest
      )} — ${escapeHtml(c.title)}</a></div>
        <div class="source-meta">${escapeHtml(c.start_timestamp)}</div>`;
      details.appendChild(item);
    });
    el.appendChild(details);
  }

  if (data.artifact_id) {
    fetchAndAttachArtifact(el, data.artifact_id);
  }

  scrollToBottom();
}

function renderErrorMessage(el, message) {
  el.classList.remove("pending");
  el.classList.add("error");
  el.querySelector(".msg-bubble").textContent = message;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

// ---------------------------------------------------------------------
// Artifact viewer
// ---------------------------------------------------------------------
function showArtifactEmpty() {
  els.artifactEmpty.classList.remove("hidden");
  els.artifactContent.classList.add("hidden");
}
function showArtifactContent() {
  els.artifactEmpty.classList.add("hidden");
  els.artifactContent.classList.remove("hidden");
}

async function fetchAndAttachArtifact(msgEl, artifactId) {
  const resp = await fetch(`${API_BASE}/artifacts/${artifactId}`);
  if (!resp.ok) return;
  const artifact = await resp.json();
  artifacts.push(artifact);

  const card = document.createElement("div");
  card.className = "artifact-card";
  card.innerHTML = `📄 <span>${escapeHtml(artifact.title)} (${artifact.kind})</span>`;
  card.addEventListener("click", () => selectArtifact(artifact.id));
  msgEl.appendChild(card);

  renderArtifactTabs();
  selectArtifact(artifact.id);
}

function renderArtifactTabs() {
  els.artifactTabs.innerHTML = "";
  artifacts.forEach((a) => {
    const tab = document.createElement("button");
    tab.className = "artifact-tab";
    tab.dataset.id = a.id;
    tab.textContent = a.title;
    tab.addEventListener("click", () => selectArtifact(a.id));
    els.artifactTabs.appendChild(tab);
  });
}

function selectArtifact(id) {
  const artifact = artifacts.find((a) => a.id === id);
  if (!artifact) return;
  showArtifactContent();
  [...els.artifactTabs.children].forEach((t) =>
    t.classList.toggle("active", Number(t.dataset.id) === id)
  );

  els.artifactBody.innerHTML = "";
  if (artifact.kind === "html") {
    renderSandboxedHtml(artifact.content);
  } else {
    const wrap = document.createElement("div");
    wrap.className = "markdown-artifact";
    wrap.innerHTML = md.render(artifact.content);
    els.artifactBody.appendChild(wrap);
  }
}

// Security: see architecture.md §7. sandbox="allow-scripts" ONLY (no allow-same-origin,
// no allow-forms, no allow-top-navigation). Content is passed via srcdoc so it never shares
// origin with the app. A strict CSP is injected so the artifact cannot reach the network.
function renderSandboxedHtml(htmlContent) {
  const note = document.createElement("div");
  note.className = "artifact-sandbox-note";
  note.textContent = "Sandboxed preview — no cookies, no network access, isolated from the app.";
  els.artifactBody.appendChild(note);

  const iframe = document.createElement("iframe");
  iframe.setAttribute("sandbox", "allow-scripts");
  iframe.setAttribute("referrerpolicy", "no-referrer");
  const csp = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:;">`;
  iframe.srcdoc = `<!doctype html><html><head>${csp}</head><body>${htmlContent}</body></html>`;
  els.artifactBody.appendChild(iframe);
}

// ---------------------------------------------------------------------
// Composer
// ---------------------------------------------------------------------
async function sendMessage(text) {
  addUserMessage(text);
  const pendingEl = addPendingMessage();
  els.sendBtn.disabled = true;

  try {
    const resp = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: text }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      renderErrorMessage(pendingEl, (data.error && data.error.message) || "Something went wrong.");
    } else {
      renderAssistantMessage(pendingEl, data);
    }
  } catch (e) {
    renderErrorMessage(pendingEl, "Could not reach the backend API.");
  } finally {
    els.sendBtn.disabled = false;
    refreshProviderStatus();
  }
}

els.composerForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = els.composerInput.value.trim();
  if (!text || !sessionId) return;
  els.composerInput.value = "";
  els.composerInput.style.height = "auto";
  sendMessage(text);
});

els.composerInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    els.composerForm.requestSubmit();
  }
});

els.composerInput.addEventListener("input", () => {
  els.composerInput.style.height = "auto";
  els.composerInput.style.height = Math.min(els.composerInput.scrollHeight, 160) + "px";
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    els.composerInput.value = chip.dataset.example;
    els.composerForm.requestSubmit();
  });
});

els.newSessionBtn.addEventListener("click", startNewSession);

// ---------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------
startNewSession();
refreshProviderStatus();
setInterval(refreshProviderStatus, 15000);
