"""
taint.py
Lightweight source→sink taint analysis (M9.3).

This is deliberately small and LOCAL. It follows taint through
assignments, calls between functions in the SAME file, and returns. It
does not try to model imports, aliasing, dynamic dispatch, or framework
magic. That is enough to catch the shape of a real bug — `name =
request.args["name"]; cursor.execute("... " + name)` — without the
false-positive rate of a whole-program dataflow engine.

Supported languages:
  * Python  — stdlib `ast` (robust on syntax errors)
  * TS/JS   — Tree-sitter (optional; skipped if the grammar is missing)

The output feeds `POST /api/security/scan` as `TAINT` flags, and has its
own endpoint so the UI can explain a flow on demand.
"""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

from parse_cache import SKIP_DIRS

log = logging.getLogger("reposcope.taint")

#: Files larger than this are skipped. Security scanning should never be
#: the reason a repository load takes a minute.
MAX_FILE_BYTES = 256 * 1024
MAX_FILES = 500

#: (prefix, human label). A match is exact or `prefix.` — so
#: `request.args.get` matches `request.args`, but `fooinput` does not
#: match `input`.
PY_SOURCES: tuple[tuple[str, str], ...] = (
    ("input", "input()"),
    ("sys.argv", "sys.argv"),
    ("sys.stdin", "sys.stdin"),
    ("os.environ", "os.environ"),
    ("os.getenv", "os.getenv()"),
    ("request.args", "request.args"),
    ("request.form", "request.form"),
    ("request.json", "request.json"),
    ("request.get_json", "request.get_json()"),
    ("request.data", "request.data"),
    ("request.values", "request.values"),
    ("request.files", "request.files"),
    ("request.cookies", "request.cookies"),
    ("request.headers", "request.headers"),
    ("request.GET", "request.GET"),
    ("request.POST", "request.POST"),
    ("flask.request", "flask.request"),
)

JS_SOURCES: tuple[tuple[str, str], ...] = (
    ("document.location", "document.location"),
    ("window.location", "window.location"),
    ("location.search", "location.search"),
    ("location.hash", "location.hash"),
    ("location.href", "location.href"),
    ("document.URL", "document.URL"),
    ("document.referrer", "document.referrer"),
    ("process.argv", "process.argv"),
    ("process.env", "process.env"),
    ("req.body", "req.body"),
    ("req.query", "req.query"),
    ("req.params", "req.params"),
    ("req.cookies", "req.cookies"),
    ("req.headers", "req.headers"),
    ("request.body", "request.body"),
    ("request.query", "request.query"),
    ("event.target.value", "event.target.value"),
)

#: Names that make a tainted value safe for the named sink family. A
#: sanitizer is trusted only by name; this is a heuristic, not a proof.
PY_SANITIZERS = {
    "int", "float", "bool", "escape", "quote", "sanitize", "clean",
    "parse_int", "to_int", "html.escape", "markupsafe.escape",
    "shlex.quote", "werkzeug.utils.secure_filename",
}
JS_SANITIZERS = {
    "parseInt", "parseFloat", "Number", "Boolean", "encodeURIComponent",
    "encodeURI", "escape", "sanitize", "DOMPurify.sanitize",
    "validator.escape", "he.encode",
}

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass(frozen=True)
class Taint:
    label: str
    line: int
    via: tuple[str, ...] = ()


@dataclass
class Flow:
    file: str
    source: str
    source_line: int
    sink: str
    sink_line: int
    severity: str
    message: str
    via: list[str] = field(default_factory=list)

    def to_flag(self) -> dict:
        """The shape `/api/security/scan` already knows how to render."""
        return {
            "type": "TAINT",
            "severity": self.severity,
            "file": self.file,
            "line": self.sink_line,
            "detail": self.message,
            "suggestion": (
                "Pass the value through a strict allow-list or an escaping "
                "function before it reaches this sink."
            ),
            "source": self.source,
            "source_line": self.source_line,
            "via": self.via,
        }


def _matches(dotted: str, prefix: str) -> bool:
    return dotted == prefix or dotted.startswith(prefix + ".")


def _source_for(dotted: str, table: tuple[tuple[str, str], ...]) -> str | None:
    for prefix, label in table:
        if _matches(dotted, prefix):
            return label
    return None


