"""
tagger.py
---------
Reads data/schedule.json and data/pv_spread.json, opens
models/office_frame.ifc, writes Pset_5D to every matched element,
and saves the result as models/office_frame_5d.ifc.

Element → Activity mapping logic
----------------------------------
Mark prefix/suffix rules (unambiguous for this model):

  FTG-*                            → A001  Substructure – Pad Footings
  COL-*-GF                         → A002  Ground Floor – RC Columns
  BM-*-GF  /  SL-*-GF             → A003  Ground Floor – RC Beams and Slab
  COL-*-L1                         → A004  Level 1 – RC Columns
  BM-*-L1  /  SL-*-L1             → A005  Level 1 – RC Beams and Slab
  COL-*-L2                         → A006  Level 2 – RC Columns
  BM-*-L2  /  SL-*-L2  /  ROOF-*  → A007  Level 2 – RC Beams and Roof Slab

Pset_5D schema written to each element
----------------------------------------
  WBS_Level1      string
  WBS_Level2      string
  WBS_Level4      string
  P6_ActivityID   string
  P6_TaskName     string
  PlannedStart    string   ISO date YYYY-MM-DD
  PlannedFinish   string   ISO date YYYY-MM-DD
  Element_Mark    string
  CostCode_1      string
  CostCode_2      string   (empty string if only one cost code)
  UOM             string
  PlannedValue    float    element's equal share of task PV ($)
  PVWeight        float    1 / elements sharing this task
  ElementsInTask  int
  Baseline_Tag    string

Run:  python tagger.py
"""

import os
import json
import time
import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.element
from collections import Counter

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SCHED_PATH = os.path.join(BASE_DIR, "data", "schedule.json")
PV_PATH    = os.path.join(BASE_DIR, "data", "pv_spread.json")
CBS_PATH   = os.path.join(BASE_DIR, "data", "cbs.json")
IN_IFC     = os.path.join(BASE_DIR, "models", "office_frame.ifc")
OUT_IFC    = os.path.join(BASE_DIR, "models", "office_frame_5d.ifc")
BASELINE   = "BL_2026-04"


# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------

def load_data():
    with open(SCHED_PATH) as f:
        schedule = json.load(f)
    with open(PV_PATH) as f:
        pv_spread = json.load(f)
    with open(CBS_PATH) as f:
        cbs_list = json.load(f)
    task_lookup = {t["task_code"]: t for t in schedule}
    uom_lookup  = {c["cost_code"]: c["uom"] for c in cbs_list}
    return task_lookup, pv_spread, uom_lookup


# ---------------------------------------------------------------------------
# 2. get_mark
# ---------------------------------------------------------------------------

def get_mark(el) -> str | None:
    psets = ifcopenshell.util.element.get_psets(el)
    for props in psets.values():
        if "Mark" in props:
            return props["Mark"]
    return el.Name if el.Name else None


# ---------------------------------------------------------------------------
# 3. get_activity  — only part that changes per project
# ---------------------------------------------------------------------------
#
# Mapping rules (plain language):
#   • FTG-*                     → A001  all footings are substructure
#   • COL-*-GF                  → A002  ground floor columns
#   • BM-*-GF or SL-*-GF       → A003  ground floor beams + slabs poured together
#   • COL-*-L1                  → A004  level 1 columns
#   • BM-*-L1 or SL-*-L1       → A005  level 1 beams + slabs
#   • COL-*-L2                  → A006  level 2 columns
#   • BM-*-L2, SL-*-L2, ROOF-* → A007  level 2 beams + all roof slabs
#   • Anything else             → None  (logged as skipped)
#
# Ambiguous elements: none — each mark encodes element type AND level.
# ---------------------------------------------------------------------------

def get_activity(el, mark: str) -> str | None:
    if mark is None:
        return None
    if mark.startswith("FTG-"):
        return "A001"
    if mark.startswith("COL-") and mark.endswith("-GF"):
        return "A002"
    if (mark.startswith("BM-") or mark.startswith("SL-")) and mark.endswith("-GF"):
        return "A003"
    if mark.startswith("COL-") and mark.endswith("-L1"):
        return "A004"
    if (mark.startswith("BM-") or mark.startswith("SL-")) and mark.endswith("-L1"):
        return "A005"
    if mark.startswith("COL-") and mark.endswith("-L2"):
        return "A006"
    if (mark.startswith("BM-") or mark.startswith("SL-")) and mark.endswith("-L2"):
        return "A007"
    if mark.startswith("ROOF-"):
        return "A007"
    return None


