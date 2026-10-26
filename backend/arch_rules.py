"""
arch_rules.py
The single source of truth for RepoScope's architecture model.

Two distinct concepts live here, and keeping them apart matters:

  1. CANONICAL LAYERS (client / backend / storage / external / compute)
     The five-way taxonomy used to colour graph nodes and to decide the
     default direction of allowed dependencies. Ported verbatim from
     frontend/src/components/graph/layerClassifier.ts.

  2. ARCHITECTURE DOMAINS + BOUNDARY RULES (.reposcope.yml)
     Team-declared domains ("domain", "infra", ...) and the edges that
     must never cross between them. Loaded from a repo's own
     .reposcope.yml so teams can version and own their rules.

Correction C6: before this module existed the layer rules lived ONLY in
frontend TypeScript, which meant the MCP server and the web UI could
disagree about what "client" or "storage" meant. This module is now the
BACKEND source of truth, served to every backend consumer — the MCP
server, the CI gate, the PR bot — via GET /api/arch/rules.

The frontend still holds a copy of the rules in
frontend/src/components/graph/layerClassifier.ts, because `classify()` is
called synchronously while the graph renders and an async fetch would
flash the wrong colours on the signature visual. That copy is not
trusted: backend/tests/test_arch_rules.py runs the frontend's own rules
(scripts/parity_classify.js) over a shared corpus and asserts zero
divergence, so the two tables cannot drift apart silently. Migrating the
frontend to consume the endpoint is tracked as a Sprint 1 follow-up.

Determinism note: every regex below is compiled with re.IGNORECASE to
match the JavaScript /i flag. Python's `$` also matches before a
trailing newline; paths never contain one, so behaviour is equivalent.
"""
from __future__ import annotations

import fnmatch
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

log = logging.getLogger("reposcope.arch_rules")

Layer = Literal["client", "backend", "storage", "external", "compute"]

# ── Canonical layers ────────────────────────────────────────────────────────

#: Ordered for display. Index is NOT significant for matching.
LAYERS: tuple[Layer, ...] = ("client", "backend", "storage", "external", "compute")

LAYER_INFO: dict[Layer, dict[str, str]] = {
    "client":   {"name": "Client / UI",            "description": "Frontends, views, components, static assets."},
    "backend":  {"name": "Backend / API",          "description": "Services, routers, handlers, controllers, domain logic."},
    "storage":  {"name": "Storage / Data",         "description": "Models, schemas, migrations, repositories, persistence, and data files."},
    "external": {"name": "External / Integrations","description": "Third-party SDKs, payment providers, webhooks, OAuth."},
    "compute":  {"name": "Compute / Workers",      "description": "Workers, schedulers, engines, queues, background jobs."},
}

# ── Non-code files ──────────────────────────────────────────────────────────
#
# The rules below were written for SOURCE CODE, but they were applied to
# every file in the repository — so a PDF in a data folder fell through
# every rule and landed in "backend". Measured on a real 154-file
# repository, 53 of 154 files (34%) were misclassified: every PDF,
# spreadsheet, CSV, markdown file, and JSON manifest.
#
# A non-code file is not part of the system's architecture. It is data, a
# document, a config file, or a media asset — and its KIND says which.
# The extension decides, not the directory: a PDF is data wherever it
# lives.

#: Images, video, audio, and fonts — assets served to the browser.
ASSET_MEDIA_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tif", ".tiff",
    ".svg", ".avif", ".heic",
    ".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v", ".ogv",
    ".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
})

#: Documents and tabular data.
ASSET_DATA_EXTENSIONS = frozenset({
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf", ".odt",
    ".ods", ".csv", ".tsv", ".parquet", ".avro",
})

#: Prose.
ASSET_DOC_EXTENSIONS = frozenset({".md", ".markdown", ".mdx", ".rst", ".txt", ".adoc", ".log"})

#: Configuration and manifests.
ASSET_CONFIG_EXTENSIONS = frozenset({
    ".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".toml", ".xml", ".ini",
    ".cfg", ".conf", ".env", ".properties", ".lock",
})

#: Archives and build output.
ASSET_ARCHIVE_EXTENSIONS = frozenset({
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz", ".jar", ".war",
})

#: Dotfiles that carry configuration rather than code.
ASSET_DOTFILES = frozenset({
    ".gitignore", ".gitattributes", ".gitmodules", ".editorconfig",
    ".dockerignore", ".npmrc", ".nvmrc", ".prettierrc", ".eslintrc",
    ".babelrc", ".stylelintrc", ".gitkeep", ".dockerfile",
})

#: Project documents with no extension.
ASSET_PROJECT_DOCUMENTS = frozenset({
    "license", "licence", "notice", "authors", "contributors", "changelog",
    "readme", "copying", "codeowners",
})

