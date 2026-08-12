# HANDOFF — S&OP Cockpit Revamp (mockups 1+2 shown to Lavi, verdict pending)

**Date:** 2026-08-13 (supersedes the earlier version of this file from the same day).
**Repo:** `~/Documents/Aiwork/sop-integrated-planning` — branch `main`, remote `LaviSahu/sop-integrated-planning` (SSH).
**Why:** session hit ~111k context. Mockup 2's collision bug (left from last session) is found and fixed.
Both mockups were opened in Lavi's browser for review — **his verdict was not yet given when this session ended.**

---

## Read this first

**`SCOPE.md`** — the locked build scope, current. Do not re-derive it. §7 governs "hand-checkable arithmetic";
§8b gives the chart grammar; §9 gives the mockup build order (each mockup needs approval before the next starts).

---

## Status

| Phase | State |
|---|---|
| Research, transcript, screenshots, scope lock | done (unchanged) |
| `mockups/tokens.css` contrast audit | done (unchanged, prior session) |
| `mockups/build_data.py` + `mockups/data.js` | done — real engine output, zero hand-typed numbers |
| **Mockup 1 — layout shell** | done, verified, **shown to Lavi this session** |
| **Mockup 2 — scenario comparison** | done, verified, fill-rate collision fixed, **shown to Lavi this session** |
| Mockup 3 — levers/drill-down | not started — **blocked on Lavi's approval of 1+2** |
| Mockup 4 — KPI tiles | not started |
| Mockup 5 — margin waterfall | not started |
| Implementation | not started. Do not start it. |

---

## Immediate next step

**Ask Lavi for his verdict on mockups 1 and 2** (both were opened via `open mockups/0{1,2}-*.html` in his
default browser at the end of the session — check whether he actually looked). Specifically need:
1. Approval to move on to mockup 3, per SCOPE §9's one-mockup-at-a-time gate.
2. The open judgement call from mockup 1: Base's solid-white bars read visually heavy against near-black —
   drop actual fills to ~85% ink, or leave as-is?
3. Any defects he spots that this session's headless-Chrome inspection missed — headless review is a proxy,
   not a substitute for his eyes on the real interactive render.

If he approves, start mockup 3 (levers + drill-down, 5-step provenance modal per SCOPE §6b) — load the
`dataviz` skill again first, per project convention.

---

## What changed this session

### Fixed: mockup 2's fill-rate axis-note collision (new defect, found on re-render)
Prior session's three flagged geometry fixes (structural-comparison gutter, variance "reference" label,
family-drilldown gutter) were **re-rendered and confirmed clean** — no action needed there.

But a fourth, previously-unflagged defect turned up: in the Fill rate row of the structural-comparison table,
the "axis starts at 98.00%, not zero" note text overlapped the Upside bar and its `100.00%` label.

**Root cause** (`mockups/02-scenario-comparison.html`, `drawLevels`): every metric's SVG used a fixed
`viewBox` height (`BH = 70`), sized to fit exactly 3 bar rows. Only the `fill` metric adds an extra bottom-axis
note line inside that same fixed height — there was no room reserved for it, so it collided with row 3.

**Fix:** added `NOTE_BH = 92` and a `hasNote` flag; metrics with a note now render in the taller box, note text
repositioned to sit clearly below all three rows. Other 5 metrics' geometry is untouched (verified: their SVGs
never reach the `hasNote` branch). Re-rendered and confirmed: 24-unit clearance between the last bar and the
note, no overlap, no regression to row alignment (the row's variance-panel cell just gets a little extra
whitespace, which is already normal in this design — e.g. Closing inventory's small variance mark).

### Tooling note: `claude-in-chrome` cannot open `file://` mockup URLs
The browser extension refuses local file URLs ("Can't interact with browser-internal or unparseable URLs").
Worked around by using headless Chrome directly for automated inspection, and macOS `open` for showing Lavi
the live interactive version:
```bash
# automated screenshot/inspection (agent-side verification)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --no-sandbox \
  --window-size=1600,2400 --screenshot=/path/out.png "file://$(pwd)/mockups/FILE.html"
# then crop regions with: uv run --with pillow python3 -c "from PIL import Image; ..."

# show Lavi the real, interactive render
open mockups/FILE.html
```
Logged to global `~/.claude/LEARNINGS.md` since this will recur on any local-HTML verification task.

---

## Engine facts (unchanged, still current — not re-derived here)

See the previous version of this file (in git history, commit `09217a2`) for full engine-facts and the
architecture-fork section (client-side lever-drag recompute → JS port, Python as reference, golden-fixture
tests). Nothing changed there this session. Two open questions for Lavi remain **unanswered**:
1. Planner override / HITL — in scope, and how deep? (`SCOPE.md` §8)
2. The JS-port fork — confirm the golden-fixture approach.

### Blocker on Stage-4 goal (unchanged)
`data/families.json` has no revenue/margin targets. Stage 4 needs an explicit target per scenario plus a
gap-to-plan line in $ and % — new input data, not just a new chart. Raise before claiming Stage 4.

---

## Next jobs, in order

1. **Get Lavi's verdict on mockups 1+2** (see "Immediate next step").
2. If approved: Mockup 3 — levers + drill-down interaction (5-step provenance modal, SCOPE §6b).
3. Mockup 4 — KPI tiles.
4. Mockup 5 — margin waterfall.

---

## Suggested skills

- **`dataviz`** — load again before touching mockup 3+, non-optional for this work per project convention.
- **`/brief`** — this session ran in brief mode; Lavi prefers it.
- **`artifact-design`** — layout/visual fundamentals, relevant for the provenance-modal work in mockup 3.
- Skip `code-review` / `simplify` until implementation actually lands.

---

## Working style (carry forward, unchanged)

- **Judge files and diffs, never prose.** Verify every claim by running it.
- **Read the sources yourself when they're the design input.**
- Lavi is terse and decisive, pushes back on badly-scoped work, wants to be grilled. Recommendation + one next
  action, not a survey.
- **Do not implement until he confirms.** Still true, still unconfirmed.

---

## Privacy

`research/wispr-transcript.md` contains real names and a private startup's commercial details.
**Local commits only — do not push to any public remote without redacting.**
