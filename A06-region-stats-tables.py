"""Write Pandoc-ready markdown tables of reef counts and areas for the report.

Run A05-reef-distribution.py first. This script reads the A05 region summary
CSV and cached reef pieces, and the L3 output dataset, and writes
data/{version}/out/stats/NW-Aus-Features_Report-tables_{version}.md.
"""

import importlib.util
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("a05", ROOT / "A05-reef-distribution.py")
a05 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a05)

VERSION = a05.VERSION
L3_DATASET = (a05.DATA_DIR / "out" / "full-classes" /
              f"AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_{VERSION}.shp")
OUTPUT_MD = a05.OUTPUT_CSV.parent / f"NW-Aus-Features_Report-tables_{VERSION}.md"
SETTINGS = {setting["slug"]: setting for setting in a05.REGIONALISATIONS}
ANALYSIS, IMCRA, CAPAD = SETTINGS["analysis-region"], SETTINGS["imcra"], SETTINGS["capad"]
NO_MATCH_LABELS = {
    ANALYSIS["name"]: "Outside all analysis regions",
    IMCRA["name"]: "Outside IMCRA meso-scale bioregions",
    CAPAD["name"]: "Outside protected areas and near regions",
}
# Table numbers are provisional; they are renumbered when pasted into Word.
TABLE_NUMBERS = {"l3": "X", "summary": "1", "protected": "2", "analysis": "3",
                 "imcra": "4", "capad": "5"}


def count(value):
    return f"{int(value):,}"


def area(value):
    value = float(value)
    return "<0.01" if 0 < value < 0.005 else f"{value:,.2f}"


def pipe_table(header, rows, bold_last=False, text_columns=1):
    """Pandoc pipe table with text columns left aligned and numbers right aligned."""
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join([":---"] * text_columns +
                             ["---:"] * (len(header) - text_columns)) + "|"]
    for index, row in enumerate(rows):
        if bold_last and index == len(rows) - 1:
            row = [f"**{cell}**" if cell else cell for cell in row]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def caption(key, text):
    return f"**Table {TABLE_NUMBERS[key]}.** {text}"


def l3_table():
    """Stock take of every mapped feature by L3 classification."""
    features = gpd.read_file(L3_DATASET, ignore_geometry=True)
    grouped = (features.groupby(["RB_Type_L2", "RB_Type_L3"])
               .agg(n=("RB_Type_L3", "size"), km2=("Area_km2", "sum")).reset_index())
    l2_totals = grouped.groupby("RB_Type_L2")["n"].sum()
    grouped["l2_n"] = grouped["RB_Type_L2"].map(l2_totals)
    grouped = grouped.sort_values(["l2_n", "RB_Type_L2", "n"], ascending=[False, True, False])
    rows = [[row.RB_Type_L2, row.RB_Type_L3, count(row.n), area(row.km2)]
            for row in grouped.itertuples()]
    rows.append(["Total", "", count(grouped["n"].sum()), area(grouped["km2"].sum())])
    return "\n\n".join([
        caption("l3", f"Number of mapped features and their area by Reef Boundary Type "
                f"(RB_Type_L3) in version {VERSION} of the dataset. Features are the "
                "individual polygons in the dataset, not countable reefs."),
        pipe_table(["RB_Type_L2", "RB_Type_L3", "Features", "Area (km²)"], rows, True, 2)])


def summary_table(reefs):
    """Countable reef totals that every regional table reconciles to."""
    rows = []
    for reef_type, _ in a05.REEF_TYPES:
        typed = reefs[reefs["RB_Type_L2"] == reef_type]
        rows.append([reef_type, count(len(typed)), area(typed.geometry.area.sum() / 1e6)])
    rows.append(["Total", count(len(reefs)), area(reefs.geometry.area.sum() / 1e6)])
    return "\n\n".join([
        caption("summary", f"Countable coral and rocky reefs in version {VERSION} of the "
                "dataset."),
        pipe_table(["Reef type", "Countable reefs", "Area (km²)"], rows, True)])


def australian_reefs(reefs):
    """CountFIDs whose Analysis-region count is assigned to an Australian region."""
    regions = gpd.read_file(ANALYSIS["source"], ignore_geometry=True)
    country = dict(zip(regions[ANALYSIS["field"]], regions["Country"]))
    pieces = a05.read_cached(a05.reef_cache_path(ANALYSIS))
    assigned = pieces[(pieces["Assigned"] == 1) & (pieces["Sliver"] == 0)]
    keep = assigned.loc[assigned["NAME"].map(country).eq("Australia"), "CountFID"]
    return reefs[reefs["CountFID"].isin(set(keep))]