#: Build and operations files — no extension, but they are tooling, not data.
BUILD_FILE_NAMES = frozenset({
    "makefile", "dockerfile", "procfile", "rakefile", "gemfile", "justfile",
    "cmakelists.txt", "makefile.am", "makefile.in",
})

#: Ordered rules — FIRST MATCH WINS. Order is load-bearing and is
#: preserved exactly from layerClassifier.ts.
#:
#: The generic words are anchored to path/word boundaries. The previous
#: patterns matched them anywhere in the string, so `myengineer.py` counted
#: as "compute" and `notpayment.py` counted as "external".
_RULE_SOURCE: tuple[tuple[Layer, str], ...] = (
    ("external",
     r"(^|/)(external|integrations?|sdk|providers?)(/|$)"
     r"|(^|[/._-])(api[_-]?client|http[_-]?client|webhooks?|oauth|payments?|stripe|slack|openai|anthropic)([/._-]|$)"
     r"|(_|-)client\."),
    ("compute",
     r"(^|/)(engines?|workers?|schedulers?|queues?|celery|cron|daemons?|consumers?|producers?|tasks?|algorithms?)([/._-]|$)"),
    ("storage",
     r"(^|/)(models?|schemas?|migrations?|db|database|datastore|persistence|repositories?|store|storehouse)(/|$)"
     r"|\.(sql|db|sqlite)$"),
    ("backend",
     r"(^|/)(backend|server|servers|services?|routers?|routes?|handlers?|controllers?|api|apis|middleware|main)(/|$)"
     r"|\.(py|go|java|rb|php|rs)$"),
    ("client",
     r"(^|/)(frontend|client|src|components?|pages?|views?|screens?|ui|styles?|assets?|public)(/|$)"
     r"|\.(tsx|jsx|vue|svelte|css|scss|html|svg|png|jpg)$"),
)

LAYER_RULES: tuple[tuple[Layer, re.Pattern[str]], ...] = tuple(
    (layer, re.compile(pattern, re.IGNORECASE)) for layer, pattern in _RULE_SOURCE
)

#: Extension fallback applied when no ordered rule matches.
_CLIENT_EXT_FALLBACK = re.compile(r"\.(tsx|jsx|ts|js|css|html|vue|svelte)$", re.IGNORECASE)

#: The layer assigned when nothing matches at all.
DEFAULT_LAYER: Layer = "backend"


def extension_of(path: str) -> str:
    """
    The lower-cased extension of a path, including the dot.

    A dotfile such as `.gitignore` has no extension — the dot is the
    name, not a separator. A file named `School-Energy-Bills.pdf` has the
    extension `.pdf`.
    """
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    # A leading dot means a dotfile, not an extension.
    if name.startswith(".") and name.count(".") == 1:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


def file_name_of(path: str) -> str:
    """The final path segment, lower-cased."""
    return path.replace("\\", "/").rsplit("/", 1)[-1].lower()


def asset_layer(path: str) -> Layer | None:
    """
    Classify a non-code file, or return None when the file is code.

    The extension decides, not the directory: a PDF is data wherever it
    lives, and an image is a media asset wherever it lives.

      media    -> client   (served to the browser)
      data,
      document,
      config,
      archive  -> storage  (inputs, outputs, and manifests)
    """
    extension = extension_of(path)
    name = file_name_of(path)

    if extension in ASSET_MEDIA_EXTENSIONS:
        return "client"
    if extension in ASSET_DATA_EXTENSIONS:
        return "storage"
    if extension in ASSET_DOC_EXTENSIONS:
        return "storage"
    if extension in ASSET_CONFIG_EXTENSIONS:
        return "storage"
    if extension in ASSET_ARCHIVE_EXTENSIONS:
        return "storage"

    if name in ASSET_DOTFILES:
        return "storage"
    if name in ASSET_PROJECT_DOCUMENTS:
        return "storage"
    if name in BUILD_FILE_NAMES:
        # Build and operations tooling — part of the backend, not data.
        return "backend"

    return None


def classify(node_id: str, label: str = "") -> Layer:
    """
    Classify a node into one of the five canonical layers.

    Mirrors layerClassifier.ts `classify()` exactly, including the
    first-match-wins ordering and the extension fallback.
    """
    # Non-code files first. Without this a PDF, a CSV, or a JSON manifest
    # falls through every rule and lands in "backend".
    #
    # The id and the label are checked SEPARATELY. They are joined with a
    # space for the path rules below, and a joined string breaks the
    # "last path segment" logic for a root-level file: "file:.gitignore
    # .gitignore" has no path separator, so its last segment is the whole
    # thing rather than ".gitignore".
    for candidate in (node_id, label):
        if not candidate:
            continue
        asset = asset_layer(candidate)
        if asset is not None:
            return asset

    haystack = f"{node_id} {label}"
    for layer, pattern in LAYER_RULES:
        if pattern.search(haystack):
            return layer
    if _CLIENT_EXT_FALLBACK.search(haystack):
        return "client"
    return DEFAULT_LAYER


