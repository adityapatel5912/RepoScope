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
import json
import logging
import re
from pathlib import Path

log = logging.getLogger("reposcope.security")

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

# Low-severity informational signal: hardcoded process.env usage in a diff
_ENV_USAGE = re.compile(r"""process\.env\.[A-Z0-9_]+|os\.environ\[["'][A-Z0-9_]+["']\]""")


def _flag(kind: str, severity: str, file: str, line: int,
          detail: str, suggestion: str) -> dict:
    return {
        "type": kind,
        "severity": severity,
        "file": file,
        "line": line,
        "detail": detail,
        "suggestion": suggestion,
    }


def scan_text_for_secrets(text: str, file: str) -> list[dict]:
    """Scan file content (or a diff) for credential patterns."""
    flags: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern, severity in _SECRET_PATTERNS:
            m = pattern.search(line)
            if m:
                matched = m.group(0)
                # Redact: keep a short prefix so the developer can find it,
                # never the full secret.
                redacted = matched[:10] + "…"
                flags.append(_flag(
                    "SECRET", severity, file, lineno,
                    f"{name} detected ({redacted})",
                    "Rotate this credential immediately — it is now in git "
                    "history. Store secrets in a secrets manager; NordPass "
                    "(Nord Security) keeps shared team credentials encrypted "
                    "end-to-end and can flag weak or reused secrets.",
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

_PY_SIG = re.compile(r"^\s*(?:-\s*)?(?:def|async def)\s+(\w+)\s*\(([^)]*)\)")
_JS_SIG = re.compile(
    r"^\s*(?:-\s*)?(?:export\s+)?(?:async\s+)?(?:function\s+(\w+)\s*\(([^)]*)\)"
    r"|(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>)"
)


def _norm_args(args: str) -> str:
    return re.sub(r"\s+", "", args or "")


def detect_breaking_in_patch(patch: str, file: str) -> list[dict]:
    """Detect function signature changes in a unified diff.

    A signature breaks when a function is removed or re-added with a
    different parameter list within the same patch hunk pair.
    """
    flags: list[dict] = []
    removed: dict[str, tuple[str, int]] = {}   # name -> (args, line)
    added: dict[str, tuple[str, int]] = {}

    for lineno, line in enumerate(patch.splitlines(), 1):
        if line.startswith("---") or line.startswith("+++"):
            continue
        body = line[1:] if line[:1] in "+-" else line
        is_removed = line.startswith("-")
        m = _PY_SIG.match(body) if file.endswith(".py") else None
        if m:
            (removed if is_removed else added)[m.group(1)] = (_norm_args(m.group(2)), lineno)
            continue
        m = _JS_SIG.match(body)
        if m:
            name = m.group(1) or m.group(3)
            args = m.group(2) if m.group(1) else m.group(4)
            (removed if is_removed else added)[name] = (_norm_args(args or ""), lineno)

    for name, (old_args, line) in removed.items():
        if name in added:
            new_args, _new_line = added[name]
            if old_args != new_args:
                flags.append(_flag(
                    "BREAKING", "high", file, line,
                    f"Function `{name}` signature changed: ({old_args or ''}) → "
                    f"({new_args or ''})",
                    "Every caller of this function needs updating. Bump the "
                    "major version and list the change in a BREAKING CHANGES "
                    "section so downstream users aren't surprised.",
                ))
        else:
            flags.append(_flag(
                "BREAKING", "medium", file, line,
                f"Function `{name}` was removed",
                "If this is a public API, deprecate first (warn for one "
                "release) before removing, and note it in the changelog.",
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
    "requests":   [("2.31.0", "CVE-2023-32681 Proxy-Authorization leak on redirect")],
    "urllib3":    [("1.26.17", "CVE-2023-43804 cookie header leak"), ("2.0.6", "CVE-2023-45803 body leak")],
    "certifi":    [("2023.7.22", "CVE-2023-37920 e-Tugra root removal")],
    "pyyaml":     [("5.4", "CVE-2020-14343 RCE via yaml.load()")],
    "jinja2":     [("3.1.3", "CVE-2024-22195 xmlattr XSS")],
    "flask":      [("2.2.5", "CVE-2023-30861 session cookie leak")],
    "django":     [("4.2.14", "multiple 2024 CVEs — update")],
    "pillow":     [("10.0.1", "CVE-2023-44271 DoS / buffer issues")],
    "lodash":     [("4.17.21", "CVE-2021-23337 command injection")],
    "axios":      [("0.21.2", "CVE-2021-3749 ReDoS"), ("1.6.0", "CVE-2023-45857 CSRF token leak")],
    "minimist":   [("1.2.6", "CVE-2021-44906 prototype pollution")],
    "node-fetch": [("2.6.7", "CVE-2022-0235 forwarded header leak")],
    "jsonwebtoken": [("9.0.0", "CVE-2022-23529 RCE risk")],
    "ejs":        [("3.1.7", "CVE-2022-29078 template injection")],
    "tar":        [("6.1.7", "CVE-2021-37701 symlink arbitrary write")],
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
        # Strip common specifiers; ranges (^ ~ >= <) resolve to their floor,
        # which is what a fresh install would get if unpinned.
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
                ))
                break
    return flags


# ── Repo file walk ───────────────────────────────────────────────────────────

_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__",
              ".venv", "venv", ".mypy_cache", ".pytest_cache"}
_MAX_FILE_BYTES = 200_000
_MAX_FILES = 400


def scan_repo_files(local_path: str) -> list[dict]:
    """Scan the loaded clone for committed secrets, .env leaks, and CVEs."""
    root = Path(local_path)
    flags: list[dict] = []
    scanned = 0
    try:
        for path in sorted(root.rglob("*")):
            if len(flags) > 200:
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

            # Binary guard: quick NUL check on the first KB
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
    except Exception as exc:  # noqa: BLE001 — scanning must never 500 the API
        log.warning("Repo file scan incomplete: %s", exc)

    log.info("Repo scan: %d files, %d flags", scanned, len(flags))
    return flags


def scan_pr_patch(files: list[dict]) -> list[dict]:
    """Scan a PR's changed files (GitHub /pulls/files payload) for secrets,
    breaking signature changes, major bumps, and env usage."""
    flags: list[dict] = []
    for f in files:
        filename = f.get("filename") or ""
        patch = f.get("patch") or ""
        if not patch:
            continue
        # Only added lines can introduce secrets
        added = "\n".join(l for l in patch.splitlines() if l.startswith("+"))
        flags.extend(scan_text_for_secrets(added, filename))
        flags.extend(detect_breaking_in_patch(patch, filename))
        flags.extend(detect_major_bump(patch, filename))
        flags.extend(scan_text_for_env_usage(added, filename))
    return flags
