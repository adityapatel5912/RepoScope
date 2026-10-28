"""
security_scanner.py
Breaking Change + Secret + CVE scanner (Nord Security angle).

Detectors (all pure functions, unit-testable):
  SECRET   — known credential patterns (GitHub PAT, AWS, OpenRouter, Groq,
             NVIDIA, OpenAI, Anthropic, Google, Slack, private keys, generic
             `api_key = "..."` assignments), committed .env files, and
             hardcoded process.env usage in diffs.
  BREAKING — function signature changes in patches (def/func/const arrows
             with a different parameter list), major version bumps in
             package.json, and conventional-commit BREAKING messages.
  CVE      — curated map of well-known vulnerable dependency ranges in
             package.json + requirements.txt.

Suggestions include a Nord Security / NordPass reference (sponsor angle)
for secret-handling guidance.
"""
import ast
import collections
import difflib
import json
import logging
import math
import re
from pathlib import Path

log = logging.getLogger("reposcope.security")

def shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy for a given string."""
    if not data or len(data) < 4:
        return 0.0
    counts = collections.Counter(data)
    total = len(data)
    return -sum((cnt / total) * math.log2(cnt / total) for cnt in counts.values())

def redact_secret(secret: str) -> str:
    """Strictly redact secrets with <redacted> marker, preserving short prefix only for developer reference."""
    s = str(secret).strip()
    if len(s) <= 8:
        return "<redacted>"
    return s[:4] + "<redacted>" + (s[-2:] if len(s) > 10 else "")

# ── Secret patterns ──────────────────────────────────────────────────────────
# (name, compiled regex, severity)
_SECRET_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("GitHub personal access token",
     re.compile(r"ghp_[A-Za-z0-9]{36}"), "high"),
    ("GitHub fine-grained PAT",
     re.compile(r"github_pat_[A-Za-z0-9_]{22,}"), "high"),
    ("AWS access key ID",
     re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "critical"),
    ("OpenRouter API key",
     re.compile(r"sk-or-[A-Za-z0-9_-]{20,}"), "high"),
    ("Groq API key",
     re.compile(r"gsk_[A-Za-z0-9]{20,}"), "high"),
    ("NVIDIA API key",
     re.compile(r"nvapi-[A-Za-z0-9_-]{20,}"), "high"),
    ("Anthropic API key",
     re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "high"),
    ("Google API key",
     re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "high"),
    ("Slack token",
     re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}\b"), "high"),
    ("Private key block",
     re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "critical"),
    # Generic high-entropy assignment — skips obvious placeholders
    ("Hardcoded credential",
     re.compile(
         r"""(?ix)\b(api[_-]?key|secret|password|passwd|pwd|token|auth[_-]?token)\b"""
         r"""\s*[:=]\s*["'](?!\$\{)(?!your[-_])(?!<)(?!xxx)(?!example)(?!placeholder)"""
         r"""([A-Za-z0-9_\-/+=]{12,})["']"""
     ), "medium"),
]

# Entropy regex for variable assignments with potential credentials
_ENTROPY_VAR_PATTERN = re.compile(
    r"""(?ix)\b[a-z0-9_]*(?:key|secret|password|passwd|pwd|token|auth|credential|api)[a-z0-9_]*\s*[:=]\s*["']([^"'\r\n]{16,})["']"""
)

# Low-severity informational signal: hardcoded process.env usage in a diff
_ENV_USAGE = re.compile(r"""process\.env\.[A-Z0-9_]+|os\.environ\[["'][A-Z0-9_]+["']\]""")