def _severity_for_sink(sink: str) -> str:
    if sink in {"eval", "exec", "Function", "os.system", "os.popen"}:
        return "critical"
    if sink.startswith("subprocess") or sink in {"pickle.loads", "yaml.load", "marshal.loads"}:
        return "critical"
    if sink in {"execute", "executemany", "query", "raw"}:
        return "high"
    if sink in {"open", "write", "unlink", "remove", "send_file", "send_from_directory"}:
        return "high"
    if sink in {"innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"}:
        return "high"
    return "medium"


def _sink_from_call(dotted: str) -> str | None:
    """Map a dotted callee to the sink name it represents, if any."""
    last = dotted.rsplit(".", 1)[-1] if dotted else ""
    if last in {"eval", "exec", "compile"}:
        return last
    if dotted in {"os.system", "os.popen"}:
        return dotted
    if dotted.startswith("subprocess.") and last in {
        "run", "call", "check_call", "check_output", "Popen",
    }:
        return f"subprocess.{last}"
    if dotted in {"pickle.loads", "yaml.load", "marshal.loads"}:
        return dotted
    if last in {"execute", "executemany"} and "." in dotted:
        return "execute"
    if dotted in {"open", "io.open", "send_file", "send_from_directory"}:
        return dotted.rsplit(".", 1)[-1]
    if dotted.startswith("requests.") and last in {
        "get", "post", "put", "patch", "delete", "head", "request",
    }:
        return f"requests.{last}"
    if dotted.startswith(("httpx.", "urllib.request.")) and last in {
        "get", "post", "urlopen", "request",
    }:
        return last
    if last in {"redirect", "HttpResponseRedirect"}:
        return "redirect"
    if last in {"render_template_string", "from_string"}:
        return "render_template_string"
    if dotted.startswith("shutil.") and last in {"copy", "copy2", "copyfile", "move"}:
        return "open"
    if last in {"unlink", "remove", "rmdir", "removedirs"} and "." in dotted:
        return "remove"
    return None


# ── Python ──────────────────────────────────────────────────────────────────

@dataclass
class _PyFunc:
    name: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    params: list[str]
    param_sources: dict[int, Taint] = field(default_factory=dict)
    return_taint: Taint | None = None


def _py_dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _py_dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return _py_dotted(node.value)
    if isinstance(node, ast.Call):
        return _py_dotted(node.func)
    return ""


def _py_target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in node.elts:
            names.extend(_py_target_names(element))
        return names
    return []


def _py_params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = node.args
    return [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]


