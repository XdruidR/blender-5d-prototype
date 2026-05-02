"""
inspect_ifc.py
--------------
Inspects an IFC file and reports:
  - All IfcElement types and counts
  - Sample element names/marks from first 20 of each type
  - Identifies the most useful identifier field

Usage:
    python inspect_ifc.py [path/to/file.ifc]
    python inspect_ifc.py               # defaults to models/office_frame.ifc
"""

import os
import sys
import ifcopenshell
import ifcopenshell.util.element
from collections import defaultdict, Counter

DEFAULT_IFC = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "models", "office_frame.ifc"
)

IFC_PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IFC


def get_mark(el):
    """Try to extract a useful identifier from an element."""
    # 1. Check Pset_ElementMark.Mark
    psets = ifcopenshell.util.element.get_psets(el)
    for pset_name, props in psets.items():
        if "Mark" in props:
            return props["Mark"]
    # 2. Tag attribute (IFC2X3 ObjectTypeOf / Tag)
    if hasattr(el, "Tag") and el.Tag:
        return el.Tag
    # 3. Name attribute
    if el.Name:
        return el.Name
    # 4. Fall back to GlobalId
    return el.GlobalId


def main():
    print(f"\nInspecting: {IFC_PATH}\n")
    if not os.path.exists(IFC_PATH):
        print(f"ERROR: file not found: {IFC_PATH}")
        sys.exit(1)

    ifc = ifcopenshell.open(IFC_PATH)

    # -----------------------------------------------------------------------
    # 1. Schema + project info
    # -----------------------------------------------------------------------
    print(f"Schema       : {ifc.schema}")
    projects = ifc.by_type("IfcProject")
    if projects:
        print(f"Project name : {projects[0].Name}")

    # -----------------------------------------------------------------------
    # 2. Count all IfcElement subtypes
    # -----------------------------------------------------------------------
    all_elements = ifc.by_type("IfcElement")
    type_counts  = Counter(el.is_a() for el in all_elements)

    print(f"\n{'─'*50}")
    print(f"{'Element Type':<25} {'Count':>6}")
    print(f"{'─'*50}")
    for etype, count in sorted(type_counts.items()):
        print(f"  {etype:<23} {count:>6}")
    print(f"{'─'*50}")
    print(f"  {'TOTAL':<23} {len(all_elements):>6}")

    # -----------------------------------------------------------------------
    # 3. Sample names per type (first 20)
    # -----------------------------------------------------------------------
    type_groups: dict[str, list] = defaultdict(list)
    for el in all_elements:
        type_groups[el.is_a()].append(el)

    print(f"\n{'─'*70}")
    print("Sample element identifiers (first 20 per type)")
    print(f"{'─'*70}")
    for etype, elements in sorted(type_groups.items()):
        samples = [get_mark(el) for el in elements[:20]]
        print(f"\n  {etype} ({len(elements)} total):")
        for i, s in enumerate(samples, 1):
            print(f"    [{i:>2}] {s}")
        if len(elements) > 20:
            print(f"    ... and {len(elements) - 20} more")

    # -----------------------------------------------------------------------
    # 4. Identifier field analysis
    # -----------------------------------------------------------------------
    print(f"\n{'─'*70}")
    print("Identifier field analysis")
    print(f"{'─'*70}")

    fields = {"Name": 0, "Tag": 0, "Pset_ElementMark.Mark": 0, "GlobalId_only": 0}
    for el in all_elements:
        psets = ifcopenshell.util.element.get_psets(el)
        has_mark = any("Mark" in p for p in psets.values())
        if has_mark:
            fields["Pset_ElementMark.Mark"] += 1
        elif hasattr(el, "Tag") and el.Tag:
            fields["Tag"] += 1
        elif el.Name:
            fields["Name"] += 1
        else:
            fields["GlobalId_only"] += 1

    for field, count in fields.items():
        pct = 100 * count / len(all_elements) if all_elements else 0
        print(f"  {field:<30} {count:>4} elements ({pct:.0f}%)")

    # -----------------------------------------------------------------------
    # 5. Property set inventory
    # -----------------------------------------------------------------------
    print(f"\n{'─'*70}")
    print("Property sets found")
    print(f"{'─'*70}")
    pset_names: Counter = Counter()
    for el in all_elements:
        for pset_name in ifcopenshell.util.element.get_psets(el):
            pset_names[pset_name] += 1
    for pname, cnt in sorted(pset_names.items()):
        print(f"  {pname:<35} on {cnt} elements")

    # -----------------------------------------------------------------------
    # 6. Recommendation
    # -----------------------------------------------------------------------
    print(f"\n{'─'*70}")
    best = max(fields, key=fields.get)
    print(f"RECOMMENDATION: Use '{best}' as primary identifier for tagger.py")
    if "Pset_ElementMark.Mark" in best:
        print("  → Read with: ifcopenshell.util.element.get_psets(el)")
        print("     psets = get_psets(el)")
        print("     mark  = next((p['Mark'] for p in psets.values() if 'Mark' in p), None)")
    elif best == "Name":
        print("  → Read with: el.Name")
    print(f"{'─'*70}\n")


if __name__ == "__main__":
    main()
