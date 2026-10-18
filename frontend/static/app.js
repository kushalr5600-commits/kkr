// BLACKBOX dashboard. Presentation only: it collects, sends and renders.
// It never computes M/D/A/U, the gate score, fragility, evidence or the action.
// Explanations come from POST /explain. Green = successful execution only —
// never used to imply safety when simulation was skipped (amber/red there).
(function () {
  "use strict";

  var DEMO_ID = null;
  var THRESHOLD = 0.6;
  var POLICY_VERSION = null;
  var requestCounter = 0;
  var selected = null;
  var lastPayload = null;
  var certificates = [];
  var datasetsCache = [];
  var healthCache = null;

  var $ = function (id) { return document.getElementById(id); };
  var states = ["idle", "busy", "error", "result"];

  function show(name) {
    states.forEach(function (s) { $("state-" + s).hidden = s !== name; });
  }
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function fmt(x, d) { return Number(x).toFixed(d === undefined ? 2 : d); }
  function unknown() { return "Unknown"; }
  function numOrUnknown(x, d) {
    return (x === null || x === undefined || Number.isNaN(Number(x))) ? unknown() : fmt(x, d);
  }

  // ------------------------------------------------------------------ nav
  function initNav() {
    var items = document.querySelectorAll(".side-item");
    Array.prototype.forEach.call(items, function (item) {
      item.addEventListener("click", function () {
        Array.prototype.forEach.call(items, function (i) { i.classList.remove("active"); });
        document.querySelectorAll(".panel-group").forEach(function (p) {
          p.hidden = true;
          p.classList.remove("active");
        });
        item.classList.add("active");
        var panel = $(item.getAttribute("data-panel"));
        panel.hidden = false;
        panel.classList.add("active");
        var titles = {
          "panel-explorer": ["Decision Explorer", "Inspect how BLACKBOX made this decision. View the full evidence, model outputs, and explanation."],
          "panel-studio": ["Dataset Studio", "Guided import: upload, preview quality, map columns, set label semantics."],
          "panel-challenge": ["Challenge Lab", "Reproducible gate-selection benchmarks with explicit label spaces."],
          "panel-experiments": ["Experiments", "Run history with dataset fingerprint and policy provenance."],
          "panel-certs": ["Certificates", "Decision Certificates issued this session."]
        };
        var t = titles[item.getAttribute("data-panel")] || ["", ""];
        $("page-title").textContent = t[0];
        $("page-sub").textContent = t[1];
        if (item.getAttribute("data-panel") === "panel-studio") loadDatasets();
        if (item.getAttribute("data-panel") === "panel-challenge") loadChallenge();
        if (item.getAttribute("data-panel") === "panel-experiments") loadExperiments();
        if (item.getAttribute("data-panel") === "panel-certs") loadCertList();
      });
    });
  }

  // ---------------------------------------------------------------- loading
  function loadHealth() {
    fetch("/health").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (h) {
      healthCache = h;
      if (h.gate_threshold) THRESHOLD = parseFloat(h.gate_threshold);
      $("runtime").textContent = "runtime: " + h.runtime + " · " + h.architecture + " · models: " + h.model_backend;
      // On the LinuxONE guest (SSH demo) the chip becomes a pulsing mainframe
      // badge: "runtime: linuxone · s390x · models: …".
      var rtChip = $("runtime");
      rtChip.className = h.runtime === "linuxone" ? "chip mainframe" : "chip";
      rtChip.title = h.runtime === "linuxone"
        ? "GET /health · IBM LinuxONE (s390x) — live over SSH"
        : "GET /health";
      $("policy-thr").textContent = fmt(THRESHOLD);
      // Policy card is backend-driven from /health (F-036) — the active
      // version/mode/formula render on first paint, never hardcoded in JS.
      if (h.policy_version) {
        POLICY_VERSION = h.policy_version;
        $("policy-version").textContent = "v" + h.policy_version;
      }
      if (h.policy_formula) $("policy-formula").textContent = h.policy_formula;
      if (h.policy_mode) {
        var polName = h.policy_mode === "interaction_aware" ? "INTERACTION-AWARE" : "FROZEN";
        $("policy-pill").textContent = polName;
        $("policy-pill").className = "pill ok";
        if ($("policy-mode")) $("policy-mode").textContent = "Impact Gate · " + polName;
      }
    }).catch(function () {
      healthCache = null;
      $("runtime").textContent = "runtime: unreachable";
      $("runtime").className = "chip";
      $("policy-thr").textContent = unknown();
    });
  }

  function loadTransactions() {
    fetch("/transactions").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (items) {
      var sel = $("tx-select");
      sel.textContent = "";
      if (!items || !items.length) {
        sel.appendChild(el("option", null, "No transactions"));
        $("break-btn").disabled = true;
        $("wi-btn").disabled = true;
        return;
      }
      items.forEach(function (item, i) {
        var tx = item.transaction;
        if (i === 0) DEMO_ID = tx.id;
        var opt = el("option", null, tx.id + " — " + item.hint);
        opt.value = String(i);
        opt._tx = tx;
        sel.appendChild(opt);
        if (i === 0) {
          selected = tx;
          $("break-btn").disabled = false;
        }
      });
      sel.addEventListener("change", function () {
        var opt = sel.options[sel.selectedIndex];
        selected = opt && opt._tx ? opt._tx : null;
        $("break-btn").disabled = !selected;
        $("wi-btn").disabled = !selected;
      });
      $("wi-btn").disabled = false;
    }).catch(function (e) {
      showError("Could not load transactions: " + e.message, null);
    });
  }

  // ----------------------------------------------------------------- analyze
  function analyze() {
    if (!selected) return;
    var mine = ++requestCounter;
    var tx = selected;
    $("busy-tx").textContent = tx.id;
    $("busy-label").textContent = "Running Impact Gate preflight on";
    $("state-result").textContent = "";
    show("busy");
    $("break-btn").disabled = true;

    var body = tx.id === DEMO_ID ? { demo_mode: true } : { transaction: tx, demo_mode: false };
    fetch("/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.text().then(function (text) {
        var data;
        try { data = text ? JSON.parse(text) : {}; }
        catch (parseErr) { data = { error_message: "Non-JSON response (HTTP " + r.status + ")" }; }
        return { ok: r.ok, data: data };
      });
    }).then(function (res) {
      if (mine !== requestCounter) return;
      if (!res.ok) {
        var d = res.data.detail || res.data;
        showError((d && d.error_message) || JSON.stringify(d), d && d.trace_id);
      } else {
        lastPayload = res.data;
        rememberCertificate(res.data.certificate || res.data);
        renderExplain(res.data);
      }
    }).catch(function (e) {
      if (mine === requestCounter) showError("Network error: " + e.message, null);
    }).then(function () {
      if (mine === requestCounter) $("break-btn").disabled = false;
    });
  }

  function rememberCertificate(cert) {
    if (!cert || !cert.certificate_id) return;
    certificates = certificates.filter(function (c) { return c.certificate_id !== cert.certificate_id; });
    certificates.unshift(cert);
    if (certificates.length > 30) certificates.pop();
  }

  // Client-side .json download of an issued Decision Certificate (F-040).
  // The certificate is exactly what the API returned — no re-serialization
  // of values, just pretty-printed for human inspection.
  function downloadJson(obj, filename) {
    var text = JSON.stringify(obj, null, 2);
    var blob = new Blob([text], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  }

  function certFilename(cert) {
    return "BLACKBOX-" + (cert && cert.certificate_id ? cert.certificate_id : "certificate") + ".json";
  }

  function showError(message, trace) {
    $("error-msg").textContent = message;
    $("error-trace").textContent = trace || "n/a";
    show("error");
    $("break-btn").disabled = !selected;
  }

  // ------------------------------------------------------------------ render
  function renderExplain(payload) {
    var cert = payload.certificate || payload;
    if (!cert.impact_score) {
      showError("Response missing certificate fields", null);
      return;
    }
    lastPayload = payload;
    var root = $("state-result");
    root.textContent = "";

    if (payload.policy_version) {
      POLICY_VERSION = payload.policy_version;
      $("policy-version").textContent = "v" + payload.policy_version;
    }
    if (payload.formula) {
      // Backend-provided short formula (interaction-aware or frozen).
      $("policy-formula").textContent = payload.formula;
    } else if (payload.technical_detail) {
      $("policy-formula").textContent = payload.technical_detail;
    }
    if (payload.policy_mode) {
      // Reflect the policy actually used — never a hardcoded "frozen" label.
      var modePill = $("policy-pill");
      var modeName = payload.policy_mode === "interaction_aware" ? "INTERACTION-AWARE" : "FROZEN";
      if (modePill) { modePill.textContent = modeName; modePill.className = "pill ok"; }
      if ($("policy-mode")) $("policy-mode").textContent = "Impact Gate · " + modeName;
    }
    $("view-cert").hidden = false;
    $("view-cert-id").textContent = cert.certificate_id || "—";
    $("view-cert").onclick = function (e) {
      e.preventDefault();
      document.querySelector('.side-item[data-panel="panel-certs"]').click();
      loadCertList(cert.certificate_id);
    };
    var dlBtn = $("dl-cert");
    dlBtn.hidden = false;
    dlBtn.onclick = function () { downloadJson(cert, certFilename(cert)); };

    // Score vs threshold — prominent. The gate decision is RENDERED from the
    // backend (gate_decision); the frontend never recomputes it.
    var scoreCard = el("section", "panel card score-card");
    scoreCard.appendChild(el("h3", null, "Impact Gate Analysis"));
    var dial = el("div", "dial");
    var ring = el("div", "dial-ring");
    var pct = Math.min(1, Math.max(0, Number(cert.impact_score.score) / Math.max(THRESHOLD, 1e-9)));
    ring.style.setProperty("--p", String(Math.min(360, pct * 360)) + "deg");
    var center = el("div", "dial-center");
    center.appendChild(el("div", "dial-score mono", fmt(cert.impact_score.score, 3)));
    center.appendChild(el("div", "dial-label", "Score"));
    ring.appendChild(center);
    dial.appendChild(ring);
    scoreCard.appendChild(dial);
    var above = !!cert.impact_score.gate_decision;
    var thrBadge = el("span", "pill " + (above ? "ok" : "warn"),
      above ? "Above threshold — simulated" : "Below threshold — simulation skipped");
    scoreCard.appendChild(thrBadge);
    scoreCard.appendChild(el("p", "fine", "Threshold " + fmt(THRESHOLD) + " · policy v" + (payload.policy_version || unknown())));

    // Components table
    var contribs = payload.contributions || [];
    if (contribs.length) {
      var table = document.createElement("table");
      var hr = el("tr", null);
      ["Component", "Value", "Weight", "Weighted"].forEach(function (h) { hr.appendChild(el("th", null, h)); });
      table.appendChild(hr);
      contribs.forEach(function (c) {
        var tr = document.createElement("tr");
        var nameCell = el("td", null);
        nameCell.appendChild(el("span", "dot " + c.code.toLowerCase(), c.code));
        nameCell.appendChild(document.createTextNode(" " + c.name.charAt(0).toUpperCase() + c.name.slice(1) + " (" + c.code + ")"));
        tr.appendChild(nameCell);
        tr.appendChild(el("td", "num", numOrUnknown(c.signal, 2)));
        tr.appendChild(el("td", "num", numOrUnknown(c.weight, 2)));
        tr.appendChild(el("td", "num", numOrUnknown(c.weighted, 3)));
        table.appendChild(tr);
      });
      scoreCard.appendChild(table);

      // Contribution bars
      var bars = el("div", "contrib-bars");
      contribs.forEach(function (c) {
        var row = el("div", "contrib-row");
        row.appendChild(el("span", "mono", c.formula_term));
        var track = el("div", "track");
        var bar = document.createElement("i");
        bar.style.width = Math.min(100, c.weighted * 100 * 2) + "%";
        track.appendChild(bar);
        row.appendChild(track);
        row.appendChild(el("span", "num", numOrUnknown(c.weighted, 3)));
        bars.appendChild(row);
      });
      scoreCard.appendChild(bars);
    }

    // Decision + simulation status
    var decCard = el("section", "panel card");
    decCard.appendChild(el("h3", null, "Decision"));
    var statusPill = el("span", "pill " + (cert.status === "SIMULATED" ? "ok" : cert.status === "REVIEW" ? "warn" : "warn"),
      cert.status);
    decCard.appendChild(el("div", "pill-row",
      null));
    var pr = el("div", "pill-row");
    pr.appendChild(el("span", "action " + cert.recommended_action, cert.recommended_action.replace(/_/g, " ")));
    pr.appendChild(statusPill);
    decCard.appendChild(pr);
    decCard.appendChild(el("p", null, payload.why || cert.decision_description));

    // Simulation results — amber for skipped, green only when simulation completed successfully
    var simBox = el("div", "sim-box " + (cert.status === "SIMULATED" ? "sim-ok" : "sim-skipped"));
    simBox.appendChild(el("h4", null, "Simulation Results"));
    var simRows = [
      ["Status", cert.status === "SIMULATED" ? "COMPLETED" : cert.status === "NO_SIMULATION" ? "SKIPPED" : "INCOMPLETE"],
      ["Forks", numOrUnknown((cert.forks_tested || []).length, 0)],
      ["Scenarios", (payload.scenarios_ran && payload.scenarios_ran.length) ? payload.scenarios_ran.join(", ") : unknown()],
      ["Elapsed", payload.timeline && payload.timeline.length
        ? numOrUnknown(sumElapsed(payload.timeline), 1) + " ms"
        : unknown()]
    ];
    var st = document.createElement("table");
    simRows.forEach(function (p) {
      var tr = document.createElement("tr");
      tr.appendChild(el("td", null, p[0]));
      tr.appendChild(el("td", "num", p[1]));
      st.appendChild(tr);
    });
    simBox.appendChild(st);
    if (cert.status === "NO_SIMULATION") {
      simBox.appendChild(el("p", "fine warn-text",
        "No deep simulation was performed. The Impact Gate score was below the threshold, "
        + "so stress scenarios and fragility search did not run. An empty fork table means "
        + "skipped simulation — not proven safety under load."));
    }
    decCard.appendChild(simBox);

    // Transaction summary
    var sumCard = el("section", "panel card");
    sumCard.appendChild(el("h3", null, "Transaction Summary"));
    if (cert.status === "SIMULATED") {
      sumCard.appendChild(el("span", "pill ok", "SELECTED FOR SIMULATION"));
    } else if (cert.status === "NO_SIMULATION") {
      sumCard.appendChild(el("span", "pill warn", "NOT SELECTED"));
    }
    var facts = (payload.transaction && payload.transaction.facts) || null;
    var ftable = document.createElement("table");
    function factRow(k, v) {
      var tr = document.createElement("tr");
      tr.appendChild(el("td", null, k));
      tr.appendChild(el("td", "num mono", v));
      ftable.appendChild(tr);
    }
    factRow("Transaction ID", cert.transaction_id || unknown());
    if (facts) {
      factRow("Type", facts.transaction_type || unknown());
      factRow("Amount", numOrUnknown(facts.amount, 2));
      factRow("Account", facts.account_id || unknown());
      factRow("Timestamp", facts.timestamp || unknown());
    }
    factRow("Trace ID", cert.trace_id || unknown());
    factRow("Certificate", cert.certificate_id || unknown());
    sumCard.appendChild(ftable);

    // Layout grid of cards
    var grid = el("div", "grid-3");
    grid.appendChild(sumCard);
    grid.appendChild(scoreCard);
    grid.appendChild(decCard);
    root.appendChild(grid);

    // Explanation
    var expCard = el("section", "panel card");
    expCard.appendChild(el("h3", null, "Explanation"));
    var plainBtn = el("button", "seg-btn active", "Plain language");
    var techBtn = el("button", "seg-btn", "Technical details");
    var toggle = el("div", "seg");
    toggle.appendChild(plainBtn);
    toggle.appendChild(techBtn);
    expCard.appendChild(toggle);
    var plainBox = el("div", "seg-panel", payload.plain_language || cert.decision_description);
    var techBox = el("div", "seg-panel mono", payload.technical_detail || "");
    techBox.hidden = true;
    plainBtn.addEventListener("click", function () {
      plainBtn.classList.add("active"); techBtn.classList.remove("active");
      plainBox.hidden = false; techBox.hidden = true;
    });
    techBtn.addEventListener("click", function () {
      techBtn.classList.add("active"); plainBtn.classList.remove("active");
      plainBox.hidden = true; techBox.hidden = false;
    });
    expCard.appendChild(plainBox);
    expCard.appendChild(techBox);
    if (contribs.length) {
      expCard.appendChild(el("h4", null, "Key points"));
      var ul = el("ul", "limits");
      ul.appendChild(el("li", null, "Score: " + fmt(cert.impact_score.score, 3) + " (threshold " + fmt(THRESHOLD) + ")"));
      var sorted = contribs.slice().sort(function (a, b) { return b.weighted - a.weighted; });
      ul.appendChild(el("li", null, "Main drivers: " + sorted.slice(0, 2).map(function (c) {
        return c.name + " (" + fmt(c.weighted, 3) + ")";
      }).join(", ")));
      ul.appendChild(el("li", null, "Simulation ran: " + ((cert.forks_tested || []).length ? "Yes (" + cert.forks_tested.length + " forks)" : "No — " + cert.status)));
      ul.appendChild(el("li", null, "Final action: " + cert.recommended_action));
      expCard.appendChild(ul);
    }

    // Scenario outcomes
    var scCard = el("section", "panel card");
    scCard.appendChild(el("h3", null, "Scenario Outcomes"));
    var forks = cert.forks_tested || [];
    if (!forks.length) {
      scCard.appendChild(el("p", "warn-text fine",
        "No scenarios ran. Stress outcome is " + unknown() + " — not a pass."));
      // Independent counterexample measurement (gate-skipped showcase txs):
      // measure stress WITHOUT changing the gate decision. Surfaces the
      // missed-failure case the product is built to expose.
      var cbtn = el("button", "btn", "Run independent counterexample measurement");
      cbtn.type = "button";
      var cout = el("div", "notice");
      cbtn.addEventListener("click", function () {
        cbtn.disabled = true;
        cbtn.textContent = "Measuring stress…";
        fetch("/counterexample/" + encodeURIComponent(cert.transaction_id))
          .then(function (r) {
            return r.json().then(function (d) { return { ok: r.ok, d: d }; });
          })
          .then(function (res) {
            if (!res.ok) {
              cout.className = "notice bad-notice";
              cout.textContent = "Counterexample unavailable: " +
                ((res.d.detail && res.d.detail.error_message) || res.d.error_message || "unknown");
              return;
            }
            var v = res.d;
            var measured = (v.certificate && v.certificate.forks_tested) || [];
            var stressLines = measured.filter(function (f) { return f.fork_name === "stress"; })
              .map(function (f) { return f.scenario + ": " + (f.survived ? "survived" : "FAILED"); });
            cout.className = "notice " + (v.stress_failure_observed ? "bad-notice" : "ok-notice");
            var head = v.missed_failure
              ? "MISSED FAILURE — the gate skipped this transaction, but independent stress measurement FAILED it:"
              : "Independent stress measurement (" + v.kind + "):";
            cout.textContent = head + " " + stressLines.join("; ") +
              " Gate decision unchanged (" + (v.gate_selected ? "selected" : "skipped") + ").";
          })
          .catch(function (e) {
            cout.className = "notice bad-notice";
            cout.textContent = "Counterexample request failed: " + e.message;
          })
          .then(function () {
            cbtn.disabled = false;
            cbtn.textContent = "Run independent counterexample measurement";
          });
      });
      scCard.appendChild(cbtn);
      scCard.appendChild(cout);
    } else {
      var scenarios = [];
      forks.forEach(function (f) { if (scenarios.indexOf(f.scenario) < 0) scenarios.push(f.scenario); });
      var incomplete = 0;
      var sct = document.createElement("table");
      var shr = el("tr", null);
      ["Scenario", "Normal", "Stress", "Result"].forEach(function (h) { shr.appendChild(el("th", null, h)); });
      sct.appendChild(shr);
      scenarios.forEach(function (name) {
        var normal = forks.filter(function (f) { return f.scenario === name && f.fork_name === "normal"; })[0];
        var stress = forks.filter(function (f) { return f.scenario === name && f.fork_name === "stress"; })[0];
        if (!normal || !stress) { incomplete += 1; return; }
        var tr = document.createElement("tr");
        tr.appendChild(el("td", "num", name));
        tr.appendChild(el("td", normal.survived ? "pass" : "fail", normal.survived ? "survived" : "failed"));
        var stressOk = stress.survived;
        tr.appendChild(el("td", stressOk ? "pass" : "fail",
          (stressOk ? "survived" : "FAILED") + " @ " + numOrUnknown(stress.metrics.intensity, 1) + "x"));
        tr.appendChild(el("td", stressOk ? "pill ok" : "pill bad", stressOk ? "SUCCESS" : "STRESS FAIL"));
        sct.appendChild(tr);
      });
      if (sct.childNodes.length > 1) scCard.appendChild(sct);
      if (incomplete) {
        scCard.appendChild(el("p", "fine", incomplete + " scenario(s) had incomplete normal/stress pairs and were omitted from the table."));
      }
      var stressFails = forks.filter(function (f) { return f.fork_name === "stress" && !f.survived; }).length;
      if (stressFails) {
        scCard.appendChild(el("div", "notice bad-notice", stressFails + " stress failure(s) observed under simulation."));
      } else if (forks.length) {
        scCard.appendChild(el("div", "notice ok-notice", "All measured stress forks survived (execution success — not a universal safety claim)."));
      }
    }

    // Execution timeline
    var tlCard = el("section", "panel card");
    tlCard.appendChild(el("h3", null, "Execution Timeline"));
    var tl = el("ul", "timeline");
    (payload.timeline || []).forEach(function (ev) {
      var li = el("li", "tl-item");
      var icon = el("span", "tl-dot ok-dot", "✓");
      if (ev.status === "error") icon.className = "tl-dot bad-dot";
      li.appendChild(icon);
      li.appendChild(el("span", "tl-name", ev.stage || ev.status || "event"));
      li.appendChild(el("span", "mono", ev.elapsed_ms !== undefined ? fmt(ev.elapsed_ms, 1) + " ms" : unknown()));
      li.appendChild(el("span", "fine", ev.status || ""));
      tl.appendChild(li);
    });
    if (!(payload.timeline || []).length) {
      tl.appendChild(el("li", "fine", "Timeline " + unknown()));
    }
    tlCard.appendChild(tl);

    // Evidence & artifacts
    var evCard = el("section", "panel card");
    evCard.appendChild(el("h3", null, "Evidence & Artifacts"));
    var evidence = [], limits = [];
    (cert.evidence || []).forEach(function (line) {
      if (line.indexOf("LIMITATION: ") === 0) limits.push(line.slice("LIMITATION: ".length));
      else evidence.push(line);
    });
    var ul = el("ul", "evidence");
    evidence.forEach(function (line) { ul.appendChild(el("li", null, line)); });
    evCard.appendChild(ul);
    if (limits.length) {
      evCard.appendChild(el("h4", null, "Limitations"));
      var lu = el("ul", "limits");
      limits.forEach(function (line) { lu.appendChild(el("li", null, line)); });
      evCard.appendChild(lu);
    }
    var r = cert.runtime || {};
    evCard.appendChild(el("div", "foot",
      "runtime " + (r.runtime || unknown()) +
      " | architecture " + (r.architecture || unknown()) +
      " | seed " + (r.random_seed !== undefined && r.random_seed !== null ? r.random_seed : unknown()) +
      " | policy v" + (payload.policy_version || unknown()) +
      " | models " + JSON.stringify(r.model_versions || {})));

    grid2 = el("div", "grid-3");
    grid2.appendChild(expCard);
    grid2.appendChild(scCard);
    grid2.appendChild(tlCard);
    root.appendChild(grid2);
    var grid3 = el("div", "grid-3");
    grid3.appendChild(evCard);

    // Legend / trust
    var leg = el("section", "panel card");
    leg.appendChild(el("h3", null, "Legend"));
    [["fact", "Fact", "Directly from data or system"],
     ["model", "Model Output", "From ML models or calculations"],
     ["label", "Label", "From external dataset or benchmark"],
     ["interp", "Interpretation", "Human readable explanation"],
     ["unknown", "Unknown", "Never shown as zero or safe"]].forEach(function (p) {
      var row = el("div", "leg-row");
      row.appendChild(el("span", "kind " + p[0], p[1]));
      row.appendChild(el("span", "fine", p[2]));
      leg.appendChild(row);
    });
    grid3.appendChild(leg);

    var trust = el("section", "panel card");
    trust.appendChild(el("h3", null, "Trust & Provenance"));
    var ttable = document.createElement("table");
    ttable.className = "kv-table";  // fixed tracks: hashes/URLs wrap, never spill
    [["Policy version", payload.policy_version || unknown()],
     ["Threshold", fmt(THRESHOLD)],
     ["Model backend", (r.model_versions && r.model_versions.backend) || unknown()],
     ["Architecture", r.architecture || unknown()],
     ["Dataset fingerprint", (r.model_versions && r.model_versions.dataset_sha256) || unknown()],
     ["Config hash", (r.model_versions && r.model_versions.config_sha256) || unknown()],
     ["Environment", (healthCache ? healthCache.runtime + " / " + healthCache.architecture : unknown())]
    ].forEach(function (p) {
      var tr = document.createElement("tr");
      tr.appendChild(el("td", null, p[0]));
      tr.appendChild(el("td", "num mono", p[1]));
      ttable.appendChild(tr);
    });
    trust.appendChild(ttable);
    grid3.appendChild(trust);

    // AI & Risk Signals panel (backend ai_signals)
    grid3.appendChild(renderAiPanel(payload));

    // LLM narrative (advisory pairing of certificate facts with Granite reasoning)
    grid3.appendChild(renderLlmCard(payload));

    root.appendChild(grid3);

    // What-If uses the module-level `selected` transaction (bound once at init).
    $("wi-btn").disabled = !selected;
    $("wi-out").hidden = true;

    show("result");
  }

  function renderAiPanel(payload) {
    var card = el("section", "panel card ai-panel");
    card.appendChild(el("h3", null, "AI & Risk Signals"));
    var ai = payload.ai_signals;
    if (!ai || ai.available === false) {
      card.appendChild(el("p", "warn-text fine", "AI signal detail unavailable: " + (ai && ai.error ? ai.error : unknown())));
      card.appendChild(el("p", "fine", "Gate still used M/D/A/U from the certificate; see Impact Gate Analysis above."));
      return card;
    }
    var backend = ai.model_backend || unknown();
    card.appendChild(el("span", "pill " + (backend === "sklearn" ? "ok" : "warn"),
      "Backend: " + backend + (backend === "numpy" ? " (fallback)" : "")));
    card.appendChild(el("p", "fine mono",
      "models: " + JSON.stringify(ai.model_versions || {}) +
      " · fit split " + (ai.fitted_on_split || unknown()) +
      " · n=" + (ai.n_fit_samples !== undefined ? ai.n_fit_samples : unknown())));

    // Anomaly block
    var a = ai.anomaly || {};
    card.appendChild(el("h4", null, "Anomaly (A) — ML"));
    var at = document.createElement("table");
    [["Raw model output", numOrUnknown(a.raw, 4)],
     ["Normalized A", numOrUnknown(a.normalized_a, 4)],
     ["Calibration", (a.calibration_method || unknown()) + " on " + (a.calibration_split || unknown())],
     ["Model", a.model_name || unknown()],
     ["In calibrated range", a.range && a.range.within_supported_range === true ? "yes" : a.range && a.range.within_supported_range === false ? "possible OOD" : unknown()]
    ].forEach(function (p) {
      var tr = document.createElement("tr");
      tr.appendChild(el("td", null, p[0]));
      tr.appendChild(el("td", "num", p[1]));
      at.appendChild(tr);
    });
    card.appendChild(at);
    (a.caveats || []).forEach(function (c) { card.appendChild(el("p", "fine", "• " + c)); });

    // Risk block
    var rsk = ai.risk || {};
    card.appendChild(el("h4", null, "Risk & Uncertainty (U) — ML"));
    var rt = document.createElement("table");
    [["Mean P(fail) ensemble", numOrUnknown(rsk.failure_probability_mean, 4)],
     ["Member std", numOrUnknown(rsk.member_std, 4)],
     ["Normalized U", numOrUnknown(rsk.normalized_u, 4)],
     ["Normalization", rsk.uncertainty_normalization || unknown()],
     ["Model", rsk.model_name || unknown()]
    ].forEach(function (p) {
      var tr = document.createElement("tr");
      tr.appendChild(el("td", null, p[0]));
      tr.appendChild(el("td", "num", p[1]));
      rt.appendChild(tr);
    });
    card.appendChild(rt);
    if (rsk.note) card.appendChild(el("p", "fine", rsk.note));
    (rsk.caveats || []).forEach(function (c) { card.appendChild(el("p", "fine", "• " + c)); });

    // Signal provenance
    card.appendChild(el("h4", null, "Signal provenance"));
    var pt = document.createElement("table");
    var sources = ai.signal_sources || {};
    [["M", sources.M], ["D", sources.D], ["A", sources.A], ["U", sources.U]].forEach(function (p) {
      var tr = document.createElement("tr");
      tr.appendChild(el("td", "mono", p[0]));
      tr.appendChild(el("td", null, String(p[1] || unknown())));
      pt.appendChild(tr);
    });
    card.appendChild(pt);

    // Trace to decision
    card.appendChild(el("h4", null, "Signal → gate trace"));
    card.appendChild(el("p", "mono fine", ai.technical_detail || ""));
    card.appendChild(el("p", null, ai.plain_language || ""));

    // Simulation evidence after decision
    var simExec = ai.gate && ai.gate.simulation_executed;
    var fails = ai.measured_stress_failures;
    card.appendChild(el("h4", null, "Post-decision evidence"));
    if (simExec === true) {
      card.appendChild(el("span", "pill ok", "SIMULATION EXECUTED"));
      card.appendChild(el("p", null, "Measured stress failures: " + numOrUnknown(fails, 0)));
    } else if (simExec === false) {
      card.appendChild(el("span", "pill warn", "SIMULATION SKIPPED"));
      card.appendChild(el("p", "fine warn-text", "Stress outcome is unknown — not a pass."));
    } else {
      card.appendChild(el("span", "pill", "Simulation status " + unknown()));
    }

    // Unknowns
    card.appendChild(el("h4", null, "What remains unknown"));
    var ul = el("ul", "limits");
    (ai.unknowns || ["none listed"]).forEach(function (u) { ul.appendChild(el("li", null, u)); });
    card.appendChild(ul);
    return card;
  }

  function renderLlmCard(payload) {
    var card = el("section", "panel card ai-panel");
    card.appendChild(el("h3", null, "LLM Narrative (advisory)"));
    var llm = payload.llm_narrative;
    if (!llm || llm.available !== true) {
      var reason = llm && llm.reason ? llm.reason : unknown();
      card.appendChild(el("p", "fine", "Narrative unavailable: " + reason));
      card.appendChild(el("p", "fine", "Advisory only — scores and decisions never depend on an LLM."));
      return card;
    }
    // URL-mode services do not report a model id; show an honest generic label
    // instead of leaking the internal endpoint URL into the pill.
    var llmModel = llm.model || "configured";
    if (/^https?:/i.test(llmModel)) { llmModel = "local service"; }
    card.appendChild(el("span", "pill ok", "LLM " + llmModel));
    card.appendChild(el("p", null, llm.text || ""));
    card.appendChild(el("p", "fine",
      "advisory only · " + numOrUnknown(llm.latency_ms, 0) + " ms · never changes scores or decisions"));
    return card;
  }

  function runWhatIf(tx) {
    var overrides = {};
    var amt = $("wi-amount").value;
    if (amt !== "") overrides.amount = Number(amt);
    var ttype = $("wi-type").value;
    if (ttype) overrides.transaction_type = ttype;
    if (!Object.keys(overrides).length) {
      $("wi-out").hidden = false;
      $("wi-out").textContent = "Enter at least one override (amount or type).";
      return;
    }
    var body = tx.id === DEMO_ID
      ? { demo_mode: true, overrides: overrides }
      : { transaction: tx, overrides: overrides };
    $("wi-out").hidden = false;
    $("wi-out").textContent = "Running research what-if…";
    fetch("/research/what-if", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, d: d }; });
    }).then(function (res) {
      if (!res.ok) {
        var det = res.d.detail || res.d;
        $("wi-out").textContent = "Rejected: " + (det.error_message || JSON.stringify(det));
        return;
      }
      var o = res.d.original || {};
      var h = res.d.hypothetical || {};
      var oS = o.signals || {};
      var hS = h.signals || {};
      var oG = o.gate || {};
      var hG = h.gate || {};
      $("wi-out").textContent = [
        "RESEARCH ONLY — not a real outcome",
        "changes: " + JSON.stringify(res.d.changes || {}),
        "score " + numOrUnknown(oG.score, 4) + " → " + numOrUnknown(hG.score, 4),
        "selected " + String(oG.selected) + " → " + String(hG.selected),
        "A " + numOrUnknown(oS.A, 4) + " → " + numOrUnknown(hS.A, 4),
        h.plain_language || ""
      ].join("\n");
    }).catch(function (e) {
      $("wi-out").textContent = "What-if error: " + e.message;
    });
  }

  var grid2; // intentional: assigned before use in renderExplain

  function sumElapsed(timeline) {
    var total = 0;
    timeline.forEach(function (ev) {
      if (typeof ev.elapsed_ms === "number") total += ev.elapsed_ms;
    });
    return total;
  }

  // ---------------------------------------------------------- dataset studio
  function loadDatasets() {
    fetch("/datasets").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (items) {
      datasetsCache = items || [];
      var list = $("ds-list");
      list.textContent = "";
      if (!items || !items.length) {
        list.appendChild(el("li", "empty", "No uploaded datasets yet."));
      } else {
        items.forEach(function (ds) {
          var li = el("li", "ds-row");
          var btn = el("button", "tx-item");
          btn.type = "button";
          btn.appendChild(el("div", "tx-id", ds.display_name + " (" + ds.dataset_id + ")"));
          btn.appendChild(el("div", "tx-meta",
            ds.row_count + " rows · " + ds.column_count + " cols · " + ds.format +
            (ds.mapping ? " · mapped" : " · needs mapping")));
          btn.addEventListener("click", function () { openDataset(ds.dataset_id); });
          li.appendChild(btn);
          // DELETE /datasets/{id} — removal was previously unreachable from the UI.
          var del = el("button", "btn danger-btn", "Delete");
          del.type = "button";
          del.title = "Remove " + ds.dataset_id;
          del.addEventListener("click", function () {
            if (!window.confirm("Delete dataset " + ds.display_name + " (" + ds.dataset_id + ")? This removes the uploaded payload.")) return;
            del.disabled = true;
            fetch("/datasets/" + ds.dataset_id, { method: "DELETE" })
              .then(function (r) {
                if (!r.ok) return r.json().then(function (d) { throw new Error((d.detail && d.detail.error_message) || d.error_message || ("HTTP " + r.status)); });
                return r.json();
              })
              .then(function () {
                $("upload-msg").textContent = "Deleted " + ds.dataset_id + ".";
                loadDatasets();
              })
              .catch(function (e) {
                $("upload-msg").textContent = "Delete failed: " + e.message;
                del.disabled = false;
              });
          });
          li.appendChild(del);
          list.appendChild(li);
        });
      }
      var mappedList = datasetsCache.filter(function (d) { return !!d.mapping; });
      $("eval-btn").disabled = !mappedList.length;
      // Explicit dataset selector: never silently evaluate an implicit dataset.
      var evalSel = $("eval-ds");
      if (evalSel) {
        var prev = evalSel.value;
        evalSel.textContent = "";
        if (!mappedList.length) {
          var none = el("option", null, "— map a dataset first —");
          none.value = "";
          evalSel.appendChild(none);
        }
        mappedList.forEach(function (d) {
          var opt = el("option", null, d.display_name + " (" + d.dataset_id + " · " + d.row_count + " rows)");
          opt.value = d.dataset_id;
          if (d.dataset_id === prev) opt.selected = true;
          evalSel.appendChild(opt);
        });
      }
    }).catch(function (e) {
      $("upload-msg").textContent = "Failed to load datasets: " + e.message;
    });
  }

  function openDataset(id) {
    fetch("/datasets/" + id + "?preview_rows=15").then(function (r) {
      if (!r.ok) return r.json().then(function (d) { throw new Error(JSON.stringify(d)); });
      return r.json();
    }).then(function (ds) {
      $("ds-detail-empty").hidden = true;
      var box = $("ds-preview");
      box.hidden = false;
      box.textContent = "";
      box.appendChild(el("h3", null, ds.display_name + " · " + ds.dataset_id));
      box.appendChild(el("p", "mono fine", "sha256 " + ds.sha256.slice(0, 16) + "… · rows " + ds.row_count));
      box.appendChild(el("p", "fine", "license: " + (ds.license || unknown()) + " (" + ds.license_status + ")"));

      // Quality badges
      var qual = el("div", "pill-row");
      qual.appendChild(el("span", "pill " + (ds.missing && Object.keys(ds.missing).length ? "warn" : "ok"),
        ds.missing && Object.keys(ds.missing).length ? "Missing values present" : "No missing values"));
      qual.appendChild(el("span", "pill " + (ds.duplicate_rows ? "warn" : "ok"),
        ds.duplicate_rows ? ds.duplicate_rows + " duplicate rows" : "No duplicates"));
      box.appendChild(qual);

      box.appendChild(el("h4", null, "Columns"));
      var ct = document.createElement("table");
      var hr = el("tr", null);
      ["Name", "Type", "Missing", "Sample"].forEach(function (h) { hr.appendChild(el("th", null, h)); });
      ct.appendChild(hr);
      ds.columns.forEach(function (c) {
        var tr = document.createElement("tr");
        tr.appendChild(el("td", null, c.name));
        tr.appendChild(el("td", null, c.inferred_type));
        tr.appendChild(el("td", "num", String(c.missing)));
        tr.appendChild(el("td", "mono", (c.unique_sample || []).join(", ")));
        ct.appendChild(tr);
      });
      box.appendChild(ct);

      box.appendChild(el("h4", null, "Column mapping"));
      var form = el("div", "map-form");
      var fields = ["id", "account_id", "amount", "timestamp", "transaction_type", "label"];
      var selects = {};
      fields.forEach(function (f) {
        var lab = el("label", null, f + (f === "label" ? " (optional)" : " *"));
        var sel = document.createElement("select");
        sel.dataset.field = f;
        var none = el("option", null, "—");
        none.value = "";
        sel.appendChild(none);
        ds.columns.forEach(function (c) {
          var opt = el("option", null, c.name);
          opt.value = c.name;
          if (ds.mapping && ds.mapping[f] === c.name) opt.selected = true;
          sel.appendChild(opt);
        });
        selects[f] = sel;
        lab.appendChild(sel);
        form.appendChild(lab);
      });
      var labSem = el("label", null, "label semantics");
      var semSel = document.createElement("select");
      ["", "fraud", "default", "operational_failure", "other"].forEach(function (s) {
        var opt = el("option", null, s || "—");
        opt.value = s;
        if (ds.label_semantics === s) opt.selected = true;
        semSel.appendChild(opt);
      });
      labSem.appendChild(semSel);
      form.appendChild(labSem);
      var saveBtn = el("button", "break", "Save mapping");
      saveBtn.type = "button";
      saveBtn.addEventListener("click", function () {
        var mapping = {};
        fields.forEach(function (f) { if (selects[f].value) mapping[f] = selects[f].value; });
        fetch("/datasets/" + id + "/map", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mapping: mapping, label_semantics: semSel.value || null })
        }).then(function (r) {
          return r.json().then(function (d) { return { ok: r.ok, d: d }; });
        }).then(function (res) {
          var msg = el("div", res.ok ? "notice ok-notice" : "notice bad-notice");
          if (!res.ok) {
            msg.textContent = (res.d.detail && res.d.detail.error_message) || "Mapping failed";
          } else {
            msg.textContent = "Mapping saved for " + id;
            loadDatasets();
          }
          box.appendChild(msg);
        });
      });
      form.appendChild(saveBtn);
      box.appendChild(form);

      if (ds.preview_rows && ds.preview_rows.length) {
        box.appendChild(el("h4", null, "Preview rows"));
        var pt = document.createElement("table");
        var cols = ds.columns.map(function (c) { return c.name; });
        var phr = el("tr", null);
        cols.forEach(function (c) { phr.appendChild(el("th", null, c)); });
        pt.appendChild(phr);
        ds.preview_rows.slice(0, 8).forEach(function (row) {
          var tr = el("tr", null);
          cols.forEach(function (c) { tr.appendChild(el("td", "num", String(row[c]))); });
          pt.appendChild(tr);
        });
        box.appendChild(pt);
      }
    }).catch(function (e) {
      $("ds-detail-empty").hidden = false;
      $("ds-detail-empty").textContent = "Failed to open dataset: " + e.message;
    });
  }

  $("upload-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var input = $("file-input");
    if (!input.files || !input.files.length) return;
    var fd = new FormData();
    fd.append("file", input.files[0]);
    fd.append("display_name", $("display-name").value);
    fd.append("attribution", $("attribution").value);
    fd.append("license_name", $("license-name").value);
    fd.append("source_url", $("source-url").value);
    if ($("registry-credit").checked) fd.append("registry_id", "ulb_creditcard_fraud");
    $("upload-msg").textContent = "Uploading…";
    fetch("/datasets/upload", { method: "POST", body: fd }).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, d: d }; });
    }).then(function (res) {
      if (!res.ok) {
        var det = res.d.detail || res.d;
        $("upload-msg").textContent = "Upload failed: " + (det.error_message || JSON.stringify(det));
      } else {
        $("upload-msg").textContent = "Uploaded " + res.d.dataset_id + " (" + res.d.row_count + " rows)";
        loadDatasets();
      }
    }).catch(function (e) {
      $("upload-msg").textContent = "Upload error: " + e.message;
    });
  });

  // ------------------------------------------------------------ open datasets
  // ----------------------------------------------------------- challenge lab
  function loadChallenge() {
    loadDatasets();
    loadExperiments();
  }

  $("eval-btn").addEventListener("click", function () {
    // Evaluate the dataset chosen in the selector (fallback: first mapped).
    var selId = $("eval-ds") ? $("eval-ds").value : "";
    var mapped = datasetsCache.filter(function (d) { return !!d.mapping && d.dataset_id === selId; })[0]
      || datasetsCache.filter(function (d) { return !!d.mapping; })[0];
    if (!mapped) {
      alert("Map a dataset first in Dataset Studio.");
      return;
    }
    $("eval-btn").disabled = true;
    $("eval-alert").textContent = "";
    fetch("/datasets/" + mapped.dataset_id + "/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_rows: 2000, run_stress_sample: $("eval-stress").checked })
    }).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, d: d }; });
    }).then(function (res) {
      $("eval-out").hidden = false;
      $("eval-out").textContent = JSON.stringify(res.d, null, 2);
      if (res.ok) renderEvalMetrics(res.d);
      loadExperiments();
      $("eval-btn").disabled = false;
    }).catch(function (e) {
      $("eval-out").hidden = false;
      $("eval-out").textContent = "Evaluation error: " + e.message;
      $("eval-btn").disabled = false;
    });
  });

  function renderEvalMetrics(report) {
    var box = $("eval-metrics");
    box.hidden = false;
    box.textContent = "";
    var m = report.metrics || {};
    // Missed-failure alert: labeled positives the gate skipped
    if (typeof m.fn_skipped_labeled_positive === "number" && m.fn_skipped_labeled_positive > 0) {
      var alert = el("div", "notice bad-notice",
        "MISSED FAILURE ALERT: " + m.fn_skipped_labeled_positive +
        " labeled positive row(s) were skipped by the gate (selection miss — not a stress-survival claim).");
      box.appendChild(alert);
    } else if (typeof m.fn_skipped_labeled_positive === "number") {
      box.appendChild(el("div", "notice ok-notice", "No labeled positives were skipped by the gate in this run."));
    } else {
      box.appendChild(el("div", "notice warn-notice", "No usable external labels — selection metrics omitted. Stress outcome remains " + unknown() + "."));
    }

    box.appendChild(el("h4", null, "Benchmark metrics (selection vs external label)"));
    var t = document.createElement("table");
    function row(k, v) {
      var tr = document.createElement("tr");
      tr.appendChild(el("td", null, k));
      tr.appendChild(el("td", "num", v));
      t.appendChild(tr);
    }
    row("Run ID", report.run_id || unknown());
    row("Dataset SHA-256", (report.dataset_sha256 || unknown()).slice(0, 20) + "…");
    row("Policy", "v" + (report.policy_version || unknown()) + " thr " + numOrUnknown(report.threshold));
    row("Rows scored", numOrUnknown(report.rows_scored, 0));
    row("Rows excluded", numOrUnknown(report.rows_excluded_unmappable_or_invalid, 0));
    row("Simulation rate", numOrUnknown(report.simulation_rate, 4));
    row("Gate selected", numOrUnknown(report.gate_selected_count, 0));
    row("Gate skipped", numOrUnknown(report.gate_skipped_count, 0));
    row("Label prevalence", numOrUnknown(m.label_positive_prevalence, 4));
    row("Selection recall (positive label)", numOrUnknown(m.selection_recall_positive_label, 4));
    row("Selection precision", numOrUnknown(m.selection_precision_positive_label, 4));
    row("Selection FPR", numOrUnknown(m.selection_false_positive_rate, 4));
    box.appendChild(t);

    if (typeof m.tp_selected_labeled_positive === "number") {
      box.appendChild(el("h4", null, "Confusion matrix (gate selection × external label)"));
      var cm = document.createElement("table");
      var hr = el("tr", null);
      ["", "Label +", "Label −"].forEach(function (h) { hr.appendChild(el("th", null, h)); });
      cm.appendChild(hr);
      var r1 = el("tr", null);
      r1.appendChild(el("td", null, "Selected"));
      r1.appendChild(el("td", "num", String(m.tp_selected_labeled_positive)));
      r1.appendChild(el("td", "num", String(m.fp_selected_labeled_negative)));
      cm.appendChild(r1);
      var r2 = el("tr", null);
      r2.appendChild(el("td", null, "Skipped"));
      r2.appendChild(el("td", "num fail", String(m.fn_skipped_labeled_positive)));
      r2.appendChild(el("td", "num", String(m.tn_skipped_labeled_negative)));
      cm.appendChild(r2);
      box.appendChild(cm);
      box.appendChild(el("p", "fine", m.confusion_note || ""));
    }
    if (report.stress_sample) {
      box.appendChild(el("h4", null, "Measured stress sample (independent of labels)"));
      box.appendChild(el("p", "fine", report.stress_sample.note || ""));
      box.appendChild(el("p", "mono", "stress failures: " + report.stress_sample.stress_failure_count + " / " + report.stress_sample.sample_size));
    }
  }

  // --------------------------------------------------------------- experiments
  function loadExperiments() {
    fetch("/experiments").then(function (r) { return r.json(); }).then(function (items) {
      var list = $("exp-list");
      list.textContent = "";
      if (!items || !items.length) {
        list.appendChild(el("li", "empty", "No experiments yet. Map a dataset and run Challenge Lab evaluation."));
        return;
      }
      items.forEach(function (ex) {
        var li = el("li");
        var btn = el("button", "tx-item");
        btn.type = "button";
        btn.appendChild(el("div", "tx-id", ex.run_id));
        btn.appendChild(el("div", "tx-meta",
          ex.dataset_id + " · rows " + ex.rows_scored +
          " · sim_rate " + numOrUnknown(ex.simulation_rate, 4) +
          " · label " + (ex.label_semantics || "none")));
        btn.addEventListener("click", function () {
          fetch("/experiments/" + ex.run_id).then(function (r) {
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.json();
          }).then(function (full) {
            $("exp-detail").hidden = false;
            $("exp-detail").textContent = JSON.stringify(full, null, 2);
          }).catch(function (e) {
            $("exp-detail").hidden = false;
            $("exp-detail").textContent = "Failed to load " + ex.run_id + ": " + e.message;
          });
        });
        li.appendChild(btn);
        list.appendChild(li);
      });
    }).catch(function (e) {
      var list = $("exp-list");
      list.textContent = "";
      list.appendChild(el("li", "empty", "Failed to load experiments: " + e.message));
    });
  }

  // --------------------------------------------------------------- certificates
  function loadCertList(focusId) {
    var list = $("cert-list");
    list.textContent = "";
    if (!certificates.length) {
      list.appendChild(el("li", "empty", "No certificates in this session yet. Run BREAK MY DECISION in Decision Explorer."));
      return;
    }
    certificates.forEach(function (c) {
      var li = el("li", "cert-row");
      var btn = el("button", "tx-item" + (focusId === c.certificate_id ? " selected" : ""));
      btn.type = "button";
      btn.appendChild(el("div", "tx-id", (c.certificate_id || unknown()) + " · " + (c.transaction_id || unknown())));
      btn.appendChild(el("div", "tx-meta",
        (c.status || unknown()) + " · " + (c.recommended_action || unknown()) +
        " · score " + numOrUnknown(c.impact_score && c.impact_score.score, 3)));
      btn.addEventListener("click", function () {
        document.querySelector('.side-item[data-panel="panel-explorer"]').click();
        lastPayload = { certificate: c, plain_language: c.decision_description, contributions: [], timeline: [], scenarios_ran: [] };
        // Re-fetch full explain for the best UX when possible
        var tx = null;
        try {
          if (c.transaction_id === DEMO_ID) tx = { demo_mode: true };
        } catch (e) { /* ignore */ }
        if (tx) {
          selected = selected;
          analyze();
        } else {
          renderExplain(lastPayload);
        }
      });
      li.appendChild(btn);
      // Per-certificate .json download (sibling of the row button).
      var dl = el("button", "btn cert-dl");
      dl.type = "button";
      dl.textContent = "↓ .json";
      dl.title = "Download " + (c.certificate_id || "certificate") + " as JSON";
      dl.addEventListener("click", function () { downloadJson(c, certFilename(c)); });
      li.appendChild(dl);
      list.appendChild(li);
    });
  }

  // -------------------------------------------------------------------- init
  initNav();
  $("break-btn").addEventListener("click", analyze);
  $("retry-btn").addEventListener("click", function () { show("idle"); });
  $("wi-btn").addEventListener("click", function () {
    if (!selected) {
      $("wi-out").hidden = false;
      $("wi-out").textContent = "Select a transaction first.";
      return;
    }
    runWhatIf(selected);
  });
  loadHealth();
  loadTransactions();
})();
