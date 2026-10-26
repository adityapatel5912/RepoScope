"""
test_feature_4_security.py
POST /api/security/scan — Breaking Change + Secret + CVE detectors
(pure-function unit tests + endpoint integration on a temp clone).
"""
import pytest
from fastapi.testclient import TestClient

import main
from security_scanner import (
    check_dependency_cves, detect_breaking_commit, detect_breaking_in_patch,
    detect_major_bump, scan_file_for_env_leak, scan_pr_patch,
    scan_repo_files, scan_text_for_secrets,
)


@pytest.fixture()
def client():
    return TestClient(main.app)


# ── SECRET detectors ─────────────────────────────────────────────────────────

def test_detects_aws_key():
    flags = scan_text_for_secrets('key = "AKIAIOSFODNN7EXAMPLE"\n', "config.py")
    assert any(f["severity"] == "critical" and f["type"] == "SECRET" for f in flags)
    assert flags[0]["detail"].startswith("AWS access key")
    assert "AKIA" in flags[0]["detail"]  # redacted prefix helps locating


def test_detects_github_pat_and_generic_assignment():
    flags = scan_text_for_secrets(
        'token = "ghp_' + "A" * 36 + '"\napi_key = "s3cr3t_value_12345"\n',
        "settings.py",
    )
    types = {f["detail"].split(" (")[0] for f in flags}
    assert any("GitHub personal access token" in t for t in types)
    assert any("Hardcoded credential" in t for t in types)


def test_skips_placeholder_assignments():
    flags = scan_text_for_secrets('api_key = "your-api-key-here"\n', "a.py")
    assert flags == []


def test_env_leak_detection():
    assert scan_file_for_env_leak(".env")
    assert scan_file_for_env_leak("backend/.env.production")
    assert not scan_file_for_env_leak(".env.example")  # template is fine
    assert not scan_file_for_env_leak("src/env.py")


def test_no_false_positive_on_clean_code():
    assert scan_text_for_secrets("x = os.getenv('API_KEY')\n", "a.py") == []


# ── BREAKING detectors ───────────────────────────────────────────────────────

def test_signature_change_python():
    patch = (
        "-def process_payment(amount, currency):\n"
        "+def process_payment(amount, currency, user_id):\n"
    )
    flags = detect_breaking_in_patch(patch, "payments.py")
    assert len(flags) == 1
    assert flags[0]["type"] == "BREAKING"
    assert "signature changed" in flags[0]["detail"]


def test_removed_function():
    patch = "-def legacy_hook():\n"
    flags = detect_breaking_in_patch(patch, "legacy.py")
    assert flags and "was removed" in flags[0]["detail"]


def test_non_breaking_same_signature():
    patch = (
        "-def helper(a, b):\n"
        "+def helper(a, b):\n"
    )
    assert detect_breaking_in_patch(patch, "m.py") == []


def test_major_bump_detection():
    patch = '-  "version": "1.4.2",\n+  "version": "2.0.0",\n'
    flags = detect_major_bump(patch, "package.json")
    assert flags and "major bump" in flags[0]["detail"]
    # minor bump is not breaking
    assert detect_major_bump('-  "version": "1.4.2"\n+  "version": "1.5.0"\n',
                            "package.json") == []
    # unrelated files ignored
    assert detect_major_bump(patch, "README.md") == []


def test_breaking_commit_message():
    flags = detect_breaking_commit("feat!: drop v1 API", "abc123def")
    assert flags and flags[0]["type"] == "BREAKING"
    assert detect_breaking_commit("fix: typo", "abc123def") == []


# ── CVE detector ─────────────────────────────────────────────────────────────

def test_cve_in_requirements():
    flags = check_dependency_cves("requests==2.25.0\nflask==2.0.0\n", "requirements.txt")
    details = " ".join(f["detail"] for f in flags)
    assert "CVE-2023-32681" in details
    assert "CVE-2023-30861" in details


def test_cve_in_package_json():
    content = '{"dependencies": {"lodash": "^4.17.0", "axios": "0.21.0"}}'
    flags = check_dependency_cves(content, "package.json")
    details = " ".join(f["detail"] for f in flags)
    assert "CVE-2021-23337" in details
    assert "CVE-2021-3749" in details


def test_cve_clean_when_patched():
    assert check_dependency_cves("requests==2.31.0\n", "requirements.txt") == []


# ── Repo + PR integration ────────────────────────────────────────────────────

def test_scan_repo_files_finds_committed_secrets(tmp_path):
    (tmp_path / ".env").write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text('password = "super_secret_123"\n')
    (tmp_path / "requirements.txt").write_text("requests==2.25.0\n")
    flags = scan_repo_files(str(tmp_path))
    assert any(f["severity"] == "critical" for f in flags)          # .env + AKIA
    assert any(f["type"] == "CVE" for f in flags)                    # requests pin
    assert all("Nord" in f["suggestion"] or "NordPass" in f["suggestion"]
               for f in flags if f["type"] == "SECRET")              # sponsor angle


def test_scan_pr_patch_full_pipeline():
    pr_files = [{
        "filename": "pkg/package.json",
        "patch": '+  "version": "3.0.0",\n-  "version": "2.1.0",\n+token = "ghp_' + "B" * 36 + '"',
        "additions": 2, "deletions": 1,
    }]
    flags = scan_pr_patch(pr_files)
    kinds = {f["type"] for f in flags}
    assert "BREAKING" in kinds and "SECRET" in kinds


def test_security_scan_endpoint(client, tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("TOKEN=ghp_" + "C" * 36 + "\n")
    state = {"repo": "octo/tiny", "local_path": str(tmp_path), "readme": "# x"}
    monkeypatch.setattr(main, "load_state", lambda: state)
    async def fake_gh(owner, name, since=None, user_token=None):
        return {"commits": [], "pulls": [], "issues": [], "releases": []}
    monkeypatch.setattr(main, "query_github", fake_gh)

    res = client.post("/api/security/scan", json={})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    assert data["repo"] == "octo/tiny"
    assert data["summary"]["SECRET"] >= 1
    assert data["flags"][0]["severity"] in ("critical", "high")  # sorted worst-first


def test_security_scan_requires_repo(client, monkeypatch):
    monkeypatch.setattr(main, "load_state", lambda: {"repo": None, "local_path": None})
    res = client.post("/api/security/scan", json={})
    assert res.status_code == 400