# ---------------------------------------------------------------------------
# 4. Fast Pset_5D writer — direct entity creation, no api.run overhead
# ---------------------------------------------------------------------------

def write_pset_5d(ifc, oh, el, props: dict):
    """
    Write Pset_5D directly without using ifcopenshell.api.run for every
    property — much faster for bulk tagging (avoids owner-history lookup
    on every single call).
    """
    pset_props = []
    for name, value in props.items():
        if isinstance(value, bool):
            nominal = ifc.create_entity("IfcBoolean", wrappedValue=value)
        elif isinstance(value, int):
            nominal = ifc.create_entity("IfcInteger", wrappedValue=value)
        elif isinstance(value, float):
            nominal = ifc.create_entity("IfcReal", wrappedValue=value)
        else:
            nominal = ifc.create_entity("IfcLabel", wrappedValue=str(value))
        pset_props.append(
            ifc.create_entity("IfcPropertySingleValue",
                Name=name, NominalValue=nominal)
        )
    pset = ifc.create_entity("IfcPropertySet",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=oh,
        Name="Pset_5D",
        HasProperties=pset_props,
    )
    ifc.create_entity("IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=oh,
        RelatedObjects=[el],
        RelatingPropertyDefinition=pset,
    )
    return pset


# ---------------------------------------------------------------------------
# 5. Main tagger — follows the mandatory tagger pattern
# ---------------------------------------------------------------------------

def tag_ifc():
    t_start = time.time()
    task_lookup, pv_spread, uom_lookup = load_data()

    ifc = ifcopenshell.open(IN_IFC)
    print(f"Opened: {IN_IFC}")
    print(f"Total IfcElement instances: {len(ifc.by_type('IfcElement'))}")

    # Grab the owner history from the file (created by generate_ifc.py)
    oh = ifc.by_type("IfcOwnerHistory")[0] if ifc.by_type("IfcOwnerHistory") else None

    # -- Build element map ------------------------------------------------
    element_map        = []
    skipped_no_mark    = []
    skipped_no_task    = []

    for el in ifc.by_type("IfcElement"):
        mark   = get_mark(el)
        act_id = get_activity(el, mark)
        if mark is None:
            skipped_no_mark.append(el.GlobalId)
        elif act_id is None:
            skipped_no_task.append(mark)
        else:
            element_map.append((el, mark, act_id))

    # -- Count elements per task (equal PV split) -------------------------
    task_count = Counter(act_id for _, _, act_id in element_map)

    # -- Write Pset_5D ----------------------------------------------------
    tagged = 0
    for el, mark, act_id in element_map:
        task      = task_lookup[act_id]
        p_codes   = task["cost_codes"]
        pv_weight = 1.0 / task_count[act_id]

        # Total PV for this task across all its cost codes
        task_pv = sum(
            sum(pv_spread[act_id][cc].values())
            for cc in p_codes
            if cc in pv_spread.get(act_id, {})
        )

        uom = uom_lookup.get(p_codes[0], "m³") if p_codes else "m³"

        props = {
            "WBS_Level1":     "CONSTRUCTION",
            "WBS_Level2":     task["wbs_level2"],
            "WBS_Level4":     task["wbs_level4"],
            "P6_ActivityID":  act_id,
            "P6_TaskName":    task["task_name"],
            "PlannedStart":   task["start_date"],
            "PlannedFinish":  task["end_date"],
            "Element_Mark":   mark,
            "CostCode_1":     p_codes[0] if p_codes else "",
            "CostCode_2":     p_codes[1] if len(p_codes) > 1 else "",
            "UOM":            uom,
            "PlannedValue":   round(task_pv * pv_weight, 2),
            "PVWeight":       round(pv_weight, 6),
            "ElementsInTask": task_count[act_id],
            "Baseline_Tag":   BASELINE,
        }

        write_pset_5d(ifc, oh, el, props)
        tagged += 1

    # -- Save -------------------------------------------------------------
    ifc.write(OUT_IFC)
    elapsed = time.time() - t_start

    # -- Report -----------------------------------------------------------
    total_els = len(ifc.by_type("IfcElement"))
    skipped   = len(skipped_no_mark) + len(skipped_no_task)

    print(f"\n── Tagger summary ───────────────────────────────────")
    print(f"  Total elements found  : {total_els}")
    print(f"  Elements tagged       : {tagged}")
    print(f"  Skipped (no mark)     : {len(skipped_no_mark)}")
    print(f"  Skipped (no task map) : {len(skipped_no_task)}")
    if skipped_no_task:
        print(f"  Unmapped marks        : {skipped_no_task[:10]}")
    print(f"  Time elapsed          : {elapsed:.1f}s")
    print()

    print(f"── Per-task breakdown ───────────────────────────────")
    print(f"  {'Task':<6} {'Name':<42} {'#El':>4} {'PV/El':>12}  WBS_Level2")
    print(f"  {'─'*6} {'─'*42} {'─'*4} {'─'*12}  {'─'*15}")
    for act_id in sorted(task_lookup):
        task   = task_lookup[act_id]
        n_el   = task_count.get(act_id, 0)
        task_pv = sum(
            sum(pv_spread[act_id][cc].values())
            for cc in task["cost_codes"]
            if cc in pv_spread.get(act_id, {})
        )
        pv_per = task_pv / n_el if n_el else 0
        print(f"  {act_id:<6} {task['task_name']:<42} {n_el:>4} "
              f"${pv_per:>11,.2f}  {task['wbs_level2']}")

    print()
    sz = os.path.getsize(OUT_IFC) / 1_000_000
    print(f"── Output ───────────────────────────────────────────")
    print(f"  {OUT_IFC}")
    print(f"  File size: {sz:.2f} MB")
    return OUT_IFC


