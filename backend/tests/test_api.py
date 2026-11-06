def test_health_rules_only(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["llm_enabled"] is False


def test_unsupported_file(client):
    r = client.post("/api/upload", files={"file": ("x.exe", b"abc")})
    assert r.status_code == 415


def test_upload_all_formats(loaded):
    docs = loaded.get("/api/documents").json()
    assert {d["kind"] for d in docs} == {"csv", "xlsx", "text", "pdf"}
    assert sum(d["rows_parsed"] for d in docs) == 105 + 5 + 4 + 5


def test_handover_report_night(loaded):
    r = loaded.get("/api/report", params={"date": "2026-11-02", "shift": "night"}).json()
    assert r["incoming_shift"] == "morning" and r["facts"]["status"] == "attention"
    acts = [a["action"] for a in r["actions"]]
    assert any("M-102" in a and "Maintenance" in a for a in acts)
    assert any("QA" in a and "M-104" in a for a in acts)
    assert r["actions"][0]["priority"] == "high"
    assert r["summary_source"] == "rules"
    # all numbers quoted in the summary exist in the facts
    assert "210" in r["summary"] or "240" in r["summary"]


def test_missing_report_detected_evening(loaded):
    r = loaded.get("/api/report", params={"date": "2026-11-02", "shift": "evening"}).json()
    assert any(m["machine"] == "M-105" for m in r["facts"]["missing_reports"])
    assert any("M-105" in a["action"] and "missing" in a["action"] for a in r["actions"])


def test_missing_report_only_shown_for_its_own_shift(loaded):
    # regression: M-105 is missing in the evening, but did report at night
    r = loaded.get("/api/report", params={"date": "2026-11-02", "shift": "night"}).json()
    assert r["facts"]["missing_reports"] == []
    assert "Missing reports" not in r["summary"]


def test_routine_changeover_is_not_a_repeat_failure(loaded):
    an = loaded.get("/api/anomalies").json()
    assert not any(a["rule"] == "repeat_failure" and a["machine"] == "M-101" for a in an)


def test_m102_maintenance_leads_the_night_handover(loaded):
    # regression: acceptance check in docs/Final directive.md
    r = loaded.get("/api/report", params={"date": "2026-11-02", "shift": "night"}).json()
    assert r["actions"][0]["machine"] == "M-102" and r["actions"][0]["priority"] == "high"
    assert "Maintenance" in r["actions"][0]["action"]


def test_anomalies_listing_and_data_error(loaded):
    an = loaded.get("/api/anomalies", params={"severity": "critical"}).json()
    assert any(a["rule"] == "impossible_downtime" and a["machine"] == "M-103" for a in an)
    assert any(a["rule"] == "repeat_failure" and a["machine"] == "M-102" for a in an)


def test_ask_cites_sources(loaded):
    r = loaded.post("/api/ask", json={"question": "Why was M-102 down in the last week?"}).json()
    assert r["sources"] and all(s["record_id"] and s["ref"] for s in r["sources"])
    assert "Motor overheating" in r["answer"]
    assert r["filters"]["machines"] == ["M-102"]


def test_ask_no_match(loaded):
    r = loaded.post("/api/ask", json={"question": "anything on machine Z-999 on 2020-01-01"}).json()
    assert r["sources"] == []


def test_toggle_action(loaded):
    rep = loaded.get("/api/report", params={"date": "2026-11-02", "shift": "night"}).json()
    aid = rep["actions"][0]["id"]
    assert loaded.patch(f"/api/actions/{aid}", json={"done": True}).json()["done"] is True
    assert loaded.patch("/api/actions/99999", json={"done": True}).status_code == 404


def test_trends_and_reset(loaded):
    t = loaded.get("/api/trends").json()
    assert len(t) == 8
    loaded.delete("/api/data")
    assert loaded.get("/api/shifts").json() == []
