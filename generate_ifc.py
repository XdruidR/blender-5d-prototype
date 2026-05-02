"""
generate_ifc.py
---------------
Generates a synthetic IFC2X3 model of a 3-storey reinforced-concrete office
building structural frame on a 4x4 column grid.

Element naming convention
--------------------------
  IfcFooting  : FTG-{row}{col}               e.g. FTG-A1          (16 elements)
  IfcColumn   : COL-{row}{col}-{level}       e.g. COL-A1-GF       (48 elements)
  IfcBeam     : BM-H-{row}{c1}{c2}-{level}  e.g. BM-H-A12-GF     (36 horizontal)
                BM-V-{col}{r1}{r2}-{level}  e.g. BM-V-1AB-GF     (36 vertical)
  IfcSlab     : SL-{bay}-{level}             e.g. SL-A1B2-GF      (27 floor slabs)
                ROOF-{bay}                   e.g. ROOF-A1B2        ( 9 roof slabs)

Total: 16 + 48 + 72 + 36 = 172 elements

Grid (plan view):
  Rows A-D (Y axis), Cols 1-4 (X axis), 6 m spacing
  3 storeys: GF (0 m), L1 (3.5 m), L2 (7.0 m)
  Roof slab at 10.5 m

Run:  python generate_ifc.py
Output: models/office_frame.ifc
"""

import os
import numpy as np
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.representation
from ifcopenshell.util.shape_builder import ShapeBuilder
from collections import Counter

# ---------------------------------------------------------------------------
# Grid config
# ---------------------------------------------------------------------------
ROWS      = ["A", "B", "C", "D"]
COLS      = [1, 2, 3, 4]
LEVELS    = ["GF", "L1", "L2"]
SPACING   = 6.0    # m between grid lines (X and Y)
STOREY_H  = 3.5    # m per storey
COL_W     = 0.40   # m column section width
BEAM_W    = 0.30   # m beam section width
BEAM_D    = 0.50   # m beam section depth
SLAB_T    = 0.20   # m slab thickness
FTG_SIZE  = 1.20   # m pad footing plan size
FTG_DEPTH = 0.60   # m pad footing depth

OUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "models", "office_frame.ifc"
)


# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------

def col_xy(row: str, col: int):
    """Return (x, y) world coordinates for a grid intersection."""
    return float((col - 1) * SPACING), float(ROWS.index(row) * SPACING)


def level_z(level: str) -> float:
    return float(LEVELS.index(level) * STOREY_H)


