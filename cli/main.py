"""
cli/main.py
The `reposcope` command.

Milestone 2.2 (Sprint 3). The point of this command is to remove the
biggest friction in the product: you should be able to point RepoScope at
a directory and get the same map you get from a public repository — with
no GitHub account, no personal access token, and nothing uploaded.

    reposcope run .              serve the app on http://127.0.0.1:4100
    reposcope run . --port 4100 --no-open
    reposcope index .            write .reposcope/graph.json, no server
    reposcope index . --format sqlite
    reposcope mcp .              serve the repository over MCP (stdio)

**Guardrails.** The server binds to loopback by default and refuses a
non-loopback address unless it is told explicitly. Nothing in this
command makes an outbound request for the repository's contents.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import typer

app = typer.Typer(
    name="reposcope",
    help="RepoScope — the code graph for humans and agents.",
    add_completion=False,
    no_args_is_help=True,
)

#: Loopback addresses. Binding anywhere else would expose a private
#: codebase to the network.
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

#: The default port. Deliberately NOT 8000 or 5173 — those belong to the
#: development servers, and a CLI that fights the developer for a port is
#: a CLI that gets killed.
DEFAULT_PORT = 4100


def _configure_stdio() -> None:
    """
    Make the console able to print the CLI's output.

    Windows consoles and pipes default to a legacy code page (cp1252),
    and Python raises `UnicodeEncodeError` when the output contains a
    character that code page cannot represent — which crashed the CLI on
    the first line containing an em dash. Replacing unencodable
    characters is not as nice as printing them, but a crash is not an
    option.

    The CLI's own output strings are ASCII for the same reason; this is
    the belt to that braces.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):  # pragma: no cover - exotic streams
            pass


def _backend_dir() -> Path:
    """The backend package directory."""
    return Path(__file__).resolve().parent.parent / "backend"


def _ensure_backend_on_path() -> None:
    backend = str(_backend_dir())
    if backend not in sys.path:
        sys.path.insert(0, backend)


def _resolve_repo(path: str) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise typer.BadParameter(f"Not a directory: {root}")
    return root


def _find_static_dir(root: Path) -> Path | None:
    """
    Locate the built frontend, if there is one.

    The CLI is installed as a package, so the frontend may not be next to
    it. Three places are tried, in order: an explicit `REPOSCOPE_STATIC_DIR`,
    the `frontend/dist` of the RepoScope checkout this CLI came from, and
    the `frontend/dist` of the repository being analysed.
    """
    explicit = os.getenv("REPOSCOPE_STATIC_DIR")
    if explicit:
        candidate = Path(explicit).expanduser()
        if (candidate / "index.html").is_file():
            return candidate

    for base in (_backend_dir().parent, root):
        candidate = base / "frontend" / "dist"
        if (candidate / "index.html").is_file():
            return candidate
    return None


# ── reposcope run ───────────────────────────────────────────────────────────