def protected_table(reefs):
    """Countable reefs in Australian waters inside, near and outside protected areas."""
    au_reefs = australian_reefs(reefs)
    pieces = a05.read_cached(a05.reef_cache_path(CAPAD))
    pieces = pieces[(pieces["Sliver"] == 0) & pieces["CountFID"].isin(set(au_reefs["CountFID"]))]
    inside = (pieces["Near"] == 0) & pieces["NAME"].ne(a05.NO_MATCH)
    near = pieces["Near"] == 1
    # A protected piece holding the count is the reef's largest piece, so this is single assignment.
    counted_inside = set(pieces.loc[inside & (pieces["Assigned"] == 1), "CountFID"])
    counted_near = set(pieces.loc[near & (pieces["Assigned"] == 1), "CountFID"]) - counted_inside

    rows, figures = [], {}
    for reef_type, _ in a05.REEF_TYPES:
        typed_reefs = au_reefs[au_reefs["RB_Type_L2"] == reef_type]
        typed = pieces[pieces["RB_Type_L2"] == reef_type]
        typed_inside = typed[inside.loc[typed.index]]
        inside_km2 = sum(unary_union(list(group)).area
                         for _, group in typed_inside.geometry.groupby(typed_inside["CountFID"]))
        near_km2 = typed.loc[near.loc[typed.index]].geometry.area.sum()
        outside_km2 = typed.loc[typed["NAME"].eq(a05.NO_MATCH)].geometry.area.sum()
        ids = set(typed_reefs["CountFID"])
        n_inside, n_near = len(ids & counted_inside), len(ids & counted_near)
        counts = {"Inside a protected area": (n_inside, inside_km2 / 1e6),
                  "Within 300 m of a protected area": (n_near, near_km2 / 1e6),
                  "Not in or near a protected area":
                      (len(ids) - n_inside - n_near, outside_km2 / 1e6)}
        total_n, total_km2 = len(ids), sum(value[1] for value in counts.values())
        for category, (n, km2) in counts.items():
            rows.append([reef_type, category, count(n), f"{100 * n / total_n:.1f}",
                         area(km2), f"{100 * km2 / total_km2:.1f}"])
            figures[(reef_type, category)] = (n, 100 * n / total_n, km2,
                                              100 * km2 / total_km2)
        rows.append([f"**{reef_type} total**", "", f"**{count(total_n)}**", "**100.0**",
                     f"**{area(total_km2)}**", "**100.0**"])
    table = "\n\n".join([
        caption("protected", "Countable reefs in Australian waters inside, near (within "
                "300 m) and outside protected areas in CAPAD 2024 - Marine. Australian "
                "waters are all Analysis-regions except Timor East / Indonesia. Areas are "
                "the reef area falling within each category."),
        pipe_table(["Reef type", "Category", "Reefs", "% of reefs", "Area (km²)",
                    "% of area"], rows, text_columns=2)])
    return table, figures


def region_table(stats, setting, key, region_heading, text):
    """Counts, partials and areas for each occupied region of one regionalisation."""
    rows_in = stats[stats["Region_dataset"] == setting["name"]]
    if setting["near_m"]:
        # Near regions are listed only where they hold a reef's count.
        rows_in = rows_in[(rows_in["Near_region"] == "No") |
                          (rows_in["Coral_reef_count"] + rows_in["Rocky_reef_count"] > 0)]
    rows = []
    for row in rows_in.itertuples():
        label = NO_MATCH_LABELS[setting["name"]] if row.Region_name == a05.NO_MATCH else row.Label
        rows.append([label, count(row.Coral_reef_count), count(row.Coral_reef_partial_count),
                     area(row.Coral_reef_area_km2), count(row.Rocky_reef_count),
                     count(row.Rocky_reef_partial_count), area(row.Rocky_reef_area_km2)])
    if not setting["overlapping"]:
        rows.append(["Total", count(rows_in["Coral_reef_count"].sum()), "",
                     area(rows_in["Coral_reef_area_km2"].sum()),
                     count(rows_in["Rocky_reef_count"].sum()), "",
                     area(rows_in["Rocky_reef_area_km2"].sum())])
    header = [region_heading, "Coral reefs", "Coral partial", "Coral area (km²)",
              "Rocky reefs", "Rocky partial", "Rocky area (km²)"]
    return "\n\n".join([caption(key, text),
                        pipe_table(header, rows, bold_last=not setting["overlapping"])])


def main():
    reefs = a05.load_countable()
    stats = pd.read_csv(a05.OUTPUT_CSV, keep_default_na=False)
    protected, figures = protected_table(reefs)
    sections = [
        f"<!-- Generated by A06-region-stats-tables.py from dataset version {VERSION}. -->",
        "## Results section tables", l3_table(),
        "## Appendix tables", summary_table(reefs), protected,
        region_table(stats, ANALYSIS, "analysis", "Analysis-region",
                     "Countable reefs and reef area by Analysis-region. Reef counts are "
                     "assigned to a single region. Partial counts are reefs that extend "
                     "into the region but are counted elsewhere."),
        region_table(stats, IMCRA, "imcra", "IMCRA meso-scale bioregion",
                     "Countable reefs and reef area by IMCRA v4.0 meso-scale bioregion. "
                     "Partial counts are reefs that extend into the region but are counted "
                     "elsewhere."),
        region_table(stats, CAPAD, "capad", "Protected area",
                     "Countable reefs and reef area by protected area in CAPAD 2024 - "
                     "Marine. 'Near:' rows are reefs counted within 300 m outside the "
                     "protected area, listed only where they hold at least one reef count. "
                     "Reefs in overlapping protected areas can be counted in more than one "
                     "row, so this table has no total."),
    ]
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    print(f"Wrote report tables: {OUTPUT_MD}")
    for (reef_type, category), (n, n_pct, km2, km2_pct) in figures.items():
        print(f"{reef_type}: {category}: {n} ({n_pct:.1f}%), {km2:.2f} km2 ({km2_pct:.1f}%)")


if __name__ == "__main__":
    main()