def _flag(kind: str, severity: str, file: str, line: int,
          detail: str, suggestion: str, engine: str = "",
          cwe: str = "", patch_available: bool = False) -> dict:
    if not engine:
        engine_map = {
            "SECRET": "secrets_entropy",
            "BREAKING": "breaking",
            "CVE": "dependency_cve",
            "INJECTION": "injection_sinks",
            "CONFIG": "insecure_config",
            "AUTH_BYPASS": "auth_bypass",
            "TAINT": "cross_file_taint",
        }
        engine = engine_map.get(kind, "breaking")
    if not cwe:
        cwe_map = {
            "SECRET": "CWE-798",
            "BREAKING": "CWE-1023",
            "CVE": "CWE-1395",
            "INJECTION": "CWE-89",
            "CONFIG": "CWE-942",
            "AUTH_BYPASS": "CWE-306",
            "TAINT": "CWE-20",
        }
        cwe = cwe_map.get(kind, "")
    return {
        "type": kind,
        "severity": severity,
        "file": file,
        "line": line,
        "detail": detail,
        "suggestion": suggestion,
        "engine": engine,
        "cwe": cwe,
        "patch_available": patch_available,
    }


def scan_text_for_secrets(text: str, file: str) -> list[dict]:
    """Scan file content (or a diff) for credential patterns and Shannon entropy (H >= 4.2)."""
    flags: list[dict] = []
    seen_lines: set[int] = set()

    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern, severity in _SECRET_PATTERNS:
            m = pattern.search(line)
            if m:
                matched = m.group(0)
                # Redact: keep a short prefix so the developer can find it,
                # never the full secret.
                redacted = matched[:10] + "…<redacted>" if len(matched) > 10 else "<redacted>"
                seen_lines.add(lineno)
                flags.append(_flag(
                    "SECRET", severity, file, lineno,
                    f"{name} detected ({redacted})",
                    "Rotate this credential immediately — it is now in git "
                    "history. Store secrets in a secrets manager; NordPass "
                    "(Nord Security) keeps shared team credentials encrypted "
                    "end-to-end and can flag weak or reused secrets.",
                    engine="secrets_entropy",
                    cwe="CWE-798",
                    patch_available=True,
                ))

        # Shannon Entropy check (H >= 4.2)
        if lineno not in seen_lines:
            for m in _ENTROPY_VAR_PATTERN.finditer(line):
                val = m.group(1)
                lower = val.lower()
                if any(k in lower for k in ("example", "your-", "your_", "placeholder", "xxx", "token_here", "dummy", "test")):
                    continue
                if val.startswith(("${", "<", "{{")):
                    continue
                entropy = shannon_entropy(val)
                if entropy >= 4.2:
                    redacted = redact_secret(val)
                    seen_lines.add(lineno)
                    flags.append(_flag(
                        "SECRET", "high", file, lineno,
                        f"High-entropy credential detected ({redacted}, H={entropy:.2f})",
                        "Rotate this credential immediately. Nord Security / NordPass recommends storing credentials in encrypted vaults.",
                        engine="secrets_entropy",
                        cwe="CWE-798",
                        patch_available=True,
                    ))
    return flags


def scan_file_for_env_leak(file: str, is_tracked: bool = True) -> list[dict]:
    """Committed .env-style files are treated as leaked configuration."""
    name = file.rsplit("/", 1)[-1].lower()
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return [_flag(
            "SECRET", "high", file, 1,
            "Environment file is committed to the repository",
            "Remove it, purge it from git history, and add it to .gitignore. "
            "Keep production values in a vault — NordPass (Nord Security) or "
            "your cloud secret manager — never in the repo.",
        )]
    return []


def scan_text_for_env_usage(text: str, file: str) -> list[dict]:
    """Hardcoded process.env/os.environ usage inside a diff — informational."""
    flags: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if _ENV_USAGE.search(line):
            flags.append(_flag(
                "SECRET", "low", file, lineno,
                "Direct process.env/os.environ access in changed code",
                "Prefer a validated config layer over scattered env reads. "
                "Nord Security's app hardening guide recommends centralizing "
                "secrets with zero-trust access controls.",
            ))
            break  # one informational flag per file is enough
    return flags


