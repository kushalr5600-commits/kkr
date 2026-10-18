"""Static consistency sweep: JS <-> HTML <-> API route cross-references.

Catches the bug class: missing elements, undefined functions, dead bindings,
frontend fetch paths that do not exist on the backend.

Handler *scope* checking (ReferenceError closure bugs like the wi-btn class)
is done by scripts/sweep_handlers.py (brace-matched, param-aware).
API response *field* contracts are done by scripts/sweep_api_contract.py.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(".")
js = (ROOT / "frontend" / "static" / "app.js").read_text(encoding="utf-8")
html = (ROOT / "frontend" / "static" / "index.html").read_text(encoding="utf-8")
main_py = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

problems: list[str] = []
notes: list[str] = []

# ---- 1. $("id") lookups must exist in HTML or be created in JS -------------
html_ids = set(re.findall(r'id="([^"]+)"', html))
js_created_ids = set(re.findall(r'\.id\s*=\s*"([^"]+)"', js))
js_created_ids |= set(re.findall(r'setAttribute\(\s*"id"\s*,\s*"([^"]+)"', js))
state_ids = {f"state-{s}" for s in ["idle", "busy", "error", "result"]}

used_ids = set(re.findall(r'\$\(\s*"([^"]+)"\s*\)', js))
if '"state-" +' in js or "'state-' +" in js:
    used_ids |= state_ids

known_ids = html_ids | js_created_ids | state_ids
missing = sorted(i for i in used_ids if i not in known_ids)
if missing:
    problems.append(f"JS references ids not in HTML/JS: {missing}")

unused_html = sorted(i for i in html_ids if i not in used_ids)
# panels are addressed via .side-item[data-panel=...] + .panel-group, not $()
data_panels = set(re.findall(r'data-panel="([^"]+)"', html))
unused_real = [i for i in unused_html if i not in data_panels and not i.startswith("panel-")]
if unused_real:
    notes.append(f"HTML ids never looked up via $(): {unused_real}")
if unused_html:
    notes.append(f"(dynamic/positional ids ok): {sorted(i for i in unused_html if i not in unused_real)}")

# ---- 2. function definitions vs calls in app.js (literals stripped) --------
def strip_literals(src: str) -> str:
    src = re.sub(r"//[^\n]*", "", src)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r'"(?:\\.|[^"\\])*"', '""', src)
    src = re.sub(r"'(?:\\.|[^'\\])*'", "''", src)
    src = re.sub(r"`(?:\\.|[^`\\])*`", "``", src)
    return src

code = strip_literals(js)
defined = set(re.findall(r'function\s+([A-Za-z_$][\w$]*)\s*\(', js))
defined |= set(re.findall(r'var\s+([A-Za-z_$][\w$]*)\s*=\s*function', js))
defined |= set(re.findall(r'([A-Za-z_$][\w$]*)\s*=\s*function\s*\(', js))
builtins = {
    "if", "for", "while", "switch", "catch", "return", "typeof", "function",
    "Number", "String", "Boolean", "Array", "Object", "JSON", "Math", "Date",
    "parseInt", "parseFloat", "setTimeout", "clearTimeout", "Error",
    "Function", "RegExp", "Promise", "encodeURIComponent", "decodeURIComponent",
    "isNaN", "console", "fetch", "alert", "confirm", "prompt",
    "FormData", "URLSearchParams", "window", "document",
}
keywords = {"do", "else", "try", "new", "await", "yield", "var", "let", "const", "in", "of", "instanceof"}
call_pat = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(")
calls = set(call_pat.findall(code))
undefined_calls = sorted(c for c in calls if c not in defined and c not in builtins and c not in keywords)
if undefined_calls:
    problems.append(f"app.js calls possibly-undefined functions: {undefined_calls}")

# ---- 3. fetch() paths vs FastAPI routes (prefix-aware) ---------------------
fetch_paths = set(re.findall(r'fetch\(\s*[`"\']([^`"\']+)[`"\']', js))
dynamic_fetch = set(re.findall(r'fetch\(\s*"([^"]+)"\s*\+', js))
routes = set(re.findall(r'@app\.(get|post|delete|put)\(\s*"([^"]+)"', main_py))
route_paths = {p for _m, p in routes}


def route_matches(path: str) -> bool:
    if path in route_paths:
        return True
    if path.endswith("/"):
        base = path.rstrip("/")
        if any(rp == base or rp.startswith(base + "/{") for rp in route_paths):
            return True
    for rp in route_paths:
        pat = "^" + re.sub(r"\{[^}]+\}", "[^/]+", rp) + "$"
        if re.match(pat, path):
            return True
    return False


for path in sorted(fetch_paths | dynamic_fetch):
    if "{" in path:
        continue
    if not route_matches(path):
        problems.append(f"frontend fetch path has no backend route: {path}")

# ---- 4. HTML buttons never referenced in app.js ----------------------------
html_buttons = re.findall(r'<button[^>]*id="([^"]+)"[^>]*>', html)
for bid in html_buttons:
    if f'"{bid}"' not in js and f"'{bid}'" not in js:
        problems.append(f"HTML button #{bid} never referenced in app.js")

print("=== PROBLEMS ===")
if problems:
    for p in problems:
        print("P:", p)
else:
    print("none")
print("=== NOTES ===")
for n in notes:
    print("N:", n)
print(f"ids_used={len(used_ids)} html_ids={len(html_ids)} fetch_paths={sorted(fetch_paths | dynamic_fetch)}")