class _PyAnalyzer:
    def __init__(
        self,
        rel: str,
        flows: list[Flow],
        funcs: dict[str, _PyFunc],
        seen: set[tuple],
        param_sources: dict[str, dict[int, Taint]],
    ):
        self.rel = rel
        self.flows = flows
        self.funcs = funcs
        self.seen = seen
        self.param_sources = param_sources
        self.tainted: dict[str, Taint] = {}
        self.return_taint: Taint | None = None
        self.calls: list[tuple[str, list[Taint], int]] = []

    # ── reporting ────────────────────────────────────────────────────────

    def _report(self, taint: Taint, sink: str, line: int) -> None:
        severity = _severity_for_sink(sink)
        key = (self.rel, taint.label, taint.line, sink, line)
        if key in self.seen:
            return
        self.seen.add(key)
        via = list(taint.via[-6:])
        self.flows.append(
            Flow(
                file=self.rel,
                source=taint.label,
                source_line=taint.line,
                sink=sink,
                sink_line=line,
                severity=severity,
                message=(
                    f"{taint.label} reaches {sink}() at line {line} "
                    "without a recognised sanitizer"
                ),
                via=via,
            )
        )

    def _check_sink(self, node: ast.Call) -> None:
        dotted = _py_dotted(node.func)
        sink = _sink_from_call(dotted)
        if not sink:
            return
        args = list(node.args) + [kw.value for kw in node.keywords]
        for arg in args:
            taint = self.expr(arg)
            if taint:
                self._report(taint, sink, node.lineno)
                return

    # ── expressions ──────────────────────────────────────────────────────

    def expr(self, node: ast.AST | None) -> Taint | None:
        if node is None:
            return None

        if isinstance(node, ast.Name):
            return self.tainted.get(node.id)

        if isinstance(node, ast.Attribute):
            dotted = _py_dotted(node)
            source = _source_for(dotted, PY_SOURCES)
            if source:
                return Taint(source, node.lineno, (dotted,))
            base = self.expr(node.value)
            if base:
                return Taint(base.label, base.line, (*base.via, node.attr))
            return None

        if isinstance(node, ast.Subscript):
            dotted = _py_dotted(node)
            source = _source_for(dotted, PY_SOURCES)
            if source:
                return Taint(source, node.lineno, (dotted,))
            return self.expr(node.value)

        if isinstance(node, ast.Call):
            return self._call(node)

        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                taint = self.expr(value)
                if taint:
                    return taint
            return None

        if isinstance(node, ast.FormattedValue):
            return self.expr(node.value)

        if isinstance(node, ast.BinOp):
            return self.expr(node.left) or self.expr(node.right)

        if isinstance(node, ast.IfExp):
            return self.expr(node.body) or self.expr(node.orelse)

        if isinstance(node, ast.Await):
            return self.expr(node.value)

        if isinstance(node, ast.NamedExpr):
            return self.expr(node.value)

        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for element in node.elts:
                taint = self.expr(element)
                if taint:
                    return taint
            return None

        if isinstance(node, ast.Dict):
            for value in node.values:
                taint = self.expr(value)
                if taint:
                    return taint
            return None

        if isinstance(node, ast.Starred):
            return self.expr(node.value)

        if isinstance(node, ast.Compare):
            return None

        if isinstance(node, ast.Lambda):
            return None

        # Generic fallback: any tainted child makes the expression tainted.
        for child in ast.iter_child_nodes(node):
            taint = self.expr(child)
            if taint:
                return taint
        return None

    def _call(self, node: ast.Call) -> Taint | None:
        dotted = _py_dotted(node.func)
        source = _source_for(dotted, PY_SOURCES)
        if source:
            return Taint(source, node.lineno, (dotted,))

        # A sink can be the receiver of a larger expression:
        # `open(path).read()`, `cursor.execute(sql).fetchall()`.
        if isinstance(node.func, ast.Attribute):
            self.expr(node.func.value)

        self._check_sink(node)

        args = list(node.args) + [kw.value for kw in node.keywords]
        arg_taints = [taint for taint in (self.expr(arg) for arg in args) if taint]

        last = dotted.rsplit(".", 1)[-1] if dotted else ""
        if last in PY_SANITIZERS or dotted in PY_SANITIZERS:
            return None

        callee = self.funcs.get(dotted) or self.funcs.get(last)
        if callee is not None:
            self.calls.append((callee.name, arg_taints, node.lineno))
            if callee.return_taint is not None:
                return callee.return_taint
            return None

        # An unknown call that receives tainted data returns tainted data.
        # This is the conservative choice: a wrapper must not silently
        # launder taint just because it lives in another file.
        return arg_taints[0] if arg_taints else None

    # ── statements ───────────────────────────────────────────────────────

    def block(self, statements: list[ast.stmt]) -> None:
        for statement in statements:
            self.stmt(statement)

    def stmt(self, node: ast.stmt) -> None:
        if isinstance(node, ast.Assign):
            taint = self.expr(node.value)
            for target in node.targets:
                self._assign(target, taint)
            return

        if isinstance(node, ast.AnnAssign):
            taint = self.expr(node.value) if node.value else None
            self._assign(node.target, taint)
            return

        if isinstance(node, ast.AugAssign):
            taint = self.expr(node.value) or self.expr(node.target)
            self._assign(node.target, taint)
            self.expr(node.value)
            return

        if isinstance(node, ast.Return):
            taint = self.expr(node.value)
            if taint and self.return_taint is None:
                self.return_taint = taint
            return

        if isinstance(node, ast.Expr):
            self.expr(node.value)
            return

        if isinstance(node, ast.If):
            self.expr(node.test)
            self.block(node.body)
            self.block(node.orelse)
            return

        if isinstance(node, (ast.For, ast.AsyncFor)):
            iter_taint = self.expr(node.iter)
            for target in _py_target_names(node.target):
                if iter_taint:
                    self.tainted[target] = iter_taint
                else:
                    self.tainted.pop(target, None)
            self.block(node.body)
            self.block(node.orelse)
            return

        if isinstance(node, ast.While):
            self.expr(node.test)
            self.block(node.body)
            self.block(node.orelse)
            return

        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                taint = self.expr(item.context_expr)
                if item.optional_vars is not None:
                    self._assign(item.optional_vars, taint)
            self.block(node.body)
            return

        if isinstance(node, ast.Try) or node.__class__.__name__ == "TryStar":
            self.block(node.body)
            for handler in node.handlers:
                if handler.type is not None:
                    self.expr(handler.type)
                self.block(handler.body)
            self.block(node.orelse)
            self.block(node.finalbody)
            return

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return

        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Pass, ast.Break,
                             ast.Continue, ast.Global, ast.Nonlocal)):
            return

        # Match / raise / assert / del: inspect expressions for sinks.
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt):
                self.stmt(child)
            elif isinstance(child, ast.expr):
                self.expr(child)

    def _assign(self, target: ast.AST, taint: Taint | None) -> None:
        names = _py_target_names(target)
        for name in names:
            if taint is None:
                self.tainted.pop(name, None)
            else:
                self.tainted[name] = Taint(taint.label, taint.line, (*taint.via, name))


