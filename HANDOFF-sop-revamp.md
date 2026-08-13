# HANDOFF — S&OP Cockpit: showcase-ready, live on GitHub Pages

**Date:** 2026-08-13 (supersedes the levers-wired version).
**Repo:** `~/Documents/Aiwork/sop-integrated-planning` — branch `main`, remote `LaviSahu/sop-integrated-planning` (SSH `github-lavisahu`, key `~/.ssh/id_lavisahu`).
**Status:** showcase cleanup **DONE + pushed**. GitHub Pages **LIVE**. One pending commit (dashboard snapshots).

---

## Read this first

**`docs/index.md`** — the public wiki home (01–08). **`README.md`** — the showcase front door. The old internal `SPEC/DESIGN/SCOPE.md` are **archived** in `archive/` (not public surface). `implementation-notes.md` stays (docs cite its deviations).

---

## Status

| Item | State |
|---|---|
| Levers wired (client-side recompute) | done, pushed earlier |
| **Wispr-transcript privacy purge** | done — removed from all history + remote |
| **Showcase README rewrite** | done + pushed (`7ccf744`) |
| **Terminology: gross→contribution margin (docs)** | done; code field names still legacy |
| **Archive internal docs** | done — `SPEC/DESIGN/SCOPE/Untitled.rtf` → `archive/` |
| **New docs 07 + 08** | done — method/assumptions + Invest-scenario story |
| **GitHub Pages live dashboard** | **LIVE** — `https://lavisahu.github.io/sop-integrated-planning/dashboard.html` (200, verified) |
| **Dashboard snapshots** | **3 PNGs dropped in `docs/img/` by Lavi — NOT committed** (pending) |

---

## What shipped this session

- **README** rewritten as a portfolio showcase: leads with the **$531,728 takeaway** (`upside value unlocked` = `margin at risk if not funded`), describes the live levers dashboard (S0–S4, ration-rule selector, provenance modal), honest "what this does NOT do" box, docs 01–08 links. Zero links to archived/internal files.
- **docs/07-method-and-assumptions.md** — model assumptions + a fully worked invest decision (overtime premium vs machine lease, on the 3,073 hr/yr bottleneck vs $531,728 margin at risk).
- **docs/08-invest-scenario-story.md** — "The 3,073-Hour Decision": Act 1 (April 114.98% / 1,423 hrs), Act 2 ($531,728 all in Dryers), Act 3 (the Invest decision), + honest spec for planned S4.
- **GitHub Pages enabled** (via `gh api` as **LaviSahu**, the owner — `gnik1487` auth 404'd). Source `main`/`/docs`, serves `docs/dashboard.html` (self-contained copy of the built cockpit, committed).
- **Contribution-margin terminology** fixed across `docs/02/03/04/05` (docs only; code's `gross_margin` field name untouched — deferred to redo).

## The snapshot problem (resolved by Lavi)

Every headless capture tool on this Mac renders the dashboard **black**: system Chrome (file + live URL), Playwright Chromium (all flags/themes), Playwright WebKit. Root cause: dark `#0a0b0f` canvas + transparent child backgrounds rasterize black in every headless engine. **Lavi screenshotted manually** into `docs/img/`. The live Pages URL IS the demo.

---

## Pending (the immediate next step)

**DONE — 2026-08-13 (a523641, pushed):** committed the **9** dashboard snapshots (not 3 — Lavi had dropped more; the `-2` variants were byte-identical duplicates and were deleted), resized to 1600px max, wired into the README's "See it live" section as a 3×3 captioned gallery (captions verified by macOS Vision OCR against the dashboard's real section titles). Push used the SSH key from the next line. The live Pages URL remains the primary demo.

## Other not-started items (deferred, Lavi's call)

1. **S4 Invest code build** — the capex→P&L, payback/ROI scenario. The story is written (docs/08) but the engine isn't. The dashboard's S4 preset is disabled with "not in engine" tag.
2. **Code rename `gross_margin` → `contribution_margin`** — the docs are fixed; the code field names are legacy (highest-credibility-ROI code fix).
3. **MAPE forecast cone + safety stock** — biggest credibility jump toward Stage-4 S&OP (roadmap's top probabilistic next step).
4. **Throughput-per-bottleneck-hour rationing** — the UI has the selector; the Python engine still sorts by raw unit_margin (SCOPE §8b).
5. **Build-ahead / backorders / inventory carrying cost** — roadmap extensions.

## Working style / conventions

- **Judge files and diffs, never prose.** Verify before claiming.
- Lavi is terse and decisive; wants to be grilled; pushes back on badly-scoped work.
- **Do not start a redesign** — "new version" is the deferred slot for items 1–5.
- The dashboard template is `mockups/dashboard-body.html` + `dashboard-app.js` + `dashboard.css`; `mockups/splice.py` regenerates `dashboard.py::_TEMPLATE`. `mockups/assemble_dashboard.py` is stale/untracked — ignore it.
- **SSH push gotcha:** `git push` needs `GIT_SSH_COMMAND="ssh -o BatchMode=yes -i ~/.ssh/id_lavisahu -o IdentitiesOnly=yes"` (agent state is unreliable). `gh` is now switched to **LaviSahu** (owner).
- After the earlier history rewrite, a normal push may hit GitHub "Internal Server Error" — `--force` resolved it (safe: it was a fast-forward).

## Suggested skills

- **`impeccable`** (project skill) — for the dashboard snapshots' presentation and any further frontend polish of the showcase (the lever panel, screenshot framing).
- **`update-config`** — only if wiring new hooks/permissions into `~/.claude/settings.json`; not needed for repo work.
- No `dataviz`/`linkedin-*`/`spark`/`brief`/`terse` relevance — single-repo engineering. Run `skill-audit` after any skill edit (CLAUDE.md requires it exit 0).

## Privacy

The wispr transcript was **purged from all history + remote**. The repo is **PUBLIC** — keep anything with real names or private commercial details out (Lavi's handoff said local-commits-only unless redacted; the transcript is gone, don't reintroduce it).
