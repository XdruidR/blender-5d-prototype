# 5D BIM Demo Dataset — Office Frame

A self-contained dataset for demonstrating **5D BIM** (geometry + schedule + cost + time) in **Blender with Bonsai / IfcOpenShell**. Every structural element in the IFC carries a `Pset_5D` property set linking it to a WBS activity, cost code, planned value, and schedule dates. Monthly PV data lives in `data/pv_spread.json` for use by a Blender N-panel time slider.

---

## Project overview

| Property | Value |
|----------|-------|
| Building type | 3-storey RC office frame |
| Grid | 4 × 4 columns, 6 m spacing |
| Storey height | 3.5 m |
| IFC schema | IFC2X3 |
| Total elements | 172 |
| Schedule | 7 activities, June 2026 – April 2027 |
| Total planned value | $1,800,000 |

---

## Folder structure

```
blender-5d-prototype/
├── README.md                 ← this file
├── generate_ifc.py           ← creates models/office_frame.ifc from scratch
├── generate_synthetic.py     ← creates data/schedule.json, cbs.json, pv_spread.json
├── inspect_ifc.py            ← reports element types, marks, pset inventory
├── tagger.py                 ← writes Pset_5D into every IFC element
├── models/
│   ├── office_frame.ifc      ← untagged model (source)
│   └── office_frame_5d.ifc   ← tagged model (load this in Blender)
└── data/
    ├── schedule.json         ← 7-activity WBS schedule
    ├── cbs.json              ← 5 cost codes
    └── pv_spread.json        ← monthly PV per task per cost code
```

---

## Quick start

### 1 — Load the tagged IFC in Blender

1. Open Blender and activate the **Bonsai** add-on.
2. In the Bonsai panel → **Project** → **Load Project**.
3. Select `models/office_frame_5d.ifc`.
4. Once loaded, select any structural element and open its **Properties** panel.
5. Under **Custom Properties** → **Pset_5D** you will see all schedule and cost fields.

### 2 — Inspect element properties in Blender's Python console

```python
import bpy, blenderbim.tool as tool, ifcopenshell.util.element as ue

obj  = bpy.context.active_object
el   = tool.Ifc.get_entity(obj)
psets = ue.get_psets(el)
p5d  = psets["Pset_5D"]

print(p5d["P6_ActivityID"])   # e.g. "A003"
print(p5d["PlannedStart"])    # e.g. "2026-09-01"
print(p5d["PlannedValue"])    # e.g. 7777.78
```

### 3 — Re-run the full pipeline from scratch

```bash
# In this folder:
pip install ifcopenshell numpy python-dateutil

python generate_ifc.py          # → models/office_frame.ifc
python generate_synthetic.py    # → data/*.json
python tagger.py                # → models/office_frame_5d.ifc
```

---

## Element naming convention

| Prefix | Type | Example | Notes |
|--------|------|---------|-------|
| `FTG-{row}{col}` | IfcFooting | `FTG-A1` | 16 pad footings |
| `COL-{row}{col}-{level}` | IfcColumn | `COL-B3-L1` | 48 columns (3 levels) |
| `BM-H-{row}{c1}{c2}-{level}` | IfcBeam | `BM-H-A12-GF` | 36 horizontal beams |
| `BM-V-{col}{r1}{r2}-{level}` | IfcBeam | `BM-V-2AB-L1` | 36 vertical beams |
| `SL-{bay}-{level}` | IfcSlab | `SL-B1C2-GF` | 27 floor slabs |
| `ROOF-{bay}` | IfcSlab | `ROOF-A1B2` | 9 roof slabs |

Levels: `GF` (ground floor, 0 m) · `L1` (3.5 m) · `L2` (7.0 m) · `ROOF` (10.5 m)

Grid rows: A → D (Y axis) · Grid cols: 1 → 4 (X axis) · Spacing: 6 m

---

## Schedule (WBS)

