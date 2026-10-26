"""
test_symbol_resolver.py
The v2 scanners and resolvers, tested without a repository build.

Every test here is deterministic and offline. The point is not to prove
that a regex can match a string; it is to prove the resolver is
conservative and that path normalization cannot create a false match.
"""
from __future__ import annotations

from pathlib import Path

from symbol_resolver import (
    enclosing_symbol,
    load_path_aliases,
    normalize_api_path,
    path_matches,
    resolve_alias_spec,
    scan_api_calls,
    scan_heritage,
    scan_routes,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v2_contract"


# ── Path normalization and matching ─────────────────────────────────────────

def test_full_urls_are_reduced_to_their_path():
    assert normalize_api_path("https://example.test/api/x?q=1#top") == "/api/x"
    assert normalize_api_path("/api/x/") == "/api/x"


def test_parameter_syntaxes_normalize_to_one_wildcard():
    for raw in ("/api/x/{id}", "/api/x/${id}", "/api/x/:id", "/api/x/<int:id>"):
        assert normalize_api_path(raw) == "/api/x/*"


def test_exact_route_match_is_confident():
    assert path_matches("/api/health", "/api/health") == (True, 1.0)


def test_parameterized_route_match_has_lower_confidence():
    matched, confidence = path_matches("/api/items/{id}", "/api/items/42")
    assert matched is True
    assert confidence < 1.0


def test_segment_count_must_agree():
    assert path_matches("/api/items", "/api/items/42") == (False, 0.0)
    assert path_matches("/api/items/{id}", "/api/items") == (False, 0.0)


def test_unknown_static_segment_does_not_match():
    assert path_matches("/api/items", "/api/users") == (False, 0.0)


# ── Python scanners ─────────────────────────────────────────────────────────

PY_ROUTES = '''
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health():
    return {}


@router.api_route("/api/items", methods=["POST", "PUT"])
def items():
    return {}


@router.websocket("/ws/live")
async def live():
    return None
'''


def test_python_route_decorators_are_scanned():
    routes = scan_routes(PY_ROUTES, "server.py", ".py")
    assert {
        (route["method"], route["path"], route["handler"])
        for route in routes
    } == {
        ("GET", "/api/health", "health"),
        ("POST", "/api/items", "items"),
        ("PUT", "/api/items", "items"),
        ("WS", "/ws/live", "live"),
    }


def test_python_route_without_a_literal_path_is_skipped():
    source = 'PATHS = ["/api/x"]\n@router.get(PATHS[0])\ndef x():\n    pass\n'
    assert scan_routes(source, "server.py", ".py") == []


def test_python_heritage_is_scanned_and_external_bases_are_kept():
    source = "class Child(Base, mixins.Mixin):\n    pass\n"
    heritage = scan_heritage(source, "child.py", ".py")
    assert heritage[0]["class"] == "Child"
    assert heritage[0]["bases"] == ["Base", "Mixin"]


def test_python_api_calls_are_scanned():
    source = (
        "import httpx\n"
        "def load():\n"
        "    return httpx.get('/api/health')\n"
    )
    symbols = [{"name": "load", "line": 2, "end_line": 3}]
    calls = scan_api_calls(source, "client.py", ".py", symbols)
    assert calls == [{
        "method": "GET",
        "path": "/api/health",
        "line": 3,
        "enclosing": "load",
        "enclosing_line": 2,
        "origin": "python",
    }]


# ── JS/TS scanners ──────────────────────────────────────────────────────────

def test_express_routes_are_scanned():
    source = 'router.post("/api/items", createItem);\n'
    routes = scan_routes(source, "server.ts", ".ts")
    assert routes[0]["method"] == "POST"
    assert routes[0]["path"] == "/api/items"
    assert routes[0]["handler"] == "createItem"


def test_js_heritage_includes_extends_and_implements():
    source = "export class Child extends Base implements A, B<C> {}\n"
    heritage = scan_heritage(source, "child.ts", ".ts")
    assert heritage[0]["bases"] == ["Base", "A", "B"]


def test_fetch_axios_and_eventsource_are_scanned():
    source = """
export async function a() {
  await fetch(`/api/items/${id}`, { method: "POST" });
  await axios.delete("/api/items/1");
  const events = new EventSource("/api/live");
}
"""
    symbols = [{"name": "a", "line": 2, "end_line": 6}]
    calls = scan_api_calls(source, "client.ts", ".ts", symbols)
    assert [(call["method"], call["path"]) for call in calls] == [
        ("POST", "/api/items/${id}"),
        ("DELETE", "/api/items/1"),
        ("GET", "/api/live"),
    ]
    assert all(call["enclosing"] == "a" for call in calls)


def test_comments_do_not_create_routes():
    source = '// router.get("/api/ghost", ghost)\nrouter.get("/api/real", real);\n'
    routes = scan_routes(source, "server.ts", ".ts")
    assert [route["path"] for route in routes] == ["/api/real"]


# ── Aliases and enclosing symbols ──────────────────────────────────────────

def test_tsconfig_aliases_are_loaded_with_comments_and_trailing_commas():
    aliases = load_path_aliases(FIXTURE)
    assert aliases["@/*"] == ["frontend/src/*"]


def test_alias_specifier_expands_to_repo_relative_candidates():
    aliases = load_path_aliases(FIXTURE)
    assert resolve_alias_spec("@/lib/util", aliases) == ["frontend/src/lib/util"]


def test_enclosing_symbol_prefers_the_innermost_range():
    symbols = [
        {"name": "Child", "line": 1, "end_line": 20},
        {"name": "save", "line": 5, "end_line": 8},
    ]
    assert enclosing_symbol(symbols, 6) == ("save", 5)
    assert enclosing_symbol(symbols, 19) == ("Child", 1)
    assert enclosing_symbol(symbols, 99) == (None, None)
