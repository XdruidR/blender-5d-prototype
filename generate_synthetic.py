"""
generate_synthetic.py
---------------------
Generates the three data files that drive the 5D BIM demo:

  data/schedule.json   — 7-activity WBS-based schedule (June 2026 – April 2027)
  data/cbs.json        — 5 cost codes, total $1,800,000
  data/pv_spread.json  — monthly Planned Value per task per cost code
                         using a bell-curve distribution

Cost architecture
------------------
  CBS-001  Concrete Substructure   $280 000  → A001
  CBS-002  Reinforced Conc. Cols   $420 000  → A002 50% / A004 25% / A006 25%
  CBS-003  Reinforced Conc. Beams  $360 000  → A003 40% / A005 35% / A007 25%
  CBS-004  Reinforced Conc. Slabs  $540 000  → A003 40% / A005 35% / A007 25%
  CBS-005  Formwork & Shoring      $200 000  → A001-A007 (10/20/20/10/20/10/10 %)

  Total Project Value: $1 800 000

Run:
    python generate_synthetic.py
Outputs: data/schedule.json, data/cbs.json, data/pv_spread.json
"""

import os
import json
import numpy as np
from datetime import date
from dateutil.relativedelta import relativedelta

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Bell-curve PV spread  (mandatory pattern — do not modify)
# ---------------------------------------------------------------------------