# ── Default dependency policy ───────────────────────────────────────────────

#: Which layers a source layer is ALLOWED to import from.
#: Dependencies flow "downward" through the stack; "external" is a leaf.
ALLOWED_IMPORTS: dict[Layer, frozenset[Layer]] = {
    "client":   frozenset({"client", "backend", "storage", "external", "compute"}),
    "backend":  frozenset({"backend", "storage", "external", "compute"}),
    "compute":  frozenset({"compute", "backend", "storage", "external"}),
    "storage":  frozenset({"storage", "external"}),
    "external": frozenset({"external"}),
}

SEVERITY_ORDER = ("info", "warning", "error")


def is_allowed(source_layer: Layer, target_layer: Layer) -> bool:
    """True when a source layer may legally import from a target layer."""
    return target_layer in ALLOWED_IMPORTS.get(source_layer, frozenset())


def check_import(
    source_layer: Layer,
    target_layer: Layer,
    source_file: str = "",
    target_file: str = "",
) -> dict | None:
    """
    Return a violation dict when source_layer may not import target_layer,
    otherwise None.
    """
    if is_allowed(source_layer, target_layer):
        return None
    return {
        "id": f"layer-{source_layer}-to-{target_layer}",
        "severity": "error",
        "kind": "layer-boundary",
        "source_file": source_file,
        "target_file": target_file,
        "source_layer": source_layer,
        "target_layer": target_layer,
        "message": (
            f"{source_layer} layer may not import from the {target_layer} layer "
            f"({source_file or '?'} -> {target_file or '?'})."
        ),
    }


# ── Team-declared architecture domains (.reposcope.yml) ─────────────────────

CONFIG_FILENAME = ".reposcope.yml"
CONFIG_FILENAMES = (".reposcope.yml", ".reposcope.yaml")


@dataclass(frozen=True)
class Domain:
    """A team-declared architectural domain, matched by path globs."""

    name: str
    include: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class BoundaryRule:
    """A forbidden edge between two declared domains."""

    id: str
    from_domain: str
    to_domain: str
    severity: str = "error"
    description: str = ""


@dataclass
class RuleSet:
    """
    The effective architecture rules for a repository.

    `source` is the config path the rules came from, or None when the
    built-in defaults are in use. `errors` holds non-fatal problems that
    were found while loading (bad config, unknown domain, ...).
    """

    version: int = 1
    domains: tuple[Domain, ...] = ()
    rules: tuple[BoundaryRule, ...] = ()
    ignore: tuple[str, ...] = ()
    source: str | None = None
    errors: list[str] = field(default_factory=list)

    def domain_for(self, rel_path: str) -> str | None:
        """Return the domain a repo-relative path belongs to, if any."""
        path = _normalise(rel_path)
        if self._ignored(path):
            return None
        for domain in self.domains:
            for pattern in domain.include:
                if fnmatch.fnmatchcase(path, pattern) or path == pattern:
                    return domain.name
        return None

    def _ignored(self, path: str) -> bool:
        return any(fnmatch.fnmatchcase(path, pat) for pat in self.ignore)


def _normalise(rel_path: str) -> str:
    """Normalise a repo-relative path to forward slashes, no leading ./."""
    p = str(rel_path or "").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def _parse_domains(raw: object, errors: list[str]) -> tuple[Domain, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        errors.append("'layers' must be a list.")
        return ()
    domains: list[Domain] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"layers[{index}] must be a mapping.")
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            errors.append(f"layers[{index}] is missing 'name'.")
            continue
        include = item.get("include") or []
        if isinstance(include, str):
            include = [include]
        if not isinstance(include, list):
            errors.append(f"layers[{index}].include must be a list of globs.")
            include = []
        domains.append(
            Domain(
                name=name,
                include=tuple(str(p) for p in include),
                description=str(item.get("description") or ""),
            )
        )
    return tuple(domains)