def analyze_python(source: str, rel: str) -> list[Flow]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []

    flows: list[Flow] = []
    seen: set[tuple] = set()

    candidates: list[ast.FunctionDef | ast.AsyncFunctionDef] = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    by_name: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for node in candidates:
        by_name.setdefault(node.name, []).append(node)

    funcs: dict[str, _PyFunc] = {}
    for name, nodes in by_name.items():
        if len(nodes) == 1:
            funcs[name] = _PyFunc(name=name, node=nodes[0], params=_py_params(nodes[0]))

    param_sources: dict[str, dict[int, Taint]] = {name: {} for name in funcs}

    # Three passes: sources in callees, then return summaries, then callers
    # that consume those summaries. Three is enough for any intra-file
    # call chain this lightweight engine claims to follow.
    for _ in range(3):
        for name, func in funcs.items():
            analyzer = _PyAnalyzer(rel, flows, funcs, seen, param_sources)
            analyzer.tainted = {
                func.params[index]: taint
                for index, taint in param_sources.get(name, {}).items()
                if index < len(func.params)
            }
            analyzer.block(func.node.body)
            func.return_taint = analyzer.return_taint
            for callee_name, arg_taints, _line in analyzer.calls:
                callee = funcs.get(callee_name)
                if callee is None:
                    continue
                for index, taint in enumerate(arg_taints):
                    if index < len(callee.params):
                        param_sources[callee_name].setdefault(index, taint)

        module_analyzer = _PyAnalyzer(rel, flows, funcs, seen, param_sources)
        module_analyzer.block(tree.body)

    return flows


# ── TypeScript / JavaScript ────────────────────────────────────────────────

@dataclass
class _JsFunc:
    name: str
    node: object
    body: object
    params: list[str]
    param_sources: dict[int, Taint] = field(default_factory=dict)
    return_taint: Taint | None = None


def _js_identifier(node) -> str:
    if node is None:
        return ""
    return node.text.decode("utf-8", "replace")


def _js_dotted(node) -> str:
    if node is None:
        return ""
    if node.type in {"identifier", "this", "property_identifier"}:
        return _js_identifier(node)
    if node.type == "member_expression":
        base = _js_dotted(node.children[0]) if node.children else ""
        prop_node = next(
            (c for c in reversed(node.children) if c.type == "property_identifier"),
            None,
        )
        prop = _js_identifier(prop_node)
        return f"{base}.{prop}" if base and prop else (prop or base)
    if node.type == "subscript_expression":
        return _js_dotted(node.children[0]) if node.children else ""
    if node.type == "call_expression":
        return _js_dotted(node.child_by_field_name("function"))
    return ""


def _js_params(function_node) -> list[str]:
    params_node = function_node.child_by_field_name("parameters")
    if params_node is None:
        for child in function_node.children:
            if child.type == "formal_parameters":
                params_node = child
                break
    if params_node is None:
        return []
    names: list[str] = []
    for child in params_node.children:
        if child.type == "identifier":
            names.append(_js_identifier(child))
        elif child.type in {"required_parameter", "optional_parameter"}:
            identifier = next(
                (c for c in child.children if c.type == "identifier"), None
            )
            if identifier is not None:
                names.append(_js_identifier(identifier))
    return names