```
CONSTRUCTION
├── SUBSTRUCTURE
│   └── PKG-FOOTINGS       A001  2026-06-01 → 2026-07-15   FTG-*
├── GROUND-FLOOR
│   ├── PKG-COLUMNS-GF     A002  2026-07-16 → 2026-08-31   COL-*-GF
│   └── PKG-FRAME-GF       A003  2026-09-01 → 2026-10-31   BM-*-GF, SL-*-GF
├── LEVEL-1
│   ├── PKG-COLUMNS-L1     A004  2026-11-01 → 2026-11-30   COL-*-L1
│   └── PKG-FRAME-L1       A005  2026-12-01 → 2027-01-31   BM-*-L1, SL-*-L1
└── LEVEL-2
    ├── PKG-COLUMNS-L2     A006  2027-02-01 → 2027-02-28   COL-*-L2
    └── PKG-FRAME-L2       A007  2027-03-01 → 2027-04-30   BM-*-L2, SL-*-L2, ROOF-*
```

---

## Cost Breakdown Structure (CBS)

| Code | Description | UOM | Total |
|------|-------------|-----|------:|
| CBS-001 | Concrete Substructure | m³ | $280,000 |
| CBS-002 | RC Columns | m³ | $420,000 |
| CBS-003 | RC Beams | m³ | $360,000 |
| CBS-004 | RC Slabs | m² | $540,000 |
| CBS-005 | Formwork & Shoring | m² | $200,000 |
| | **Total** | | **$1,800,000** |

Each activity's `PlannedValue` = sum of its CBS shares divided equally across the elements in that task. Monthly cash flow uses a bell-curve distribution (peak mid-activity).

---

## Pset_5D schema

Every `IfcElement` in `office_frame_5d.ifc` carries this property set:

| Property | Type | Example |
|----------|------|---------|
| `WBS_Level1` | string | `CONSTRUCTION` |
| `WBS_Level2` | string | `GROUND-FLOOR` |
| `WBS_Level4` | string | `PKG-FRAME-GF` |
| `P6_ActivityID` | string | `A003` |
| `P6_TaskName` | string | `Ground Floor – RC Beams and Slab` |
| `PlannedStart` | string | `2026-09-01` |
| `PlannedFinish` | string | `2026-10-31` |
| `Element_Mark` | string | `BM-H-A12-GF` |
| `CostCode_1` | string | `CBS-003` |
| `CostCode_2` | string | `CBS-004` |
| `UOM` | string | `m³` |
| `PlannedValue` | float | `7777.78` |
| `PVWeight` | float | `0.041667` |
| `ElementsInTask` | int | `24` |
| `Baseline_Tag` | string | `BL_2026-04` |

> **Note:** WBS uses Level1 / Level2 / Level4 — Level3 is intentionally absent to match the existing panel schema.

---

## Using pv_spread.json with a time slider

`data/pv_spread.json` is structured as:

```json
{
  "A003": {
    "CBS-003": { "2026-09": 43200.00, "2026-10": 100800.00 },
    "CBS-004": { "2026-09": 64800.00, "2026-10": 151200.00 }
  }
}
```

For a Blender N-panel slider at date `T`:

```python
import json
from datetime import date

pv_spread   = json.load(open("data/pv_spread.json"))
schedule    = json.load(open("data/schedule.json"))
task_lookup = {t["task_code"]: t for t in schedule}

def cumulative_pv_at(slider_date: date) -> float:
    """Sum all monthly PV buckets with YYYY-MM <= slider_date."""
    d_str = slider_date.strftime("%Y-%m")
    total = 0.0
    for act_id, cc_dict in pv_spread.items():
        for cc, months in cc_dict.items():
            total += sum(v for mo, v in months.items() if mo <= d_str)
    return total
```

---

## Dependencies

| Package | Version tested | Notes |
|---------|---------------|-------|
| `ifcopenshell` | 0.8.5 | Bundled with Bonsai; install standalone via pip for scripts |
| `numpy` | any | Bell-curve spread in `generate_synthetic.py` |
| `python-dateutil` | any | `relativedelta` for monthly iteration |

```bash
pip install ifcopenshell numpy python-dateutil
```

When running inside Blender's Python environment (Bonsai installed), `ifcopenshell` is already available — no extra install needed.

---

## Data integrity

| Check | Result |
|-------|--------|
| Elements tagged | 172 / 172 |
| Pset_5D keys complete | 15 / 15 on every element |
| CBS totals balanced | All 5 codes exact match |
| Sum of element PVs | $1,799,999.93 (rounding drift $0.07) |

---

*Generated 2026-04-27 — Baseline: BL_2026-04*