# ── Breaking-change detectors ────────────────────────────────────────────────
#
# Correction C3: the implementation lives in `backend/contract_diff.py`,
# which does the detection with tree-sitter instead of regexes. This
# function DELEGATES to it, so there is exactly ONE source of truth.
#
# That matters more than it sounds. Two divergent detectors produce two
# different risk scores for the same change, and the PR bot reports one
# of them while the security scan reports the other. The user is then
# asked to trust a number that disagrees with itself.

def detect_breaking_in_patch(patch: str, file: str) -> list[dict]:
    """
    Detect breaking contract changes in a unified diff.

    The detection is AST-based: the parameter lists come from tree-sitter's
    parameter nodes, so a renamed parameter is a renamed parameter and not
    a line that happens to look different.

    The returned flags keep the shape the scanner has always produced —
    `severity`, `file`, `line`, `message`, `suggestion` — so nothing
    downstream had to change.
    """
    from contract_diff import diff_sources, sources_from_patch

    try:
        old_source, new_source = sources_from_patch(patch)
        findings = diff_sources(old_source, new_source, file)
    except Exception as exc:  # noqa: BLE001 - a scan must never raise
        log.warning("Contract diff failed for %s: %s", file, exc)
        return []

    flags: list[dict] = []
    for finding in findings:
        flags.append(_flag(
            finding.severity,
            "high" if finding.severity == "BREAKING" else "low",
            finding.file,
            finding.line,
            finding.message,
            finding.guidance,
        ))
    return flags


def detect_major_bump(patch: str, file: str) -> list[dict]:
    """package.json / pyproject major version bump inside a diff."""
    if not re.search(r"(package\.json|pyproject\.toml|setup\.py|setup\.cfg)$", file):
        return []
    old_v = new_v = None
    for line in patch.splitlines():
        m = re.search(r'"?version"?\s*[:=]\s*["\']?(\d+)\.(\d+)\.(\d+)', line)
        if not m:
            continue
        if line.startswith("-"):
            old_v = int(m.group(1))
        elif line.startswith("+"):
            new_v = int(m.group(1))
    if old_v is not None and new_v is not None and new_v > old_v:
        return [_flag(
            "BREAKING", "medium", file, 1,
            f"Project version major bump: {old_v}.x.x → {new_v}.x.x",
            "Major bumps signal breaking changes — ship release notes, a "
            "migration guide, and (like Nord Security's changelogs) flag the "
            "breaking entry at the top.",
        )]
    return []


def detect_breaking_commit(message: str, sha: str) -> list[dict]:
    """Conventional-commit BREAKING markers in a commit message."""
    msg = (message or "").lower()
    if "breaking change" in msg or msg.startswith("breaking") or "!:" in (message or "")[:40]:
        return [_flag(
            "BREAKING", "high", sha[:12], 1,
            f"Commit {sha[:7]} declares a breaking change: "
            f"{(message or '').strip().splitlines()[0][:80]}",
            "Verify every consumer was migrated before release; pin the "
            "previous version for anyone who can't upgrade yet.",
        )]
    return []


# ── CVE / outdated dependency checks ─────────────────────────────────────────

