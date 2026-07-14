"""
dashboard.py — the self-contained HTML decision cockpit.

`build_context(...)` assembles the exact JSON-serializable dict the
dashboard's `<script>const DATA = {...}</script>` blob embeds: the KPI
comparison tiles, per-resource capacity utilization (with the 100% RCCP
line) for all three scenarios, the monthly demand-vs-shipped gap per
scenario, the family-level financial reconciliation table, and a
computed exec-takeaway callout built from the actual numbers.

`render_dashboard(context, out_path)` renders a single, zero-CDN
`output/dashboard.html` — inline CSS (dual theme), vanilla JS, inline
SVG — following DESIGN.md exactly. The context JSON is embedded once as
`const DATA = {...}` and every section is drawn client-side by a small
pure JS function, so the renderer never recomputes anything.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import capacity as capacity_mod
from . import finance as finance_mod
from .models import (
    Family,
    FinanceLine,
    FinanceSummary,
    Kpi,
    Resource,
    ResourceLoad,
    ScenarioId,
    SupplyLine,
    jsonable,
)

_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

_SCENARIOS_IN_ORDER = [ScenarioId.BASE, ScenarioId.UPSIDE, ScenarioId.CONSTRAINED]


def _capacity_series(loads: list[ResourceLoad], resources: list[Resource]) -> dict:
    by_resource: dict[str, list[dict]] = {r.id: [] for r in resources}
    for ld in sorted(loads, key=lambda x: (x.resource_id, x.month)):
        by_resource[ld.resource_id].append(
            {
                "month": ld.month,
                "load_hours": ld.load_hours,
                "available_hours": ld.available_hours,
                "utilization_pct": ld.utilization_pct,
            }
        )
    peaks = capacity_mod.peak_utilization_by_resource(loads)
    return {
        "by_resource": by_resource,
        "peak_utilization_pct": {rid: round(v, 2) for rid, v in peaks.items()},
    }


def _scenario_monthly_totals(supply_lines: list[SupplyLine]) -> list[dict]:
    """Total demand/produced/shipped/unmet across all families, per month."""
    totals: dict[int, dict[str, float]] = {
        m: {"demand": 0.0, "produced": 0.0, "shipped": 0.0, "unmet": 0.0} for m in range(1, 13)
    }
    for sl in supply_lines:
        t = totals[sl.month]
        t["demand"] += sl.demand_units
        t["produced"] += sl.produced_units
        t["shipped"] += sl.shipped_units
        t["unmet"] += sl.unmet_units
    return [
        {
            "month": m,
            "month_name": _MONTH_NAMES[m - 1],
            "demand": round(totals[m]["demand"], 1),
            "produced": round(totals[m]["produced"], 1),
            "shipped": round(totals[m]["shipped"], 1),
            "unmet": round(totals[m]["unmet"], 1),
        }
        for m in range(1, 13)
    ]


def _family_reconciliation_rows(
    families: list[Family],
    supply_lines: list[SupplyLine],
    finance_lines: list[FinanceLine],
) -> list[dict]:
    gm_by_family = finance_mod.gross_margin_by_family(finance_lines)
    lm_by_family = finance_mod.lost_margin_by_family(finance_lines)
    rows = []
    for family in families:
        fam_supply = [s for s in supply_lines if s.family_id == family.id]
        fam_finance = [f for f in finance_lines if f.family_id == family.id]
        total_demand = sum(s.demand_units for s in fam_supply)
        total_shipped = sum(s.shipped_units for s in fam_supply)
        total_unmet = sum(s.unmet_units for s in fam_supply)
        december = next((f for f in fam_finance if f.month == 12), None)
        rows.append(
            {
                "family_id": family.id,
                "family_name": family.name,
                "unit_margin": family.unit_margin,
                "demand_units": round(total_demand, 1),
                "shipped_units": round(total_shipped, 1),
                "unmet_units": round(total_unmet, 1),
                "fill_rate_pct": round((total_shipped / total_demand * 100.0) if total_demand > 0 else 100.0, 1),
                "revenue": round(sum(f.revenue for f in fam_finance), 2),
                "gross_margin": gm_by_family.get(family.id, 0.0),
                "lost_margin": lm_by_family.get(family.id, 0.0),
                "ending_inventory_value": december.inventory_value if december else 0.0,
            }
        )
    return rows


def build_context(
    families: list[Family],
    resources: list[Resource],
    loads_by_scenario: dict[ScenarioId, list[ResourceLoad]],
    supply_by_scenario: dict[ScenarioId, list[SupplyLine]],
    finance_lines_by_scenario: dict[ScenarioId, list[FinanceLine]],
    summary_by_scenario: dict[ScenarioId, FinanceSummary],
    kpis: dict[str, Kpi],
    generated_at: str,
) -> dict:
    """
    Assemble everything the dashboard needs into one JSON-serializable
    dict. This is the contract between the engine and the renderer —
    designed so the renderer never recomputes anything, only formats
    what's here.
    """
    scenarios_ctx: dict[str, dict] = {}
    for scenario in _SCENARIOS_IN_ORDER:
        summary = summary_by_scenario[scenario]
        supply_lines = supply_by_scenario[scenario]
        finance_lines = finance_lines_by_scenario[scenario]
        scenarios_ctx[scenario.value] = {
            "id": scenario.value,
            "summary": jsonable(summary),
            "capacity": _capacity_series(loads_by_scenario[scenario], resources),
            "monthly_totals": _scenario_monthly_totals(supply_lines),
            "reconciliation": _family_reconciliation_rows(families, supply_lines, finance_lines),
        }

    bottleneck_resource_id = capacity_mod.binding_resource(loads_by_scenario[ScenarioId.UPSIDE])
    resources_by_id = {r.id: r for r in resources}
    bottleneck_ctx = None
    if bottleneck_resource_id is not None:
        peak_load = max(
            (ld for ld in loads_by_scenario[ScenarioId.UPSIDE] if ld.resource_id == bottleneck_resource_id),
            key=lambda ld: ld.utilization_pct,
        )
        bottleneck_ctx = {
            "resource_id": bottleneck_resource_id,
            "resource_name": resources_by_id[bottleneck_resource_id].name,
            "month": peak_load.month,
            "month_name": _MONTH_NAMES[peak_load.month - 1],
            "utilization_pct": peak_load.utilization_pct,
        }

    return {
        "generated_at": generated_at,
        "company": "Cascade Appliances",
        "kpis": {key: jsonable(k) for key, k in kpis.items()},
        "resources": [jsonable(r) for r in resources],
        "families": [jsonable(f) for f in families],
        "scenarios": scenarios_ctx,
        "bottleneck": bottleneck_ctx,
    }


# --------------------------------------------------------------------------
# The dashboard template. Built with a __DATA_JSON__ sentinel (not str.format)
# so every literal { } in the CSS/JS stays literal. The context JSON is
# embedded once; </ is escaped to <\/ so an embedded string can never close
# the <script> element early.
# --------------------------------------------------------------------------

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>S&amp;OP Integrated Planning — Cascade Appliances</title>
<style>
  :root, :root[data-theme="dark"] {
    --page:#0d0d0d; --surface:#1a1a19; --surface-2:#222220;
    --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
    --s1:#3987e5; --s2:#199e70; --s3:#c98500; --s4:#008300;
    --s5:#9085e9; --s6:#e66767; --s7:#d55181; --s8:#d95926;
    --good:#0ca30c; --warn:#fab219; --serious:#ec835a; --critical:#d03b3b;
  }
  :root[data-theme="light"] {
    --page:#f9f9f7; --surface:#fcfcfb; --surface-2:#f0efec;
    --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
    --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10);
    --s1:#2a78d6; --s2:#1baf7a; --s3:#eda100; --s4:#008300;
    --s5:#4a3aa7; --s6:#e34948; --s7:#e87ba4; --s8:#eb6834;
    --good:#0ca30c; --warn:#fab219; --serious:#ec835a; --critical:#d03b3b;
  }
  @media (prefers-color-scheme: light) {
    :root:not([data-theme]) {
      --page:#f9f9f7; --surface:#fcfcfb; --surface-2:#f0efec;
      --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
      --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10);
      --s1:#2a78d6; --s2:#1baf7a; --s3:#eda100; --s4:#008300;
      --s5:#4a3aa7; --s6:#e34948; --s7:#e87ba4; --s8:#eb6834;
    }
  }

  * { box-sizing:border-box; }
  html, body { margin:0; padding:0; }
  body {
    background:var(--page); color:var(--ink-2);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    font-size:14px; line-height:1.45;
    -webkit-font-smoothing:antialiased;
  }
  .wrap { max-width:1280px; margin:0 auto; padding:24px; }
  .num { font-variant-numeric: tabular-nums; }

  header.top {
    display:flex; align-items:center; gap:16px;
    padding-bottom:20px; margin-bottom:24px;
    border-bottom:1px solid var(--ring);
  }
  .brand { display:flex; align-items:center; gap:12px; }
  .brand svg { display:block; }
  .brand h1 { margin:0; font-size:19px; font-weight:700; color:var(--ink); letter-spacing:-.01em; display:flex; align-items:center; gap:8px; }
  .brand .sub { margin:2px 0 0; font-size:12px; color:var(--muted); }
  .brand .demo { font-size:9px; font-weight:700; letter-spacing:.1em; color:var(--muted); border:1px solid var(--ring); border-radius:20px; padding:2px 8px; position:relative; top:-1px; }
  .top .spacer { flex:1; }
  .stamp { font-size:12px; color:var(--muted); text-align:right; }
  .stamp b { color:var(--ink-2); font-weight:600; }
  .themebtn {
    display:flex; align-items:center; justify-content:center;
    width:38px; height:38px; border-radius:9px;
    background:var(--surface); border:1px solid var(--ring);
    color:var(--ink-2); cursor:pointer; padding:0;
  }
  .themebtn:hover { background:var(--surface-2); color:var(--ink); }
  .themebtn .moon { display:none; }
  :root[data-theme="dark"] .themebtn .sun { display:none; }
  :root[data-theme="dark"] .themebtn .moon { display:block; }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme]) .themebtn .sun { display:none; }
    :root:not([data-theme]) .themebtn .moon { display:block; }
  }

  .kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px,1fr)); gap:16px; margin-bottom:24px; }
  .tile { background:var(--surface); border:1px solid var(--ring); border-radius:10px; padding:16px; transition:border-color .15s; }
  .tile:hover { border-color:color-mix(in srgb, var(--s1) 35%, var(--ring)); }
  .tile .label { font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }
  .tile .value { font-size:28px; font-weight:700; color:var(--ink); margin:8px 0 4px; line-height:1.05; }
  .tile .value .unit { font-size:14px; font-weight:600; color:var(--ink-2); margin-left:2px; }
  .tile .ctx { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--muted); }
  .tile .ctx .dot { width:8px; height:8px; border-radius:50%; flex:none; }

  .card { background:var(--surface); border:1px solid var(--ring); border-radius:12px; padding:20px; margin-bottom:24px; }
  .kicker { font-size:12px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }
  .card h2 { margin:4px 0 0; font-size:16px; font-weight:600; color:var(--ink); }
  .card .head { display:flex; align-items:flex-end; gap:16px; margin-bottom:16px; flex-wrap:wrap; }
  .card .head .note { font-size:12px; color:var(--muted); margin-left:auto; }

  .tabs { display:flex; gap:4px; border-bottom:1px solid var(--ring); margin-bottom:18px; flex-wrap:wrap; }
  .tab { font-family:inherit; font-size:13px; color:var(--ink-2); background:none; border:none; padding:9px 14px; cursor:pointer; border-bottom:2px solid transparent; margin-bottom:-1px; }
  .tab:hover { color:var(--ink); }
  .tab.active { color:var(--ink); font-weight:600; border-bottom-color:var(--s1); }

  .legendrow { display:flex; flex-wrap:wrap; gap:14px; margin-bottom:12px; }
  .legendrow .item { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--ink-2); }
  .sw { display:inline-block; width:10px; height:10px; border-radius:2px; }

  .chartwrap { position:relative; }
  .chartwrap svg { display:block; width:100%; height:auto; }

  table { width:100%; border-collapse:collapse; font-size:13px; }
  thead th { text-align:left; font-size:11px; font-weight:600; letter-spacing:.04em; text-transform:uppercase; color:var(--muted); padding:0 10px 10px; border-bottom:1px solid var(--ring); white-space:nowrap; }
  thead th.n, tbody td.n { text-align:right; }
  tbody td { padding:9px 10px; border-bottom:1px solid var(--grid); color:var(--ink-2); vertical-align:top; }
  tbody tr:hover td { background:var(--surface-2); }
  tbody td.n { font-variant-numeric:tabular-nums; }
  tbody td.fam { color:var(--ink); font-weight:600; }
  tbody tr.total td { border-top:1px solid var(--ring); border-bottom:none; font-weight:700; color:var(--ink); }

  .callout { display:flex; gap:14px; align-items:flex-start; }
  .callout .icon { flex:none; width:34px; height:34px; border-radius:9px; display:flex; align-items:center; justify-content:center; background:color-mix(in srgb, var(--warn) 16%, var(--surface)); color:var(--warn); font-weight:700; }
  .callout p { margin:0 0 8px; color:var(--ink-2); }
  .callout p:last-child { margin-bottom:0; }
  .callout b { color:var(--ink); }

  footer.foot { border-top:1px solid var(--ring); padding-top:16px; margin-top:8px; font-size:12px; color:var(--muted); }
  footer.foot b { color:var(--ink-2); font-weight:600; }

  #tip { position:fixed; z-index:50; pointer-events:none; background:var(--surface); border:1px solid var(--ring); border-radius:9px; padding:9px 11px; font-size:12px; color:var(--ink-2); box-shadow:0 6px 24px rgba(0,0,0,.28); max-width:260px; opacity:0; transition:opacity .08s; }
  #tip .tt { color:var(--ink); font-weight:600; margin-bottom:3px; }
  #tip .kv { display:flex; justify-content:space-between; gap:14px; }
  #tip .kv b { color:var(--ink); font-weight:600; font-variant-numeric:tabular-nums; }
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="brand">
      <svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-hidden="true">
        <rect x="4" y="18" width="6" height="12" rx="1.5" style="fill:var(--s1)"/>
        <rect x="14" y="10" width="6" height="20" rx="1.5" style="fill:var(--s5)"/>
        <rect x="24" y="4" width="6" height="26" rx="1.5" style="fill:var(--s8)"/>
      </svg>
      <div>
        <h1>S&amp;OP Integrated Planning <span class="demo">DEMO DATA</span></h1>
        <p class="sub" id="subtitle"></p>
      </div>
    </div>
    <div class="spacer"></div>
    <div class="stamp">Generated<br><b id="genstamp"></b></div>
    <button class="themebtn" id="themebtn" title="Toggle theme" aria-label="Toggle light/dark theme">
      <svg class="sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/></svg>
      <svg class="moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
    </button>
  </header>

  <section class="kpis" id="kpis"></section>

  <section class="card">
    <div class="head">
      <div><div class="kicker">Rough-Cut Capacity Planning</div><h2>Capacity Utilization by Resource</h2></div>
      <div class="note" id="capnote"></div>
    </div>
    <div class="tabs" id="captabs"></div>
    <div class="legendrow" id="caplegend"></div>
    <div class="chartwrap"><svg id="capchart" viewBox="0 0 900 260"></svg></div>
  </section>

  <section class="card">
    <div class="head">
      <div><div class="kicker">Demand vs. Supply</div><h2>Monthly Demand vs. Shipped Units</h2></div>
      <div class="note" id="gapnote"></div>
    </div>
    <div class="tabs" id="gaptabs"></div>
    <div class="legendrow" id="gaplegend"></div>
    <div class="chartwrap"><svg id="gapchart" viewBox="0 0 900 260"></svg></div>
  </section>

  <section class="card">
    <div class="head"><div><div class="kicker">Reconciliation</div><h2>Financial Reconciliation by Family</h2></div></div>
    <div class="tabs" id="rectabs"></div>
    <table id="rectable"><thead></thead><tbody></tbody></table>
  </section>

  <section class="card">
    <div class="head"><div><div class="kicker">Recommendation</div><h2>Exec Takeaway</h2></div></div>
    <div class="callout"><div class="icon">!</div><div id="calloutbody"></div></div>
  </section>

  <footer class="foot">
    <span>Monthly S&amp;OP reconciliation (Wallace &amp; Stahl) extended to Integrated Business Planning (Oliver Wight, Palmatier &amp; Crum); RCCP per standard MRP-II/APICS practice.</span><br>
    <b>Built with S&amp;OP Integrated Planning</b> · see <b>docs/</b> for methodology.
  </footer>
</div>

<div id="tip"></div>

<script>
const DATA = __DATA_JSON__;

const $ = (s, r) => (r||document).querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const SCEN_LABEL = { base:'Base', upside:'Upside', constrained:'Constrained' };
const SCEN_COLOR = { base:'var(--s1)', upside:'var(--s2)', constrained:'var(--s8)' };

function fmtMoney(v){
  const a = Math.abs(v);
  const sign = v < 0 ? '-' : '';
  if (a >= 1e9) return sign + '$' + (a/1e9).toFixed(2) + 'B';
  if (a >= 1e6) return sign + '$' + (a/1e6).toFixed(2) + 'M';
  if (a >= 1e3) return sign + '$' + Math.round(a/1e3) + 'K';
  return sign + '$' + Math.round(a);
}
function fmtInt(v){ return Math.round(v).toLocaleString(); }

const tip = $('#tip');
function showTip(html, x, y){
  tip.innerHTML = html;
  tip.style.opacity = '1';
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let lx = x + pad, ly = y + pad;
  if (lx + w > window.innerWidth - 8) lx = x - w - pad;
  if (ly + h > window.innerHeight - 8) ly = y - h - pad;
  tip.style.left = Math.max(8, lx) + 'px';
  tip.style.top  = Math.max(8, ly) + 'px';
}
function hideTip(){ tip.style.opacity = '0'; }

function renderHeader(){
  $('#subtitle').textContent = 'Base vs Upside vs Constrained · ' + DATA.company + ' (demo network)';
  let stamp = DATA.generated_at;
  try {
    const d = new Date(DATA.generated_at);
    if (!isNaN(d)) stamp = d.toLocaleString(undefined, {year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) + ' UTC';
  } catch(e){}
  $('#genstamp').textContent = stamp;
}

function kpiVal(k){
  const u = k.unit;
  if (u === '$') return fmtMoney(k.value);
  if (u === '%') return k.value.toFixed(1) + '<span class="unit">%</span>';
  return (Math.round(k.value*100)/100).toLocaleString();
}
function renderKpis(){
  const K = DATA.kpis;
  const order = ['fill_rate_base','fill_rate_upside','fill_rate_constrained','bottleneck','upside_value_unlocked','lost_margin_constrained'];
  const accent = {
    fill_rate_base: ['var(--good)','●'],
    fill_rate_upside: ['var(--good)','●'],
    fill_rate_constrained: ['var(--serious)','▲'],
    bottleneck: ['var(--critical)','▲'],
    upside_value_unlocked: ['var(--good)','●'],
    lost_margin_constrained: ['var(--critical)','▲'],
  };
  const host = $('#kpis'); host.innerHTML = '';
  order.forEach(key => {
    const k = K[key]; if (!k) return;
    const [col, ico] = accent[key] || ['var(--muted)','●'];
    const tile = document.createElement('div');
    tile.className = 'tile';
    tile.innerHTML = '<div class="label">'+esc(k.label)+'</div><div class="value num">'+kpiVal(k)+'</div>' +
      '<div class="ctx"><span style="color:'+col+';font-size:10px">'+ico+'</span> '+esc(k.context||'—')+'</div>';
    host.appendChild(tile);
  });
}

// ============================================================ CAPACITY
let capScenario = 'upside';
function renderCapTabs(){
  const host = $('#captabs'); host.innerHTML = '';
  ['base','upside','constrained'].forEach(id => {
    const b = document.createElement('button');
    b.className = 'tab' + (id === capScenario ? ' active' : '');
    b.textContent = SCEN_LABEL[id];
    b.onclick = () => { capScenario = id; renderCapTabs(); renderCapChart(); };
    host.appendChild(b);
  });
}
function renderCapLegend(){
  const host = $('#caplegend'); host.innerHTML =
    '<span class="item"><span class="sw" style="background:var(--s1)"></span>Utilization</span>' +
    '<span class="item"><span class="sw" style="background:var(--critical);width:14px;height:3px;border-radius:2px"></span>100% installed capacity</span>';
}
function renderCapChart(){
  renderCapLegend();
  const s = DATA.scenarios[capScenario];
  const resources = DATA.resources;
  const svg = $('#capchart');
  const W = 900, H = 260, mL = 50, mR = 20, mT = 16, mB = 46;
  const pw = W - mL - mR, ph = H - mT - mB;
  const n = resources.length;
  const bw = pw / n * 0.5;
  const maxU = Math.max(120, ...resources.map(r => s.capacity.peak_utilization_pct[r.id] || 0));
  const yOf = v => mT + ph - (v/maxU)*ph;
  const xOf = i => mL + (i + 0.5) * (pw/n);

  let g = '';
  const ticks = [0,25,50,75,100];
  if (maxU > 100) ticks.push(Math.ceil(maxU/25)*25);
  Array.from(new Set(ticks)).forEach(v => {
    const y = yOf(v);
    g += '<line x1="'+mL+'" y1="'+y+'" x2="'+(mL+pw)+'" y2="'+y+'" style="stroke:var(--grid)" stroke-width="1"/>';
    g += '<text x="'+(mL-8)+'" y="'+(y+3.5)+'" text-anchor="end" class="num" style="fill:var(--muted)" font-size="10">'+v+'%</text>';
  });
  const y100 = yOf(100);
  g += '<line x1="'+mL+'" y1="'+y100+'" x2="'+(mL+pw)+'" y2="'+y100+'" style="stroke:var(--critical)" stroke-width="1.6" stroke-dasharray="5 4"/>';

  resources.forEach((r, i) => {
    const pct = s.capacity.peak_utilization_pct[r.id] || 0;
    const x = xOf(i) - bw/2;
    const y = yOf(pct);
    const h = mT + ph - y;
    const over = pct > 100;
    const fill = over ? 'var(--critical)' : 'var(--s1)';
    g += '<rect class="bar" data-r="'+r.id+'" x="'+x+'" y="'+y+'" width="'+bw+'" height="'+Math.max(0,h)+'" rx="4" style="fill:'+fill+';cursor:pointer"/>';
    g += '<text x="'+xOf(i)+'" y="'+(y-8)+'" text-anchor="middle" class="num" style="fill:var(--ink)" font-size="12" font-weight="700">'+pct.toFixed(1)+'%</text>';
    g += '<text x="'+xOf(i)+'" y="'+(mT+ph+18)+'" text-anchor="middle" style="fill:var(--ink-2)" font-size="11">'+esc(r.name)+'</text>';
  });

  svg.innerHTML = g;
  svg.querySelectorAll('.bar').forEach(bar => {
    const r = resources.find(x => x.id === bar.dataset.r);
    const pct = s.capacity.peak_utilization_pct[r.id] || 0;
    bar.addEventListener('mousemove', e => {
      const html = '<div class="tt">'+esc(r.name)+'</div>' +
        '<div class="kv"><span>Peak utilization</span><b>'+pct.toFixed(1)+'%</b></div>' +
        '<div class="kv"><span>Installed capacity</span><b>'+fmtInt(r.monthly_available_hours)+' hrs/mo</b></div>' +
        (pct > 100 ? '<div class="kv" style="color:var(--critical)"><span>⚠ over installed capacity</span><b></b></div>' : '');
      showTip(html, e.clientX, e.clientY);
    });
    bar.addEventListener('mouseleave', hideTip);
  });
  $('#capnote').textContent = SCEN_LABEL[capScenario] + ' scenario · peak monthly utilization vs installed capacity';
}

// ============================================================ DEMAND VS SUPPLY
let gapScenario = 'constrained';
function renderGapTabs(){
  const host = $('#gaptabs'); host.innerHTML = '';
  ['base','upside','constrained'].forEach(id => {
    const b = document.createElement('button');
    b.className = 'tab' + (id === gapScenario ? ' active' : '');
    b.textContent = SCEN_LABEL[id];
    b.onclick = () => { gapScenario = id; renderGapTabs(); renderGapChart(); };
    host.appendChild(b);
  });
}
function renderGapLegend(){
  $('#gaplegend').innerHTML =
    '<span class="item"><span class="sw" style="background:var(--s1);width:14px;height:3px;border-radius:2px"></span>Demand</span>' +
    '<span class="item"><span class="sw" style="background:var(--s8);width:14px;height:3px;border-radius:2px"></span>Shipped</span>';
}
function renderGapChart(){
  renderGapLegend();
  const s = DATA.scenarios[gapScenario];
  const rows = s.monthly_totals;
  const svg = $('#gapchart');
  const W = 900, H = 260, mL = 60, mR = 20, mT = 16, mB = 34;
  const pw = W - mL - mR, ph = H - mT - mB;
  const n = rows.length;
  const maxV = Math.max(...rows.map(r => r.demand)) * 1.1;
  const xOf = i => mL + (n === 1 ? pw/2 : i/(n-1)*pw);
  const yOf = v => mT + ph - (v/maxV)*ph;

  let g = '';
  for (let k = 0; k <= 4; k++){
    const v = maxV * k / 4;
    const y = yOf(v);
    g += '<line x1="'+mL+'" y1="'+y+'" x2="'+(mL+pw)+'" y2="'+y+'" style="stroke:var(--grid)" stroke-width="1"/>';
    g += '<text x="'+(mL-8)+'" y="'+(y+3.5)+'" text-anchor="end" class="num" style="fill:var(--muted)" font-size="10">'+fmtInt(v)+'</text>';
  }
  rows.forEach((r, i) => {
    g += '<text x="'+xOf(i)+'" y="'+(mT+ph+16)+'" text-anchor="middle" class="num" style="fill:var(--muted)" font-size="10">'+r.month_name+'</text>';
  });

  const path = key => rows.map((r, i) => (i?'L':'M')+xOf(i).toFixed(1)+','+yOf(r[key]).toFixed(1)).join(' ');
  const backShip = rows.map((r,i) => 'L'+xOf(n-1-i).toFixed(1)+','+yOf(rows[n-1-i].shipped).toFixed(1)).join(' ');
  g += '<path d="'+path('demand')+' '+backShip+' Z" style="fill:var(--s8);opacity:.12"/>';
  g += '<path d="'+path('demand')+'" fill="none" style="stroke:var(--s1)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';
  g += '<path d="'+path('shipped')+'" fill="none" style="stroke:var(--s8)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';

  g += '<rect id="gaphit" x="'+mL+'" y="'+mT+'" width="'+pw+'" height="'+ph+'" fill="transparent"/>';
  svg.innerHTML = g;

  const hit = $('#gaphit', svg);
  const pt = svg.createSVGPoint();
  hit.addEventListener('mousemove', e => {
    pt.x = e.clientX; pt.y = e.clientY;
    const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
    let i = Math.round((loc.x - mL) / (pw/(n-1)));
    i = Math.max(0, Math.min(n-1, i));
    const r = rows[i];
    const gap = r.demand - r.shipped;
    const html = '<div class="tt">'+r.month_name+'</div>' +
      '<div class="kv"><span><span class="sw" style="background:var(--s1)"></span>Demand</span><b>'+fmtInt(r.demand)+'</b></div>' +
      '<div class="kv"><span><span class="sw" style="background:var(--s8)"></span>Shipped</span><b>'+fmtInt(r.shipped)+'</b></div>' +
      (gap > 0.5 ? '<div class="kv" style="color:var(--critical)"><span>Unmet</span><b>'+fmtInt(gap)+'</b></div>' : '');
    showTip(html, e.clientX, e.clientY);
  });
  hit.addEventListener('mouseleave', hideTip);
  $('#gapnote').textContent = SCEN_LABEL[gapScenario] + ' scenario · monthly totals across all families';
}

// ============================================================ RECONCILIATION
let recScenario = 'constrained';
function renderRecTabs(){
  const host = $('#rectabs'); host.innerHTML = '';
  ['base','upside','constrained'].forEach(id => {
    const b = document.createElement('button');
    b.className = 'tab' + (id === recScenario ? ' active' : '');
    b.textContent = SCEN_LABEL[id];
    b.onclick = () => { recScenario = id; renderRecTabs(); renderRecTable(); };
    host.appendChild(b);
  });
}
function renderRecTable(){
  const s = DATA.scenarios[recScenario];
  const thead = $('#rectable thead'), tbody = $('#rectable tbody');
  thead.innerHTML = '<tr><th>Family</th><th class="n">Demand</th><th class="n">Shipped</th>' +
    '<th class="n">Fill %</th><th class="n">Revenue</th><th class="n">Gross Margin</th>' +
    '<th class="n">Lost Margin</th><th class="n">End. Inventory ($)</th></tr>';
  const rows = s.reconciliation;
  tbody.innerHTML = rows.map(r =>
    '<tr>' +
    '<td class="fam">'+esc(r.family_name)+'</td>' +
    '<td class="n">'+fmtInt(r.demand_units)+'</td>' +
    '<td class="n">'+fmtInt(r.shipped_units)+'</td>' +
    '<td class="n">'+r.fill_rate_pct.toFixed(1)+'</td>' +
    '<td class="n">'+fmtMoney(r.revenue)+'</td>' +
    '<td class="n">'+fmtMoney(r.gross_margin)+'</td>' +
    '<td class="n" style="color:'+(r.lost_margin>0?'var(--critical)':'var(--ink-2)')+'">'+(r.lost_margin>0?fmtMoney(r.lost_margin):'—')+'</td>' +
    '<td class="n">'+fmtMoney(r.ending_inventory_value)+'</td>' +
    '</tr>').join('') +
    '<tr class="total"><td>Total</td>' +
    '<td class="n">'+fmtInt(rows.reduce((a,r)=>a+r.demand_units,0))+'</td>' +
    '<td class="n">'+fmtInt(rows.reduce((a,r)=>a+r.shipped_units,0))+'</td>' +
    '<td class="n">'+s.summary.fill_rate.toFixed ? (s.summary.fill_rate*100).toFixed(1) : ''+'</td>' +
    '<td class="n">'+fmtMoney(s.summary.total_revenue)+'</td>' +
    '<td class="n">'+fmtMoney(s.summary.total_gross_margin)+'</td>' +
    '<td class="n" style="color:'+(s.summary.total_lost_margin>0?'var(--critical)':'var(--ink-2)')+'">'+(s.summary.total_lost_margin>0?fmtMoney(s.summary.total_lost_margin):'—')+'</td>' +
    '<td class="n">'+fmtMoney(s.summary.ending_inventory_value)+'</td></tr>';
}

// ============================================================ CALLOUT
function renderCallout(){
  const K = DATA.kpis;
  const bn = DATA.bottleneck;
  const host = $('#calloutbody');
  if (!bn){ host.innerHTML = '<p>No resource exceeds installed capacity under the upside demand plan this year.</p>'; return; }
  const gapHours = null;
  const worstFamily = (K.lost_margin_constrained && K.lost_margin_constrained.context) ? K.lost_margin_constrained.context.replace('concentrated in ', '') : 'the lowest-margin family on that resource';
  host.innerHTML =
    '<p>Upside demand is worth <b>'+fmtMoney(K.upside_value_unlocked.value)+'</b> in incremental gross margin, but ' +
    '<b>'+esc(bn.resource_name)+'</b> is the binding constraint at <b>'+bn.utilization_pct.toFixed(1)+'%</b> utilization in ' +
    '<b>'+bn.month_name+'</b>.</p>' +
    '<p>Without added capacity we fill only <b>'+K.fill_rate_constrained.value.toFixed(1)+'%</b> of upside demand — leaving ' +
    '<b>'+fmtMoney(K.lost_margin_constrained.value)+'</b> of margin on the table, concentrated in <b>'+esc(worstFamily)+'</b>.</p>' +
    '<p><b>Recommendation:</b> add capacity at '+esc(bn.resource_name)+' (or pre-build inventory ahead of '+bn.month_name+') to capture the upside; ' +
    'if not, allocate remaining hours to the highest-margin families and communicate the fill shortfall to sales now, not at month-end.</p>';
}

// ============================================================ THEME
function applyStoredTheme(){
  const t = localStorage.getItem('sip-theme');
  if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
}
function toggleTheme(){
  const cur = document.documentElement.getAttribute('data-theme');
  let next;
  if (cur) next = cur === 'dark' ? 'light' : 'dark';
  else next = matchMedia('(prefers-color-scheme: dark)').matches ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('sip-theme', next);
}

// ============================================================ BOOT
applyStoredTheme();
$('#themebtn').addEventListener('click', toggleTheme);
renderHeader();
renderKpis();
renderCapTabs();
renderCapChart();
renderGapTabs();
renderGapChart();
renderRecTabs();
renderRecTable();
renderCallout();
</script>
</body>
</html>
"""


def render_dashboard(context: dict, out_path: Path | str) -> None:
    """Render the self-contained cockpit HTML, embedding `context` once."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data_json = json.dumps(context, ensure_ascii=False).replace("</", "<\\/")
    html_doc = _TEMPLATE.replace("__DATA_JSON__", data_json)
    out_path.write_text(html_doc, encoding="utf-8")