# ---------------------------------------------------------------------------
# 6. Spot-check verification
# ---------------------------------------------------------------------------

def verify(out_ifc_path: str):
    ifc     = ifcopenshell.open(out_ifc_path)
    els     = ifc.by_type("IfcElement")
    tagged  = sum(1 for el in els
                  if "Pset_5D" in ifcopenshell.util.element.get_psets(el))

    print(f"\n── Verification ─────────────────────────────────────")
    print(f"  Elements in file      : {len(els)}")
    print(f"  Elements with Pset_5D : {tagged}")

    expected_keys = {
        "WBS_Level1", "WBS_Level2", "WBS_Level4",
        "P6_ActivityID", "P6_TaskName",
        "PlannedStart", "PlannedFinish",
        "Element_Mark", "CostCode_1", "CostCode_2",
        "UOM", "PlannedValue", "PVWeight", "ElementsInTask", "Baseline_Tag",
    }

    # Sample one of each type
    for ifc_type in ["IfcFooting", "IfcColumn", "IfcBeam", "IfcSlab"]:
        el    = ifc.by_type(ifc_type)[0]
        psets = ifcopenshell.util.element.get_psets(el)
        p5d   = psets.get("Pset_5D", {})
        missing = expected_keys - set(p5d.keys())
        status  = "✓" if not missing else f"MISSING: {missing}"
        act_id  = p5d.get("P6_ActivityID", "—")
        pv      = p5d.get("PlannedValue", 0)
        print(f"  {ifc_type:<14} {el.Name:<25}  task={act_id}  "
              f"PV=${pv:>10,.2f}  {status}")

    # PV total sanity check
    total_pv = sum(
        p5d.get("PlannedValue", 0)
        for el in els
        for p5d in [ifcopenshell.util.element.get_psets(el).get("Pset_5D", {})]
        if p5d
    )
    print(f"\n  Sum of all element PVs: ${total_pv:>14,.2f}")
    print(f"  Expected project total: $  1,800,000.00")
    diff = abs(total_pv - 1_800_000.0)
    print(f"  Difference            : ${diff:>14,.2f}  "
          f"{'✓' if diff < 1.0 else 'CHECK ROUNDING'}")
    print()


if __name__ == "__main__":
    out_path = tag_ifc()
    verify(out_path)