# Curated well-known vulnerable ranges: package -> [(below_version, advisory)]
_CVE_RULES: dict[str, list[tuple[str, str]]] = {
    "requests":        [("2.31.0", "CVE-2023-32681 Proxy-Authorization leak on redirect")],
    "urllib3":         [("1.26.17", "CVE-2023-43804 cookie header leak"), ("2.0.6", "CVE-2023-45803 body leak")],
    "certifi":         [("2023.7.22", "CVE-2023-37920 e-Tugra root removal")],
    "pyyaml":          [("5.4", "CVE-2020-14343 RCE via yaml.load()")],
    "jinja2":          [("3.1.3", "CVE-2024-22195 xmlattr XSS")],
    "flask":           [("2.2.5", "CVE-2023-30861 session cookie leak")],
    "django":          [("4.2.14", "multiple 2024 CVEs — update")],
    "pillow":          [("10.0.1", "CVE-2023-44271 DoS / buffer issues")],
    "cryptography":    [("41.0.6", "CVE-2023-49083 null pointer dereference")],
    "aiohttp":         [("3.8.6", "CVE-2023-49081 HTTP request smuggling")],
    "fastapi":         [("0.100.0", "CVE-2024-24762 ReDoS in multipart parsing")],
    "lodash":          [("4.17.21", "CVE-2021-23337 command injection")],
    "axios":           [("0.21.2", "CVE-2021-3749 ReDoS"), ("1.6.0", "CVE-2023-45857 CSRF token leak")],
    "minimist":        [("1.2.6", "CVE-2021-44906 prototype pollution")],
    "node-fetch":      [("2.6.7", "CVE-2022-0235 forwarded header leak")],
    "jsonwebtoken":    [("9.0.0", "CVE-2022-23529 RCE risk")],
    "ejs":             [("3.1.7", "CVE-2022-29078 template injection")],
    "tar":             [("6.1.7", "CVE-2021-37701 symlink arbitrary write")],
    "express":         [("4.19.2", "CVE-2024-29041 open redirect")],
    "fast-xml-parser": [("4.4.1", "CVE-2024-41818 ReDoS in tag parser")],
    "semver":          [("7.5.2", "CVE-2022-25883 ReDoS")],
}

