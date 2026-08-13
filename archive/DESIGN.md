# S&OP Integrated Planning — Dashboard Design Spec (frozen)

One self-contained `output/dashboard.html` (inline CSS + vanilla JS +
inline SVG, zero CDN). It must read as a polished ops product — an
executive S&OP decision cockpit — not a generated report.

## Theme system

Dual theme, dark default. CSS custom properties on `:root`, toggle
button stamps `data-theme="light|dark"` (persisted via
`localStorage`); also respects `prefers-color-scheme` when no explicit
choice has been made. Colors match the same validated, colorblind-safe
palette used across the author's other showcase repos — referenced by
role, never raw hex in the body:

```css
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
  /* status colors unchanged */
}
```

Typography: `system-ui, -apple-system, "Segoe UI", sans-serif`
everywhere (hero numbers included). `font-variant-numeric: tabular-nums`
only in table columns and axis ticks. Text always wears ink tokens,
never series colors; a colored swatch beside text carries identity.

## Layout

Max-width 1280px centered, 24px gutters. Section order:

1. **Header bar** — small inline-SVG bar-chart glyph (three ascending
   bars, `--s1`/`--s5`/`--s8`), product name "S&OP Integrated Planning"
   with a "DEMO DATA" chip, subtitle "Base vs Upside vs Constrained ·
   Cascade Appliances (demo network)", generated-at stamp (passed in at
   build), theme toggle (sun/moon SVG button).
2. **KPI tile row** — Fill Rate ×3 (Base/Upside/Constrained), Bottleneck
   Resource Utilization, Upside Value Unlocked, Margin at Risk
   (Constrained). Tile = hero value (28px, ink), label (11px, muted,
   uppercase tracking), one-line context row with a status dot/triangle
   (never color alone — icon + text). Border 1px `--ring`, radius 10px,
   background `--surface`.
3. **Capacity utilization card** — scenario tabs (Base/Upside/
   Constrained). Bar chart, one bar per resource, height = that
   scenario's peak monthly utilization %; a dashed `--critical` line at
   the 100%-of-installed-capacity mark; bars that clear 100% render in
   `--critical` instead of `--s1`. Hover tooltip: resource name, peak
   utilization, installed hours/month, an explicit "over installed
   capacity" flag when applicable.
4. **Demand vs. supply card** — scenario tabs. Monthly line chart:
   demand (`--s1`) vs shipped (`--s8`), the gap between them shaded
   faintly in `--s8` wherever shipped falls short. Crosshair-style
   hover shows both series' values for the hovered month, plus the
   unmet-units gap when nonzero.
5. **Reconciliation card** — scenario tabs. Table by family: demand,
   shipped, fill %, revenue, gross margin, lost margin (only colored
   `--critical` when nonzero), ending inventory value; a totals row.
6. **Exec takeaway card** — one text callout, dynamically composed from
   the real KPI numbers: what the upside is worth, which resource binds
   and when, what happens if nothing is done (fill rate, margin at
   risk, which family absorbs it), and a one-line recommendation.
7. **Footer** — one-line methodology note (S&OP → IBP reconciliation
   citation + RCCP) + "Built with S&OP Integrated Planning" + docs
   pointer.

## Chart rules (non-negotiable)

- One y-axis per chart, never dual-axis. Hairline grids (`--grid`), no
  chart borders except the card ring.
- Fixed color-per-series assignment (demand always `--s1`, shipped/
  supply always `--s8`, over-capacity always `--critical`) — never
  repainted on tab switch.
- Every chart has a hover/tooltip layer: HTML div positioned near the
  cursor, `--surface` background, `--ring` border, 12px text, values
  bold and tabular.
- Selective labels only (bar values, line endpoints) — never one label
  per data point.
- Cards: `--surface` background, 1px `--ring` border, radius 12px, 20px
  padding, 16px section titles (600 weight) with a muted 12px kicker
  above ("ROUGH-CUT CAPACITY PLANNING", "DEMAND VS. SUPPLY",
  "RECONCILIATION", "RECOMMENDATION").

## JS behavior

Single `<script>` at the end: `const DATA = {...}` embedded via the
`__DATA_JSON__` sentinel (not `str.format`/f-string, so literal `{ }`
in the CSS/JS stay intact) with `</` escaped to `<\/` so no embedded
string can prematurely close the `<script>` element. Small pure
functions render each card from `DATA`; scenario tabs re-render only
the affected card. Theme toggle persists via `localStorage`. No
frameworks, no build step — the file is the artifact.

## Quality bar

Open it and it should look like a product screenshot you'd put in a
portfolio hero: aligned grids, consistent 8px spacing, no text under
11px, no pure `#000`/`#fff` mixing, nothing clipped at 1280px or 900px
width (cards stack via grid auto-flow on narrow viewports; wide charts
live inside their own horizontally-scrollable container rather than
squashing).
