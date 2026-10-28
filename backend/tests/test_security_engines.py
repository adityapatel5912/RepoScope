"""
test_security_engines.py
Phase 13: Six-Engine Graph-Contextual Security Suite Tests
Covers:
  - Engine 1: Cross-File Taint Propagation (source -> propagator -> sink trace)
  - Engine 2: Hardcoded Secrets & Shannon Entropy (H >= 4.2) with strict <redacted> masking
  - Engine 3: Offline Dependency CVEs
  - Engine 4: Injection Sinks (SQL, Subprocess shell=True, Code Eval, Path Traversal)
  - Engine 5: Insecure Configuration & CORS (Wildcard CORS, Disabled SSL, Debug Flags)
  - Engine 6: Permission & Authentication Bypass (State-mutating routes without auth guards)
  - Non-destructive Patch Generator with AST syntax verification
  - Standard OASIS SARIF 2.1.0 exporter
"""
import ast
import json
import pytest
from fastapi.testclient import TestClient

import main
from security_scanner import (
    check_dependency_cves,
    generate_security_patch,
    redact_secret,
    scan_for_auth_bypass,
    scan_for_injection_sinks,
    scan_for_insecure_config,
    scan_text_for_secrets,
    shannon_entropy,
)
from taint import analyze_python, scan_repository, summarize_py_source
from sarif import flags_to_sarif, to_sarif, Rule, RULES


@pytest.fixture()
def client():
    return TestClient(main.app)


# ── Engine 1: Cross-File Taint Propagation ──────────────────────────────────

def test_cross_file_taint_propagation(tmp_path):
    """File A calls helper in File B; taint travels from A to B's sink."""
    file_b = tmp_path / "utils.py"
    file_b.write_text(
        "import subprocess\n\n"
        "def run_exec(command):\n"
        "    subprocess.run(command, shell=True)\n",
        encoding="utf-8",
    )

    file_a = tmp_path / "app.py"
    file_a.write_text(
        "from flask import request\n"
        "from utils import run_exec\n\n"
        "def handler():\n"
        "    data = request.args.get('cmd')\n"
        "    run_exec(data)\n",
        encoding="utf-8",
    )

    flags = scan_repository(tmp_path)
    # Check that a cross-file flow was identified
    taint_flags = [f for f in flags if f.get("type") == "TAINT"]
    assert len(taint_flags) >= 1
    flow_flag = taint_flags[0]
    assert flow_flag["severity"] == "critical"
    assert "subprocess.run" in flow_flag["sink"]
    assert flow_flag["source"] == "request.args"
    # Verify trace structure
    trace = flow_flag.get("trace")
    assert trace is not None
    assert "source_file" in trace
    assert "sink_file" in trace
    assert "propagators" in trace


# ── Engine 2: Hardcoded Secrets & Shannon Entropy ───────────────────────────

def test_shannon_entropy_calculation():
    # Low entropy uniform/simple strings
    assert shannon_entropy("aaaaaaa") < 1.0
    assert shannon_entropy("12345") < 3.0
    # High entropy cryptographic key
    high_entropy_key = "aF9#zK2$pL9@xQ1!vB8&"
    h = shannon_entropy(high_entropy_key)
    assert h >= 4.0


def test_secrets_entropy_and_redaction():
    text = 'secret_token = "K9#xL2$vB8&pQ1!mZ5*qW7@"\n'
    flags = scan_text_for_secrets(text, "config.py")
    assert len(flags) >= 1
    f = flags[0]
    assert f["type"] == "SECRET"
    assert f["engine"] == "secrets_entropy"
    assert f["cwe"] == "CWE-798"
    assert "<redacted>" in f["detail"]
    assert "K9#xL2$vB8&pQ1!mZ5*qW7@" not in f["detail"]  # Never leak raw secret in detail!


def test_redact_secret_helper():
    assert redact_secret("short") == "<redacted>"
    redacted = redact_secret("AKIAIOSFODNN7EXAMPLE")
    assert redacted.startswith("AKIA<redacted>")
    assert "<redacted>" in redacted


# ── Engine 3: Offline Dependency CVEs ───────────────────────────────────────

def test_offline_cve_scanning():
    req_content = "cryptography==39.0.0\naiohttp==3.8.1\n"
    flags = check_dependency_cves(req_content, "requirements.txt")
    assert len(flags) >= 2
    cves = [f["detail"] for f in flags]
    assert any("CVE-2023-49083" in c for c in cves)
    assert any("CVE-2023-49081" in c for c in cves)
    assert all(f["engine"] == "dependency_cve" for f in flags)


# ── Engine 4: Injection Sinks ───────────────────────────────────────────────

def test_injection_sinks_sql_fstring():
    py_code = (
        "def query_user(user_id):\n"
        "    cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")\n"
    )
    flags = scan_for_injection_sinks(py_code, "database.py")
    assert len(flags) >= 1
    assert any(f["cwe"] == "CWE-89" and "SQL" in f["detail"] for f in flags)


def test_injection_sinks_subprocess_shell_true():
    py_code = (
        "import subprocess\n"
        "def run(user_cmd):\n"
        "    subprocess.run(user_cmd, shell=True)\n"
    )
    flags = scan_for_injection_sinks(py_code, "executor.py")
    assert len(flags) >= 1
    assert any(f["cwe"] == "CWE-78" and "shell=True" in f["detail"] for f in flags)


