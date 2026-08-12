# HANDOFF — S&OP Cockpit Revamp (research → alignment → build)

**Date:** 2026-08-12. **Repo:** `~/Documents/Aiwork/sop-integrated-planning` (branch `main`, remote `LaviSahu/sop-integrated-planning`, SSH).
**Why this handoff:** session hit ~128k context mid-task. Research is DONE and saved as files. The heavy unread inputs (transcript + screenshots) are read in the FRESH session. **Nothing durable is lost** — everything is a file in `research/` + this doc, committed locally (not pushed).

---

## The transcript — saved & converted (cockpit design-philosophy gold)
- **`research/wispr-transcript.md`** — clean markdown (1014 lines) of Lavi's "clean discussion," converted from the original **`research/Untitled.rtf`** (421 KB) via `textutil`.
- **What it actually is:** notes from a **zerOm** meeting (a causal decision engine; attendees incl. Lavi, Saurabh Verma, Prabhat Agarwal, Ravi Shanker; Union Coop UAE retail demo). It is **not** S&OP arithmetic — it's **cockpit/dashboard design philosophy** that maps 1:1 onto this revamp:
  - **MECE, non-overlapping KPI signals** (so execs don't dispute the read).
  - **Surface positives alongside pain points** — holistic view, not just red.
  - **Explainability/trust is the crux** — causal linkage must "land smoothly"; cover edge cases, not just the happy path.
  - **Tabular view alongside the visual** (simpler consumption / audit).
  - **Backtesting view** (lift on past data, same formulas) → builds trust.
  - **Human-in-the-loop override** — let users feed corrections / business knowledge back in.
- Read it for the **design language**, then cross-apply to the S&OP cockpit (white-box, drill-down, scenario levers).
- ⚠️ **Privacy:** real names + a private startup's details. Commit is **local only** — do NOT push to a public remote without redacting.

---

## What's done & exactly where to read it
1. **`research/findings.md`** — full grounded research in readable markdown: executive summary, 12 revamp pillars, **9 ranked decisions** (each with options + recommendation + why), cross-cutting themes, all **48 findings** across 6 dimensions, every source cited with URL + year. **Read first.**
2. **`research/findings.html`** — interactive version (183 KB, offline, light/dark toggle). Same content, clickable links.
3. **`research/vision-state.md`** — the strategic pivot + Claude's recommendation + inputs-to-ingest + next-session job + open questions. **Read second.**
4. Raw research JSON (re-extraction only): `/private/tmp/claude-501/-Users-lavisahu/8ca3b857-b564-41c1-ac68-119fa2e18b8b/tasks/wyys62zwa.output` → `.result.dimensions[]`, `.result.brief`. *(Temp file — may be cleaned; `findings.md` is the durable copy.)*

---

## Lavi's strategic pivot (headline — overrides earlier "stdlib-only" framing)
1. **Drop the Python-stdlib-only constraint.** Go more elaborate (allow `pandas`/`numpy`; keep the dashboard hand-rolled HTML/SVG for IBCS visual control).
2. **NO optimizer route** (no LP/MIP solver) — confirmed.
3. **All possible scenarios + user levers** → an interactive S&OP **what-if simulator** (drag levers, recompute, compare scenarios).
4. **Both Gartner Stage 3 AND Stage 4.**
5. Bar: **real realism, detailed, not a toy, impeccable visuals, double-click drill-down.** "Multiple scenarios, depth, connections, parameters that are connected, easy to understand."

**Claude's reframe (confirm with Lavi in fresh session):** no-optimizer is *compatible* with elaborate — scenarios/levers = parameter sweeps recomputed by readable rules (TOC heuristic, rolling inventory `Opening+Production−Demand=Closing`, contribution-margin rationing, MAPE/forecast-error), NOT optimization. Reposition from "zero-dependency white-box" to **"fully transparent planning logic — no proprietary optimizer, every lever traceable."** Stage-4 probabilistic demand via sampling/distributions, not solving.

**Open debate Lavi flagged:** scope of "all scenarios + various levers" can sprawl — define the scenario matrix + lever list deliberately so it stays comprehensible (not a toy in the *other* direction — bloated).

---

## Fresh-session job (STRICT ORDER — NO code until aligned)
1. **Read:** `research/findings.md` + `research/vision-state.md` + `research/wispr-transcript.md` + the **11 screenshots** at `~/Documents/Screenshot/SCR-20260805-*.{jpeg,png}`.
2. **Synthesize** "here's what I understand" → confirm same page with Lavi.
3. **Iterated HTML mockups**, ONE section at a time: layout shell → scenario comparison → lever/drill-down interaction → KPI tiles → margin waterfall. Lavi approves/corrects each.
4. **Lock scope** (reframe the 9 decisions against the pivot) → then implement.

---

## The 9 decisions (full text in `findings.md` § Top decisions)
1 Scope/identity (white-box audit cockpit) · 2 Gartner maturity target · 3 Demand representation (deterministic vs forecast cone) · 4 Rationing-rule correction (one-line TOC fix vs LP) · 5 Rolling cycle depth · 6 Backorder policy · 7 Allocation-rule posture · 8 Visualization posture (strict IBCS shared-scale) · 9 "Gross margin"→contribution-margin rename.
**Note:** Decision 1 (stdlib positioning) is now in flux per the pivot — re-litigate first in the fresh session.

---

## Repo / run facts
- Regenerate current dashboard: `PYTHONPATH=src python3 -m sop_integrated_planning.cli dashboard` → `output/dashboard.html`.
- Tree was clean before this session; new untracked `research/` + this handoff are committed locally (no push).

---

## Suggested skills (next session)
- **`/brief`** — keep scannable output (this session ran brief).
- **`artifact-design` + `dataviz`** — load BEFORE the first cockpit mockup (IBCS discipline, color formula, mark specs). Holds the "impeccable" bar.
- `claude-api` — only if a real LLM/forecast layer gets wired (unlikely under the no-solver stance).
- Skip `code-review` / `simplify` until implementation lands.

---

## Working style (carry forward)
- Judge files/diffs, never prose. Verify every claim before stating it.
- Lavi is terse, decisive, pushes back on badly-scoped work — give a recommendation + one clear next action, not exhaustive surveys.
- He wants to be grilled and to debate scope (esp. stdlib-vs-elaborate + "all scenarios" sprawl). Define the lever/scenario matrix deliberately; don't over-build.
- **Do NOT implement until he confirms same page.** He said so explicitly.
