# KPI Reference

Every formula below is transcribed from `capacity.py`, `constrain.py`,
`finance.py`, and `kpi.py` as actually implemented. Values in the right
column are from a live `make demo` run against the seeded Cascade
Appliances dataset (seed `20260714`, `output/comparison.json`) — re-run
the demo after editing `datagen.py` and these numbers will change;
nothing here is hardcoded in `kpi.py` itself.

## Fill rate (`finance.summarize`, `kpi.fill_rate_kpi`)

```
fill_rate = total_shipped_units / total_demand_units      # across all families, all 12 months
```

| Scenario | Fill rate |
|---|---|
| Base | 100.00% |
| Upside | 100.00% |
| Constrained | 99.09% |

## RCCP utilization (`capacity.compute_loads`)

```
load_hours[resource, month]   = sum(demand_units[family, month] * hours_per_unit[family, resource] for family in families)
utilization_pct[resource, month] = load_hours / resource.monthly_available_hours * 100
is_bottleneck = utilization_pct > 100.0   # strictly greater — exactly 100% is feasible, not a bottleneck
```

Computed **against installed capacity, always** — regardless of
scenario. This is what makes the Upside bottleneck visible even though
Upside's supply plan fully ships (see
[Scenario Guide](05-scenario-guide.md)).

## Bottleneck resource (`kpi.bottleneck_kpi`)

The single worst `(resource, month)` combination in the Upside demand
plan:

```
peak = max(loads, key=utilization_pct)
```

| Field | Value |
|---|---|
| Resource | Assembly Line A (heavy) (`RES-LINEA`) |
| Month | April |
| Peak utilization | 114.98% |
| Installed capacity | 9,500 hrs/month |

The next-closest resource, Test/QA, peaks at 95.34% under the same
Upside demand — comfortably under 100%, so Assembly Line A is the sole,
unambiguous binding constraint (see `implementation-notes.md` for the
tuning pass that produced this clean single-bottleneck result).

## Constrained rationing (`constrain._allowed_units_this_month`)

When a resource's load exceeds installed capacity and no investment is
assumed (Constrained), hours are granted to each family in **descending
unit-margin order** until the budget is exhausted:

```
for family in sorted(users, key=unit_margin, reverse=True):
    wanted_hours = demand_units[family] * hours_per_unit[family, resource]
    granted_hours = max(0, min(wanted_hours, remaining_hours))
    remaining_hours -= granted_hours
```

Family unit margins on the bottleneck resource, descending: Refrigerators
$537.00 > Washers $328.00 > Dryers $297.00. Refrigerators and Washers
are fully protected all year (0 unmet units); Dryers absorbs the entire
shortfall.

## Revenue, gross margin, lost revenue, lost margin (`finance.py`)

```
revenue       = shipped_units * unit_price
gross_margin  = shipped_units * unit_margin
lost_revenue  = unmet_units   * unit_price
lost_margin   = unmet_units   * unit_margin
```

| Metric | Base | Upside | Constrained |
|---|---|---|---|
| Revenue | $127,687,935 | $148,472,953 | $147,221,512 |
| Gross margin | $52,203,890 | $60,625,548 | $60,093,820 |
| Lost revenue | $0 | $0 | $1,251,441 |
| Lost margin | $0 | $0 | $531,728 |

## Ending inventory value (`finance.summarize`)

```
ending_inventory_value = sum(inventory_value for line in finance_lines if line.month == 12)
```

Deliberately **only December**, not summed across all 12 months — a
month's ending inventory becomes next month's opening balance, so
summing every month would count the same carried stock repeatedly.

| Scenario | Ending inventory value (Dec, at cost) |
|---|---|
| Base | $8,421,000 |
| Upside | $8,421,000 |
| Constrained | $7,375,800 |

## Upside value unlocked (`kpi.upside_value_unlocked_kpi`)

```
upside_value_unlocked = upside.total_gross_margin - constrained.total_gross_margin
```

**$531,728** — and by construction this is *exactly equal* to Margin at
Risk (Constrained) below: Upside ships 100% of the same uplifted demand
Constrained only partially ships, so the entire gross-margin gap
between the two scenarios is precisely the margin Constrained left on
the table.

## Margin at risk / lost revenue (Constrained) (`kpi.lost_margin_kpi`, `kpi.lost_revenue_kpi`)

```
lost_margin_by_family = {family: sum(finance_line.lost_margin for that family's 12 finance lines)}
worst_family = max(lost_margin_by_family, key=lost_margin_by_family.get)
```

| KPI | Value | Context |
|---|---|---|
| Margin at Risk (Constrained) | $531,728 | concentrated in FAM-DRY (Dryers) |
| Lost Revenue (Constrained) | $1,251,441 | value of unmet demand, full year |

Next: [Data Dictionary](04-data-dictionary.md).
