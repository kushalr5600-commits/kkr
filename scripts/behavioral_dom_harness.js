// Behavioral harness: run the real app.js in a minimal DOM stub and exercise
// the user flows. Catches ReferenceError/TypeError dead-handlers like wi-btn.
// Usage: node scripts/behavioral_dom_harness.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.join(__dirname, "..");
const jsSrc = fs.readFileSync(path.join(ROOT, "frontend", "static", "app.js"), "utf8");
const htmlSrc = fs.readFileSync(path.join(ROOT, "frontend", "static", "index.html"), "utf8");

// ---------- build DOM from index.html ids ----------
const htmlIds = [...htmlSrc.matchAll(/id="([^"]+)"/g)].map((m) => m[1]);
const classById = {};
for (const m of htmlSrc.matchAll(/<(\w+)[^>]*id="([^"]+)"[^>]*class="([^"]+)"/g)) classById[m.id] = m[3];

class ClassList {
  constructor(el) { this.el = el; this.set = new Set(); }
  add(...c) { c.forEach((x) => this.set.add(x)); }
  remove(...c) { c.forEach((x) => this.set.delete(x)); }
  contains(c) { return this.set.has(c); }
}
class El {
  constructor(tag, id) {
    this.tagName = (tag || "div").toUpperCase();
    this.id = id || "";
    this.children = [];
    this.listeners = {};
    this.style = { setProperty() {}, width: "" };
    this.dataset = {};
    this.classList = new ClassList(this);
    this._text = "";
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.type = "";
    this.files = [];
    this.options = [];
    this.selectedIndex = 0;
    this.attributes = {};
    this.className = "";
    if (this.id && classById[this.id]) {
      this.className = classById[this.id];
      classById[this.id].split(/\s+/).filter(Boolean).forEach((c) => this.classList.add(c));
    }
  }
  get textContent() { return this._text; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get innerHTML() { return this._text; }
  set innerHTML(v) { this.textContent = v; }
  appendChild(c) { this.children.push(c); if (this.options && this.tagName === "SELECT") this.options.push(c); return c; }
  removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); return c; }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  removeEventListener(type, fn) { const a = this.listeners[type] || []; const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); }
  setAttribute(k, v) { this.attributes[k] = String(v); if (k === "id") this.id = String(v); }
  getAttribute(k) { return k in this.attributes ? this.attributes[k] : (k === "data-panel" ? this.dataset.panel || null : null); }
  dispatch(type, ev) {
    const e = Object.assign({ type, preventDefault() {}, target: this }, ev || {});
    for (const fn of this.listeners[type] || []) fn(e);
    if (type === "click" && typeof this.onclick === "function") this.onclick(e);
    return e;
  }
  click() { try { this.dispatch("click"); } catch (err) { throw err; } }
  querySelector() { return null; }
  querySelectorAll() { return []; }
}

const registry = {};
for (const id of htmlIds) registry[id] = new El("div", id);
// tx-select is a select with options array behavior
registry["tx-select"].tagName = "SELECT";

const sideItems = ["panel-explorer", "panel-studio", "panel-challenge", "panel-experiments", "panel-certs"];
const sideItemEls = sideItems.map((p, i) => {
  const e = new El("button", "");
  e.classList.add("side-item");
  if (i === 0) e.classList.add("active");
  e.dataset.panel = p;
  e.attributes["data-panel"] = p;
  return e;
});
const panelEls = sideItems.map((p, i) => {
  const e = new El("section", p);
  e.classList.add("panel-group");
  if (i === 0) { e.classList.add("active"); e.hidden = false; } else { e.hidden = true; }
  return e;
});

const document = {
  getElementById(id) { return registry[id] || null; },
  createElement(tag) { return new El(tag, ""); },
  createTextNode(t) { const e = new El("#text"); e._text = String(t); return e; },
  querySelector(sel) {
    const m = sel.match(/data-panel="([^"]+)"/);
    if (m && sel.includes(".side-item")) return sideItemEls.find((e) => e.dataset.panel === m[1]) || null;
    return null;
  },
  querySelectorAll(sel) {
    if (sel === ".side-item") return sideItemEls.slice();
    if (sel === ".panel-group") return panelEls.slice();
    return [];
  },
  get body() { return new El("body"); },
};