def _js_function_name(node) -> str:
    if node.type in {"function_declaration", "method_definition"}:
        name = node.child_by_field_name("name")
        if name is not None:
            return _js_identifier(name)
        property_node = next(
            (c for c in node.children if c.type in {"identifier", "property_identifier"}),
            None,
        )
        return _js_identifier(property_node)
    if node.type == "variable_declarator":
        return _js_identifier(node.child_by_field_name("name"))
    return ""


class _JsAnalyzer:
    def __init__(
        self,
        rel: str,
        flows: list[Flow],
        funcs: dict[str, _JsFunc],
        seen: set[tuple],
        param_sources: dict[str, dict[int, Taint]],
    ):
        self.rel = rel
        self.flows = flows
        self.funcs = funcs
        self.seen = seen
        self.param_sources = param_sources
        self.tainted: dict[str, Taint] = {}
        self.return_taint: Taint | None = None
        self.calls: list[tuple[str, list[Taint], int]] = []

    def _report(self, taint: Taint, sink: str, line: int) -> None:
        key = (self.rel, taint.label, taint.line, sink, line)
        if key in self.seen:
            return
        self.seen.add(key)
        self.flows.append(
            Flow(
                file=self.rel,
                source=taint.label,
                source_line=taint.line,
                sink=sink,
                sink_line=line,
                severity=_severity_for_sink(sink),
                message=(
                    f"{taint.label} reaches {sink} at line {line} "
                    "without a recognised sanitizer"
                ),
                via=list(taint.via[-6:]),
            )
        )

    # ── expressions ──────────────────────────────────────────────────────

    def expr(self, node) -> Taint | None:
        if node is None:
            return None

        if node.type == "identifier":
            return self.tainted.get(_js_identifier(node))

        if node.type == "member_expression":
            dotted = _js_dotted(node)
            source = _source_for(dotted, JS_SOURCES)
            if source:
                return Taint(source, node.start_point[0] + 1, (dotted,))
            base = self.expr(node.children[0] if node.children else None)
            if base:
                return Taint(base.label, base.line, (*base.via, dotted.rsplit(".", 1)[-1]))
            return None

        if node.type == "subscript_expression":
            source = _source_for(_js_dotted(node), JS_SOURCES)
            if source:
                return Taint(source, node.start_point[0] + 1, (_js_dotted(node),))
            return self.expr(node.children[0] if node.children else None)

        if node.type == "call_expression":
            return self._call(node)

        if node.type == "new_expression":
            args = node.child_by_field_name("arguments")
            if args is not None:
                for arg in args.named_children:
                    taint = self.expr(arg)
                    if taint:
                        return taint
            return None

        if node.type == "assignment_expression":
            right = node.child_by_field_name("right")
            return self.expr(right)

        if node.type in {"parenthesized_expression", "await_expression",
                         "as_expression", "non_null_expression", "unary_expression",
                         "yield_expression"}:
            for child in node.named_children:
                taint = self.expr(child)
                if taint:
                    return taint
            return None

        if node.type == "template_string":
            for child in node.named_children:
                if child.type == "template_substitution":
                    for inner in child.named_children:
                        taint = self.expr(inner)
                        if taint:
                            return taint
            return None

        if node.type == "binary_expression":
            return (
                self.expr(node.child_by_field_name("left"))
                or self.expr(node.child_by_field_name("right"))
            )

        if node.type == "ternary_expression":
            return (
                self.expr(node.child_by_field_name("consequence"))
                or self.expr(node.child_by_field_name("alternative"))
            )

        if node.type in {"array", "object", "arguments"}:
            for child in node.named_children:
                taint = self.expr(child)
                if taint:
                    return taint
            return None

        if node.type == "pair":
            return self.expr(node.child_by_field_name("value"))

        if node.type == "spread_element":
            return self.expr(node.children[-1]) if node.children else None

        return None

    def _call(self, node) -> Taint | None:
        function_node = node.child_by_field_name("function")
        dotted = _js_dotted(function_node)
        source = _source_for(dotted, JS_SOURCES)
        if source:
            return Taint(source, node.start_point[0] + 1, (dotted,))

        args_node = node.child_by_field_name("arguments")
        args = list(args_node.named_children) if args_node is not None else []
        arg_taints = [taint for taint in (self.expr(arg) for arg in args) if taint]

        sink = _js_sink(dotted)
        if sink and arg_taints:
            self._report(arg_taints[0], sink, node.start_point[0] + 1)

        last = dotted.rsplit(".", 1)[-1] if dotted else ""
        if last in JS_SANITIZERS or dotted in JS_SANITIZERS:
            return None

        callee = self.funcs.get(dotted) or self.funcs.get(last)
        if callee is not None:
            self.calls.append((callee.name, arg_taints, node.start_point[0] + 1))
            return callee.return_taint

        return arg_taints[0] if arg_taints else None

    # ── statements ───────────────────────────────────────────────────────

    def block(self, node) -> None:
        if node is None:
            return
        for child in node.named_children:
            self.stmt(child)

    def stmt(self, node) -> None:
        if node.type in {"lexical_declaration", "variable_declaration"}:
            for child in node.named_children:
                if child.type == "variable_declarator":
                    self.stmt(child)
            return

        if node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value = node.child_by_field_name("value")
            taint = self.expr(value)
            for name in _js_declared_names(name_node):
                self._assign(name, taint)
            return

        if node.type == "expression_statement":
            child = node.named_children[0] if node.named_children else None
            if child is not None and child.type == "assignment_expression":
                self.stmt(child)
            else:
                self.expr(child)
            return

        if node.type == "assignment_expression":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            taint = self.expr(right)
            if left is not None and left.type == "member_expression":
                prop_node = next(
                    (c for c in reversed(left.children) if c.type == "property_identifier"),
                    None,
                )
                prop = _js_identifier(prop_node)
                if prop in {"innerHTML", "outerHTML"} and taint:
                    self._report(taint, prop, node.start_point[0] + 1)
            for name in _js_declared_names(left):
                self._assign(name, taint)
            return

        if node.type == "return_statement":
            taint = self.expr(node.named_children[0]) if node.named_children else None
            if taint and self.return_taint is None:
                self.return_taint = taint
            return

        if node.type in {"if_statement", "while_statement", "switch_statement",
                         "for_statement", "for_in_statement", "switch_case",
                         "switch_default", "catch_clause", "finally_clause"}:
            for child in node.named_children:
                self.stmt(child)
            return

        if node.type == "try_statement":
            for child in node.named_children:
                self.stmt(child)
            return

        if node.type in {"statement_block", "program", "switch_body"}:
            self.block(node)
            return

        if node.type in {"function_declaration", "method_definition",
                         "arrow_function", "function_expression"}:
            return

        if node.type == "throw_statement":
            self.expr(node.named_children[0] if node.named_children else None)
            return

        for child in node.named_children:
            if child.type in {
                "lexical_declaration", "variable_declaration", "expression_statement",
                "return_statement", "if_statement", "try_statement",
            }:
                self.stmt(child)
            else:
                self.expr(child)

    def _assign(self, name: str, taint: Taint | None) -> None:
        if not name:
            return
        if taint is None:
            self.tainted.pop(name, None)
        else:
            self.tainted[name] = Taint(taint.label, taint.line, (*taint.via, name))


