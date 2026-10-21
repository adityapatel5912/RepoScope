#!/usr/bin/env python
"""
scripts/qa.py
The RepoScope QA runner.

Part III of docs/ROADMAP_V2.md, Section 18.2.

    python scripts/qa.py            # boot, wait, test, report
    python scripts/qa.py --headed   # watch it run
    python scripts/qa.py --ui       # Playwright's interactive UI
    python scripts/qa.py --grep J01 # run one journey

What it does:
    1. Starts the backend  (uvicorn on 127.0.0.1:8010, REPOSCOPE_QA=1)
    2. Starts the frontend (vite dev on 127.0.0.1:5173)
    3. Waits for /api/health == 200 and for the frontend to serve
    4. Runs the Playwright suite
    5. Writes qa-report/index.html and qa-report/results.json
    6. Exits non-zero on any failure OR any un-whitelisted console error

REPOSCOPE_QA=1 makes the backend hermetic: no GitHub calls, no LLM provider
calls, isolated state, no writes to the real data/repo_state.json. A QA run
that depends on the network fails for the wrong reason.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
BACKEND_DIR = REPO_ROOT / "backend"
QA_REPORT_DIR = REPO_ROOT / "qa-report"

BACKEND_PORT = int(os.getenv("REPOSCOPE_QA_BACKEND_PORT", "8010"))
# The QA harness uses its OWN frontend port so it never fights a developer's
# dev server on :5173. Sharing the port meant the QA run could kill (or be
# confused with) the server the developer was actually using.
FRONTEND_PORT = int(os.getenv("REPOSCOPE_QA_FRONTEND_PORT", "5183"))
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"

BOOT_TIMEOUT = 90


class Colours:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls) -> None:
        cls.RED = cls.GREEN = cls.YELLOW = cls.CYAN = cls.DIM = cls.RESET = ""


def log(message: str, colour: str = "") -> None:
    print(f"{colour}{message}{Colours.RESET}", flush=True)


def port_is_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def wait_for(url: str, timeout: int = BOOT_TIMEOUT, label: str = "") -> bool:
    """Poll a URL until it answers 2xx, or the timeout expires."""
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=4) as response:
                if 200 <= response.status < 300:
                    log(f"  ready: {label or url}", Colours.GREEN)
                    return True
                last_error = f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001 - boot polling
            last_error = str(exc)
        time.sleep(0.6)
    log(f"  TIMEOUT waiting for {label or url} ({last_error})", Colours.RED)
    return False


def pids_on_port(port: int) -> list[int]:
    """The PIDs of the processes listening on a TCP port."""
    try:
        import psutil
    except ImportError:
        return []

    pids: list[int] = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and getattr(conn.laddr, "port", None) == port and conn.pid:
                pids.append(int(conn.pid))
    except Exception:  # noqa: BLE001 - needs elevation on some systems
        # Fall back to netstat, which does not.
        try:
            output = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=20
            ).stdout
            for line in output.splitlines():
                if f":{port}" in line and "LISTENING" in line.upper():
                    parts = line.split()
                    if parts and parts[-1].isdigit():
                        pids.append(int(parts[-1]))
        except Exception:  # noqa: BLE001
            return []
    return sorted(set(pids))


def free_port(port: int) -> None:
    """
    Make sure a port is free, taking it from whatever is holding it.

    **This is the difference between a gate and a decoration.** The
    harness used to reuse any server it found on :8010. That sounds
    convenient and is actually dangerous: the backend IS the thing under
    test, so a QA run against a server somebody started an hour ago
    tests an hour-old build. It can be green while the code on disk is
    broken — and the failure then shows up as "the suite passed but the
    feature is broken", which is the worst possible outcome.

    So the harness always starts its own servers, and takes the ports
    from whatever was there. :8010 and :5183 belong to the harness.
    """
    if not port_is_open(port):
        return

    pids = pids_on_port(port)
    if not pids:
        log(
            f"  port :{port} is in use but its owner could not be found — "
            "close it and re-run",
            Colours.YELLOW,
        )
        return

    log(f"  port :{port} is in use — stopping the process that owns it", Colours.YELLOW)
    for pid in pids:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, timeout=30,
            )
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:  # noqa: BLE001
                pass

    for _ in range(20):
        if not port_is_open(port):
            return
        time.sleep(0.25)


def start_backend() -> subprocess.Popen | None:
    free_port(BACKEND_PORT)
    env = dict(os.environ)
    env["REPOSCOPE_QA"] = "1"
    env["PYTHONPATH"] = str(BACKEND_DIR)
    log(f"  starting backend on :{BACKEND_PORT}", Colours.CYAN)
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(BACKEND_PORT),
         "--log-level", "warning"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_frontend() -> subprocess.Popen | None:
    free_port(FRONTEND_PORT)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    env = dict(os.environ)
    # The Vite dev server proxies /api to :8000 by default. Point it at the
    # QA backend so the journey exercises the hermetic instance.
    env["REPOSCOPE_QA_BACKEND_URL"] = BACKEND_URL
    log(f"  starting frontend on :{FRONTEND_PORT}", Colours.CYAN)
    return subprocess.Popen(
        [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(FRONTEND_PORT)],
        cwd=str(FRONTEND_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop(process: subprocess.Popen | None) -> None:
    """
    Stop a server AND everything it spawned.

    `npm run dev` spawns Vite as a CHILD process. Killing npm alone leaves
    the child running — a Vite server stays bound to :5173, still proxying
    /api to the QA backend on :8010. When the QA run ends and :8010 goes
    away, that orphaned Vite turns every API call into a bare 500
    "Internal Server Error" for whoever opens the app next.

    So the whole process TREE has to go.
    """
    if process is None:
        return

    if os.name == "nt":
        # taskkill /T kills the process tree.
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=30,
            )
        except Exception:  # noqa: BLE001 - best effort
            pass
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except Exception:  # noqa: BLE001
            pass

    try:
        process.wait(timeout=8)
    except Exception:  # noqa: BLE001
        try:
            process.kill()
        except Exception:  # noqa: BLE001
            pass

    # Give the OS a moment to release the port.
    time.sleep(0.4)


def run_playwright(extra_args: list[str]) -> int:
    npx = "npx.cmd" if os.name == "nt" else "npx"
    command = [
        npx, "playwright", "test",
        "--config", str(FRONTEND_DIR / "playwright.config.ts"),
        *extra_args,
    ]
    log(f"  $ {' '.join(command)}", Colours.DIM)
    return subprocess.call(command, cwd=str(FRONTEND_DIR))


def build_report(exit_code: int) -> None:
    """Write a small standalone HTML report beside the Playwright output."""
    QA_REPORT_DIR.mkdir(parents=True, exist_ok=True)

    results_path = QA_REPORT_DIR / "results.json"
    tests: list[dict] = []
    if results_path.exists():
        try:
            raw = json.loads(results_path.read_text(encoding="utf-8"))
            for suite in raw.get("suites", []):
                for spec in suite.get("specs", []):
                    for test_case in spec.get("tests", []):
                        tests.append({
                            "title": spec.get("title", "?"),
                            "status": test_case.get("status", "unknown"),
                            "duration_ms": test_case.get("results", [{}])[0].get("duration", 0)
                            if test_case.get("results") else 0,
                        })
        except (json.JSONDecodeError, OSError, IndexError, TypeError):
            tests = []

    passed = sum(1 for t in tests if t["status"] == "expected")
    failed = sum(1 for t in tests if t["status"] == "unexpected")

    rows = "\n".join(
        f"<tr><td>{'PASS' if t['status'] == 'expected' else 'FAIL'}</td>"
        f"<td>{t['title']}</td><td>{t['duration_ms']} ms</td></tr>"
        for t in tests
    )
    verdict = (
        "ALL JOURNEYS PASSED" if exit_code == 0 and not failed
        else f"FAILURES DETECTED ({failed})"
    )
    colour = "#16a34a" if exit_code == 0 and not failed else "#dc2626"

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>RepoScope QA Report</title>
<style>
  body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem;
         background: #0f1117; color: #e6e6e6; }}
  h1 {{ font-size: 1.4rem; margin-bottom: .25rem; }}
  .verdict {{ display:inline-block; padding:.4rem .8rem; border-radius:.4rem;
              background:{colour}; color:#fff; font-weight:700; margin:.5rem 0 1rem; }}
  table {{ border-collapse: collapse; width:100%; max-width:60rem; }}
  th, td {{ text-align:left; padding:.5rem .7rem; border-bottom:1px solid #262a36; }}
  th {{ color:#9aa4b2; font-weight:600; }}
  code {{ background:#1b1f2a; padding:.1rem .35rem; border-radius:.25rem; }}
</style></head><body>
<h1>RepoScope QA Report</h1>
<p class="verdict">{verdict}</p>
<p>{passed} passed &middot; {failed} failed &middot; {len(tests)} total</p>
<table><thead><tr><th>Status</th><th>Journey</th><th>Duration</th></tr></thead>
<tbody>{rows}</tbody></table>
<p><small>Screenshots: <code>docs/screenshots/v2/</code> &middot;
Full Playwright report: <code>qa-report/html/index.html</code></small></p>
</body></html>"""

    (QA_REPORT_DIR / "index.html").write_text(html, encoding="utf-8")
    log(f"  report: {QA_REPORT_DIR / 'index.html'}", Colours.DIM)


