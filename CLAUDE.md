# sop-integrated-planning

**S&OP / IBP cockpit:** demand plan → Rough-Cut Capacity Planning → constrained supply plan → financial reconciliation → self-contained HTML dashboard comparing base, upside, and constrained scenarios.

- **Build scope (locked 2026-08-12):** pandas/numpy are allowed in the data layer, the cockpit is an interactive
  what-if simulator, and there is still **no optimizer**. The public reference layer is `docs/` — start with
  `docs/01-architecture.md`, then `docs/02-sop-ibp-method.md`; `docs/07-method-and-assumptions.md` states the honest limitations.
- Behavioural contract: see `docs/01-architecture.md` (dashboard context contract) before changing behaviour.
  `implementation-notes.md` logs deviations.
- Dashboard stays hand-rolled HTML + inline SVG (no charting library, no CDN). Zero API keys. Build via `Makefile`;
  outputs in `output/`.

Generic coding-behaviour guidance lives once at `~/.claude/reference/coding-guidelines.md` — read it for heavy refactors, not routine edits.
