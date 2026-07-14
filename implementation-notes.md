# Implementation Notes — S&OP Integrated Planning

Scope of this pass: the full repo — engine (`models.py` through
`kpi.py`), `dashboard.py`, `cli.py`, `tests/`, `docs/`, and the
showcase `README.md` — built in one pass, verified end to end
(`make demo`, `make test`) before the initial commit.

## Deviations

Per the brief's instruction to log deviations, pick the conservative
option, and keep going. None of these block the two verification
commands (`PYTHONPATH=src python3 -m unittest discover -s tests -v`,
`make demo`), both of which pass cleanly.

1. **Scenario semantics — resolving an apparent tension in the brief.**
   The brief describes UPSIDE as both "expose the bottleneck" and
   "if we add capacity" (implying the bottleneck gets resolved). These
   are reconciled by separating two concerns that live in different
   modules: `capacity.py`'s RCCP utilization is **always** computed
   against installed capacity, regardless of scenario — so UPSIDE's
   bottleneck is genuinely visible in the capacity chart. Only
   `constrain.py` decides what happens next: UPSIDE's
   `effective_capacity_hours` invests exactly enough to close the gap
   RCCP flagged (full fill, 0% lost margin), while CONSTRAINED's does
   not (real rationing). This makes UPSIDE and CONSTRAINED share one
   demand plan and one RCCP diagnostic, differing only in the supply-
   side investment decision — which is the whole point of running three
   scenarios instead of one.

2. **`datagen.RESOURCE_TABLE`'s Test/QA capacity tuned from 2,100 to
   2,220 hours/month.** The initial seeded dataset produced a secondary
   near-bottleneck: Test/QA hit 100.79% utilization under UPSIDE
   demand, alongside Assembly Line A's 114.98% — muddying the "single,
   clean bottleneck" narrative the brief asks for. Verified via ad hoc
   script execution that bumping Test/QA's installed hours by 120
   (2,100 → 2,220) drops its UPSIDE peak to 95.34% (safely under 100%)
   while leaving BASE unaffected (Line A still peaks at 94.48%, fully
   feasible) and Line A's UPSIDE peak unchanged at 114.98–115.0%. This
   is the only constant tuned away from a first-draft value; every
   other number in `datagen.py` is as originally drafted and happens to
   produce the required BASE-feasible/UPSIDE-bottlenecked tension
   without further adjustment.

3. **Margin-priority rationing can drive a family to zero shipments in
   a given month**, not just a partial cut. `constrain.py`'s
   `_allowed_units_this_month` allocates a resource's remaining hours to
   families in strict descending-margin order; if the highest-margin
   users alone consume the entire budget, lower-margin users get
   nothing that month. This is the literal, uncited "protect the
   highest-margin business first" rule the brief specifies — no floor
   or minimum-allocation rule was invented, since the brief doesn't ask
   for one and adding one would be inventing an undocumented policy.
   In the real seeded CONSTRAINED run this shows up as Dryers (the
   lowest-margin heavy user of the bottleneck resource) taking the
   full shortfall, worst in May (57.95% fill that month) while
   Refrigerators and Washers stay fully protected all year.

4. **No backorders / no build-ahead**, in either direction. `shipped =
   min(opening + produced, demand)` — unmet demand is a lost sale, not
   a promise fulfilled next month; and `produced` is capped at that
   month's own demand — the model never stockpiles ahead of a future
   shortfall it could in principle see coming (RCCP is a monthly
   feasibility check, not a multi-period optimizer). This is the
   simpler, more conservative reading of "constrained supply plan" and
   matches the single-stage scope of the brief; a real S&OP process
   would often pre-build ahead of a known seasonal peak, which is
   exactly the kind of enhancement flagged in `docs/06-roadmap.md`
   rather than added here.

5. **Test suite path shim: `tests/_bootstrap.py`, not
   `tests/__init__.py`.** `python -m unittest discover -s tests` (no
   `-t`) treats `tests/` as its own top-level directory and imports
   `test_*.py` as flat top-level modules, not as `tests.test_*` — so
   code in `tests/__init__.py` never executes in that invocation and
   can't be used to extend `sys.path`. Every test module instead starts
   with a plain `import _bootstrap`, which inserts `src/` onto
   `sys.path`. `tests/__init__.py` is kept (marks the directory as a
   package for other tooling) but is not load-bearing for the
   documented `python3 -m unittest discover -s tests -v` invocation.

6. **CLI data-path resolution derives the repo root from `__file__`**
   (`cli.py::_repo_root`, three parents up from
   `src/sop_integrated_planning/cli.py`), not from the current working
   directory. This makes `python -m sop_integrated_planning demo` (and
   `make demo`, which sets `PYTHONPATH=src` but does not `cd`) resolve
   `data/` and `output/` identically regardless of the invoking shell's
   working directory, without requiring `--data-dir`/`--output-dir`
   flags in the common case. Both flags exist as overrides.

## Verification performed

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` → **83
  tests, all passing** (well over the 30-test target): real math and
  boundary asserts per engine module (including an exact
  100%-utilization boundary that must NOT trip `is_bottleneck`), a
  margin-priority rationing case worked by hand in `tests/fixtures.py`,
  a full-pipeline integration suite run on the real seeded dataset
  (asserting BASE ≤100% everywhere, UPSIDE >100% on at least one
  resource, CONSTRAINED fill <100% with lost margin >0), and a
  dashboard-render suite (self-contained HTML, JSON-safe against an
  embedded `</script>` string).
- `make demo` runs clean end to end: regenerates `data/families.json` +
  `data/resources.json`, prints the three-scenario console comparison,
  writes `output/comparison.json` and `output/dashboard.html`.
- `output/dashboard.html` confirmed self-contained: no `http://`,
  `https://`, `<script src=`, or `<link` of any kind in the rendered
  file.
- Real seeded run confirms the required emergent tension: BASE peak
  utilization 94.48% (Assembly Line A, no bottleneck anywhere);
  UPSIDE's Assembly Line A peaks at 115.0% in April (the sole
  bottleneck — Test/QA is the next-closest at 95.3%, safely under);
  CONSTRAINED fill rate 99.1%, $531,728 lost margin concentrated in
  Dryers, exactly equal to the $531,728 Upside Value Unlocked KPI (an
  exact identity: UPSIDE ships the same uplifted demand CONSTRAINED
  only partially ships, so the gross-margin delta between them is by
  construction the margin CONSTRAINED left on the table).
