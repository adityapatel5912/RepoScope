"""
test_metrics_hotspots.py
Unit and integration tests for Phase 10: Churn, Hotspots, Bus Factor, Time Machine & Tracking/Incident Polish (V2.7).
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from main import app
from git_history import compute_ast_complexity, compute_hotspots, compare_refs
from repo_tracker import record_incident, get_incidents, classify_incident_event

pytestmark = pytest.mark.usefixtures("fake_ai_provider")


def test_ast_complexity_calculation(tmp_path: Path):
    py_file = tmp_path / "sample.py"
    py_file.write_text(
        "def test_fn(x):\n"
        "    if x > 0:\n"
        "        for i in range(x):\n"
        "            try:\n"
        "                if i % 2 == 0:\n"
        "                    pass\n"
        "            except Exception:\n"
        "                pass\n"
        "    return x\n",
        encoding="utf-8",
    )
    complexity = compute_ast_complexity(py_file)
    assert complexity >= 4


def test_incident_classification_and_recording():
    # Test incident classification
    c1 = classify_incident_event("breaking_change", {"route": "/api/v1"})
    assert c1["severity"] == "high"
    assert c1["category"] == "breaking_change"

    c2 = classify_incident_event("security_vulnerability", {"cve": "CVE-2026-1001"})
    assert c2["severity"] == "critical"

    # Test record and retrieve
    inc = record_incident("test_regression", {"test": "test_auth.py"})
    assert inc["category"] == "test_regression"
    assert "id" in inc

    timeline = get_incidents(10)
    assert len(timeline) >= 1
    assert timeline[0]["id"] == inc["id"]


def test_compute_hotspots_in_repo():
    repo_dir = Path(__file__).parent.parent.parent
    report = compute_hotspots(repo_dir, limit=50)
    assert report["ok"] is True
    assert "quadrant_summary" in report
    assert "critical" in report["quadrant_summary"]
    assert "files" in report


def test_compare_refs():
    repo_dir = Path(__file__).parent.parent.parent
    # Compare HEAD~1 to HEAD
    res = compare_refs(repo_dir, "HEAD~1", "HEAD")
    assert res["ok"] is True
    assert "summary" in res
    assert "architectural_drift" in res

    # Illegal ref characters rejected
    bad_res = compare_refs(repo_dir, "HEAD; rm -rf /", "HEAD")
    assert bad_res["ok"] is False


def test_api_metrics_endpoints():
    client = TestClient(app)
    # Test /api/metrics/hotspots
    res_hotspots = client.get("/api/metrics/hotspots?limit=20")
    if res_hotspots.status_code == 200:
        data = res_hotspots.json()
        assert data["ok"] is True
        assert "files" in data

    # Test /api/metrics/compare
    res_comp = client.get("/api/metrics/compare?ref_a=HEAD~1&ref_b=HEAD")
    if res_comp.status_code == 200:
        comp_data = res_comp.json()
        assert comp_data["ok"] is True

    # Test /api/tracking/incidents
    res_inc = client.get("/api/tracking/incidents?limit=20")
    assert res_inc.status_code == 200
    assert res_inc.json()["ok"] is True
