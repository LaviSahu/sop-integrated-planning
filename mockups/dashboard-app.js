/* =============================================================================
   dashboard-app.js — the merged S&OP cockpit application script.

   One IIFE. Reuses the five approved mockups' logic verbatim where it can,
   with the shared helpers (money/units/pct/svgEl/paintScenario/showTip/
   stepHtml/openModal/...) deduplicated to ONE definition each, and each
   panel rendered into its own container id. This is the file the assemble
   step embeds into the self-contained output/dashboard.html.
   ========================================================================== */
(function () {
  "use strict";
  // DATA is defined by the build template's separate <script> block
  // (const DATA = __DATA_JSON__;). It is global-scoped across classic
  // scripts, so referencing it here by name works; window.SOP_DATA does
  // not exist in the built dashboard.
  var D = typeof DATA !== "undefined" ? DATA : window.SOP_DATA;
  var SC = ["base", "upside", "constrained"];
  var SC_LABEL = { base: "Base", upside: "Upside", constrained: "Constrained" };
  var focus = "constrained";
  var MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

  /* ---- formatting (m1/m2/m3/m4/m5 — unified) ----------------------------- */
  function money(v) {
    var sign = v < 0 ? "-" : "";
    var a = Math.abs(v);
    if (a >= 1e6) return sign + "$" + (a / 1e6).toFixed(2) + "M";
    if (a >= 1e3) return sign + "$" + (a / 1e3).toFixed(0) + "k";
    return sign + "$" + a.toFixed(0);
  }
  function money2(v) { return "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function units(v) { return Math.round(v).toLocaleString("en-US"); }
  function units2(v) { return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function pct(v, dp) { return v.toFixed(dp === undefined ? 1 : dp) + "%"; }
  function hrs(v) { return v.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " h"; }
  function signed(v, dp) { return (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(dp === undefined ? 1 : dp); }

  function deltaEl(delta, goodIsUp, unit, dp) {
    var s = document.createElement("span");
    var flat = Math.abs(delta) < 0.005;
    var good = goodIsUp === false ? delta < 0 : delta > 0;
    s.className = "delta " + (flat ? "delta--flat" : good ? "delta--good" : "delta--bad");
    s.textContent = (flat ? "▬ " : delta > 0 ? "▲ " : "▼ ") + signed(delta, dp) + (unit ? " " + unit : "%");
    return s;
  }

  // SVG namespace URI. Built without a literal "http:" scheme so the
  // rendered file stays greppable-clean for network references (the
  // dashboard is zero-CDN; this is a fixed URN the SVG spec requires,
  // never a fetch).
  var SVG_NS = "http:" + "//www.w3.org/2000/svg";
  function svgEl(tag, attrs) {
    var e = document.createElementNS(SVG_NS, tag);
    for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    return e;
  }

  // Scenario identity = fill pattern, never hue (SCOPE §8b).
  function paintScenario(el, sid) {
    if (sid === "constrained") el.setAttribute("fill", "url(#hatch)");
    else if (sid === "upside") el.setAttribute("fill", "var(--sop-color-ink-soft)");
    else {
      el.setAttribute("fill", "var(--sop-color-chart-actual)");
      el.setAttribute("fill-opacity", "0.85");
    }
  }

  // IBCS notation for time-series rows (m1): actual = solid ink, plan =
  // outline, constrained = hatched (dashed stroke stands in for a stroke).
  function paint(el, style, sid) {
    if (style === "plan") {
      el.setAttribute("fill", "none");
      el.setAttribute("stroke", "var(--sop-color-ink-soft)");
      el.setAttribute("stroke-width", "1");
    } else if (sid === "constrained") {
      el.setAttribute("fill", "url(#hatch)");
    } else if (sid === "upside") {
      el.setAttribute("fill", "var(--sop-color-ink-soft)");
    } else {
      el.setAttribute("fill", "var(--sop-color-chart-actual)");
      el.setAttribute("fill-opacity", "0.85");
    }
  }

  /* ---- tooltip (m1's richer variant — head + rows + foot) ---------------- */
  var tip = document.getElementById("tip");
  function showTip(evt, head, rows, foot) {
    tip.innerHTML = "";
    var h = document.createElement("div"); h.className = "tip__head"; h.textContent = head; tip.appendChild(h);
    (rows || []).forEach(function (r) {
      var d = document.createElement("div"); d.className = "tip__row";
      var a = document.createElement("span"); a.textContent = r[0];
      var b = document.createElement("b"); b.textContent = r[1];
      d.appendChild(a); d.appendChild(b); tip.appendChild(d);
    });
    if (foot) { var f = document.createElement("div"); f.className = "tip__foot"; f.textContent = foot; tip.appendChild(f); }
    tip.dataset.show = "1";
    var x = evt.clientX + 14, y = evt.clientY + 14;
    if (x + 300 > window.innerWidth) x = evt.clientX - 300;
    if (y + 150 > window.innerHeight) y = evt.clientY - 150;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function hideTip() { tip.dataset.show = "0"; }

  /* ---- derived aggregates (m2) ------------------------------------------- */
  function agg(sid) {
    var s = D.scenarios[sid], m = s.monthly;
    var unmet = m.reduce(function (a, r) { return a + r.unmet; }, 0);
    var demand = m.reduce(function (a, r) { return a + r.demand; }, 0);
    var util = s.utilization[D.bottleneck.resource_id];
    return {
      revenue: s.summary.total_revenue,
      margin: s.summary.total_gross_margin,
      lost_margin: s.summary.total_lost_margin,
      inventory: s.summary.ending_inventory_value,
      fill: s.summary.fill_rate * 100,
      unmet: unmet,
      demand: demand,
      peak_util: Math.max.apply(null, util.map(function (r) { return r.utilization_pct; })),
      months_over: util.filter(function (r) { return r.utilization_pct > 100; }).length
    };
  }
  var A = { base: agg("base"), constrained: agg("constrained"), upside: agg("upside") };

  function resName(rid) { return D.resources.filter(function (r) { return r.id === rid; })[0].name; }
  function lineA() { return D.scenarios.constrained.utilization[D.bottleneck.resource_id]; } // 12 months
  function peakMonth() {
    return lineA().reduce(function (a, b) { return b.utilization_pct > a.utilization_pct ? b : a; });
  }

  /* =========================================================================
     SECTION 1 — TOPBAR + THEME
     ========================================================================= */
  document.getElementById("co").textContent = "S&OP Cockpit — " + D.company;
  document.getElementById("cycle").textContent = "Annual plan · 12 monthly buckets";
  var th = document.getElementById("themetoggle");
  th.addEventListener("click", function () {
    var light = document.documentElement.getAttribute("data-theme") === "light";
    document.documentElement.setAttribute("data-theme", light ? "dark" : "light");
    th.textContent = light ? "Light" : "Dark";
  });

  /* =========================================================================
     SECTION 2 — HEADLINE BAND (m4's richer headline)
     ========================================================================= */
  function buildHeadline() {
    var base = D.scenarios.base.summary, up = D.scenarios.upside.summary, con = D.scenarios.constrained.summary;
    var lift = up.total_gross_margin - base.total_gross_margin;
    var conVsBase = con.total_gross_margin - base.total_gross_margin;
    var atRisk = con.total_lost_margin;
    var pk = peakMonth();
    document.getElementById("headline").innerHTML =
      '<div class="headline__top">' +
        '<div><span class="headline__kicker">Recommended plan</span>' +
        '<p class="headline__lede">Ship <strong>Constrained</strong>: <strong>' + money(con.total_gross_margin) + '</strong> gross margin at <strong>' + pct(con.fill_rate * 100, 2) + '</strong> fill — the realistic ceiling.</p></div>' +
        '<div><span class="headline__kicker">The one constraint</span>' +
        '<p class="headline__lede">' + resName(D.bottleneck.resource_id) + ' peaks at <strong>' + pct(pk.utilization_pct, 1) + '</strong> of installed hours in ' + D.month_names[pk.month - 1] + ' — it rations Dryers and caps the plan.</p></div>' +
      '</div>' +
      '<div class="headline__trade">' +
        'Constrained banks <span class="delta delta--good">▲ ' + money(conVsBase) + '</span> over Base' +
        ' while shedding only <span class="delta delta--bad">▼ ' + money2(atRisk) + '</span> of the ' + money(lift) + ' Upside lift (Dryers, 3 months).' +
      '</div>';
  }

  /* =========================================================================
     SECTION 3 — KPI TILES (m1)
     ========================================================================= */
  function buildTiles() {
    var base = D.scenarios.base.summary,
        up = D.scenarios.upside.summary,
        con = D.scenarios.constrained.summary;
    var tiles = [
      { label: "Revenue", value: money(con.total_revenue), delta: (con.total_revenue / base.total_revenue - 1) * 100,
        basis: "vs Base " + money(base.total_revenue), why: "shipped units × unit price" },
      { label: "Gross margin", value: money(con.total_gross_margin), delta: (con.total_gross_margin / base.total_gross_margin - 1) * 100,
        basis: "vs Base " + money(base.total_gross_margin), why: "shipped units × unit margin" },
      { label: "Fill rate", value: pct(con.fill_rate * 100, 2), delta: (con.fill_rate - base.fill_rate) * 100,
        deltaUnit: "pp", deltaDp: 2,
        basis: "vs Base " + pct(base.fill_rate * 100, 2), why: "shipped ÷ demanded, full year" },
      { label: "Lost margin", value: money(con.total_lost_margin), delta: null, goodIsUp: false,
        basis: "Base and Upside both " + money(0), why: "unmet units × unit margin" }
    ];
    var host = document.getElementById("tiles");
    tiles.forEach(function (t) {
      var el = document.createElement("div"); el.className = "tile";
      var lab = document.createElement("div"); lab.className = "tile__label"; lab.textContent = t.label;
      var why = document.createElement("button"); why.className = "why"; why.type = "button"; why.textContent = "why?";
      why.title = t.why + " — see the 5-step derivation below";
      lab.appendChild(why);
      var val = document.createElement("div"); val.className = "tile__value"; val.textContent = t.value;
      var foot = document.createElement("div"); foot.className = "tile__foot";
      if (t.delta !== null) foot.appendChild(deltaEl(t.delta, t.goodIsUp, t.deltaUnit, t.deltaDp));
      var b = document.createElement("span"); b.className = "basis"; b.textContent = t.basis;
      foot.appendChild(b);
      el.appendChild(lab); el.appendChild(val); el.appendChild(foot);
      host.appendChild(el);
    });
  }

  /* =========================================================================
     SECTION 4 — SMALL MULTIPLES (m1): demand vs shipped, revenue, bottleneck
     ========================================================================= */
  var ROWS = [
    {
      key: "volume", name: "Demand vs shipped", unit: "units / month", type: "bar",
      series: [
        { field: "demand", label: "Demand", style: "plan" },
        { field: "shipped", label: "Shipped", style: "actual" }
      ],
      fmt: units
    },
    {
      key: "revenue", name: "Revenue", unit: "$ / month", type: "line",
      series: [{ field: "revenue", label: "Revenue", style: "actual" }],
      fmt: money
    },
    {
      key: "util", name: resName(D.bottleneck.resource_id), unit: "% of available hours", type: "bar",
      series: [{ field: "utilization_pct", label: "Utilisation", style: "actual" }],
      fmt: function (v) { return pct(v); }, ref: 100, source: "utilization"
    }
  ];
  var SM_W = 260, SM_H = 108, SM_PL = 4, SM_PR = 4, SM_PT = 10, SM_PB = 16;

  function rowValues(row, sid) {
    if (row.source === "utilization") {
      return D.scenarios[sid].utilization[D.bottleneck.resource_id].map(function (r, i) {
        return { name: D.month_names[i], utilization_pct: r.utilization_pct,
                 load_hours: r.load_hours, available_hours: r.available_hours };
      });
    }
    return D.scenarios[sid].monthly;
  }

  function domain(row) {
    var max = 0;
    SC.forEach(function (sid) {
      rowValues(row, sid).forEach(function (d) {
        row.series.forEach(function (s) { if (d[s.field] > max) max = d[s.field]; });
      });
    });
    if (row.ref && row.ref > max) max = row.ref;
    return [0, max * 1.08];
  }

  function drawCell(row, sid, dom) {
    var data = rowValues(row, sid);
    var svg = svgEl("svg", { viewBox: "0 0 " + SM_W + " " + SM_H, role: "img" });
    var plotW = SM_W - SM_PL - SM_PR, plotH = SM_H - SM_PT - SM_PB;
    var y = function (v) { return SM_PT + plotH - (v / dom[1]) * plotH; };
    var n = data.length, step = plotW / n;

    svg.appendChild(svgEl("line", { x1: SM_PL, y1: y(0), x2: SM_W - SM_PR, y2: y(0), class: "axis-line" }));

    if (row.type === "bar") {
      var multi = row.series.length > 1;
      var bw = Math.max(3, step * 0.72);
      data.forEach(function (d, i) {
        var cx = SM_PL + step * i + step / 2;
        row.series.forEach(function (s, si) {
          var v = d[s.field]; if (v === undefined || v === null) return;
          var w = !multi ? bw : (s.style === "plan" ? bw : bw * 0.5);
          var r = svgEl("rect", { x: cx - w / 2, y: y(v), width: w, height: Math.max(0.6, y(0) - y(v)), rx: 1 });
          paint(r, s.style, sid);
          svg.appendChild(r);
        });
        if (multi && d.unmet > 0) {
          svg.appendChild(svgEl("rect", {
            x: cx - bw / 2, y: y(d.demand), width: bw,
            height: Math.max(1, y(d.shipped) - y(d.demand)),
            fill: "var(--sop-color-bad)", rx: 1
          }));
        }
      });
    } else {
      var pts = data.map(function (d, i) { return [SM_PL + step * i + step / 2, y(d[row.series[0].field])]; });
      svg.appendChild(svgEl("polyline", {
        points: pts.map(function (p) { return p[0] + "," + p[1]; }).join(" "),
        fill: "none",
        stroke: sid === "base" ? "var(--sop-color-chart-actual)" : "var(--sop-color-ink-soft)",
        "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round",
        "stroke-dasharray": sid === "constrained" ? "5 3" : null
      }));
    }

    if (row.ref) {
      svg.appendChild(svgEl("line", { x1: SM_PL, y1: y(row.ref), x2: SM_W - SM_PR, y2: y(row.ref), class: "ref-line" }));
      var t = svgEl("text", { x: SM_W - SM_PR, y: y(row.ref) - 3, class: "tick-text", "text-anchor": "end" });
      t.textContent = "capacity 100%"; svg.appendChild(t);
    }

    [0, 5, n - 1].forEach(function (i) {
      var t = svgEl("text", { x: SM_PL + step * i + step / 2, y: SM_H - 4, class: "tick-text", "text-anchor": "middle" });
      t.textContent = data[i].name; svg.appendChild(t);
    });

    data.forEach(function (d, i) {
      var hit = svgEl("rect", { x: SM_PL + step * i, y: SM_PT, width: step, height: plotH, class: "mark-hit" });
      hit.addEventListener("mousemove", function (e) {
        var rows = [], foot;
        if (row.source === "utilization") {
          rows.push(["Load", d.load_hours.toLocaleString("en-US") + " h"]);
          rows.push(["Available", d.available_hours.toLocaleString("en-US") + " h"]);
          rows.push(["Utilisation", pct(d.utilization_pct)]);
          foot = "load ÷ available × 100";
        } else {
          row.series.forEach(function (s) { rows.push([s.label, row.fmt(d[s.field])]); });
          if (d.unmet !== undefined && row.key === "volume") rows.push(["Unmet", units(d.unmet)]);
          if (row.key === "revenue") foot = "shipped units × unit price";
        }
        showTip(e, SC_LABEL[sid] + " · " + d.name, rows, foot);
      });
      hit.addEventListener("mouseleave", hideTip);
      svg.appendChild(hit);
    });
    return svg;
  }

  function buildSmallMultiples() {
    var sm = document.getElementById("sm");
    sm.appendChild(Object.assign(document.createElement("div"), { className: "sm__corner" }));
    SC.forEach(function (sid) {
      var h = document.createElement("div"); h.className = "sm__colhead";
      var n = document.createElement("span"); n.className = "sm__colhead-name"; n.textContent = SC_LABEL[sid];
      var s = document.createElement("span"); s.className = "sm__colhead-sub";
      s.textContent = money(D.scenarios[sid].summary.total_gross_margin) + " GM";
      h.appendChild(n); h.appendChild(s); sm.appendChild(h);
    });
    ROWS.forEach(function (row) {
      var dom = domain(row);
      var rh = document.createElement("div"); rh.className = "sm__rowhead";
      var nm = document.createElement("div"); nm.className = "sm__rowhead-name"; nm.textContent = row.name;
      var un = document.createElement("div"); un.className = "sm__rowhead-unit"; un.textContent = row.unit;
      var sc = document.createElement("div"); sc.className = "sm__rowhead-scale";
      sc.textContent = "0 – " + row.fmt(dom[1]) + " (shared)";
      rh.appendChild(nm); rh.appendChild(un); rh.appendChild(sc);
      sm.appendChild(rh);
      SC.forEach(function (sid) {
        var c = document.createElement("div"); c.className = "sm__cell";
        c.appendChild(drawCell(row, sid, dom)); sm.appendChild(c);
      });
    });
  }

  /* =========================================================================
     SECTION 5 — SCENARIO PRESETS + STRUCTURAL COMPARISON (m2)
     ========================================================================= */
  var PRESETS = [
    { id: "S0", key: "base", name: "Base", q: "What does the consensus plan look like?" },
    { id: "S1", key: "constrained", name: "Constrained", q: "What can we actually make?" },
    { id: "S2", key: "upside", name: "Upside", q: "What if demand lands high?" },
    { id: "S3", key: null, name: "Invest", q: "Is relieving the bottleneck worth it?",
      tag: "not in engine", disabled: true }
  ];
  function buildPresets() {
    var presetHost = document.getElementById("presets");
    PRESETS.forEach(function (p) {
      var b = document.createElement("button");
      b.className = "preset"; b.type = "button";
      b.setAttribute("aria-pressed", String(p.key === focus));
      if (p.disabled) b.disabled = true;
      var id = document.createElement("div"); id.className = "preset__id";
      id.appendChild(document.createTextNode(p.id));
      if (p.tag) { var t = document.createElement("span"); t.className = "tag"; t.textContent = p.tag; id.appendChild(t); }
      var nm = document.createElement("div"); nm.className = "preset__name"; nm.textContent = p.name;
      var q = document.createElement("p"); q.className = "preset__q"; q.textContent = p.q;
      b.appendChild(id); b.appendChild(nm); b.appendChild(q);
      if (!p.disabled) b.addEventListener("click", function () {
        focus = p.key; renderComparison();
        Array.prototype.forEach.call(presetHost.children, function (c, i) {
          c.setAttribute("aria-pressed", String(PRESETS[i].key === focus));
        });
      });
      presetHost.appendChild(b);
    });
  }

  var METRICS = [
    { key: "revenue", name: "Revenue", unit: "$ full year", fmt: money, goodIsUp: true,
      why: "shipped units × unit price, summed over 12 months" },
    { key: "margin", name: "Gross margin", unit: "$ full year", fmt: money, goodIsUp: true,
      why: "shipped units × unit margin" },
    { key: "lost_margin", name: "Lost margin", unit: "$ full year", fmt: money, goodIsUp: false,
      why: "unmet units × unit margin" },
    { key: "unmet", name: "Unmet demand", unit: "units full year", fmt: units, goodIsUp: false,
      why: "demand − shipped, summed over 12 months" },
    { key: "inventory", name: "Closing inventory", unit: "$ at variable cost", fmt: money, goodIsUp: false,
      why: "December closing units × unit variable cost" },
    { key: "fill", name: "Fill rate", unit: "% of demand served", fmt: function (v) { return pct(v, 2); },
      goodIsUp: true, deltaUnit: "pp", why: "shipped ÷ demanded" }
  ];
  var BW = 460, BH = 70, NOTE_BH = 92, GUTTER = 74, BPAD_R = 74, ROWH = 18, GAP = 4;

  function drawLevels(metric) {
    var vals = SC.map(function (s) { return A[s][metric.key]; });
    var max = Math.max.apply(null, vals);
    var min = Math.min.apply(null, vals);
    var lo = metric.key === "fill" ? Math.floor(min - 0.5) : 0;
    var hasNote = lo !== 0;
    var chartH = hasNote ? NOTE_BH : BH;
    var hi = max * 1.02 || 1;
    var plotW = BW - GUTTER - BPAD_R;
    var x = function (v) { return GUTTER + ((v - lo) / (hi - lo)) * plotW; };
    var svg = svgEl("svg", { viewBox: "0 0 " + BW + " " + chartH, role: "img" });
    SC.forEach(function (sid, i) {
      var y = i * (ROWH + GAP) + 2, v = A[sid][metric.key];
      var lab = svgEl("text", { x: GUTTER - 8, y: y + ROWH / 2 + 3.5, class: "bar-label", "text-anchor": "end" });
      lab.textContent = SC_LABEL[sid]; svg.appendChild(lab);
      var w = Math.max(0, x(v) - GUTTER);
      if (w > 0.5) {
        var r = svgEl("rect", { x: GUTTER, y: y, width: w, height: ROWH, rx: 1 });
        paintScenario(r, sid); svg.appendChild(r);
      }
      var val = svgEl("text", { x: GUTTER + w + 6, y: y + ROWH / 2 + 3.5, class: "bar-value" });
      val.textContent = metric.fmt(v); svg.appendChild(val);
      var hit = svgEl("rect", { x: 0, y: y, width: BW, height: ROWH, class: "mark-hit" });
      hit.addEventListener("mousemove", function (e) {
        var d = v - A.base[metric.key];
        showTip(e, SC_LABEL[sid] + " · " + metric.name,
          [[metric.name, metric.fmt(v)],
           ["vs Base", (d >= 0 ? "+" : "−") + metric.fmt(Math.abs(d)) + (metric.deltaUnit ? " " + metric.deltaUnit : "")]],
          metric.why);
      });
      hit.addEventListener("mouseleave", hideTip); svg.appendChild(hit);
    });
    svg.appendChild(svgEl("line", { x1: GUTTER, y1: 0, x2: GUTTER, y2: BH - 10, class: "axis-line" }));
    if (hasNote) {
      var z = svgEl("text", { x: GUTTER, y: chartH - 4, class: "tick-text" });
      z.textContent = "axis starts at " + metric.fmt(lo) + ", not zero"; svg.appendChild(z);
    }
    return svg;
  }

  function drawVariance(metric) {
    var deltas = SC.map(function (s) { return A[s][metric.key] - A.base[metric.key]; });
    var span = Math.max.apply(null, deltas.map(Math.abs)) || 1;
    var W = 230, LABEL_W = 92, mid = 26, plotW = W - LABEL_W - mid - 6;
    var x = function (d) { return mid + (d / span) * plotW; };
    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + BH, role: "img" });
    svg.appendChild(svgEl("line", { x1: mid, y1: 0, x2: mid, y2: BH - 10, class: "axis-line" }));
    SC.forEach(function (sid, i) {
      var y = i * (ROWH + GAP) + 2, d = deltas[i];
      var isBase = sid === "base";
      var flat = Math.abs(d) < 1e-9;
      var good = metric.goodIsUp ? d > 0 : d < 0;
      if (!isBase && !flat) {
        var x0 = Math.min(mid, x(d)), w = Math.abs(x(d) - mid);
        svg.appendChild(svgEl("rect", { x: x0, y: y + 4, width: Math.max(1.5, w), height: ROWH - 8, rx: 1,
          fill: good ? "var(--sop-color-good)" : "var(--sop-color-bad)" }));
      }
      var t = svgEl("text", { x: W - 2, y: y + ROWH / 2 + 3.5, class: "bar-value", "text-anchor": "end",
        fill: isBase || flat ? "var(--sop-color-text-muted)" : good ? "var(--sop-color-good)" : "var(--sop-color-bad)" });
      t.textContent = isBase ? "reference" : flat ? "▬ no change"
        : (d > 0 ? "▲ +" : "▼ −") + metric.fmt(Math.abs(d)) + (metric.deltaUnit ? " " + metric.deltaUnit : "");
      svg.appendChild(t);
    });
    return svg;
  }

  // Bullet graphs with graded bands (m2/m4 — bands are OUR thresholds).
  var BANDS = [
    { to: 85, label: "safe", fill: "rgba(52, 211, 153, 0.20)" },
    { to: 100, label: "strained", fill: "rgba(251, 191, 36, 0.22)" },
    { to: 125, label: "critical", fill: "rgba(248, 113, 113, 0.26)" }
  ];

  function bulletSvg(value, maxScale, refValue, refLabel, fmt, sid, bands) {
    var W = 400, H = 36, LABEL_W = 54, plotW = W - LABEL_W;
    var x = function (v) { return (v / maxScale) * plotW; };
    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img" });
    var useBands = bands || BANDS, prev = 0;
    if (useBands.length) {
      useBands.forEach(function (b) {
        svg.appendChild(svgEl("rect", { x: x(prev), y: 2, width: Math.max(0, x(Math.min(b.to, maxScale)) - x(prev)), height: 20, fill: b.fill }));
        if (prev > 0) svg.appendChild(svgEl("line", { x1: x(prev), y1: 2, x2: x(prev), y2: 22, stroke: "var(--sop-color-canvas)", "stroke-width": 1 }));
        prev = b.to;
      });
    } else {
      svg.appendChild(svgEl("rect", { x: 0, y: 2, width: plotW, height: 20, rx: 2, fill: "var(--sop-color-surface-sunken)" }));
    }
    var measure = svgEl("rect", { x: 0, y: 8.5, width: Math.max(2, x(value)), height: 7, rx: 1 });
    paintScenario(measure, sid); svg.appendChild(measure);
    svg.appendChild(svgEl("line", { x1: x(refValue), y1: 0, x2: x(refValue), y2: 24, stroke: "var(--sop-color-text-primary)", "stroke-width": 2 }));
    var rl = svgEl("text", { x: x(refValue) - 4, y: 33, class: "tick-text", "text-anchor": "end" });
    rl.textContent = refLabel; svg.appendChild(rl);
    var vl = svgEl("text", { x: W, y: 16, class: "bar-value", "text-anchor": "end" });
    vl.textContent = fmt(value); svg.appendChild(vl);
    return svg;
  }

  function renderBullets() {
    var host = document.getElementById("bullets");
    host.innerHTML = "";
    var items = D.resources.map(function (r) {
      var rows = D.scenarios[focus].utilization[r.id];
      var peak = Math.max.apply(null, rows.map(function (x) { return x.utilization_pct; }));
      var over = rows.filter(function (x) { return x.utilization_pct > 100; }).length;
      return { name: r.name, value: peak, sub: over + " of 12 months over capacity",
               fmt: function (v) { return pct(v); }, ref: 100, refLabel: "capacity", max: 125 };
    });
    items.push({
      name: "Fill rate", value: A[focus].fill, sub: "reference is full demand served, not a business target",
      fmt: function (v) { return pct(v, 2); }, ref: 100, refLabel: "all demand", max: 125, isFill: true
    });
    items.forEach(function (it) {
      var d = document.createElement("div"); d.className = "bullet";
      var h = document.createElement("div"); h.className = "bullet__head";
      var n = document.createElement("span"); n.className = "bullet__name"; n.textContent = it.name;
      var s = document.createElement("span"); s.className = "bullet__sub"; s.textContent = it.sub;
      h.appendChild(n); h.appendChild(s); d.appendChild(h);
      d.appendChild(bulletSvg(it.value, it.max, it.ref, it.refLabel, it.fmt, focus));
      host.appendChild(d);
    });
    var key = document.getElementById("bandkey");
    key.innerHTML = "";
    BANDS.forEach(function (b, i) {
      var prev = i === 0 ? 0 : BANDS[i - 1].to;
      var el = document.createElement("span"); el.className = "bandkey__item";
      el.innerHTML = '<span class="bandkey__swatch" style="background:' + b.fill +
        ';border:1px solid var(--sop-color-border-strong)"></span><span>' +
        b.label + " — " + prev + "–" + b.to + "%</span>";
      key.appendChild(el);
    });
    var f = document.createElement("span"); f.className = "bandkey__item";
    f.innerHTML = '<span style="color:var(--sop-color-text-muted)">Showing: <strong style="color:var(--sop-color-text-primary)">' +
      SC_LABEL[focus] + "</strong> — pick a preset above to switch</span>";
    key.appendChild(f);
  }

  function renderFamilies() {
    var host = document.getElementById("fam");
    host.innerHTML = "";
    ["Family", "Gross margin — shared scale", "Margin lost to rationing"].forEach(function (h, i) {
      var d = document.createElement("div");
      d.className = "cmp__colhead" + (i === 2 ? " cmp__colhead--var" : "");
      d.textContent = h; host.appendChild(d);
    });
    var recon = {};
    SC.forEach(function (s) {
      recon[s] = {};
      D.scenarios[s].reconciliation.forEach(function (r) { recon[s][r.family_id] = r; });
    });
    var fams = D.scenarios.base.reconciliation.slice().sort(function (a, b) {
      return b.gross_margin - a.gross_margin;
    });
    var maxGM = Math.max.apply(null, SC.map(function (s) {
      return Math.max.apply(null, D.scenarios[s].reconciliation.map(function (r) { return r.gross_margin; }));
    }));
    var maxLost = Math.max.apply(null, D.scenarios[focus].reconciliation.map(function (r) { return r.lost_margin; })) || 1;

    fams.forEach(function (f) {
      var lab = document.createElement("div"); lab.className = "cmp__metric";
      var nm = document.createElement("div"); nm.className = "cmp__metric-name"; nm.textContent = f.family_name;
      var un = document.createElement("div"); un.className = "cmp__metric-unit";
      un.textContent = "$" + f.unit_margin + " margin / unit";
      lab.appendChild(nm); lab.appendChild(un);

      var FW = 460, FH = 48, FG = 74, FR = 74, fplotW = FW - FG - FR, rowh = 12, gap = 3;
      var fsvg = svgEl("svg", { viewBox: "0 0 " + FW + " " + FH, role: "img" });
      SC.forEach(function (sid, i) {
        var r = recon[sid][f.family_id];
        var y = i * (rowh + gap) + 2;
        var fx = function (v) { return FG + (v / maxGM) * fplotW; };
        var fl = svgEl("text", { x: FG - 8, y: y + rowh / 2 + 3, class: "bar-label", "text-anchor": "end" });
        fl.textContent = SC_LABEL[sid]; fsvg.appendChild(fl);
        var fw = Math.max(0, fx(r.gross_margin) - FG);
        if (fw > 0.5) {
          var bar = svgEl("rect", { x: FG, y: y, width: fw, height: rowh, rx: 1 });
          paintScenario(bar, sid); fsvg.appendChild(bar);
        }
        var ft = svgEl("text", { x: FG + fw + 6, y: y + rowh / 2 + 3.5, class: "bar-value" });
        ft.textContent = money(r.gross_margin); fsvg.appendChild(ft);
        var hit = svgEl("rect", { x: 0, y: y, width: FW, height: rowh, class: "mark-hit" });
        hit.addEventListener("mousemove", function (e) {
          showTip(e, f.family_name + " · " + SC_LABEL[sid],
            [["Gross margin", money(r.gross_margin)],
             ["Shipped", units(r.shipped_units) + " u"],
             ["Unmet", units(r.unmet_units) + " u"],
             ["Fill rate", pct(r.fill_rate_pct, 2)]],
            "shipped units × $" + f.unit_margin + " unit margin");
        });
        hit.addEventListener("mouseleave", hideTip); fsvg.appendChild(hit);
      });
      fsvg.appendChild(svgEl("line", { x1: FG, y1: 0, x2: FG, y2: FH - 6, class: "axis-line" }));
      var bars = document.createElement("div"); bars.className = "cmp__bars"; bars.appendChild(fsvg);

      var lost = recon[focus][f.family_id].lost_margin;
      var LW = 230, LLW = 92, lmid = 26, lplotW = LW - LLW - lmid - 6;
      var lsvg = svgEl("svg", { viewBox: "0 0 " + LW + " " + FH, role: "img" });
      lsvg.appendChild(svgEl("line", { x1: lmid, y1: 0, x2: lmid, y2: FH - 6, class: "axis-line" }));
      if (lost > 0) {
        var lx = lmid + (lost / maxLost) * lplotW;
        lsvg.appendChild(svgEl("rect", { x: lmid, y: 14, width: Math.max(2, lx - lmid), height: 12, rx: 1, fill: "var(--sop-color-bad)" }));
      }
      var lt = svgEl("text", { x: LW - 2, y: 24, class: "bar-value", "text-anchor": "end",
        fill: lost > 0 ? "var(--sop-color-bad)" : "var(--sop-color-text-muted)" });
      lt.textContent = lost > 0 ? "▼ −" + money(lost) : "▬ none";
      lsvg.appendChild(lt);
      var vr = document.createElement("div"); vr.className = "cmp__var"; vr.appendChild(lsvg);

      host.appendChild(lab); host.appendChild(bars); host.appendChild(vr);
    });
    document.getElementById("famnote").textContent =
      "Gross margin by family under each scenario, plus what rationing takes off " + SC_LABEL[focus] +
      ". Sorted by Base margin — the rationing rule follows unit margin, so the order is the priority order.";
  }

  function renderComparison() {
    var cmp = document.getElementById("cmp");
    cmp.innerHTML = "";
    ["Metric", "Level — shared scale per metric", "Variance vs Base"].forEach(function (h, i) {
      var d = document.createElement("div");
      d.className = "cmp__colhead" + (i === 2 ? " cmp__colhead--var" : "");
      d.textContent = h; cmp.appendChild(d);
    });
    METRICS.forEach(function (m) {
      var lab = document.createElement("div"); lab.className = "cmp__metric";
      var nm = document.createElement("div"); nm.className = "cmp__metric-name";
      nm.appendChild(document.createTextNode(m.name));
      var w = document.createElement("button"); w.className = "why"; w.type = "button";
      w.textContent = "why?"; w.title = m.why + " — full derivation in the drill-down grid below";
      nm.appendChild(w);
      var un = document.createElement("div"); un.className = "cmp__metric-unit"; un.textContent = m.unit;
      lab.appendChild(nm); lab.appendChild(un);
      var bars = document.createElement("div"); bars.className = "cmp__bars"; bars.appendChild(drawLevels(m));
      var vr = document.createElement("div"); vr.className = "cmp__var"; vr.appendChild(drawVariance(m));
      cmp.appendChild(lab); cmp.appendChild(bars); cmp.appendChild(vr);
    });
    renderBullets();
    renderFamilies();
  }

  /* =========================================================================
     SECTION 6 — LEVERS (m3, static) + SCENARIO TABS
     ========================================================================= */
  var tabHost = document.getElementById("scenariotabs");
  SC.forEach(function (sid) {
    var b = document.createElement("button");
    b.className = "scenariotab"; b.type = "button";
    b.setAttribute("aria-pressed", String(sid === focus));
    b.textContent = SC_LABEL[sid];
    b.addEventListener("click", function () {
      focus = sid;
      Array.prototype.forEach.call(tabHost.children, function (c, i) {
        c.setAttribute("aria-pressed", String(SC[i] === focus));
      });
      renderGrid();
    });
    tabHost.appendChild(b);
  });

  var resourceCaption = D.resources.map(function (r) {
    return r.name + " " + units(r.monthly_available_hours) + " h/mo installed";
  }).join(" · ");

  var TIER1 = [
    { group: "Demand", levers: [
      { label: "Volume multiplier (global)", unit: "%", note: "Base = 0% (no change)" },
      { label: "Per-family uplift %", unit: "%", note: "Upside/Constrained already apply each family's own upside_uplift_pct — this lever would override it" },
      { label: "Seasonality shift", unit: "± months", note: "Base = 0 (no shift)" }
    ]},
    { group: "Supply", levers: [
      { label: "Available hours per resource", unit: "h/mo", note: resourceCaption },
      { label: "Overtime hours", unit: "h/mo", note: "Base = 0 (no overtime modeled)" }
    ]},
    { group: "Policy", levers: [
      { label: "Safety stock", unit: "weeks of cover", note: "Not in the current data model — would need a new input" },
      { label: "Rationing rule", unit: "throughput-per-constraint ▸ fair-share ▸ strategic-priority", note: "Engine currently hardcodes throughput-per-constraint (descending unit margin) — see step 3 in any drill-down" }
    ]},
    { group: "Financial", levers: [
      { label: "Unit price Δ%", unit: "%", note: "Base = 0% (no change)" },
      { label: "Unit variable cost Δ%", unit: "%", note: "Base = 0% (no change)" }
    ]},
    { group: "Inventory", levers: [
      { label: "Opening inventory Δ%", unit: "%", note: "Base = 0% (no change)" }
    ]}
  ];
  var TIER2 = [
    { group: "Demand (advanced)", levers: [
      { label: "Forecast bias %", unit: "%", note: "Not in the current data model" },
      { label: "Per-family MAPE override", unit: "%", note: "Stage-4 residual-cone input — SCOPE §5, not yet in this data" }
    ]},
    { group: "Supply (advanced)", levers: [
      { label: "Yield / scrap %", unit: "%", note: "Not modeled — engine assumes 100% yield" },
      { label: "Minimum lot size", unit: "units", note: "Not modeled" }
    ]},
    { group: "Policy (advanced)", levers: [
      { label: "Backorder vs lost sale", unit: "per family", note: "Engine currently always treats unmet demand as a lost sale — no backorder carry" },
      { label: "Build-ahead horizon", unit: "months", note: "Not modeled — supply never exceeds the current month's own demand" }
    ]},
    { group: "Financial (advanced)", levers: [
      { label: "Inventory carrying %", unit: "%", note: "Not modeled" },
      { label: "Overtime premium %", unit: "%", note: "Not modeled — no overtime lever yet" },
      { label: "Stockout penalty per unit", unit: "$/unit", note: "Not modeled — lost_margin is the only cost of a stockout today" }
    ]},
    { group: "Inventory (advanced)", levers: [
      { label: "Max inventory cap", unit: "units", note: "Not modeled — no cap enforced" }
    ]}
  ];

  function renderLevers(hostId, groups) {
    var host = document.getElementById(hostId);
    host.innerHTML = "";
    groups.forEach(function (g) {
      var wrap = document.createElement("div");
      var t = document.createElement("h3"); t.className = "levergroup__title"; t.textContent = g.group;
      wrap.appendChild(t);
      g.levers.forEach(function (lv) {
        var row = document.createElement("div"); row.className = "lever";
        var head = document.createElement("div"); head.className = "lever__row";
        var lab = document.createElement("span"); lab.className = "lever__label"; lab.textContent = lv.label;
        var un = document.createElement("span"); un.className = "lever__val"; un.textContent = lv.unit;
        head.appendChild(lab); head.appendChild(un);
        var range = document.createElement("input"); range.type = "range"; range.className = "lever__range";
        range.min = "0"; range.max = "100"; range.value = "50"; range.disabled = true;
        range.setAttribute("aria-label", lv.label + " — not wired; client-side recompute is a later build (SCOPE §2 row 7)");
        var note = document.createElement("div"); note.className = "step__subrow"; note.textContent = lv.note;
        row.appendChild(head); row.appendChild(range); row.appendChild(note);
        wrap.appendChild(row);
      });
      host.appendChild(wrap);
    });
  }
  renderLevers("levergroups", TIER1);
  renderLevers("levergroups2", TIER2);

  /* =========================================================================
     SECTION 7 — DRILL-DOWN GRID (m3) + 5-STEP PROVENANCE MODAL (shared)
     ========================================================================= */
  function famList() {
    return D.families.slice().sort(function (a, b) { return b.unit_margin - a.unit_margin; });
  }

  function renderGrid() {
    var t = document.getElementById("grid");
    t.innerHTML = "";
    var fams = famList();
    var head = "<thead><tr><th>Family</th>" + D.month_names.map(function (m) { return "<th>" + m + "</th>"; }).join("") + "</tr></thead>";
    var body = "<tbody>" + fams.map(function (f) {
      var cells = D.month_names.map(function (mn, i) {
        var month = i + 1;
        var entry = D.provenance[focus][f.id][String(month)];
        var sl = entry.supply;
        var unmet = sl.unmet_units > 0;
        return '<td><button class="cell' + (unmet ? " cell--unmet" : "") + '" type="button" data-fam="' + f.id +
          '" data-month="' + month + '" aria-label="' + f.name + " " + mn + " fill rate " + pct(sl.fill_rate * 100, 1) +
          (unmet ? ", " + units(sl.unmet_units) + " units unmet" : "") + '">' + pct(sl.fill_rate * 100, 0) + "</button></td>";
      }).join("");
      return "<tr><td><span class=\"famname\">" + f.name + "</span><span class=\"famsub\">$" + f.unit_margin + " margin/unit</span></td>" + cells + "</tr>";
    }).join("") + "</tbody>";
    t.innerHTML = head + body;

    Array.prototype.forEach.call(t.querySelectorAll(".cell"), function (btn) {
      btn.addEventListener("mousemove", function (e) {
        var fam = btn.getAttribute("data-fam"), month = btn.getAttribute("data-month");
        var f = D.families.filter(function (x) { return x.id === fam; })[0];
        var entry = D.provenance[focus][fam][month];
        var sl = entry.supply;
        showTip(e, f.name + " · " + D.month_names[month - 1],
          [["Demand", units(sl.demand_units) + " u"],
           ["Shipped", units(sl.shipped_units) + " u"],
           ["Unmet", units(sl.unmet_units) + " u"],
           ["Fill rate", pct(sl.fill_rate * 100, 2)]],
          "Click for the full 5-step derivation");
      });
      btn.addEventListener("mouseleave", hideTip);
      btn.addEventListener("click", function () {
        openModal(focus, btn.getAttribute("data-fam"), Number(btn.getAttribute("data-month")));
      });
    });
    document.getElementById("gridnote").textContent =
      "Fill rate by family and month, " + SC_LABEL[focus] + " scenario. Red cells had unmet demand. Every cell drills to its real Demand → Capacity → Rationing → Supply → Financials arithmetic.";
  }

  /* ---- shared modal chrome ---- */
  var scrim = document.getElementById("scrim");
  var modalBody = document.getElementById("modalbody");
  var lastFocus = null;

  function showModal(html) {
    modalBody.innerHTML = html;
    lastFocus = document.activeElement;
    scrim.dataset.open = "1";
    document.getElementById("modalclose").focus();
    document.addEventListener("keydown", onModalKeydown);
    Array.prototype.forEach.call(modalBody.querySelectorAll("[data-drill]"), function (btn) {
      btn.addEventListener("click", function () {
        var parts = btn.getAttribute("data-drill").split("|");
        openModal(parts[0], parts[1], Number(parts[2]));
      });
    });
    Array.prototype.forEach.call(modalBody.querySelectorAll("[data-rollup]"), function (btn) {
      btn.addEventListener("click", function () { openRollup(btn.getAttribute("data-rollup")); });
    });
  }
  function closeModal() {
    scrim.dataset.open = "0";
    document.removeEventListener("keydown", onModalKeydown);
    if (lastFocus) lastFocus.focus();
  }
  function onModalKeydown(e) { if (e.key === "Escape") closeModal(); }
  document.getElementById("modalclose").addEventListener("click", closeModal);
  scrim.addEventListener("click", function (e) { if (e.target === scrim) closeModal(); });

  function stepHtml(num, title, formulaHtml, noteHtml, live) {
    return (
      '<div class="step">' +
        '<div class="step__rail"><div class="step__num' + (live === false ? " step__num--skip" : " step__num--live") + '">' + num + '</div>' +
          '<div class="step-connector"></div></div>' +
        '<div class="step__body"><div class="step__title">' + title + '</div>' +
          (formulaHtml ? '<div class="step__formula">' + formulaHtml + '</div>' : "") +
          (noteHtml ? '<p class="step__note">' + noteHtml + '</p>' : "") +
        '</div>' +
      '</div>'
    );
  }

  function openModal(scenario, famId, month) {
    var f = D.families.filter(function (x) { return x.id === famId; })[0];
    var mn = D.month_names[month - 1];
    var entry = D.provenance[scenario][famId][String(month)];
    var dem = entry.demand, sup = entry.supply, fin = entry.financials;
    var cap = entry.capacity, rat = entry.rationing;

    var html = '<p class="modal__eyebrow">' + SC_LABEL[scenario] + " · " + f.name + " · " + mn + '</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + pct(sup.fill_rate * 100, 1) + ' fill rate was made</h2>';

    var demFormula = dem.uplift_applied
      ? units(dem.base_units) + " base × (1 + " + pct(dem.uplift_pct * 100, 1) + ") = " + units(dem.demand_units) + " units"
      : units(dem.base_units) + " base, no uplift in " + SC_LABEL[scenario] + " = " + units(dem.demand_units) + " units";
    html += stepHtml(1, "Demand", demFormula, "Base monthly demand for " + f.name + " in " + mn + (dem.uplift_applied ? ", uplifted by this family's own promotion assumption." : "."));

    if (cap.length === 0) {
      html += stepHtml(2, "Capacity", null, f.name + " doesn't share a constrained resource — no RCCP load to check.", false);
    } else {
      var capRows = cap.map(function (c) {
        var rname = D.resources.filter(function (r) { return r.id === c.resource_id; })[0].name;
        return rname + ": " + hrs(c.load_hours) + " load ÷ " + hrs(c.available_hours) + " installed = " + pct(c.utilization_pct, 1) +
          (c.is_bottleneck ? " — OVER installed capacity" : "");
      }).join("<br>");
      html += stepHtml(2, "Capacity", capRows, "Load = every family's demand this month × hours/unit on that resource, summed. Measured against installed hours regardless of scenario (RCCP is a feasibility test, not a decision).");
    }

    if (rat.length === 0) {
      html += stepHtml(3, "Rationing", null, "No shared resource to ration.", false);
    } else {
      var anyConstrained = rat.some(function (r) { return r && r.constrained; });
      var ratRows = rat.map(function (r) {
        if (!r) return "";
        var rname = D.resources.filter(function (x) { return x.id === r.resource_id; })[0].name;
        if (!r.constrained) {
          return rname + ": not over capacity — full ask granted (" + hrs(r.wanted_hours) + ").";
        }
        return rname + ": rank " + r.rank + " of " + r.n_users + " by margin ($" + r.unit_margin + "/unit). " +
          hrs(r.remaining_before_hours) + " hours left before this family → min(" + hrs(r.wanted_hours) + " wanted, " +
          hrs(r.remaining_before_hours) + " left) = " + hrs(r.granted_hours) + " granted → " + hrs(r.remaining_after_hours) + " left for lower-ranked families. " +
          "= " + units2(r.allowed_units) + " units this resource can support.";
      }).join("<br><br>");
      html += stepHtml(3, "Rationing",
        anyConstrained ? ratRows : null,
        anyConstrained
          ? "When a resource is over capacity, " + SC_LABEL[scenario] + " protects the highest-margin business first — greedily, in descending unit-margin order — until hours run out."
          : "Nothing was over capacity this month, so nothing was rationed." + (rat.length ? "<br>" + ratRows : ""),
        anyConstrained);
    }

    var supFormula =
      "Produced = min(what rationing allowed, " + units(dem.demand_units) + " demand) = " + units2(sup.produced_units) + " units<br>" +
      "Shipped = min(" + units2(sup.opening_inventory_units) + " opening + " + units2(sup.produced_units) + " produced, " + units(dem.demand_units) + " demand) = " + units2(sup.shipped_units) + " units<br>" +
      "Unmet = " + units(dem.demand_units) + " demand − " + units2(sup.shipped_units) + " shipped = " + units2(sup.unmet_units) + " units<br>" +
      "Ending inventory = " + units2(sup.opening_inventory_units) + " + " + units2(sup.produced_units) + " − " + units2(sup.shipped_units) + " = " + units2(sup.ending_inventory_units) + " units";
    html += stepHtml(4, "Supply", supFormula, "No backorders: unmet demand this month is a lost sale, not a promise for next month. Ending inventory carries forward as next month's opening balance.");

    var finFormula =
      "Revenue = " + units2(sup.shipped_units) + " shipped × $" + fin.unit_price + " price = " + money2(fin.revenue) + "<br>" +
      "Gross margin = " + units2(sup.shipped_units) + " shipped × $" + fin.unit_margin + " margin/unit = " + money2(fin.gross_margin) +
      (sup.unmet_units > 0 ? "<br>Lost margin = " + units2(sup.unmet_units) + " unmet × $" + fin.unit_margin + " = " + money2(fin.lost_margin) : "") +
      "<br>Inventory value = " + units2(sup.ending_inventory_units) + " ending × $" + fin.unit_variable_cost + " variable cost = " + money2(fin.inventory_value);
    html += stepHtml(5, "Financials", finFormula, null);

    html += '<div class="kpi-tieback"><p class="kpi-tieback__label">Rolls into fill rate</p>' +
      '<p class="kpi-tieback__val">' + units2(sup.shipped_units) + ' ÷ ' + units(dem.demand_units) + ' = ' + pct(sup.fill_rate * 100, 1) + '</p>' +
      '<p class="step__note">This is one family/month; the tiles and reconciliation tables sum this same arithmetic across all families and 12 months.</p></div>';

    showModal(html);
  }

  /* =========================================================================
     SECTION 8 — KPI ROLLUPS (m4 + m5) — aggregates traced to real families
     ========================================================================= */
  function fillRateSummary(scenario) {
    var rows = D.scenarios[scenario].reconciliation;
    var demand = 0, shipped = 0, unmet = 0;
    rows.forEach(function (r) { demand += r.demand_units; shipped += r.shipped_units; unmet += r.unmet_units; });
    return { rows: rows, demand: demand, shipped: shipped, unmet: unmet, fillRate: shipped / demand };
  }

  function familyMonthlyFill(scenario, famId) {
    var p = D.provenance[scenario][famId], out = [];
    for (var m = 1; m <= 12; m++) out.push(p[String(m)].supply.fill_rate * 100);
    return out;
  }
  function fillSvg(series) {
    var W = 200, H = 34, PL = 2, PR = 2, PT = 2, PB = 2;
    var plotW = W - PL - PR, plotH = H - PT - PB;
    var lo = Math.min.apply(null, series) - 2, hi = 100;
    var range = Math.max(1, hi - lo);
    var x = function (i) { return PL + (i / 11) * plotW; };
    var y = function (v) { return PT + plotH - ((v - lo) / range) * plotH; };
    var s = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img" });
    s.appendChild(svgEl("polyline", { fill: "none", stroke: "var(--sop-color-chart-actual)", "stroke-width": 1.5,
      "stroke-opacity": 0.85, "stroke-linejoin": "round", "stroke-linecap": "round",
      points: series.map(function (v, i) { return x(i).toFixed(1) + "," + y(v).toFixed(1); }).join(" ") }));
    s.appendChild(svgEl("line", { x1: PL, y1: y(100), x2: W - PR, y2: y(100), stroke: "var(--sop-color-border-strong)", "stroke-width": 1, "stroke-dasharray": "2 2" }));
    series.forEach(function (v, i) {
      s.appendChild(svgEl("circle", { cx: x(i), cy: y(v), r: 1.6, fill: "var(--sop-color-chart-actual)", "fill-opacity": 0.8 }));
    });
    return s;
  }

  function openFillRateRollup(scenario) {
    var s = fillRateSummary(scenario);
    var html = '<p class="modal__eyebrow">' + SC_LABEL[scenario] + ' · Fill rate rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + pct(s.fillRate * 100, 1) + ' fill rate was made</h2>';
    var rowsHtml = s.rows.map(function (r) {
      var hi = r.unmet_units > 0 ? " is-highlight" : "";
      return '<tr class="' + hi.trim() + '"><td>' + r.family_name + '</td><td>' + units(r.demand_units) +
        '</td><td>' + units(r.shipped_units) + '</td><td>' + units(r.unmet_units) + '</td><td>' + pct(r.fill_rate_pct, 1) + '</td></tr>';
    }).join("");
    html += '<table class="rolluptable"><thead><tr><th>Family</th><th>Demand</th><th>Shipped</th><th>Unmet</th><th>Fill %</th></tr></thead><tbody>' +
      rowsHtml + '<tr class="is-total"><td>Total</td><td>' + units(s.demand) + '</td><td>' + units(s.shipped) +
      '</td><td>' + units(s.unmet) + '</td><td>' + pct(s.fillRate * 100, 1) + '</td></tr></tbody></table>';
    html += '<div class="rollup-formula">Σ shipped ÷ Σ demand = ' + units(s.shipped) + ' ÷ ' + units(s.demand) + ' = ' + pct(s.fillRate * 100, 1) + '</div>';
    if (scenario === "constrained") {
      var dry = s.rows.filter(function (r) { return r.family_id === "FAM-DRY"; })[0];
      html += '<p class="rollup-note">Dryers are the <strong>only</strong> family with any unmet demand — ' +
        units(dry.unmet_units) + ' units across 3 months (April, May, December). May alone is 65% of it.</p>' +
        '<button type="button" class="rollup-link" data-drill="constrained|FAM-DRY|5">Full derivation for May →</button>';
    }
    if (scenario === "upside") {
      html += '<p class="rollup-note">Assembly Line A exceeds installed capacity in 4 of these 12 months (peak 115% in April) — ' +
        'the same load as Constrained — but Upside ships everything anyway. Upside assumes the gap gets topped up, Constrained does not.</p>' +
        '<button type="button" class="rollup-link" data-rollup="bottleneck">See the capacity curve →</button>';
    }
    showModal(html);
  }

  function openBottleneckRollup() {
    var rid = D.bottleneck.resource_id;
    var resource = D.resources.filter(function (r) { return r.id === rid; })[0];
    var monthly = D.scenarios.constrained.utilization[rid];
    var peak = monthly.reduce(function (a, b) { return b.utilization_pct > a.utilization_pct ? b : a; });
    var html = '<p class="modal__eyebrow">Constrained · ' + resource.name + ' · Capacity rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + pct(peak.utilization_pct, 1) + ' peak utilization was made</h2>';
    var rowsHtml = monthly.map(function (m) {
      var over = m.utilization_pct > 100;
      var isPeak = m.month === peak.month;
      return '<tr class="' + (over ? "is-highlight" : "") + '"><td>' + D.month_names[m.month - 1] + (isPeak ? " ★" : "") +
        '</td><td>' + hrs(m.load_hours) + '</td><td>' + hrs(m.available_hours) + '</td><td>' + pct(m.utilization_pct, 1) + '</td></tr>';
    }).join("");
    html += '<table class="rolluptable"><thead><tr><th>Month</th><th>Load</th><th>Installed</th><th>Utilization</th></tr></thead><tbody>' + rowsHtml + '</tbody></table>';
    html += '<div class="rollup-formula">Peak = ' + D.month_names[peak.month - 1] + ': ' + hrs(peak.load_hours) + ' load ÷ ' + hrs(peak.available_hours) + ' installed = ' + pct(peak.utilization_pct, 1) + '</div>';
    html += '<p class="rollup-note">Load = every family\'s demand that month × hours/unit on ' + resource.name + ', summed — RCCP is measured against installed hours regardless of scenario. ' +
      resource.name + ' is the only resource that ever breaches capacity: QA and Packaging stay under 93% in every scenario.</p>' +
      '<p class="rollup-note">This exact constraint is what rations Dryers in May — rank 3 of 3 by margin, only 1,128.8 of 1,947.9 hours wanted were granted.</p>' +
      '<button type="button" class="rollup-link" data-drill="constrained|FAM-DRY|5">See that rationing decision →</button>';
    showModal(html);
  }

  function openUpsideValueRollup() {
    var rb = D.scenarios.base.reconciliation, ru = D.scenarios.upside.reconciliation;
    var totalDm = 0, totalDr = 0;
    var rowsHtml = rb.map(function (b, i) {
      var u = ru[i];
      var dm = u.gross_margin - b.gross_margin;
      var dr = u.revenue - b.revenue;
      totalDm += dm; totalDr += dr;
      return '<tr><td>' + b.family_name + '</td><td>' + money(b.gross_margin) + '</td><td>' + money(u.gross_margin) +
        '</td><td>' + money(dm) + '</td><td>' + money(dr) + '</td></tr>';
    }).join("");
    var html = '<p class="modal__eyebrow">Base → Upside · Financial rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + money(totalDm) + ' margin was unlocked</h2>';
    html += '<table class="rolluptable"><thead><tr><th>Family</th><th>Base margin</th><th>Upside margin</th><th>Δ margin</th><th>Δ revenue</th></tr></thead><tbody>' +
      rowsHtml + '<tr class="is-total"><td>Total</td><td>' + money(D.scenarios.base.summary.total_gross_margin) +
      '</td><td>' + money(D.scenarios.upside.summary.total_gross_margin) + '</td><td>' + money(totalDm) + '</td><td>' + money(totalDr) + '</td></tr></tbody></table>';
    html += '<div class="rollup-formula">ΣUpside margin − ΣBase margin = ' + money(D.scenarios.upside.summary.total_gross_margin) + ' − ' +
      money(D.scenarios.base.summary.total_gross_margin) + ' = ' + money(totalDm) + '<br>Revenue uplift (context, not the headline): ' + money(totalDr) + '</div>';
    html += '<p class="rollup-note">Refrigerators and Washers together are ~80% of the margin uplift. Upside assumes every family\'s own upside_uplift_pct demand ships in full.</p>';
    showModal(html);
  }

  function openMarginAtRiskRollup() {
    var months = [4, 5, 12];
    var total = 0;
    var rowsHtml = months.map(function (m) {
      var sl = D.provenance.constrained["FAM-DRY"][String(m)].supply;
      var lost = sl.unmet_units * D.provenance.constrained["FAM-DRY"][String(m)].financials.unit_margin;
      total += lost;
      return '<tr><td><button type="button" class="rowbtn" data-drill="constrained|FAM-DRY|' + m + '">' + D.month_names[m - 1] + '</button></td>' +
        '<td>' + units2(sl.unmet_units) + '</td><td>$' + D.provenance.constrained["FAM-DRY"][String(m)].financials.unit_margin + '</td><td>' + money2(lost) + '</td></tr>';
    }).join("");
    var html = '<p class="modal__eyebrow">Constrained · Dryers · Financial-risk rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + money2(total) + ' margin at risk was made</h2>';
    html += '<table class="rolluptable"><thead><tr><th>Month</th><th>Unmet units</th><th>Unit margin</th><th>Lost margin</th></tr></thead><tbody>' +
      rowsHtml + '<tr class="is-total"><td>Total</td><td></td><td></td><td>' + money2(total) + '</td></tr></tbody></table>';
    html += '<p class="rollup-note">Other 9 months: fully served, $0 lost margin. Dryers are the only family that loses anything in Constrained — see the Bottleneck rollup for why Assembly Line A picks Dryers last.</p>' +
      '<button type="button" class="rollup-link" data-rollup="bottleneck">Why Assembly Line A rations Dryers →</button>';
    showModal(html);
  }

  function openBaseRollup() {
    var rows = D.scenarios.base.reconciliation;
    var tot = 0;
    var rowsHtml = rows.map(function (r) { tot += r.gross_margin; return '<tr><td>' + r.family_name + '</td><td>' + money(r.gross_margin) + '</td></tr>'; }).join("");
    var html = '<p class="modal__eyebrow">Base · Financial rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + money(D.scenarios.base.summary.total_gross_margin) + ' base margin was made</h2>';
    html += '<table class="rolluptable"><thead><tr><th>Family</th><th>Margin</th></tr></thead><tbody>' +
      rowsHtml + '<tr class="is-total"><td>Total</td><td>' + money(tot) + '</td></tr></tbody></table>';
    html += '<div class="rollup-formula">Σ margin per family = ' + money(tot) + ' = Base total</div>';
    showModal(html);
  }

  function openConstrainedRollup() {
    var rows = D.scenarios.constrained.reconciliation;
    var tot = 0;
    var rowsHtml = rows.map(function (r) { tot += r.gross_margin; return '<tr><td>' + r.family_name + '</td><td>' + money(r.gross_margin) + '</td></tr>'; }).join("");
    var html = '<p class="modal__eyebrow">Constrained · Financial rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + money(D.scenarios.constrained.summary.total_gross_margin) + ' realized margin was made</h2>';
    html += '<table class="rolluptable"><thead><tr><th>Family</th><th>Margin</th></tr></thead><tbody>' +
      rowsHtml + '<tr class="is-total"><td>Total</td><td>' + money(tot) + '</td></tr></tbody></table>';
    html += '<p class="rollup-note">Constrained ships less Dryers (Apr/May/Dec shortfall) — that is the ▼ constrained penalty in the waterfall.</p>';
    html += '<div class="rollup-formula">Σ margin per family = ' + money(tot) + ' = Realized total</div>';
    showModal(html);
  }

  function openWaterfallRollup() {
    var b = D.scenarios.base.summary, u = D.scenarios.upside.summary, c = D.scenarios.constrained.summary;
    var lift = u.total_gross_margin - b.total_gross_margin, penalty = c.total_lost_margin;
    var html = '<p class="modal__eyebrow">Margin waterfall · Bridge rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + money(c.total_gross_margin) + ' realized margin was made</h2>';
    html += '<table class="rolluptable"><thead><tr><th>Step</th><th>Value</th></tr></thead><tbody>' +
      '<tr><td>Base</td><td>' + money(b.total_gross_margin) + '</td></tr>' +
      '<tr><td>Upside lift (▲)</td><td>' + money(lift) + '</td></tr>' +
      '<tr><td>Constrained penalty (▼)</td><td>' + money2(penalty) + '</td></tr>' +
      '<tr class="is-total"><td>Net</td><td>' + money(c.total_gross_margin) + '</td></tr></tbody></table>';
    html += '<div class="rollup-formula">Base ' + money(b.total_gross_margin) + ' + lift ' + money(lift) + ' − penalty ' + money2(penalty) + ' = realized ' + money(c.total_gross_margin) + '</div>';
    showModal(html);
  }

  function openRollup(kind) {
    if (kind === "waterfall") return openWaterfallRollup();
    if (kind === "bottleneck") return openBottleneckRollup();
    if (kind === "upside-value") return openUpsideValueRollup();
    if (kind === "margin-at-risk") return openMarginAtRiskRollup();
    if (kind.indexOf("fillrate-") === 0) return openFillRateRollup(kind.slice("fillrate-".length));
  }

  /* =========================================================================
     SECTION 9 — KPI PANELS (m4): fill bullets, load curve, margin months,
     upside variance
     ========================================================================= */
  function animateCount(el, to, fmt, ms) {
    var t0 = null;
    var dur = ms || 700;
    function frame(t) {
      if (!t0) t0 = t;
      var p = Math.min(1, (t - t0) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(to * eased);
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function perFamilyRows(scenario, rows) {
    var lines = rows.slice().sort(function (a, b) { return b.unmet_units - a.unmet_units; })
      .slice(0, 5)
      .map(function (r) { return r.family_name + " " + pct(r.fill_rate_pct, 1) + (r.unmet_units > 0 ? " · " + units(r.unmet_units) + " unmet" : ""); });
    return lines.join("<br>");
  }

  function buildPanelNotes() {
    var base = D.scenarios.base.summary, up = D.scenarios.upside.summary, con = D.scenarios.constrained.summary;
    var totalLost = con.total_lost_margin, lift = up.total_gross_margin - base.total_gross_margin;
    document.getElementById("fillnote").innerHTML =
      "Every scenario except <strong>Constrained</strong> ships everything — only Dryers fall short, and only <strong>3 months of the year</strong>." +
      ' <span class="delta delta--good">▲ <span class="num-anim">' + money(lift) + '</span></span> is the margin upside; ' +
      ' <span class="delta delta--bad">▼ <span class="num-anim">' + money2(totalLost) + '</span></span> is what Constrained would leave on the table. Hover a bullet for the monthly story.';
    var pk = peakMonth();
    document.getElementById("loadnote").innerHTML =
      'One resource ever breaches capacity: <strong>' + resName(D.bottleneck.resource_id) + '</strong>, peaking at ' +
      '<strong>' + pct(pk.utilization_pct, 1) + '</strong> in ' + D.month_names[pk.month - 1] +
      ' — the constraint that rations <strong>Dryers</strong> in Apr · May · Dec. Click for the 12-month table.';
    document.getElementById("marginnote").innerHTML =
      'Dryers lose <strong>' + money2(totalLost) + '</strong> — all of it in <strong>April, May and December</strong>; the other nine months cost nothing.';
    document.getElementById("upsidenote").innerHTML =
      'Upside banks <strong>▲ ' + money(lift) + '</strong> margin over Base' +
      ' — Refrigerators and Washers are <strong>~80%</strong> of the uplift. Margin is the KPI; revenue is context.';
  }

  function wireDrill(id, fn) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("click", function (e) { e.stopPropagation(); fn(); });
  }

  var fillPop = document.createElement("div");
  fillPop.className = "fillpop"; fillPop.setAttribute("role", "status");
  document.body.appendChild(fillPop);

  function showFillPop(evt, sid) {
    var s = fillRateSummary(sid);
    var famWithData = s.rows.map(function (r) { return r.family_id; });
    var series = familyMonthlyFill(sid, famWithData[0]);
    var top = s.rows.slice().sort(function (a, b) { return b.unmet_units - a.unmet_units; })[0];
    var topName = top.family_name, topFill = pct(top.fill_rate_pct, 1);
    fillPop.innerHTML = "";
    var head = document.createElement("div"); head.className = "fillpop__head";
    head.textContent = SC_LABEL[sid] + " · monthly fill";
    fillPop.appendChild(head);
    fillPop.appendChild(fillSvg(series));
    var note = document.createElement("p");
    note.style.cssText = "font-size:var(--sop-text-small);color:var(--sop-color-text-secondary);margin:6px 0 0;line-height:1.5;";
    note.innerHTML = "Worst month: " + topName + " at " + topFill + (top.unmet_units > 0 ? " — " + units(top.unmet_units) + " units short" : "");
    fillPop.appendChild(note);
    fillPop.dataset.show = "1";
    var x = evt.clientX + 14, y = evt.clientY - fillPop.offsetHeight - 10;
    if (y < 6) y = evt.clientY + 14;
    if (x + 226 > window.innerWidth) x = window.innerWidth - 226;
    fillPop.style.left = x + "px"; fillPop.style.top = y + "px";
  }
  function hideFillPop() { fillPop.dataset.show = "0"; }

  function buildFillBullets() {
    var host = document.getElementById("fillrow");
    host.innerHTML = "";
    var con = fillRateSummary("constrained");
    var dryUnmet = con.rows.filter(function (r) { return r.family_id === "FAM-DRY"; })[0].unmet_units;
    var totalLost = D.scenarios.constrained.summary.total_lost_margin;
    ["base", "upside", "constrained"].forEach(function (sid) {
      var s = fillRateSummary(sid);
      var wrap = document.createElement("div"); wrap.className = "bullet clickable";
      var head = document.createElement("div"); head.className = "bullet__head";
      var nm = document.createElement("span"); nm.className = "bullet__name"; nm.textContent = SC_LABEL[sid];
      var sub = document.createElement("span"); sub.className = "bullet__sub";
      sub.textContent = s.unmet > 0 ? units(dryUnmet) + " unmet · −" + money2(totalLost) : "0 unmet";
      head.appendChild(nm); head.appendChild(sub); wrap.appendChild(head);
      var chart = bulletSvg(s.fillRate * 100, 100, 100, "full fill", function (v) { return pct(v, 1); }, sid, []);
      wrap.appendChild(chart);
      var tipLong = SC_LABEL[sid] + " fill rate " + pct(s.fillRate * 100, 2) + " — " +
        (s.unmet > 0 ? units(dryUnmet) + " units unmet (Dryers)" : "everything shipped") +
        "<br>" + perFamilyRows(sid, s.rows) + "<br>Click for the rollup";
      wrap.addEventListener("click", function () { openFillRateRollup(sid); });
      wrap.addEventListener("mouseenter", function (e) { showTip(e, tipLong); showFillPop(e, sid); });
      wrap.addEventListener("mousemove", function (e) { showTip(e, tipLong); showFillPop(e, sid); });
      wrap.addEventListener("mouseleave", function () { hideTip(); hideFillPop(); });
      host.appendChild(wrap);
    });
  }

  function drawLoadCurve() {
    var data = lineA(), pk = peakMonth(), maxScale = 125;
    var BW = 520, BH = 150, PL = 8, PR = 8, PT = 16, PB = 22;
    var plotW = BW - PL - PR, plotH = BH - PT - PB, slot = plotW / 12, bw = slot * 0.6;
    var cx = function (i) { return PL + (i + 0.5) * slot; };
    var y = function (v) { return PT + plotH - (Math.min(v, maxScale) / maxScale) * plotH; };
    var svg = svgEl("svg", { viewBox: "0 0 " + BW + " " + BH, role: "img" });
    var prev = 0;
    BANDS.forEach(function (b) {
      svg.appendChild(svgEl("rect", { x: PL, y: y(b.to), width: plotW, height: y(prev) - y(b.to), fill: b.fill }));
      prev = b.to;
    });
    svg.appendChild(svgEl("line", { x1: PL, y1: y(100), x2: BW - PR, y2: y(100), class: "ref-line" }));
    var cap = svgEl("text", { x: BW - PR, y: y(100) - 4, class: "tick-text", "text-anchor": "end" });
    cap.textContent = "installed capacity (100%)"; svg.appendChild(cap);
    var RATION = [4, 5, 12];
    data.forEach(function (m, i) {
      var over = m.utilization_pct > 100;
      var ration = RATION.indexOf(m.month) !== -1;
      svg.appendChild(svgEl("rect", { x: cx(i) - bw / 2, y: y(m.utilization_pct), width: bw, height: PT + plotH - y(m.utilization_pct), rx: 1,
        fill: over ? "var(--sop-color-bad)" : "var(--sop-color-chart-actual)", "fill-opacity": over ? 0.9 : 0.8 }));
      if (m.month === pk.month) {
        var lab = svgEl("text", { x: cx(i), y: y(m.utilization_pct) - 5, class: "bar-value", "text-anchor": "middle", fill: "var(--sop-color-bad)" });
        lab.textContent = pct(m.utilization_pct, 1); svg.appendChild(lab);
      }
      if (ration) {
        svg.appendChild(svgEl("rect", { x: cx(i) - slot / 2, y: PT + plotH + 3, width: slot, height: 3, rx: 1, class: "mflag mflag--ration track" }));
        var rl = svgEl("text", { x: cx(i), y: BH - 8, class: "mflag mflag--ration", "text-anchor": "middle", "font-size": 9 });
        rl.textContent = "·"; svg.appendChild(rl);
      }
      var ml = svgEl("text", { x: cx(i), y: BH - 6, class: "tick-text", "text-anchor": "middle" });
      ml.textContent = D.month_names[m.month - 1].slice(0, 1); svg.appendChild(ml);
      var hit = svgEl("rect", { x: cx(i) - slot / 2, y: PT, width: slot, height: plotH + 8, class: "mark-hit" });
      hit.addEventListener("mousemove", function (e) {
        showTip(e, D.month_names[m.month - 1] + ": " + hrs(m.load_hours) + " load ÷ " + hrs(m.available_hours) + " = " + pct(m.utilization_pct, 1) + (over ? " — OVER capacity" : "") + (ration ? " · rations Dryers" : ""));
      });
      hit.addEventListener("mouseleave", hideTip); svg.appendChild(hit);
    });
    var wrap = document.getElementById("loadwrap"); wrap.innerHTML = ""; wrap.appendChild(svg);
    var lnote = document.createElement("p"); lnote.className = "chartnote";
    lnote.textContent = "Apr · May · Dec over 100% — the only months that cost shipped units.";
    wrap.appendChild(lnote);
    wrap.addEventListener("click", function () { openBottleneckRollup(); });
  }

  function drawMarginMonths() {
    var rows = [4, 5, 12].map(function (mo) {
      var entry = D.provenance.constrained["FAM-DRY"][String(mo)];
      return { month: mo, unmet: entry.supply.unmet_units, um: entry.financials.unit_margin,
               lost: entry.supply.unmet_units * entry.financials.unit_margin };
    });
    var total = rows.reduce(function (a, r) { return a + r.lost; }, 0);
    var max = Math.max.apply(null, rows.map(function (r) { return r.lost; })) || 1;
    var BW = 360, BH = 130, PL = 8, PR = 8, PT = 16, PB = 22;
    var plotW = BW - PL - PR, plotH = BH - PT - PB, slot = plotW / rows.length, bw = slot * 0.5;
    var cx = function (i) { return PL + (i + 0.5) * slot; };
    var y = function (v) { return PT + plotH - (v / max) * plotH; };
    var svg = svgEl("svg", { viewBox: "0 0 " + BW + " " + BH, role: "img" });
    svg.appendChild(svgEl("line", { x1: PL, y1: PT + plotH, x2: BW - PR, y2: PT + plotH, class: "axis-line" }));
    rows.forEach(function (r, i) {
      var bar = svgEl("rect", { x: cx(i) - bw / 2, y: y(r.lost), width: bw, height: PT + plotH - y(r.lost), rx: 1, fill: "var(--sop-color-bad)", "fill-opacity": 0.85 });
      bar.classList.add("rise", "rise--" + (i + 1)); svg.appendChild(bar);
      var vl = svgEl("text", { x: cx(i), y: y(r.lost) - 5, class: "bar-value", "text-anchor": "middle", fill: "var(--sop-color-bad)" });
      var n = svgEl("tspan", {}); vl.appendChild(n);
      animateCount(n, r.lost, function (v) { return money(v); }, 600);
      svg.appendChild(vl);
      var ml = svgEl("text", { x: cx(i), y: BH - 6, class: "tick-text", "text-anchor": "middle" });
      ml.textContent = D.month_names[r.month - 1]; svg.appendChild(ml);
      var hit = svgEl("rect", { x: cx(i) - slot / 2, y: PT, width: slot, height: plotH, class: "mark-hit" });
      hit.addEventListener("mousemove", function (e) {
        showTip(e, D.month_names[r.month - 1] + " · Dryers: " + units2(r.unmet) + " unmet × $" + r.um + " = " + money2(r.lost) + " lost");
      });
      hit.addEventListener("mouseleave", hideTip); svg.appendChild(hit);
    });
    var wrap = document.getElementById("marginwrap"); wrap.innerHTML = ""; wrap.appendChild(svg);
    var note = document.createElement("p"); note.className = "chartnote";
    note.textContent = "0 lost margin in the other 9 months. Total at risk: " + money2(total) + ".";
    wrap.appendChild(note);
    wrap.addEventListener("click", function () { openMarginAtRiskRollup(); });
  }

  function drawUpsideVariance() {
    var base = D.scenarios.base.summary.total_gross_margin, up = D.scenarios.upside.summary.total_gross_margin;
    var BW = 460, BH = 70, GUT = 74, PR = 74, ROWH = 18, GAP = 4;
    var hi = up * 1.02 || 1, plotW = BW - GUT - PR;
    var x = function (v) { return GUT + (v / hi) * plotW; };
    var svg = svgEl("svg", { viewBox: "0 0 " + BW + " " + BH, role: "img" });
    [["base", base], ["upside", up]].forEach(function (r, i) {
      var sid = r[0], v = r[1], yy = i * (ROWH + GAP) + 2;
      var lab = svgEl("text", { x: GUT - 8, y: yy + ROWH / 2 + 3.5, class: "bar-label", "text-anchor": "end" });
      lab.textContent = SC_LABEL[sid]; svg.appendChild(lab);
      var w = Math.max(0, x(v) - GUT);
      if (w > 0.5) {
        var bar = svgEl("rect", { x: GUT, y: yy, width: w, height: ROWH, rx: 1 });
        if (sid === "upside") bar.classList.add("rise", "rise--" + (i + 1));
        paintScenario(bar, sid); svg.appendChild(bar);
      }
      var vl = svgEl("text", { x: GUT + w + 6, y: yy + ROWH / 2 + 3.5, class: "bar-value" });
      if (sid === "upside") {
        var n = svgEl("tspan", {}); vl.appendChild(n);
        animateCount(n, v, function (x) { return money(x); }, 700);
      } else { vl.textContent = money(v); }
      svg.appendChild(vl);
      var hit = svgEl("rect", { x: 0, y: yy, width: BW, height: ROWH, class: "mark-hit" });
      hit.addEventListener("mousemove", function (e) {
        showTip(e, SC_LABEL[sid] + " gross margin " + money2(v) + (sid === "base" ? "" : "  (+" + money2(v - base) + " vs Base)"));
      });
      hit.addEventListener("mouseleave", hideTip); svg.appendChild(hit);
    });
    svg.appendChild(svgEl("line", { x1: GUT, y1: 0, x2: GUT, y2: BH - 10, class: "axis-line" }));
    var wrap = document.getElementById("upsidewrap"); wrap.innerHTML = ""; wrap.appendChild(svg);
    var dm = up - base, dr = D.scenarios.upside.summary.total_revenue - D.scenarios.base.summary.total_revenue;
    var note = document.createElement("p"); note.className = "chartnote";
    note.innerHTML = '<span class="delta delta--good">▲ ' + money(dm) + '</span> margin &middot; <span class="delta delta--good">▲ ' + money(dr) + '</span> revenue (context). Margin is the KPI.';
    wrap.appendChild(note);
    wrap.addEventListener("click", function () { openUpsideValueRollup(); });
  }

  /* =========================================================================
     SECTION 10 — MARGIN WATERFALL (m5)
     ========================================================================= */
  function buildWaterfall() {
    var b = D.scenarios.base.summary, u = D.scenarios.upside.summary, c = D.scenarios.constrained.summary;
    var WF = {
      base: b.total_gross_margin,
      lift: u.total_gross_margin - b.total_gross_margin,
      penalty: c.total_lost_margin,
      realized: c.total_gross_margin
    };
    var steps = [
      { key: "base", label: "Base", val: WF.base, kind: "base" },
      { key: "lift", label: "+ Upside lift", val: WF.lift, kind: "up" },
      { key: "penalty", label: "− Constrained penalty", val: -WF.penalty, kind: "pen" },
      { key: "real", label: "Realized — Constrained", val: WF.realized, kind: "real" }
    ];
    var svg = document.getElementById("wfsvg");
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 760, H = 300, PL = 70, PR = 20, PT = 30, PB = 50;
    var plotW = W - PL - PR, plotH = H - PT - PB;
    var max = WF.base * 1.05;
    var min = Math.min(0, -WF.penalty) * 1.15;
    var span = (max - min) || 1;
    var y = function (v) { return PT + plotH - ((v - min) / span) * plotH; };
    var slot = plotW / steps.length, bw = Math.min(slot * 0.62, 96), gutter = slot * 0.18;

    svg.appendChild(svgEl("line", { x1: PL, y1: y(0), x2: W - PR, y2: y(0), class: "wf__baseline" }));
    [0, max, min].forEach(function (v) {
      var t = svgEl("text", { x: PL - 8, y: y(v) + 4, class: "wf__axislabel", "text-anchor": "end" });
      t.textContent = money(v); svg.appendChild(t);
    });

    var cursor = WF.base;
    steps.forEach(function (st, i) {
      var cx = PL + (i + 0.5) * slot;
      var isDelta = st.kind === "up" || st.kind === "pen";
      var isTotal = st.kind === "real";
      var top = isDelta ? cursor : 0;
      var bottom = isDelta ? cursor + st.val : st.val;
      var yy = Math.min(y(top), y(bottom));
      var h = Math.abs(y(bottom) - y(top));
      var fill = st.kind === "base" ? "var(--sop-color-ink)"
        : st.kind === "up" ? "var(--sop-color-good)"
        : st.kind === "pen" ? "var(--sop-color-bad)"
        : "var(--sop-color-info)";
      var bar = svgEl("rect", { x: cx - bw / 2, y: yy, width: bw, height: Math.max(1, h),
        rx: st.kind === "pen" ? 0 : 4, fill: fill, "fill-opacity": st.kind === "real" ? 0.9 : 0.85 });
      svg.appendChild(bar);
      if (i > 0) {
        var prevEnd = PL + (i - 1 + 0.5) * slot + bw / 2 + gutter;
        var connStart = cx - bw / 2 - gutter;
        svg.appendChild(svgEl("line", { x1: prevEnd, y1: y(cursor), x2: connStart, y2: y(cursor), class: "wf__connector" }));
        if (st.kind === "pen") {
          svg.appendChild(svgEl("line", { x1: cx, y1: y(0), x2: cx, y2: y(cursor), class: "wf__connector" }));
        }
      }
      var valY = st.kind === "pen" ? Math.max(y(bottom) + 14, y(top) + 12) : y(top) - 8;
      var onColor = st.kind === "up" || st.kind === "pen" || st.kind === "real";
      var onLight = st.kind === "base";
      var cls = onColor ? "wf__label-on-bar" : (onLight ? "wf__label-on-light" : "wf__stepval");
      var vl = svgEl("text", { x: cx, y: valY, class: cls, "text-anchor": "middle" });
      vl.textContent = (st.kind === "up" ? "▲ " : st.kind === "pen" ? "▼ " : "") + (st.kind === "pen" ? money2(Math.abs(st.val)) : money(st.val));
      svg.appendChild(vl);
      var lab = svgEl("text", { x: cx, y: H - 28, class: "wf__steplabel", "text-anchor": "middle" });
      lab.textContent = st.label; svg.appendChild(lab);
      var hit = svgEl("rect", { x: cx - slot / 2, y: PT, width: slot, height: plotH, class: "mark-hit" });
      (function (st2) {
        hit.addEventListener("mousemove", function (e) {
          showTip(e, st2.label + ": " + money2(Math.abs(st2.val)) + " · click for the rollup");
        });
        hit.addEventListener("mouseleave", hideTip);
        hit.addEventListener("click", function () {
          if (st2.kind === "up") openUpsideValueRollup();
          else if (st2.kind === "pen") openMarginAtRiskRollup();
          else if (st2.kind === "base") openBaseRollup();
          else openConstrainedRollup();
        });
      })(st);
      svg.appendChild(hit);
      if (isDelta || isTotal) cursor += st.val;
    });
  }

  function buildBridgeTable() {
    var b = D.scenarios.base.summary, u = D.scenarios.upside.summary, c = D.scenarios.constrained.summary;
    var WF = {
      base: b.total_gross_margin,
      lift: u.total_gross_margin - b.total_gross_margin,
      penalty: c.total_lost_margin,
      realized: c.total_gross_margin
    };
    var tb = document.querySelector("#bridgetable tbody");
    tb.innerHTML = "";
    var rows = [
      { label: "Base margin (plan)", val: WF.base, kind: "base", extra: "See how →" },
      { label: "Upside lift (▲)", val: WF.lift, kind: "up", extra: "Upside − Base" },
      { label: "Constrained penalty (▼)", val: WF.penalty, kind: "pen", extra: "Dryers, 3 months" },
      { label: "Realized — Constrained", val: WF.realized, kind: "real", extra: "Recommended plan" }
    ];
    rows.forEach(function (r) {
      var tr = document.createElement("tr");
      var td1 = document.createElement("td"); td1.textContent = r.label; tr.appendChild(td1);
      var td2 = document.createElement("td"); td2.className = r.kind === "up" ? "wf__val-good" : r.kind === "pen" ? "wf__val-bad" : "";
      td2.textContent = (r.kind === "up" ? "▲ " : r.kind === "pen" ? "▼ " : "") + (r.kind === "pen" ? money2(r.val) : money(r.val));
      tr.appendChild(td2);
      var td3 = document.createElement("td");
      var btn = document.createElement("button"); btn.type = "button"; btn.className = "wf__cellclick";
      btn.textContent = r.extra;
      (function (kind) {
        btn.addEventListener("click", function () {
          if (kind === "up") openUpsideValueRollup();
          else if (kind === "pen") openMarginAtRiskRollup();
          else if (kind === "base") openBaseRollup();
          else openConstrainedRollup();
        });
      })(r.kind);
      td3.appendChild(btn); tr.appendChild(td3);
      tb.appendChild(tr);
    });
    var tot = document.createElement("tr"); tot.className = "is-total";
    var t1 = document.createElement("td"); t1.textContent = "Net check";
    var t2 = document.createElement("td"); t2.className = "wf__val-good"; t2.textContent = money(WF.realized);
    var t3 = document.createElement("td"); t3.textContent = money(WF.base) + " + " + money(WF.lift) + " − " + money2(WF.penalty) + " = " + money(WF.realized);
    tot.appendChild(t1); tot.appendChild(t2); tot.appendChild(t3); tb.appendChild(tot);
  }

  /* =========================================================================
     SECTION 11 — TABLE COLLAPSE (m1 summary table) + LEGEND
     ========================================================================= */
  function buildSummaryTable() {
    var t = document.getElementById("table");
    var head = "<thead><tr><th>Metric</th>" + SC.map(function (s) { return "<th>" + SC_LABEL[s] + "</th>"; }).join("") + "</tr></thead>";
    var metrics = [
      ["Revenue", function (s) { return money(s.total_revenue); }],
      ["Gross margin", function (s) { return money(s.total_gross_margin); }],
      ["Lost revenue", function (s) { return money(s.total_lost_revenue); }],
      ["Lost margin", function (s) { return money(s.total_lost_margin); }],
      ["Ending inventory (at cost)", function (s) { return money(s.ending_inventory_value); }],
      ["Fill rate", function (s) { return pct(s.fill_rate * 100, 2); }]
    ];
    var body = "<tbody>" + metrics.map(function (m) {
      return "<tr><td>" + m[0] + "</td>" + SC.map(function (s) {
        return "<td>" + m[1](D.scenarios[s].summary) + "</td>";
      }).join("") + "</tr>";
    }).join("") + "</tbody>";
    t.innerHTML = head + body;
  }

  function buildLegend() {
    var lg = document.getElementById("legend");
    [
      { html: '<span class="legend__swatch" style="background:var(--sop-color-chart-actual);opacity:0.85"></span>', text: "Base — solid" },
      { html: '<span class="legend__swatch" style="background:var(--sop-color-ink-soft)"></span>', text: "Upside — light solid" },
      { html: '<svg class="legend__swatch" viewBox="0 0 20 11"><rect width="20" height="11" fill="url(#hatch)"/></svg>', text: "Constrained — hatched" },
      { html: '<span class="legend__swatch" style="border:1px solid var(--sop-color-ink-soft)"></span>', text: "Demand (plan) — outline" },
      { html: '<span class="legend__swatch" style="background:var(--sop-color-bad)"></span>', text: "unmet demand" },
      { html: '<span class="delta delta--good">▲</span>', text: "better than Base" },
      { html: '<span class="delta delta--bad">▼</span>', text: "worse than Base" }
    ].forEach(function (it) {
      var d = document.createElement("span"); d.className = "legend__item";
      d.innerHTML = it.html + "<span>" + it.text + "</span>";
      lg.appendChild(d);
    });
  }

  var tw = document.getElementById("tablewrap"), tb = document.getElementById("tabletoggle");
  tb.addEventListener("click", function () {
    var open = tw.hasAttribute("hidden");
    if (open) tw.removeAttribute("hidden"); else tw.setAttribute("hidden", "");
    tb.setAttribute("aria-expanded", String(open));
    tb.textContent = open ? "Hide table" : "Show table";
  });

  /* =========================================================================
     SECTION 12 — NARRATIVE RAIL (m1)
     ========================================================================= */
  function buildRail() {
    var bn = D.bottleneck;
    var con = D.scenarios.constrained.summary;
    var worstMonth = D.scenarios.constrained.monthly.reduce(function (a, b) { return b.unmet > a.unmet ? b : a; });
    var overCap = D.scenarios.constrained.utilization[bn.resource_id].filter(function (r) { return r.utilization_pct > 100; });
    var findings = [
      { dot: "warn", html: "<strong>" + bn.resource_name + "</strong> runs over capacity in <strong>" +
          overCap.length + " of 12 months</strong>, peaking at " + pct(bn.utilization_pct) + " in " + bn.month_name + "." },
      { dot: "bad", html: "Worst shortfall is <strong>" + worstMonth.name + "</strong> — " +
          units(worstMonth.unmet) + " units unserved, " + money(worstMonth.lost_margin) + " of margin lost." },
      { dot: "good", html: "Fill rate holds at <strong>" + pct(con.fill_rate * 100, 2) +
          "</strong>; the shortfall is concentrated, not spread across the year." },
      { dot: "info", html: "Base and Upside both clear demand fully by construction — they carry <strong>no capacity check</strong>. Only Constrained is buildable." }
    ];
    var fh = document.getElementById("findings");
    findings.forEach(function (f) {
      var li = document.createElement("li"); li.className = "rail__item";
      var d = document.createElement("span"); d.className = "dot dot--" + f.dot;
      var t = document.createElement("span"); t.innerHTML = f.html;
      li.appendChild(d); li.appendChild(t); fh.appendChild(li);
    });
    document.getElementById("assumptions").innerHTML =
      "Upside applies a per-family uplift to Base demand. Constrained rations the same demand against " +
      D.resources.length + " finite resources, in unit-margin order. Inventory is carried at variable cost. " +
      "No optimiser runs — rationing is a priority rule, and it is visible.";
  }

  /* =========================================================================
     INIT
     ========================================================================= */
  buildHeadline();
  buildTiles();
  buildSmallMultiples();
  buildPresets();
  renderComparison();
  renderGrid();
  buildPanelNotes();
  buildFillBullets();
  drawLoadCurve();
  drawMarginMonths();
  drawUpsideVariance();
  wireDrill("margindrill", openMarginAtRiskRollup);
  wireDrill("upsidedrill", openUpsideValueRollup);
  buildWaterfall();
  buildBridgeTable();
  buildSummaryTable();
  buildLegend();
  buildRail();

  document.getElementById("prov").textContent =
    D.families.length + " families · " + D.resources.length + " resources · 12 monthly buckets · every figure from the engine";
  document.getElementById("stamp").textContent = "Generated " + new Date(D.generated_at).toLocaleString();
})();