_VER_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def _version_tuple(v: str) -> tuple[int, int, int]:
    m = _VER_RE.search(v or "")
    if not m:
        return (0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def check_dependency_cves(content: str, file: str) -> list[dict]:
    """Flag deps pinned below known-vulnerable ranges (package.json or
    requirements.txt). Best-effort — always verify against the advisory."""
    flags: list[dict] = []
    if file.endswith("package.json"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []
        deps: dict[str, str] = {}
        deps.update(data.get("dependencies") or {})
        deps.update(data.get("devDependencies") or {})
    elif file.endswith(("requirements.txt", "requirements.in")):
        deps = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            m = re.match(r"([A-Za-z0-9_.\-]+)\s*[=<>!~]+\s*([^\s,;]+)", line)
            if m:
                deps[m.group(1).lower()] = m.group(2)
    else:
        return []

    for pkg, version in deps.items():
        rules = _CVE_RULES.get(pkg.lower())
        if not rules:
            continue
        ver = re.sub(r"^[\^~>=<!*\s]+", "", str(version).split(",")[0]).strip()
        vt = _version_tuple(ver)
        for below, advisory in rules:
            if vt < _version_tuple(below):
                flags.append(_flag(
                    "CVE", "medium", file, 1,
                    f"{pkg} {version} is below the fixed version for {advisory}",
                    f"Upgrade {pkg} to >={below} and re-run your lockfile "
                    "audit. Nord Security's patch-management advice: "
                    "automate dependency updates so CVEs close within days, "
                    "not quarters.",
                    engine="dependency_cve",
                    cwe="CWE-1395",
                    patch_available=True,
                ))
                break
    return flags


# ── Engine 4: Injection Sinks ───────────────────────────────────────────────

def scan_for_injection_sinks(content: str, file: str) -> list[dict]:
    """Engine 4: Injection Sinks (SQL, Command Injection, Code Eval, Path Traversal)."""
    flags: list[dict] = []
    if file.endswith(".py"):
        try:
            tree = ast.parse(content)
        except (SyntaxError, ValueError):
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                dotted = ""
                if isinstance(node.func, ast.Name):
                    dotted = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    base = node.func.value.id if isinstance(node.func.value, ast.Name) else ""
                    dotted = f"{base}.{node.func.attr}" if base else node.func.attr

                last = dotted.rsplit(".", 1)[-1]

                # SQL Injection: cursor.execute / query with f-string or concatenation
                if last in {"execute", "executemany", "raw", "query"} and node.args:
                    first_arg = node.args[0]
                    is_injected = False
                    if isinstance(first_arg, ast.JoinedStr) and any(
                        isinstance(v, ast.FormattedValue) for v in first_arg.values
                    ):
                        is_injected = True
                    elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, (ast.Add, ast.Mod)):
                        is_injected = True
                    elif isinstance(first_arg, ast.Call) and isinstance(first_arg.func, ast.Attribute) and first_arg.func.attr == "format":
                        is_injected = True

                    if is_injected:
                        flags.append(_flag(
                            "INJECTION", "high", file, node.lineno,
                            f"SQL query constructed with dynamic string interpolation in {last}()",
                            "Use parameterized queries (e.g. cursor.execute(query, (params,))) to separate SQL logic from data and prevent SQL injection.",
                            engine="injection_sinks",
                            cwe="CWE-89",
                            patch_available=True,
                        ))

                # Command Injection: subprocess with shell=True
                if (dotted.startswith("subprocess.") or dotted in {"subprocess"}) and any(
                    kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in node.keywords
                ):
                    flags.append(_flag(
                        "INJECTION", "critical", file, node.lineno,
                        "Subprocess invoked with shell=True risks arbitrary command execution",
                        "Set shell=False and pass command and arguments as a list (e.g. ['executable', 'arg1']).",
                        engine="injection_sinks",
                        cwe="CWE-78",
                        patch_available=True,
                    ))

                # Command Injection: os.system / os.popen with dynamic expression
                if dotted in {"os.system", "os.popen"} and node.args:
                    if not isinstance(node.args[0], ast.Constant):
                        flags.append(_flag(
                            "INJECTION", "critical", file, node.lineno,
                            f"{dotted}() called with dynamic command argument",
                            "Replace with subprocess.run(..., shell=False) with parameterized arguments.",
                            engine="injection_sinks",
                            cwe="CWE-78",
                            patch_available=True,
                        ))

                # Code Eval: eval / exec with non-constant argument
                if dotted in {"eval", "exec"} and node.args:
                    if not isinstance(node.args[0], ast.Constant):
                        flags.append(_flag(
                            "INJECTION", "critical", file, node.lineno,
                            f"Dynamic code evaluation via {dotted}()",
                            "Avoid dynamic code execution. Use ast.literal_eval() or json.loads() for data parsing.",
                            engine="injection_sinks",
                            cwe="CWE-95",
                            patch_available=True,
                        ))

                # Path Traversal: open with unvalidated variable in file operations
                if dotted in {"open", "io.open"} and node.args:
                    first_arg = node.args[0]
                    if isinstance(first_arg, (ast.JoinedStr, ast.BinOp)):
                        flags.append(_flag(
                            "INJECTION", "high", file, node.lineno,
                            "Dynamic path concatenation in file open() operation",
                            "Ensure paths are validated with os.path.abspath and containment check or werkzeug.utils.secure_filename.",
                            engine="injection_sinks",
                            cwe="CWE-22",
                            patch_available=True,
                        ))

    elif file.endswith((".js", ".jsx", ".ts", ".tsx")):
        for lineno, line in enumerate(content.splitlines(), 1):
            if re.search(r"""\b(?:query|execute)\s*\(\s*`[^`]*\$\{""", line):
                flags.append(_flag(
                    "INJECTION", "high", file, lineno,
                    "SQL query constructed with template literal expression in query()",
                    "Use parameterized query placeholders ($1, $2 or ?) instead of string interpolation.",
                    engine="injection_sinks",
                    cwe="CWE-89",
                    patch_available=True,
                ))
            if re.search(r"""\bchild_process\.(?:exec|execSync)\s*\(""", line) or re.search(r"""\bexec\s*\(\s*`[^`]*\$\{""", line):
                flags.append(_flag(
                    "INJECTION", "critical", file, lineno,
                    "Command execution via child_process.exec() with dynamic input",
                    "Use child_process.spawn(executable, [args], { shell: false }) instead of shell execution.",
                    engine="injection_sinks",
                    cwe="CWE-78",
                    patch_available=True,
                ))
            if re.search(r"""\beval\s*\([^"']+\)""", line) or re.search(r"""\bnew\s+Function\s*\(""", line):
                flags.append(_flag(
                    "INJECTION", "critical", file, lineno,
                    "Dynamic code evaluation via eval() or new Function()",
                    "Avoid dynamic code generation and eval in client/server code.",
                    engine="injection_sinks",
                    cwe="CWE-95",
                    patch_available=True,
                ))

    return flags


# ── Engine 5: Insecure Configuration & CORS ─────────────────────────────────

def scan_for_insecure_config(content: str, file: str) -> list[dict]:
    """Engine 5: Insecure Configuration & CORS (Wildcard CORS, Disabled SSL, Production Debug Flags)."""
    flags: list[dict] = []
    is_test_file = any(part in file.lower() for part in ("test", "tests", "mock", "fixture"))

    for lineno, line in enumerate(content.splitlines(), 1):
        # 1. Wildcard CORS
        if re.search(r"""(?:allow_origins\s*=\s*\[\s*["']\*["']\s*\]|Access-Control-Allow-Origin["']?\s*:\s*["']\*["']|origin\s*:\s*["']\*["'])""", line):
            flags.append(_flag(
                "CONFIG", "medium", file, lineno,
                "Wildcard CORS origin '*' allows any external domain to make cross-origin requests",
                "Specify explicit allowed origins or read them from a trusted environment configuration.",
                engine="insecure_config",
                cwe="CWE-942",
                patch_available=True,
            ))

        # 2. Disabled SSL verification
        if re.search(r"""\bverify\s*=\s*False\b""", line) or re.search(r"""rejectUnauthorized\s*:\s*false""", line):
            flags.append(_flag(
                "CONFIG", "high", file, lineno,
                "TLS certificate verification disabled (verify=False / rejectUnauthorized: false)",
                "Enable SSL certificate verification to defend against man-in-the-middle (MITM) attacks.",
                engine="insecure_config",
                cwe="CWE-295",
                patch_available=True,
            ))

        # 3. Production debug flags (skip in test files)
        if not is_test_file:
            if re.search(r"""\bDEBUG\s*=\s*True\b""", line) or re.search(r"""\bapp\.run\s*\(.*debug\s*=\s*True.*\)""", line):
                flags.append(_flag(
                    "CONFIG", "low", file, lineno,
                    "Debug mode explicitly enabled in application code",
                    "Disable debug mode or gate it behind an environment variable (e.g. os.getenv('DEBUG', '0') == '1').",
                    engine="insecure_config",
                    cwe="CWE-489",
                    patch_available=True,
                ))

    return flags


# ── Engine 6: Permission & Authentication Bypass ────────────────────────────

def scan_for_auth_bypass(content: str, file: str) -> list[dict]:
    """Engine 6: Permission & Authentication Bypass (State-mutating routes without auth guards)."""
    flags: list[dict] = []
    is_test_file = any(part in file.lower() for part in ("test", "tests", "mock", "fixture"))
    if is_test_file or not file.endswith(".py"):
        return []

    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                dec_call = dec if isinstance(dec, ast.Call) else None
                dec_func = dec_call.func if dec_call else dec
                dotted = ""
                if isinstance(dec_func, ast.Attribute):
                    base = dec_func.value.id if isinstance(dec_func.value, ast.Name) else ""
                    dotted = f"{base}.{dec_func.attr}" if base else dec_func.attr
                elif isinstance(dec_func, ast.Name):
                    dotted = dec_func.id

                verb = dotted.rsplit(".", 1)[-1].lower()
                # Check for state-mutating HTTP methods
                if verb in {"post", "put", "delete", "patch"}:
                    param_names = [a.arg.lower() for a in node.args.args]
                    auth_exact = {"auth", "user", "current_user", "token", "credentials", "session", "admin"}
                    has_auth_param = any(
                        (name in auth_exact or name.endswith(("_auth", "_token", "_user")))
                        and name not in {"user_id", "userid", "user_pk", "user_email", "user_name", "username"}
                        for name in param_names
                    )
                    has_depends = any(
                        isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "Depends"
                        for d in (*node.args.defaults, *node.args.kw_defaults)
                    )
                    has_dec_deps = dec_call is not None and any(
                        kw.arg == "dependencies" for kw in dec_call.keywords
                    )

                    if not (has_auth_param or has_depends or has_dec_deps):
                        sev = "high" if verb in {"delete", "post"} else "medium"
                        flags.append(_flag(
                            "AUTH_BYPASS", sev, file, node.lineno,
                            f"State-mutating endpoint '{node.name}' ({verb.upper()}) lacks authentication dependency or guard",
                            "Add an authentication dependency like 'user = Depends(get_current_user)' or route-level security dependency.",
                            engine="auth_bypass",
                            cwe="CWE-306",
                            patch_available=True,
                        ))

    return flags


# ── Non-Destructive Suggested Patch Generator ───────────────────────────────

def generate_security_patch(
    file: str,
    line: int,
    engine: str = "injection_sinks",
    detail: str = "",
    source: str | None = None,
    repo_root: str | None = None,
) -> dict:
    """Non-destructive suggested patch generator with AST syntax verification."""
    source_lines: list[str] = []
    if source is not None:
        source_lines = source.splitlines(keepends=True)
    elif repo_root:
        target_path = Path(repo_root) / file
        if target_path.is_file():
            try:
                source_lines = target_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            except OSError:
                pass

    if not source_lines:
        return {
            "ok": False,
            "file": file,
            "line": line,
            "engine": engine,
            "diff": "",
            "syntax_valid": False,
            "explanation": "Source file could not be read to construct patch.",
        }

    idx = max(0, min(line - 1, len(source_lines) - 1))
    target_line = source_lines[idx]
    new_line = target_line
    explanation = "Suggested remediation patch."

    # Heuristic patching based on engine & line content
    if engine == "injection_sinks" or "SQL" in detail:
        if "f\"" in target_line or "f'" in target_line:
            new_line = re.sub(r'f(["\'].*?)\{([^}]+)\}(.*?["\'])', r'\1%s\3, (\2,)', target_line)
            explanation = "Parameterized query placeholders prevent SQL injection by separating SQL commands from untrusted data."
        elif "shell=True" in target_line:
            new_line = target_line.replace("shell=True", "shell=False")
            explanation = "Disabling shell=True prevents remote command injection via shell metacharacters."
        elif "os.system(" in target_line:
            new_line = target_line.replace("os.system(", "subprocess.run(shlex.split(")
            explanation = "subprocess.run with tokenized arguments avoids invocation of system shell interpreters."
    elif engine == "insecure_config" or "CORS" in detail:
        if '["*"]' in target_line or "['*']" in target_line:
            new_line = target_line.replace('["*"]', 'os.getenv("ALLOWED_ORIGINS", "https://app.example.com").split(",")')
            new_line = new_line.replace("['*']", 'os.getenv("ALLOWED_ORIGINS", "https://app.example.com").split(",")')
            explanation = "Replaced wildcard CORS origin with environment-configured whitelist."
        elif "verify=False" in target_line:
            new_line = target_line.replace("verify=False", "verify=True")
            explanation = "Re-enabled TLS certificate verification to prevent MITM attacks."
        elif "DEBUG = True" in target_line:
            new_line = target_line.replace("DEBUG = True", 'DEBUG = os.getenv("APP_DEBUG", "0") == "1"')
            explanation = "Gated debug mode behind environment variable to prevent production debug leaks."
    elif engine == "auth_bypass" or "AUTH" in detail:
        if "def " in target_line and "):" in target_line:
            new_line = target_line.replace("):", ", current_user: dict = Depends(get_current_user)):")
            new_line = new_line.replace("(, ", "(")
            explanation = "Enforced authentication by requiring verified current_user dependency."
    elif engine == "secrets_entropy" or "SECRET" in detail:
        m = re.search(r'([A-Za-z0-9_]+)\s*=\s*["\'][^"\']+["\']', target_line)
        if m:
            var_name = m.group(1)
            env_key = var_name.upper()
            new_line = re.sub(r'=\s*["\'][^"\']+["\']', f'= os.getenv("{env_key}")', target_line)
            explanation = f"Moved hardcoded secret to environment variable '{env_key}'."

    if new_line == target_line:
        new_line = "# [REMEDIATION]: Parameterize and sanitize values before reaching this line\n" + target_line

    patched_lines = list(source_lines)
    patched_lines[idx] = new_line

    # Syntax verification
    syntax_valid = True
    if file.endswith(".py"):
        try:
            ast.parse("".join(patched_lines))
        except SyntaxError:
            syntax_valid = False

    diff_lines = list(difflib.unified_diff(
        source_lines, patched_lines,
        fromfile=f"a/{file}",
        tofile=f"b/{file}",
        lineterm="",
    ))
    diff_text = "\n".join(diff_lines)

    return {
        "ok": True,
        "file": file,
        "line": line,
        "engine": engine,
        "diff": diff_text,
        "syntax_valid": syntax_valid,
        "explanation": explanation,
    }


# ── Repo file walk ───────────────────────────────────────────────────────────

_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__",
              ".venv", "venv", ".mypy_cache", ".pytest_cache"}
