# sop-integrated-planning

**S&OP / IBP cockpit:** demand plan → Rough-Cut Capacity Planning → constrained supply plan → financial reconciliation → self-contained HTML dashboard comparing base, upside, and constrained scenarios.

- `DESIGN.md` is the contract — read before changing behaviour. `implementation-notes.md` logs deviations.
- Pure Python stdlib, zero dependencies, zero API keys. Build via `Makefile`; outputs in `output/`.

Generic coding-behaviour guidance lives once at `~/.claude/reference/coding-guidelines.md` — read it for heavy refactors, not routine edits.