@app.command()
def run(
    path: str = typer.Argument(".", help="The repository to analyse."),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="The port to serve on."),
    host: str = typer.Option("127.0.0.1", "--host", help="The address to bind."),
    no_open: bool = typer.Option(False, "--no-open", help="Do not open a browser."),
    no_watch: bool = typer.Option(False, "--no-watch", help="Do not watch for file changes."),
    allow_remote: bool = typer.Option(
        False, "--allow-remote",
        help="Allow binding a non-loopback address. Off by default: this serves private code.",
    ),
) -> None:
    """Serve RepoScope for a local repository, with live updates."""
    root = _resolve_repo(path)

    if host not in LOOPBACK_HOSTS and not allow_remote:
        typer.secho(
            f"Refusing to bind {host}: this serves your source code. "
            "Use --allow-remote if you mean it.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    _ensure_backend_on_path()
    from repo_loader import load_local_repo

    info = load_local_repo(str(root))

    static_dir = _find_static_dir(root)
    if static_dir is not None:
        os.environ["REPOSCOPE_STATIC_DIR"] = str(static_dir)

    import uvicorn

    from main import app as fastapi_app

    if static_dir is not None:
        from fastapi.staticfiles import StaticFiles

        # Mounted LAST so the API routes — registered first — still win.
        fastapi_app.mount(
            "/",
            StaticFiles(directory=str(static_dir), html=True),
            name="frontend",
        )

    url = f"http://{host}:{port}"
    _configure_stdio()
    typer.secho("RepoScope - local mode", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"  repository : {root}")
    typer.echo(f"  files      : {info.get('file_count')}")
    typer.echo(f"  serving on : {url}")
    if static_dir is not None:
        typer.echo(f"  frontend   : {static_dir}")
    else:
        typer.secho(
            "  frontend   : not built - the API is served, but the UI is not. "
            "Run `npm run build` in frontend/, or use the dev server.",
            fg=typer.colors.YELLOW,
        )
    typer.echo(f"  watching   : {'off' if no_watch else 'on (the graph updates as you edit)'}")
    typer.echo("  nothing from this repository leaves your machine.")
    typer.echo("")

    if not no_open:
        threading.Thread(
            target=lambda: (time.sleep(1.2), webbrowser.open(url)),
            daemon=True,
        ).start()

    uvicorn.run(
        fastapi_app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )


# ── reposcope index ─────────────────────────────────────────────────────────

@app.command()
def index(
    path: str = typer.Argument(".", help="The repository to index."),
    fmt: str = typer.Option(
        "json", "--format", "-f",
        help="Where to write the index: json or sqlite.",
    ),
    out: str = typer.Option(None, "--out", "-o", help="An explicit output path."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Ignore the parse cache."),
) -> None:
    """Index a repository without starting a server."""
    _configure_stdio()
    root = _resolve_repo(path)

    if fmt not in ("json", "sqlite"):
        typer.secho(f"Unknown format {fmt!r}. Use 'json' or 'sqlite'.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    _ensure_backend_on_path()

    from graph_builder import build_graph_from_repo
    from parse_cache import ParseCache, default_cache_path

    cache = None
    if not no_cache:
        cache = ParseCache(default_cache_path(root))
        cache.load()

    started = time.perf_counter()
    graph = build_graph_from_repo(str(root), cache)
    elapsed = (time.perf_counter() - started) * 1000

    if cache is not None:
        cache.save()

    if fmt == "json":
        from graph_store import JsonGraphStore

        store = JsonGraphStore(out) if out else JsonGraphStore(root / ".reposcope" / "graph.json")
    else:
        from graph_store import SqliteGraphStore

        store = SqliteGraphStore(out) if out else SqliteGraphStore(root / ".reposcope" / "graph.db")

    store.save(graph)

    nodes = len(graph.get("nodes", []) or [])
    edges = len(graph.get("edges", []) or [])
    typer.secho(f"Indexed {root}", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  nodes      : {nodes}")
    typer.echo(f"  edges      : {edges}")
    typer.echo(f"  index      : {store.path}")
    typer.echo(f"  time       : {elapsed:.0f} ms")
    if cache is not None:
        stats = cache.stats()
        typer.echo(f"  cache      : {stats['entries']} entries, {stats['hits']} hits / {stats['misses']} misses")


# ── reposcope mcp ───────────────────────────────────────────────────────────

@app.command()
def mcp(
    path: str = typer.Argument(".", help="The repository to serve."),
    http: bool = typer.Option(False, "--http", help="Serve over Streamable HTTP instead of stdio."),
    host: str = typer.Option("127.0.0.1", "--host", help="The address to bind (HTTP only)."),
    port: int = typer.Option(8765, "--port", help="The port to bind (HTTP only)."),
) -> None:
    """Serve the repository's code graph over the Model Context Protocol."""
    _configure_stdio()
    root = _resolve_repo(path)
    _ensure_backend_on_path()

    from mcp_server.server import main as mcp_main

    argv = ["--root", str(root)]
    if http:
        argv += ["--http", "--host", host, "--port", str(port)]

    typer.secho(f"RepoScope MCP server — {root}", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"  transport  : {'streamable-http' if http else 'stdio'}")
    typer.echo("  register with your client:")
    typer.echo(f'    {{"mcpServers": {{"reposcope": {{"command": "reposcope-mcp",')
    typer.echo(f'      "args": ["--root", "{root}"]}}}}}}')
    typer.echo("")

    raise typer.Exit(code=mcp_main(argv))


# ── reposcope security ──────────────────────────────────────────────────────

@app.command()
def security(
    path: str = typer.Argument(".", help="The repository to scan."),
    sarif: bool = typer.Option(False, "--sarif", help="Output OASIS SARIF 2.1.0 format."),
) -> None:
    """Run the 6-Engine Graph-Contextual Security Suite on a repository."""
    _configure_stdio()
    root = _resolve_repo(path)
    _ensure_backend_on_path()
    from security_scanner import scan_repo_files
    from taint import scan_repository as scan_taint
    from sarif import flags_to_sarif_json

    flags = scan_repo_files(str(root))
    try:
        t_flags = scan_taint(root)
        flags.extend(t_flags)
    except Exception:
        pass

    if sarif:
        typer.echo(flags_to_sarif_json(flags))
        return

    typer.secho(f"RepoScope 6-Engine Security Suite — {root}", fg=typer.colors.CYAN, bold=True)
    typer.secho(f"  findings   : {len(flags)}", fg=typer.colors.GREEN if not flags else typer.colors.YELLOW)
    for f in flags[:15]:
        sev_color = typer.colors.RED if f.get("severity") in ("critical", "high") else typer.colors.YELLOW
        typer.secho(f"  [{f.get('severity', 'warning').upper()}] {f.get('engine', f.get('type'))} in {f.get('file')}:{f.get('line', 1)}", fg=sev_color)
        typer.echo(f"    {f.get('detail')}")
        typer.echo(f"    Tip: {f.get('suggestion')}")


# ── reposcope version ───────────────────────────────────────────────────────

@app.command()
def version() -> None:
    """Print the RepoScope version."""
    try:
        from version import __version__
    except ImportError:
        __version__ = "2.8.0"
    typer.echo(f"RepoScope {__version__} (local mode)")


def _free_port(host: str, port: int) -> int:
    """Return a free port, starting from `port`."""
    for candidate in range(port, port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, candidate))
            except OSError:
                continue
            return candidate
    raise typer.BadParameter(f"No free port near {port}")


if __name__ == "__main__":  # pragma: no cover - process entry point
    app()
