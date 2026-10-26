"""
test_taint.py
M9.3 — source→sink flows through assignments, calls, and returns.

The negative tests carry the weight: a scanner that flags `int(x)` as
tainted is noise, and noise gets security tooling switched off.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import main
from taint import analyze_source, scan_repository

PY_VULN = '''
import os
import subprocess
from flask import request


def handler():
    name = request.args.get("name")
    cursor.execute("SELECT * FROM users WHERE name = '" + name + "'")
    cmd = build(name)
    subprocess.run(cmd, shell=True)


def build(value):
    return "echo " + value
'''

PY_SAFE = '''
from flask import request


def handler():
    ident = int(request.args.get("id"))
    cursor.execute("SELECT * FROM users WHERE id = %s", (ident,))
'''

JS_VULN = '''
function handler(req, res) {
  const name = req.query.name;
  db.query("SELECT * FROM users WHERE name = '" + name + "'");
  document.getElementById("out").innerHTML = name;
  res.redirect(req.query.next);
}

function build(value) {
  return "<b>" + value + "</b>";
}

function render(req) {
  document.body.innerHTML = build(req.body.html);
}
'''


def _kinds(flows):
    return {(flow.source, flow.sink) for flow in flows}


def test_python_sql_and_command_flows_are_found():
    flows = analyze_source(PY_VULN, "app.py")
    kinds = _kinds(flows)
    assert ("request.args", "execute") in kinds
    assert ("request.args", "subprocess.run") in kinds


def test_return_value_propagates_between_functions():
    flows = analyze_source(PY_VULN, "app.py")
    # `build(name)` returns tainted data; the sink is in handler.
    assert any(
        flow.sink == "subprocess.run" and flow.source == "request.args"
        for flow in flows
    )


def test_sanitizer_breaks_the_flow():
    flows = analyze_source(PY_SAFE, "safe.py")
    assert flows == []


def test_javascript_dom_sql_and_redirect_flows_are_found():
    flows = analyze_source(JS_VULN, "app.ts")
    sinks = {flow.sink for flow in flows}
    assert {"query", "innerHTML", "redirect"} <= sinks
    # render() receives the taint through build()'s return.
    assert any(flow.sink == "innerHTML" and flow.source == "req.body" for flow in flows)


def test_flow_has_actionable_location_and_via_chain():
    flows = analyze_source(PY_VULN, "app.py")
    sql = next(flow for flow in flows if flow.sink == "execute")
    assert sql.file == "app.py"
    assert sql.source_line == 8
    assert sql.sink_line == 9
    assert "name" in sql.via
    flag = sql.to_flag()
    assert flag["type"] == "TAINT"
    assert flag["severity"] == "high"


def test_scan_repository_skips_build_directories(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(PY_VULN, encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "bad.py").write_text(PY_VULN, encoding="utf-8")

    flags = scan_repository(tmp_path)
    files = {flag["file"] for flag in flags}
    assert "src/app.py" in files
    assert not any(path.startswith("node_modules/") for path in files)


def test_taint_endpoint_returns_flows(monkeypatch, tmp_path):
    state = {"repo": "octo/tiny", "local_path": str(tmp_path)}
    monkeypatch.setattr(main, "load_state", lambda: state)
    client = TestClient(main.app)

    res = client.post("/api/security/taint")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["summary"]["flows"] == 0


def test_taint_endpoint_requires_a_loaded_repo(monkeypatch):
    monkeypatch.setattr(main, "load_state", lambda: {"repo": None, "local_path": None})
    client = TestClient(main.app)
    res = client.post("/api/security/taint")
    assert res.status_code == 400