// ---------- fetch mock ----------
const calls = [];
const FIX = {
  "/health": { status: "ok", runtime: "local", architecture: "AMD64", version: "0.1.0-prebuild", model_backend: "numpy", gate_threshold: "0.60", python: "3.12.10", otel_enabled: "0", otel_package: "0", dataset_studio: "enabled", openml_client: "0" },
  "/transactions": [
    { transaction: { id: "TX-DEMO-0001", account_id: "A", amount: 100, timestamp: "2026-01-01T00:00:00Z", transaction_type: "card_payment" }, hint: "Fixed demo" },
    { transaction: { id: "TX-00300", account_id: "B", amount: 5000, timestamp: "2026-01-01T00:00:00Z", transaction_type: "wire_transfer" }, hint: "selected_fails" },
  ],
  "/experiments": [{ run_id: "EX-1", dataset_id: "DS-1", label_semantics: "fraud", rows_scored: 13, simulation_rate: 0, metrics: {} }],
  "/datasets": [],
  "/datasets/registry": { entries: [], openml: {}, policy: "meta" },
  "/counterexample/TX-00108-B": { transaction_id: "TX-00108-B", gate_selected: false, missed_failure: true, stress_measured: true, kind: "showcase" },
};
const explainPayload = {
  policy_version: "1.0.0",
  technical_detail: "I = 0.30*M + 0.30*D + 0.25*A + 0.15*U",
  contributions: [
    { code: "M", name: "magnitude", signal: 0.1, weight: 0.3, weighted: 0.03, source: "statistical" },
    { code: "D", name: "dependency", signal: 0.8, weight: 0.3, weighted: 0.24, source: "graph_derived" },
    { code: "A", name: "anomaly", signal: 0.5, weight: 0.25, weighted: 0.125, source: "ml_model" },
    { code: "U", name: "uncertainty", signal: 0.1, weight: 0.15, weighted: 0.015, source: "ml_model" },
  ],
  timeline: [],
  scenarios_ran: [],
  ai_signals: {
    available: true, model_backend: "numpy", model_versions: { backend: "numpy" },
    fitted_on_split: "calibration", n_fit_samples: 100, n_fit_failures: 10,
    anomaly: { raw: -0.1, normalized_a: 0.5, model_name: "m", calibration_method: "empirical_cdf", calibration_split: "calibration", range: { within_supported_range: true }, caveats: ["not a fraud probability"] },
    risk: { failure_probability_mean: 0.2, member_std: 0.05, normalized_u: 0.1, model_name: "r", uncertainty_normalization: "std/0.5", caveats: ["not a calibrated confidence"] },
    signal_sources: { M: "statistical", D: "graph_derived", A: "ml_model", U: "ml_model" },
    gate: { score: 0.41, threshold: 0.6, selected: false, formula: "I=...", simulation_executed: false },
    plain_language: "plain", technical_detail: "tech",
    unknowns: ["anomaly score is not a fraud probability"],
    measured_stress_failures: null,
  },
  certificate: {
    certificate_id: "CERT-1", trace_id: "TR-1", status: "NO_SIMULATION", transaction_id: "TX-DEMO-0001",
    decision_description: "demo", impact_score: { transaction_id: "TX-DEMO-0001", signals: { magnitude: 0.1, dependency: 0.8, anomaly: 0.5, uncertainty: 0.1 }, score: 0.41, gate_decision: false },
    forks_tested: [], fragility: [], recommended_action: "ALLOW_NORMAL_PATH",
    evidence: ["No deep simulation was run", "LIMITATION: demo"], runtime: { runtime: "local", architecture: "AMD64", model_versions: { backend: "numpy" } },
  },
  plain_language: "demo", decision_description: "demo", score: 0.41,
};
const whatIfPayload = {
  research_only: true, disclaimer: "research",
  original: { transaction: { id: "TX-DEMO-0001", amount: 2406.59 }, account_baseline: {}, gate: { score: 0.41, selected: false }, signals: { M: 0.1, D: 0.8, A: 0.5, U: 0.1 } },
  hypothetical: { transaction: { id: "TX-DEMO-0001", amount: 50000 }, account_baseline: {}, gate: { score: 0.62, selected: true }, plain_language: "hyp" },
  changes: { amount: 50000 },
  delta: { score: 0.21, selected_before: false, selected_after: true, A: 0.1, M: 0.4 },
};