def _parse_rules(
    raw: object,
    domains: tuple[Domain, ...],
    errors: list[str],
) -> tuple[BoundaryRule, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        errors.append("'rules' must be a list.")
        return ()
    known = {d.name for d in domains}
    rules: list[BoundaryRule] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"rules[{index}] must be a mapping.")
            continue
        rule_id = str(item.get("id") or f"rule-{index}").strip()
        from_domain = str(item.get("from") or "").strip()
        to_domain = str(item.get("to") or "").strip()
        if not from_domain or not to_domain:
            errors.append(f"rules[{index}] needs both 'from' and 'to'.")
            continue
        if known and (from_domain not in known or to_domain not in known):
            errors.append(
                f"rules[{index}] ({rule_id}) references an undeclared layer: "
                f"{from_domain} -> {to_domain}."
            )
            continue
        severity = str(item.get("severity") or "error").lower()
        if severity not in SEVERITY_ORDER:
            errors.append(f"rules[{index}] ({rule_id}) has unknown severity '{severity}'.")
            severity = "error"
        rules.append(
            BoundaryRule(
                id=rule_id,
                from_domain=from_domain,
                to_domain=to_domain,
                severity=severity,
                description=str(item.get("description") or ""),
            )
        )
    return tuple(rules)


def load_ruleset(repo_root: str | Path | None = None) -> RuleSet:
    """
    Load the effective RuleSet for a repository.

    Falls back to the built-in defaults (no declared domains, no custom
    boundary rules) when no config is present. A malformed config NEVER
    raises — problems are collected in `RuleSet.errors` and the built-in
    defaults are used instead.
    """
    if repo_root is None:
        return RuleSet()

    root = Path(repo_root)
    config_path: Path | None = None
    for candidate in CONFIG_FILENAMES:
        p = root / candidate
        if p.is_file():
            config_path = p
            break
    if config_path is None:
        return RuleSet()

    errors: list[str] = []
    try:
        import yaml

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception as exc:  # malformed YAML, unreadable file, missing pyyaml
        log.warning("Failed to read %s: %s", config_path, exc)
        return RuleSet(
            source=str(config_path),
            errors=[f"Could not parse {config_path.name}: {exc}"],
        )

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        return RuleSet(
            source=str(config_path),
            errors=[f"{config_path.name} must contain a mapping at the top level."],
        )

    version = raw.get("version", 1)
    try:
        version = int(version)
    except (TypeError, ValueError):
        errors.append(f"Unknown version '{version}' — expected an integer.")
        version = 1

    domains = _parse_domains(raw.get("layers"), errors)
    rules = _parse_rules(raw.get("rules"), domains, errors)

    ignore = raw.get("ignore") or []
    if isinstance(ignore, str):
        ignore = [ignore]
    if not isinstance(ignore, list):
        errors.append("'ignore' must be a list of globs.")
        ignore = []

    return RuleSet(
        version=version,
        domains=domains,
        rules=rules,
        ignore=tuple(str(p) for p in ignore),
        source=str(config_path),
        errors=errors,
    )


def check_boundary(
    ruleset: RuleSet,
    source_file: str,
    target_file: str,
) -> dict | None:
    """
    Check a file-to-file edge against the team's declared boundary rules.

    Returns a violation dict, or None when the edge is permitted.
    """
    if not ruleset.rules:
        return None
    source_domain = ruleset.domain_for(source_file)
    target_domain = ruleset.domain_for(target_file)
    if not source_domain or not target_domain:
        return None
    if source_domain == target_domain:
        return None

    for rule in ruleset.rules:
        if rule.from_domain == source_domain and rule.to_domain == target_domain:
            return {
                "id": rule.id,
                "severity": rule.severity,
                "kind": "domain-boundary",
                "source_file": source_file,
                "target_file": target_file,
                "source_domain": source_domain,
                "target_domain": target_domain,
                "message": (
                    f"'{source_domain}' may not depend on '{target_domain}' "
                    f"({source_file} -> {target_file})."
                ),
            }
    return None


def to_api_payload(ruleset: RuleSet | None = None) -> dict:
    """
    The payload served by GET /api/arch/rules.

    This is the single contract the frontend, the MCP server, and CI all
    consume, so the rule table exists in exactly one place.
    """
    ruleset = ruleset or RuleSet()
    return {
        "version": ruleset.version,
        "layers": [
            {
                "id": layer,
                "name": LAYER_INFO[layer]["name"],
                "description": LAYER_INFO[layer]["description"],
            }
            for layer in LAYERS
        ],
        "layer_rules": [
            {"layer": layer, "pattern": pattern.pattern}
            for layer, pattern in LAYER_RULES
        ],
        "default_layer": DEFAULT_LAYER,
        "allowed_imports": {
            layer: sorted(targets) for layer, targets in ALLOWED_IMPORTS.items()
        },
        "domains": [
            {
                "name": d.name,
                "include": list(d.include),
                "description": d.description,
            }
            for d in ruleset.domains
        ],
        "boundary_rules": [
            {
                "id": r.id,
                "from": r.from_domain,
                "to": r.to_domain,
                "severity": r.severity,
                "description": r.description,
            }
            for r in ruleset.rules
        ],
        "ignore": list(ruleset.ignore),
        "config_source": ruleset.source,
        "config_errors": list(ruleset.errors),
    }
