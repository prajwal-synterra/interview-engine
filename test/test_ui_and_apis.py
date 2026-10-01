"""
Test Suite for UI Multi-Page Views and REST APIs.
Validates:
1. Multi-page HTML view endpoints (/, /telemetry, /reports, /logs, /architecture).
2. Static assets (/static/css/dashboard.css, /static/js/dashboard.js).
3. Telemetry, Database, Vector, Reports, and Logs REST endpoints.
"""

import requests

BASE_URL = "http://127.0.0.1:8000"


def test_html_pages_render():
    """Verify all 5 multi-page views return 200 and proper HTML content."""
    pages = ["/", "/telemetry", "/reports", "/logs", "/architecture"]
    for path in pages:
        res = requests.get(f"{BASE_URL}{path}", timeout=5)
        assert res.status_code == 200, f"Page {path} returned status {res.status_code}"
        assert "<!DOCTYPE html>" in res.text, f"Page {path} missing DOCTYPE"
        assert "Socratic AI" in res.text, f"Page {path} missing brand text"
    print("All 5 multi-page HTML views rendered successfully!")


def test_static_assets_serve():
    """Verify CSS design system and JavaScript utilities are served correctly."""
    css_res = requests.get(f"{BASE_URL}/static/css/dashboard.css", timeout=5)
    assert css_res.status_code == 200
    assert "--bg-app" in css_res.text

    js_res = requests.get(f"{BASE_URL}/static/js/dashboard.js", timeout=5)
    assert js_res.status_code == 200
    assert "showToast" in js_res.text
    print("Static assets served successfully!")


def test_rest_api_db_overview():
    """Verify PostgreSQL overview stats endpoint."""
    res = requests.get(f"{BASE_URL}/api/db/overview", timeout=5)
    assert res.status_code == 200
    data = res.json()
    assert "sessions_count" in data
    assert "compacted_cards_count" in data
    assert "turn_logs_count" in data
    assert "final_reports_count" in data
    assert data["status"] == "ONLINE"
    print(f"DB Overview verified: {data}")


def test_rest_api_vector_endpoints():
    """Verify Dynoxide status, pillar catalogue, and semantic matching endpoint."""
    status_res = requests.get(f"{BASE_URL}/api/vector/status", timeout=5)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["provider"] == "Dynoxide (Local DynamoDB Vector)"

    pillars_res = requests.get(f"{BASE_URL}/api/vector/pillars", timeout=5)
    assert pillars_res.status_code == 200
    pillars_data = pillars_res.json()
    assert len(pillars_data["pillars"]) >= 8

    # Test semantic match
    match_res = requests.post(
        f"{BASE_URL}/api/vector/test-match",
        json={"text": "I designed high-throughput distributed caching in Redis and real-time WebSockets"},
        timeout=10
    )
    assert match_res.status_code == 200
    matches = match_res.json().get("matches", [])
    assert len(matches) > 0
    print(f"Vector search matched: {[m['name'] for m in matches]}")


def test_rest_api_reports_and_logs():
    """Verify reports archive and live log streaming endpoints."""
    rep_res = requests.get(f"{BASE_URL}/api/reports", timeout=5)
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert "reports" in rep_data

    logs_res = requests.get(f"{BASE_URL}/api/logs", timeout=5)
    assert logs_res.status_code == 200
    logs_data = logs_res.json()
    assert "lines" in logs_data
    assert len(logs_data["lines"]) > 0
    print(f"Reports ({len(rep_data['reports'])}) and Logs ({len(logs_data['lines'])}) verified!")


if __name__ == "__main__":
    test_html_pages_render()
    test_static_assets_serve()
    test_rest_api_db_overview()
    test_rest_api_vector_endpoints()
    test_rest_api_reports_and_logs()
    print("ALL API AND UI TESTS PASSED!")