function mockFetch(url, opts) {
  calls.push({ url, method: (opts && opts.method) || "GET", body: (opts && opts.body) || null });
  let data;
  const method = (opts && opts.method) || "GET";
  if (method === "POST" && url === "/explain") data = explainPayload;
  else if (method === "POST" && url === "/research/what-if") data = whatIfPayload;
  else if (method === "POST" && url === "/analyze") data = explainPayload.certificate;
  else data = FIX[url];
  if (data === undefined) data = { error_message: "no fixture for " + url };
  return Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve(JSON.parse(JSON.stringify(data))),
    text: () => Promise.resolve(JSON.stringify(data)),
  });
}

// ---------- sandbox ----------
const errors = [];
const sandbox = {
  document,
  fetch: mockFetch,
  console,
  setTimeout,
  clearTimeout,
  FormData: class { append() {} },
  URLSearchParams,
  Number, String, JSON, Math, Date, Array, Object, Promise, Error, RegExp, isNaN, parseInt, parseFloat,
  encodeURIComponent, decodeURIComponent,
  window: {},
  alert: (m) => { calls.push({ url: "alert", body: m }); },
};
sandbox.window = sandbox;
vm.createContext(sandbox);

function step(name, fn) {
  try { fn(); return null; }
  catch (e) { errors.push(`${name}: ${e.name}: ${e.message}`); return e; }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  // 1. script init
  step("init", () => vm.runInContext(jsSrc, sandbox, { filename: "app.js" }));
  await sleep(50); // let health/transactions promises resolve

  // 2. transactions loaded -> break + what-if enabled?
  const wi = registry["wi-btn"];
  const br = registry["break-btn"];
  if (wi.disabled) errors.push("wi-btn still disabled after transactions loaded");
  if (br.disabled) errors.push("break-btn still disabled after transactions loaded");

  // 3. click BREAK MY DECISION
  step("click break-btn", () => br.dispatch("click"));
  await sleep(80);
  const resultShown = registry["state-result"].hidden === false;
  if (!resultShown) errors.push("state-result not shown after analyze");
  if (wi.disabled) errors.push("wi-btn disabled after result render");

  // 4. enter override + click Run what-if (THE BUG FLOW)
  registry["wi-amount"].value = "50000";
  step("click wi-btn", () => wi.dispatch("click"));
  await sleep(80);
  const wiCall = calls.find((c) => c.url === "/research/what-if");
  if (!wiCall) errors.push("Run what-if produced NO fetch to /research/what-if");
  else {
    const body = JSON.parse(wiCall.body);
    if (!body.overrides || body.overrides.amount !== 50000) errors.push("what-if body wrong: " + wiCall.body);
    if (!body.demo_mode && !body.transaction) errors.push("what-if body missing transaction/demo_mode");
  }
  const outText = registry["wi-out"].textContent;
  if (!outText || outText.indexOf("score") === -1) errors.push("wi-out not populated with result: " + JSON.stringify(outText));

  // 5. what-if with no override -> message, no crash
  registry["wi-amount"].value = "";
  registry["wi-type"].value = "";
  step("click wi-btn empty", () => wi.dispatch("click"));
  await sleep(20);
  if (registry["wi-out"].textContent.indexOf("Enter at least one override") === -1)
    errors.push("empty-override message missing: " + registry["wi-out"].textContent);

  // 6. nav to every panel
  for (const item of sideItemEls) {
    step("nav " + item.dataset.panel, () => item.dispatch("click"));
  }

  // 7. counterexample showcase (via direct fetch path used by UI if bound)
  // 8. retry button
  step("retry", () => registry["retry-btn"].dispatch("click"));

  // 9. selector change
  step("tx change", () => {
    registry["tx-select"].selectedIndex = 1;
    registry["tx-select"].dispatch("change");
  });
  await sleep(10);
  if (registry["wi-btn"].disabled) errors.push("wi-btn disabled after selecting a valid transaction");

  // 10. error path: showError via unknown — skip; check break re-enabled
  if (br.disabled) errors.push("break-btn disabled after flows (should be re-enabled)");

  // report
  console.log("calls:", calls.filter((c) => c.url !== "alert").map((c) => c.method + " " + c.url).join(" | "));
  if (errors.length) {
    console.log("ERRORS(" + errors.length + "):");
    errors.forEach((e) => console.log("  X " + e));
    process.exit(1);
  }
  console.log("BEHAVIORAL_HARNESS: ALL_FLOWS_OK");
  process.exit(0);
})().catch((e) => { console.error("HARNESS_CRASH", e); process.exit(2); });