def main() -> int:
    parser = argparse.ArgumentParser(description="RepoScope QA runner")
    parser.add_argument("--headed", action="store_true", help="run with a visible browser")
    parser.add_argument("--ui", action="store_true", help="open Playwright's UI mode")
    parser.add_argument("--grep", default=None, help="only run journeys matching this pattern")
    parser.add_argument("--no-server", action="store_true", help="assume servers are already running")
    args = parser.parse_args()

    if os.name != "nt" and not sys.stdout.isatty():
        Colours.disable()

    log("RepoScope QA", Colours.CYAN)
    backend = frontend = None
    exit_code = 1
    try:
        if not args.no_server:
            log("booting servers", Colours.CYAN)
            backend = start_backend()
            frontend = start_frontend()
            if not wait_for(f"{BACKEND_URL}/api/health", label="backend /api/health"):
                return 1
            if not wait_for(FRONTEND_URL, label="frontend"):
                return 1
        else:
            if not wait_for(f"{BACKEND_URL}/api/health", timeout=15, label="backend /api/health"):
                return 1

        log("running journeys", Colours.CYAN)
        extra: list[str] = []
        if args.headed:
            extra.append("--headed")
        if args.ui:
            extra.append("--ui")
        if args.grep:
            extra.extend(["--grep", args.grep])
        exit_code = run_playwright(extra)

        if exit_code == 0:
            log("ALL JOURNEYS PASSED", Colours.GREEN)
        else:
            log(f"FAILURES — playwright exit code {exit_code}", Colours.RED)
    except KeyboardInterrupt:
        log("interrupted", Colours.YELLOW)
        exit_code = 130
    finally:
        stop(frontend)
        stop(backend)
        build_report(exit_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
