"""Deep handler-scope + call-graph verification (file-based, no shell quoting issues)."""
from __future__ import annotations

import re
import pathlib

js = pathlib.Path("frontend/static/app.js").read_text(encoding="utf-8")

problems: list[str] = []

# --- 1. brace-matched handler extraction -------------------------------------
def handler_spans(src: str):
    spans = []
    pat = re.compile(r'(?:\.onclick\s*=\s*function|addEventListener\(\s*"click"\s*,\s*function)\s*\([^)]*\)\s*\{')
    for m in pat.finditer(src):
        start = m.end() - 1
        depth = 0
        for i, ch in enumerate(src[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    spans.append((m.start(), i + 1))
                    break
    return spans

def enclosing_scope(src: str, pos: int) -> set[str]:
    """Collect `var x` / param names from every enclosing function before pos."""
    names: set[str] = set()
    # walk backwards for `function (...)` and their bodies: simplified —
    # collect ALL var declarations that open before pos and whose function hasn't closed.
    # Simpler heuristic: all `var name` occurring before pos at any depth + params of functions started before pos.
    for m in re.finditer(r"\bfunction\s*[\w$]*\s*\(([^)]*)\)", src[:pos]):
        params = [p.strip() for p in m.group(1).split(",") if p.strip()]
        names.update(params)
    for m in re.finditer(r"\bvar\s+([A-Za-z_$][\w$]*)", src[:pos]):
        names.add(m.group(1))
    # catch/forEach params: .forEach(function (item, i)
    return names

spans = handler_spans(js)
print(f"handlers_found={len(spans)}")

check_names = ("tx", "cert", "item", "ds", "ex", "selected", "lastPayload", "requestCounter")
for start, end in spans:
    body = js[start:end]
    sig = js[start : start + 70].replace("\n", " ")
    scope = enclosing_scope(js, start)
    # locals inside body
    body_vars = set(re.findall(r"\bvar\s+([A-Za-z_$][\w$]*)", body))
    body_params = set()
    pm = re.search(r"function\s*[\w$]*\s*\(([^)]*)\)", body)
    if pm:
        body_params.update(p.strip() for p in pm.group(1).split(",") if p.strip())
    for name in check_names:
        if re.search(rf"(?<![\w$.]){name}\b", body):
            if name in body_vars or name in body_params or name in scope:
                continue
            problems.append(f"UNSCOPED `{name}` in handler: {sig}...")

# --- 2. real function calls ---------------------------------------------------
defined = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", js))
defined |= set(re.findall(r"\bvar\s+([A-Za-z_$][\w$]*)\s*=\s*function", js))
# calls in code (strip strings + comments first)
def strip_literals(src: str) -> str:
    src = re.sub(r"//[^\n]*", "", src)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r'"(?:\\.|[^"\\])*"', '""', src)
    src = re.sub(r"'(?:\\.|[^'\\])*'", "''", src)
    src = re.sub(r"`(?:\\.|[^`\\])*`", "``", src)
    return src

code = strip_literals(js)
builtins = {
    "if", "for", "while", "switch", "catch", "return", "typeof", "new", "try",
    "Number", "String", "Boolean", "Array", "Object", "JSON", "Math", "Date",
    "parseInt", "parseFloat", "isNaN", "Error", "Function", "RegExp", "Promise",
    "FormData", "URLSearchParams", "setTimeout", "clearTimeout", "encodeURIComponent",
    "fetch", "console", "alert", "confirm", "prompt", "window", "document",
}
keywords = {"function", "var", "let", "const", "else", "do", "in", "of", "await"}
calls = set(re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(", code))
undef = sorted(c for c in calls if c not in defined and c not in builtins and c not in keywords)
if undef:
    problems.append(f"possibly undefined functions: {undef}")

# --- 3. fetch paths vs routes (prefix-aware) ---------------------------------
main_py = pathlib.Path("backend/main.py").read_text(encoding="utf-8")
route_paths = set(re.findall(r'@app\.(?:get|post|delete|put)\(\s*"([^"]+)"', main_py))
fetches = re.findall(r'fetch\(\s*"([^"]+)"', js)
fetches += re.findall(r"fetch\(\s*'([^']+)'", js)

def route_matches(path: str) -> bool:
    if path in route_paths:
        return True
    for rp in route_paths:
        pat = "^" + re.sub(r"\{[^}]+\}", "[^/]+", re.escape(rp).replace(r"\{", "{").replace(r"\}", "}")) + "$"
        if re.match(pat, path):
            return True
    # prefix dynamic: "/datasets/" used with + id — ensure a param route exists under it
    if path.endswith("/"):
        base = path.rstrip("/")
        if any(rp.startswith(base + "/{") or rp == base for rp in route_paths):
            return True
    return False

for f in sorted(set(fetches)):
    if not route_matches(f):
        problems.append(f"fetch path without backend route: {f}")

# --- 4. every addEventListener target id exists ------------------------------
html = pathlib.Path("frontend/static/index.html").read_text(encoding="utf-8")
html_ids = set(re.findall(r'id="([^"]+)"', html))
for m in re.finditer(r'\$\(\s*"([^"]+)"\s*\)\.addEventListener', js):
    if m.group(1) not in html_ids and not m.group(1).startswith("state-"):
        problems.append(f"addEventListener on missing id: {m.group(1)}")

# --- 5. handlers bound exactly once (no double/none) -------------------------
for bid in ("wi-btn", "break-btn", "retry-btn"):
    n = len(re.findall(rf'\$\("{bid}"\)\s*\.addEventListener|\$\("{bid}"\)\s*\.onclick\s*=', js))
    print(f"bind_{bid}={n}")
    if n == 0:
        problems.append(f"{bid} has no bound handler")

print("=== PROBLEMS ===")
for p in problems:
    print("P:", p)
if not problems:
    print("none")