def bell_spread(total: float, start_date: date, end_date: date) -> dict:
    """Distribute `total` dollars over monthly buckets using a bell curve."""
    months = []
    d = start_date.replace(day=1)
    while d <= end_date.replace(day=1):
        months.append(d.strftime("%Y-%m"))
        d += relativedelta(months=1)
    n = len(months)
    if n == 1:
        return {months[0]: round(total, 2)}
    weights = np.exp(-0.5 * (np.linspace(-2, 2, n) ** 2))
    weights /= weights.sum()
    values = {m: round(float(total * w), 2) for m, w in zip(months, weights)}
    # Correct rounding drift on the peak month
    diff = round(total - sum(values.values()), 2)
    if diff != 0:
        peak = months[n // 2]
        values[peak] = round(values[peak] + diff, 2)
    return values


# ---------------------------------------------------------------------------
# Schedule definition
# ---------------------------------------------------------------------------
#
# Construction sequence for a 3-storey RC frame:
#   A001  Substructure – Footings
#   A002  Ground Floor – Columns
#   A003  Ground Floor – Beams & Slab
#   A004  Level 1 – Columns
#   A005  Level 1 – Beams & Slab
#   A006  Level 2 – Columns
#   A007  Level 2 – Beams & Roof Slab
#
# Note: slight overlaps between column and frame activities on different
# levels are intentional and reflect real fast-track construction logic.
# ---------------------------------------------------------------------------

SCHEDULE = [
    {
        "task_code":  "A001",
        "task_name":  "Substructure – Pad Footings",
        "start_date": "2026-06-01",
        "end_date":   "2026-07-15",
        "wbs_level1": "CONSTRUCTION",
        "wbs_level2": "SUBSTRUCTURE",
        "wbs_level4": "PKG-FOOTINGS",
        "cost_codes": ["CBS-001", "CBS-005"],
    },
    {
        "task_code":  "A002",
        "task_name":  "Ground Floor – RC Columns",
        "start_date": "2026-07-16",
        "end_date":   "2026-08-31",
        "wbs_level1": "CONSTRUCTION",
        "wbs_level2": "GROUND-FLOOR",
        "wbs_level4": "PKG-COLUMNS-GF",
        "cost_codes": ["CBS-002", "CBS-005"],
    },
    {
        "task_code":  "A003",
        "task_name":  "Ground Floor – RC Beams and Slab",
        "start_date": "2026-09-01",
        "end_date":   "2026-10-31",
        "wbs_level1": "CONSTRUCTION",
        "wbs_level2": "GROUND-FLOOR",
        "wbs_level4": "PKG-FRAME-GF",
        "cost_codes": ["CBS-003", "CBS-004", "CBS-005"],
    },
    {
        "task_code":  "A004",
        "task_name":  "Level 1 – RC Columns",
        "start_date": "2026-11-01",
        "end_date":   "2026-11-30",
        "wbs_level1": "CONSTRUCTION",
        "wbs_level2": "LEVEL-1",
        "wbs_level4": "PKG-COLUMNS-L1",
        "cost_codes": ["CBS-002", "CBS-005"],
    },
    {
        "task_code":  "A005",
        "task_name":  "Level 1 – RC Beams and Slab",
        "start_date": "2026-12-01",
        "end_date":   "2027-01-31",
        "wbs_level1": "CONSTRUCTION",
        "wbs_level2": "LEVEL-1",
        "wbs_level4": "PKG-FRAME-L1",
        "cost_codes": ["CBS-003", "CBS-004", "CBS-005"],
    },
    {
        "task_code":  "A006",
        "task_name":  "Level 2 – RC Columns",
        "start_date": "2027-02-01",
        "end_date":   "2027-02-28",
        "wbs_level1": "CONSTRUCTION",
        "wbs_level2": "LEVEL-2",
        "wbs_level4": "PKG-COLUMNS-L2",
        "cost_codes": ["CBS-002", "CBS-005"],
    },
    {
        "task_code":  "A007",
        "task_name":  "Level 2 – RC Beams and Roof Slab",
        "start_date": "2027-03-01",
        "end_date":   "2027-04-30",
        "wbs_level1": "CONSTRUCTION",
        "wbs_level2": "LEVEL-2",
        "wbs_level4": "PKG-FRAME-L2",
        "cost_codes": ["CBS-003", "CBS-004", "CBS-005"],
    },
]


# ---------------------------------------------------------------------------
# Cost Breakdown Structure
# ---------------------------------------------------------------------------
#
# Each cost code specifies total_cost = sum over all linked activities.
# The per-activity split is defined in CBS_SPLITS below (separate from
# cbs.json to keep that file clean for the Blender panel).
# ---------------------------------------------------------------------------

CBS = [
    {
        "cost_code":         "CBS-001",
        "description":       "Concrete Substructure (pad footings, blinding, lean mix)",
        "uom":               "m³",
        "total_cost":        280000.0,
        "linked_activities": ["A001"],
    },
    {
        "cost_code":         "CBS-002",
        "description":       "Reinforced Concrete Columns (formwork, rebar, pour, cure)",
        "uom":               "m³",
        "total_cost":        420000.0,
        "linked_activities": ["A002", "A004", "A006"],
    },
    {
        "cost_code":         "CBS-003",
        "description":       "Reinforced Concrete Beams (formwork, rebar, pour, cure)",
        "uom":               "m³",
        "total_cost":        360000.0,
        "linked_activities": ["A003", "A005", "A007"],
    },
    {
        "cost_code":         "CBS-004",
        "description":       "Reinforced Concrete Slabs (formwork, rebar, pour, cure, finish)",
        "uom":               "m²",
        "total_cost":        540000.0,
        "linked_activities": ["A003", "A005", "A007"],
    },
    {
        "cost_code":         "CBS-005",
        "description":       "Formwork, Propping & Shoring (all levels)",
        "uom":               "m²",
        "total_cost":        200000.0,
        "linked_activities": ["A001", "A002", "A003", "A004", "A005", "A006", "A007"],
    },
]

# Per-activity cost allocation weights (must sum to 1.0 per CBS code)
CBS_SPLITS = {
    "CBS-001": {"A001": 1.00},
    "CBS-002": {"A002": 0.50, "A004": 0.25, "A006": 0.25},
    "CBS-003": {"A003": 0.40, "A005": 0.35, "A007": 0.25},
    "CBS-004": {"A003": 0.40, "A005": 0.35, "A007": 0.25},
    "CBS-005": {"A001": 0.10, "A002": 0.20, "A003": 0.20,
                "A004": 0.10, "A005": 0.20, "A006": 0.10, "A007": 0.10},
}


# ---------------------------------------------------------------------------
# PV spread generation
# ---------------------------------------------------------------------------

def generate_pv_spread() -> dict:
    """
    Returns pv_spread[task_code][cost_code] = {YYYY-MM: value, ...}

    For each (task, cost_code) pair the total is:
        CBS total_cost  ×  CBS_SPLITS[cost_code][task_code]

    The monthly distribution uses bell_spread() over the task's duration.
    """
    # Build lookup maps
    task_lookup = {t["task_code"]: t for t in SCHEDULE}
    cbs_lookup  = {c["cost_code"]: c for c in CBS}

    pv: dict = {}

    for task in SCHEDULE:
        act_id = task["task_code"]
        start  = date.fromisoformat(task["start_date"])
        end    = date.fromisoformat(task["end_date"])
        pv[act_id] = {}

        for cc in task["cost_codes"]:
            cbs_total  = cbs_lookup[cc]["total_cost"]
            split_frac = CBS_SPLITS[cc].get(act_id, 0.0)
            act_total  = round(cbs_total * split_frac, 2)
            if act_total > 0:
                pv[act_id][cc] = bell_spread(act_total, start, end)

    return pv


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(pv_spread: dict):
    cbs_lookup = {c["cost_code"]: c for c in CBS}
    print("\n── Validation ──────────────────────────────────────")
    ok = True
    for cbs in CBS:
        cc        = cbs["cost_code"]
        expected  = cbs["total_cost"]
        actual    = sum(
            sum(pv_spread.get(act, {}).get(cc, {}).values())
            for act in cbs["linked_activities"]
        )
        diff = round(actual - expected, 2)
        status = "OK" if abs(diff) < 0.10 else f"DRIFT={diff}"
        if abs(diff) >= 0.10:
            ok = False
        print(f"  {cc}  expected={expected:>12,.2f}  actual={actual:>12,.2f}  {status}")
    total_expected = sum(c["total_cost"] for c in CBS)
    total_actual   = sum(
        v for act in pv_spread.values()
        for cc_vals in act.values()
        for v in cc_vals.values()
    )
    print(f"  {'TOTAL':6}  expected={total_expected:>12,.2f}  actual={total_actual:>12,.2f}")
    print(f"  {'─'*50}")
    if ok:
        print("  All CBS totals match ✓")
    else:
        print("  WARNING: some CBS totals have drift > $0.10")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    pv_spread = generate_pv_spread()

    # Write schedule.json
    sched_path = os.path.join(OUT_DIR, "schedule.json")
    with open(sched_path, "w") as f:
        json.dump(SCHEDULE, f, indent=2)
    print(f"Written: {sched_path}  ({len(SCHEDULE)} activities)")

    # Write cbs.json
    cbs_path = os.path.join(OUT_DIR, "cbs.json")
    with open(cbs_path, "w") as f:
        json.dump(CBS, f, indent=2)
    print(f"Written: {cbs_path}  ({len(CBS)} cost codes)")

    # Write pv_spread.json
    pv_path = os.path.join(OUT_DIR, "pv_spread.json")
    with open(pv_path, "w") as f:
        json.dump(pv_spread, f, indent=2)
    print(f"Written: {pv_path}")

    # Print schedule summary
    print("\n── Schedule summary ─────────────────────────────────")
    print(f"  {'Code':<6} {'Task':<42} {'Start':>10} {'End':>10} {'Cost Codes'}")
    print(f"  {'─'*6} {'─'*42} {'─'*10} {'─'*10} {'─'*20}")
    for t in SCHEDULE:
        print(f"  {t['task_code']:<6} {t['task_name']:<42} "
              f"{t['start_date']:>10} {t['end_date']:>10}  "
              f"{', '.join(t['cost_codes'])}")

    # Print PV summary
    print("\n── PV spread sample (first task) ────────────────────")
    first = SCHEDULE[0]["task_code"]
    for cc, months in pv_spread[first].items():
        print(f"  {first} / {cc}:")
        for mo, val in months.items():
            bar = "█" * int(val / 5000)
            print(f"    {mo}  ${val:>10,.2f}  {bar}")

    validate(pv_spread)


if __name__ == "__main__":
    main()
