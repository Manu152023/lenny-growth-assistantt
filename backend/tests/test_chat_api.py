from unittest.mock import patch


def _patched(fake_provider):
    return patch("app.routers.chat.get_provider", return_value=fake_provider)


def test_create_session_returns_id(client):
    resp = client.post("/sessions")
    assert resp.status_code == 201
    body = resp.json()
    assert "session_id" in body


def test_grounded_question_returns_citations(client, fake_provider):
    sid = client.post("/sessions").json()["session_id"]
    with _patched(fake_provider):
        resp = client.post(
            f"/sessions/{sid}/messages",
            json={"content": "What does the podcast say about onboarding activation?"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tool_used"] == "chat"
    assert body["citations"], "expected at least one citation for a covered topic"
    assert body["citations"][0]["guest"] == "Ada Chen Rekhi"


def test_uncovered_question_abstains_without_fabricating_citation(client, fake_provider):
    sid = client.post("/sessions").json()["session_id"]
    with _patched(fake_provider):
        resp = client.post(
            f"/sessions/{sid}/messages",
            json={"content": "zzqqxxnonexistenttoken12345 supply chain logistics"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "couldn't find" in body["content"].lower()
    assert not body["citations"]


def test_ship30_trigger_creates_markdown_artifact_near_target_length(client, fake_provider):
    sid = client.post("/sessions").json()["session_id"]
    with _patched(fake_provider):
        resp = client.post(
            f"/sessions/{sid}/messages",
            json={"content": "Turn our discussion on onboarding into a Ship 30 for 30 essay"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tool_used"] == "ship30_essay"
    assert body["artifact_id"] is not None

    artifact = client.get(f"/artifacts/{body['artifact_id']}").json()
    assert artifact["kind"] == "markdown"
    word_count = len(artifact["content"].split())
    assert 1000 <= word_count <= 1500


def test_artifact_trigger_creates_artifact_with_expected_shape(client, fake_provider):
    sid = client.post("/sessions").json()["session_id"]
    with _patched(fake_provider):
        resp = client.post(
            f"/sessions/{sid}/messages",
            json={"content": "Make this into a one-pager document"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tool_used"] == "artifact"
    artifact = client.get(f"/artifacts/{body['artifact_id']}").json()
    assert artifact["title"] == "Test Doc"
    assert artifact["kind"] == "markdown"


def test_session_history_persists_across_turns(client, fake_provider):
    sid = client.post("/sessions").json()["session_id"]
    with _patched(fake_provider):
        client.post(f"/sessions/{sid}/messages", json={"content": "Tell me about onboarding"})
        client.post(f"/sessions/{sid}/messages", json={"content": "Say more about that"})
    history = client.get(f"/sessions/{sid}").json()
    assert len(history["messages"]) == 4  # 2 user + 2 assistant
    assert history["messages"][0]["role"] == "user"
    assert history["messages"][1]["role"] == "assistant"


def test_message_to_unknown_session_returns_404(client, fake_provider):
    with _patched(fake_provider):
        resp = client.post("/sessions/does-not-exist/messages", json={"content": "hi"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_empty_message_content_is_rejected(client):
    sid = client.post("/sessions").json()["session_id"]
    resp = client.post(f"/sessions/{sid}/messages", json={"content": ""})
    assert resp.status_code == 422