_MAX_FILE_BYTES = 200_000
_MAX_FILES = 400


def scan_repo_files(local_path: str) -> list[dict]:
    """Scan the loaded clone for committed secrets, .env leaks, CVEs, injection sinks, insecure configs, and auth bypasses."""
    root = Path(local_path)
    flags: list[dict] = []
    scanned = 0
    try:
        for path in sorted(root.rglob("*")):
            if len(flags) > 300:
                break
            if any(p in _SKIP_DIRS for p in path.parts):
                continue
            if not path.is_file():
                continue
            try:
                rel = str(path.relative_to(root)).replace("\\", "/")
            except ValueError:
                continue

            flags.extend(scan_file_for_env_leak(rel))

            try:
                with open(path, "rb") as fh:
                    head = fh.read(1024)
                if b"\x00" in head:
                    continue
                content = path.read_text(errors="ignore")[:_MAX_FILE_BYTES]
            except OSError:
                continue

            scanned += 1
            if scanned > _MAX_FILES:
                break

            flags.extend(scan_text_for_secrets(content, rel))
            if path.name in ("package.json",) or path.name.startswith("requirements"):
                flags.extend(check_dependency_cves(content, rel))
            flags.extend(scan_for_injection_sinks(content, rel))
            flags.extend(scan_for_insecure_config(content, rel))
            flags.extend(scan_for_auth_bypass(content, rel))
    except Exception as exc:  # noqa: BLE001 — scanning must never 500 the API
        log.warning("Repo file scan incomplete: %s", exc)

    log.info("Repo scan: %d files, %d flags", scanned, len(flags))
    return flags


def scan_pr_patch(files: list[dict]) -> list[dict]:
    """Scan a PR's changed files (GitHub /pulls/files payload) for secrets,
    breaking signature changes, major bumps, env usage, and injection sinks."""
    flags: list[dict] = []
    for f in files:
        filename = f.get("filename") or ""
        patch = f.get("patch") or ""
        if not patch:
            continue
        # Only added lines can introduce secrets and injection sinks
        added = "\n".join(l for l in patch.splitlines() if l.startswith("+"))
        flags.extend(scan_text_for_secrets(added, filename))
        flags.extend(detect_breaking_in_patch(patch, filename))
        flags.extend(detect_major_bump(patch, filename))
        flags.extend(scan_text_for_env_usage(added, filename))
        flags.extend(scan_for_injection_sinks(added, filename))
        flags.extend(scan_for_insecure_config(added, filename))
        flags.extend(scan_for_auth_bypass(added, filename))
    return flags