def _js_declared_names(node) -> list[str]:
    if node is None:
        return []
    if node.type == "identifier":
        return [_js_identifier(node)]
    if node.type == "member_expression":
        return [_js_dotted(node)]
    if node.type in {"object_pattern", "array_pattern"}:
        names: list[str] = []
        for child in node.named_children:
            names.extend(_js_declared_names(child))
        return names
    return []


def _js_sink(dotted: str) -> str | None:
    last = dotted.rsplit(".", 1)[-1] if dotted else ""
    if last in {"eval", "Function"}:
        return last
    if last in {"setTimeout", "setInterval"}:
        return "eval"
    if dotted in {"document.write", "document.writeln"}:
        return "document.write"
    if dotted.startswith("child_process.") and last in {
        "exec", "execSync", "spawn", "spawnSync",
    }:
        return f"child_process.{last}"
    if last == "insertAdjacentHTML":
        return "insertAdjacentHTML"
    if last in {"query", "execute"} and "." in dotted:
        return last
    if dotted.startswith(("fs.", "fs.promises.")) and last in {
        "readFile", "readFileSync", "writeFile", "writeFileSync",
        "unlink", "unlinkSync", "createReadStream",
    }:
        return "open"
    if last in {"get", "post", "put", "delete", "fetch"} and dotted.startswith(
        ("fetch", "axios.", "http.", "https.", "request")
    ):
        return "fetch"
    if last == "redirect":
        return "redirect"
    return None


