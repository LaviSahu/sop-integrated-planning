# sop-integrated-planning

**S&OP / IBP cockpit:** demand plan → Rough-Cut Capacity Planning → constrained supply plan → financial reconciliation → self-contained HTML dashboard comparing base, upside, and constrained scenarios.

- **`SCOPE.md` is the current build scope (locked 2026-08-12) — read it first.** It supersedes the stdlib-only
  positioning below: pandas/numpy are allowed in the data layer, the cockpit is an interactive what-if simulator,
  and there is still **no optimizer**.
- `DESIGN.md` is the behavioural contract — read before changing behaviour. `implementation-notes.md` logs deviations.
- Dashboard stays hand-rolled HTML + inline SVG (no charting library, no CDN). Zero API keys. Build via `Makefile`;
  outputs in `output/`.

Generic coding-behaviour guidance lives once at `~/.claude/reference/coding-guidelines.md` — read it for heavy refactors, not routine edits.