def placement_matrix(x=0.0, y=0.0, z=0.0) -> np.ndarray:
    m = np.eye(4)
    m[0, 3] = x
    m[1, 3] = y
    m[2, 3] = z
    return m


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build():
    ifc = ifcopenshell.api.run("project.create_file", version="IFC2X3")

    # -- Owner history entities (auto-discovered by ifcopenshell.api) ------
    person = ifc.create_entity("IfcPerson", FamilyName="Rodriguez", GivenName="Andres")
    org    = ifc.create_entity("IfcOrganization", Name="5D-Demo")
    ifc.create_entity("IfcPersonAndOrganization", ThePerson=person, TheOrganization=org)
    app_org = ifc.create_entity("IfcOrganization", Name="IfcOpenShell")
    ifc.create_entity(
        "IfcApplication",
        ApplicationDeveloper=app_org,
        Version="0.8.5",
        ApplicationFullName="5D Demo Generator",
        ApplicationIdentifier="5DDEMO",
    )

    # -- Project + geometry context ----------------------------------------
    project   = ifcopenshell.api.run("root.create_entity", ifc,
                    ifc_class="IfcProject", name="Office Frame 5D Demo")
    model_ctx = ifcopenshell.api.run("context.add_context", ifc, context_type="Model")
    body_ctx  = ifcopenshell.api.run("context.add_context", ifc,
                    context_type="Model", context_identifier="Body",
                    target_view="MODEL_VIEW", parent=model_ctx)

    builder = ShapeBuilder(ifc)
    body    = body_ctx

    def rect_profile(xdim: float, ydim: float):
        """Create IfcRectangleProfileDef — Bonsai handles this without errors."""
        return ifc.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA",
            XDim=xdim,
            YDim=ydim,
        )

    # -- Spatial hierarchy -------------------------------------------------
    site    = ifcopenshell.api.run("root.create_entity", ifc,
                  ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.run("root.create_entity", ifc,
                  ifc_class="IfcBuilding", name="Office Building")
    ifcopenshell.api.run("aggregate.assign_object", ifc,
        products=[site], relating_object=project)
    ifcopenshell.api.run("aggregate.assign_object", ifc,
        products=[building], relating_object=site)

    # Storey definitions: (label, elevation_m)
    storey_defs = [
        ("SUBSTRUCTURE", -FTG_DEPTH),
        ("GF",  0.0),
        ("L1",  STOREY_H),
        ("L2",  2 * STOREY_H),
    ]
    storey_map = {}
    for label, elev in storey_defs:
        s = ifcopenshell.api.run("root.create_entity", ifc,
                ifc_class="IfcBuildingStorey", name=label)
        s.Elevation = elev
        storey_map[label] = s

    ifcopenshell.api.run("aggregate.assign_object", ifc,
        products=list(storey_map.values()), relating_object=building)

    storey_elems: dict[str, list] = {k: [] for k in storey_map}

    # -- Element factory helpers -------------------------------------------

    def place(el, x=0.0, y=0.0, z=0.0):
        ifcopenshell.api.run("geometry.edit_object_placement", ifc,
            product=el, matrix=placement_matrix(x, y, z))

    def add_rep(el, solid):
        rep = builder.get_representation(body, [solid])
        ifcopenshell.api.run("geometry.assign_representation", ifc,
            product=el, representation=rep)

    def add_pset(el, props: dict, pset_name="Pset_ElementMark"):
        pset = ifcopenshell.api.run("pset.add_pset", ifc,
                   product=el, name=pset_name)
        ifcopenshell.api.run("pset.edit_pset", ifc,
            pset=pset, properties=props)

    def contain(el, storey_key: str):
        ifcopenshell.api.run("spatial.assign_container", ifc,
            products=[el], relating_structure=storey_map[storey_key])
        storey_elems[storey_key].append(el)

    # =====================================================================
    # FOOTINGS  (16 elements)
    # =====================================================================
    ftg_prof  = rect_profile(FTG_SIZE, FTG_SIZE)
    for row in ROWS:
        for col in COLS:
            mark = f"FTG-{row}{col}"
            x, y = col_xy(row, col)
            el   = ifcopenshell.api.run("root.create_entity", ifc,
                       ifc_class="IfcFooting", name=mark,
                       predefined_type="PAD_FOOTING")
            place(el, x=x, y=y, z=-FTG_DEPTH)
            add_rep(el, builder.extrude(ftg_prof, magnitude=FTG_DEPTH))
            add_pset(el, {
                "Mark":        mark,
                "ElementType": "Footing",
                "GridRef":     f"{row}{col}",
            })
            contain(el, "SUBSTRUCTURE")

    # =====================================================================
    # COLUMNS  (48 elements — 16 per level × 3 levels)
    # =====================================================================
    col_prof = rect_profile(COL_W, COL_W)
    for level in LEVELS:
        z = level_z(level)
        for row in ROWS:
            for col in COLS:
                mark = f"COL-{row}{col}-{level}"
                x, y = col_xy(row, col)
                el   = ifcopenshell.api.run("root.create_entity", ifc,
                           ifc_class="IfcColumn", name=mark)
                place(el, x=x, y=y, z=z)
                add_rep(el, builder.extrude(col_prof, magnitude=STOREY_H))
                add_pset(el, {
                    "Mark":        mark,
                    "ElementType": "Column",
                    "GridRef":     f"{row}{col}",
                    "Level":       level,
                })
                contain(el, level)

    # =====================================================================
    # BEAMS  (72 elements — 24 per level × 3 levels)
    # Each level: 12 horizontal (along X) + 12 vertical (along Y)
    # =====================================================================
    # Profile in XY plane; object placement rotates beam into span direction.
    bm_prof_z = rect_profile(BEAM_W, BEAM_D)
    for level in LEVELS:
        z_bm = level_z(level) + STOREY_H - BEAM_D  # beam soffit at slab level

        def beam_matrix_x(x, y, z):
            """Object placement: local Z → world +X (beam spans X)."""
            # Col 0 (local X) = world Y, Col 1 (local Y) = world Z, Col 2 (local Z) = world X
            m = np.array([
                [0., 0., 1., x],
                [1., 0., 0., y],
                [0., 1., 0., z],
                [0., 0., 0., 1.],
            ])
            return m

        def beam_matrix_y(x, y, z):
            """Object placement: local Z → world +Y (beam spans Y)."""
            # Col 0 (local X) = world X, Col 1 (local Y) = world Z, Col 2 (local Z) = world Y
            m = np.array([
                [1., 0., 0., x],
                [0., 0., 1., y],
                [0., 1., 0., z],
                [0., 0., 0., 1.],
            ])
            return m

        # --- Horizontal beams (span along X, one per row-span) ---
        for row in ROWS:
            y = ROWS.index(row) * SPACING
            for c1, c2 in zip(COLS[:-1], COLS[1:]):
                mark = f"BM-H-{row}{c1}{c2}-{level}"
                x    = (c1 - 1) * SPACING
                el   = ifcopenshell.api.run("root.create_entity", ifc,
                           ifc_class="IfcBeam", name=mark)
                ifcopenshell.api.run("geometry.edit_object_placement", ifc,
                    product=el, matrix=beam_matrix_x(x, y, z_bm))
                add_rep(el, builder.extrude(bm_prof_z, magnitude=SPACING))
                add_pset(el, {
                    "Mark":        mark,
                    "ElementType": "Beam",
                    "Direction":   "H",
                    "Level":       level,
                })
                contain(el, level)

        # --- Vertical beams (span along Y, one per col-span) ---
        for col in COLS:
            x = (col - 1) * SPACING
            for r1, r2 in zip(ROWS[:-1], ROWS[1:]):
                mark = f"BM-V-{col}{r1}{r2}-{level}"
                y    = ROWS.index(r1) * SPACING
                el   = ifcopenshell.api.run("root.create_entity", ifc,
                           ifc_class="IfcBeam", name=mark)
                ifcopenshell.api.run("geometry.edit_object_placement", ifc,
                    product=el, matrix=beam_matrix_y(x, y, z_bm))
                add_rep(el, builder.extrude(bm_prof_z, magnitude=SPACING))
                add_pset(el, {
                    "Mark":        mark,
                    "ElementType": "Beam",
                    "Direction":   "V",
                    "Level":       level,
                })
                contain(el, level)

    # =====================================================================
    # SLABS  (27 floor + 9 roof = 36 elements)
    # =====================================================================
    slab_prof = rect_profile(SPACING, SPACING)
    for level in LEVELS + ["ROOF"]:
        if level == "ROOF":
            z_sl       = len(LEVELS) * STOREY_H
            storey_key = "L2"
        else:
            z_sl       = level_z(level) + STOREY_H
            storey_key = level

        for r1, r2 in zip(ROWS[:-1], ROWS[1:]):
            for c1, c2 in zip(COLS[:-1], COLS[1:]):
                bay  = f"{r1}{c1}{r2}{c2}"
                mark = f"ROOF-{bay}" if level == "ROOF" else f"SL-{bay}-{level}"
                x, y = col_xy(r1, c1)
                el   = ifcopenshell.api.run("root.create_entity", ifc,
                           ifc_class="IfcSlab", name=mark,
                           predefined_type="FLOOR")
                place(el, x=x, y=y, z=z_sl)
                add_rep(el, builder.extrude(slab_prof, magnitude=SLAB_T))
                add_pset(el, {
                    "Mark":        mark,
                    "ElementType": "Roof Slab" if level == "ROOF" else "Floor Slab",
                    "Bay":         bay,
                    "Level":       level,
                })
                contain(el, storey_key)

    # =====================================================================
    # Write
    # =====================================================================
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    ifc.write(OUT_PATH)

    all_els     = [e for v in storey_elems.values() for e in v]
    type_counts = Counter(el.is_a() for el in all_els)
    print(f"Written: {OUT_PATH}")
    print(f"Total elements: {len(all_els)}")
    for t, n in sorted(type_counts.items()):
        print(f"  {t:20s}: {n}")
    return OUT_PATH


if __name__ == "__main__":
    build()