def analyze_javascript(source: bytes, rel: str) -> list[Flow]:
    try:
        from parsers.registry import get_parser
    except Exception:  # pragma: no cover - import cycle guard
        return []

    suffix = Path(rel).suffix.lower()
    parser = get_parser(suffix)
    if parser is None:
        return []

    try:
        tree = parser._parser.parse(source)  # noqa: SLF001 - reuse the grammar
        root = tree.root_node
    except Exception as exc:  # noqa: BLE001
        log.debug("taint: could not parse %s: %s", rel, exc)
        return []

    flows: list[Flow] = []
    seen: set[tuple] = set()

    candidates: list[tuple[str, object, object]] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in {
            "function_declaration", "method_definition", "arrow_function",
            "function_expression", "generator_function_declaration",
        }:
            name = _js_function_name(node)
            if not name and node.parent is not None and node.parent.type == "variable_declarator":
                name = _js_identifier(node.parent.child_by_field_name("name"))
            body = node.child_by_field_name("body")
            if name and body is not None:
                candidates.append((name, node, body))
            continue
        stack.extend(node.children)

    funcs: dict[str, _JsFunc] = {}
    for name, node, body in candidates:
        if name not in funcs:
            funcs[name] = _JsFunc(name=name, node=node, body=body, params=_js_params(node))

    param_sources: dict[str, dict[int, Taint]] = {name: {} for name in funcs}

    for _ in range(3):
        for name, func in funcs.items():
            analyzer = _JsAnalyzer(rel, flows, funcs, seen, param_sources)
            analyzer.tainted = {
                func.params[index]: taint
                for index, taint in param_sources.get(name, {}).items()
                if index < len(func.params)
            }
            analyzer.block(func.body)
            func.return_taint = analyzer.return_taint
            for callee_name, arg_taints, _line in analyzer.calls:
                callee = funcs.get(callee_name)
                if callee is None:
                    continue
                for index, taint in enumerate(arg_taints):
                    if index < len(callee.params):
                        param_sources[callee_name].setdefault(index, taint)

        module_analyzer = _JsAnalyzer(rel, flows, funcs, seen, param_sources)
        module_analyzer.block(root)

    return flows


# ── Repository scan ────────────────────────────────────────────────────────

def analyze_source(source: str | bytes, rel: str) -> list[Flow]:
    """Analyze one file's contents. Unknown languages return []."""
    suffix = Path(rel).suffix.lower()
    try:
        if suffix == ".py":
            text = source.decode("utf-8", "replace") if isinstance(source, bytes) else source
            return analyze_python(text, rel)
        if suffix in {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"}:
            data = source.encode("utf-8") if isinstance(source, str) else source
            return analyze_javascript(data, rel)
    except Exception as exc:  # noqa: BLE001 - a scan must never break the API
        log.warning("taint analysis failed for %s: %s", rel, exc)
    return []


def scan_repository(root: str | Path) -> list[dict]:
    """
    Scan a repository tree and return taint flags, highest severity first.

    Bounded in both files and bytes so a security scan cannot become a
    denial-of-service on a huge monorepo.
    """
    root_path = Path(root)
    flags: list[dict] = []
    seen: set[tuple] = set()
    files = 0

    for path in root_path.rglob("*"):
        if files >= MAX_FILES:
            break
        if not path.is_file():
            continue
        rel = str(path.relative_to(root_path)).replace("\\", "/")
        if any(part in SKIP_DIRS for part in rel.split("/")):
            continue
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"}:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            source = path.read_bytes()
        except OSError:
            continue
        files += 1
        for flow in analyze_source(source, rel):
            key = (flow.file, flow.source_line, flow.sink, flow.sink_line)
            if key in seen:
                continue
            seen.add(key)
            flags.append(flow.to_flag())

    flags.sort(key=lambda flag: (
        _SEVERITY_ORDER.get(flag.get("severity", "low"), 9),
        flag.get("file", ""),
        int(flag.get("line") or 0),
    ))
    return flags