def test_injection_sinks_code_eval():
    py_code = (
        "def execute_dynamic(code):\n"
        "    eval(code)\n"
    )
    flags = scan_for_injection_sinks(py_code, "runner.py")
    assert len(flags) >= 1
    assert any(f["cwe"] == "CWE-95" and "eval" in f["detail"] for f in flags)


# ── Engine 5: Insecure Configuration & CORS ─────────────────────────────────

def test_insecure_config_wildcard_cors():
    code = 'app.add_middleware(CORSMiddleware, allow_origins=["*"])\n'
    flags = scan_for_insecure_config(code, "main.py")
    assert len(flags) >= 1
    assert any(f["engine"] == "insecure_config" and "CORS" in f["detail"] for f in flags)


def test_insecure_config_disabled_ssl():
    code = 'requests.get("https://internal.api", verify=False)\n'
    flags = scan_for_insecure_config(code, "client.py")
    assert len(flags) >= 1
    assert any(f["cwe"] == "CWE-295" and "verify=False" in f["detail"] for f in flags)


def test_insecure_config_debug_in_prod():
    code = "DEBUG = True\n"
    flags = scan_for_insecure_config(code, "settings.py")
    assert len(flags) >= 1
    assert any(f["cwe"] == "CWE-489" for f in flags)


# ── Engine 6: Permission & Authentication Bypass ────────────────────────────

def test_auth_bypass_mutating_route():
    code = (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n\n"
        "@app.post('/api/delete-user')\n"
        "async def delete_user(user_id: int):\n"
        "    return {'status': 'deleted'}\n"
    )
    flags = scan_for_auth_bypass(code, "routes.py")
    assert len(flags) >= 1
    f = flags[0]
    assert f["type"] == "AUTH_BYPASS"
    assert f["engine"] == "auth_bypass"
    assert f["cwe"] == "CWE-306"
    assert "delete_user" in f["detail"]


# ── Patch Generator with Syntax Verification ────────────────────────────────

def test_generate_security_patch_sql():
    code = (
        "def get_user(uid):\n"
        "    cursor.execute(f\"SELECT * FROM users WHERE id = {uid}\")\n"
    )
    res = generate_security_patch(
        file="db.py",
        line=2,
        engine="injection_sinks",
        detail="SQL query constructed with dynamic string interpolation",
        source=code,
    )
    assert res["ok"] is True
    assert res["syntax_valid"] is True
    assert "-" in res["diff"]
    assert "+" in res["diff"]
    assert "%s" in res["diff"]


def test_generate_security_patch_cors():
    code = 'app.add_middleware(CORSMiddleware, allow_origins=["*"])\n'
    res = generate_security_patch(
        file="app.py",
        line=1,
        engine="insecure_config",
        detail="Wildcard CORS origin",
        source=code,
    )
    assert res["ok"] is True
    assert res["syntax_valid"] is True
    assert "ALLOWED_ORIGINS" in res["diff"]


# ── SARIF Exporter ──────────────────────────────────────────────────────────

def test_sarif_export_schema():
    sample_flags = [
        {
            "type": "INJECTION",
            "engine": "injection_sinks",
            "cwe": "CWE-89",
            "severity": "high",
            "file": "db.py",
            "line": 15,
            "detail": "SQL Injection in execute()",
            "suggestion": "Use parameterized queries.",
        },
        {
            "type": "SECRET",
            "engine": "secrets_entropy",
            "cwe": "CWE-798",
            "severity": "critical",
            "file": "config.py",
            "line": 4,
            "detail": "High-entropy credential detected (<redacted>)",
            "suggestion": "Move to vault.",
        },
    ]
    sarif_doc = flags_to_sarif(sample_flags)
    assert sarif_doc["version"] == "2.1.0"
    assert "$schema" in sarif_doc
    assert len(sarif_doc["runs"]) == 1
    results = sarif_doc["runs"][0]["results"]
    assert len(results) == 2
    assert results[0]["ruleId"] == "reposcope/injection-sink"
    assert results[1]["ruleId"] == "reposcope/hardcoded-secret"


# ── API Endpoints Integration ───────────────────────────────────────────────

def test_api_security_patch_endpoint(client, tmp_path, monkeypatch):
    test_file = tmp_path / "app.py"
    test_file.write_text('subprocess.run(cmd, shell=True)\n', encoding="utf-8")
    monkeypatch.setattr(main, "load_state", lambda: {"repo": "test/repo", "local_path": str(tmp_path)})

    res = client.post("/api/security/patch", json={
        "file": "app.py",
        "line": 1,
        "engine": "injection_sinks",
        "detail": "shell=True command injection",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["syntax_valid"] is True
    assert "shell=False" in data["diff"]


def test_api_security_sarif_endpoint(client):
    res = client.post("/api/security/sarif", json={
        "flags": [
            {
                "type": "CONFIG",
                "engine": "insecure_config",
                "severity": "medium",
                "file": "main.py",
                "line": 10,
                "detail": "Wildcard CORS origin '*'",
            }
        ]
    })
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/sarif+json")
    sarif = res.json()
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"][0]["ruleId"] == "reposcope/insecure-configuration"
