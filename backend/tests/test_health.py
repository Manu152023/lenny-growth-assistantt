def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_reports_index_populated(client):
    resp = client.get("/health/ready")
    body = resp.json()
    assert body["checks"]["index_populated"] is True
    assert body["checks"]["database"] is True
    # No LLM provider is reachable in the test sandbox -> readiness should say so, not crash.
    assert "llm_provider_reachable" in body["checks"]
