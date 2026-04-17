"""Script: A02b-tier1-overlap-analysis.py
This script apportions the contribution each reference dataset (Tier 1 automated and Tier 2 manual) 
makes to the total number of reefs that were previously known.

Analyses the contribution of each reference dataset (Tier 1 automated and Tier 2
manual) to the classification of countable reef clusters.

Reads the annotated reef clusters output from A02-unmapped-reefs.py and produces:
  - Individual dataset coverage across all 8 sources.
  - Cumulative contribution when adding datasets in order of coverage, with
    mapped sources before indicated sources.
  - Marginal drop analysis showing clusters lost if each dataset were removed.

Usage:
    python A02b-tier1-overlap-analysis.py
"""

import configparser
import os

import geopandas as gpd
import pandas as pd

# ── Configuration ──────────────────────────────────────────────────────────────
cfg = configparser.ConfigParser()
cfg.read("config.ini")
version = cfg.get("general", "version")

ANALYSIS_SHP = f"working/{version}/A02/unmapped-reefs-analysis.shp"

# All eight source flag columns, grouped by tier and type
TIER1_SOURCES = ["src_AHS", "src_KIM", "src_UNEP", "src_GA"]
TIER2_MAPPED = ["src_bath_m", "src_cht_m"]
TIER2_INDICATED = ["src_bath_i", "src_cht_i"]
ALL_SOURCES = TIER1_SOURCES + TIER2_MAPPED + TIER2_INDICATED

LABELS = {
    "src_AHS": "AHS",
    "src_KIM": "ReefKIM",
    "src_UNEP": "UNEP",
    "src_GA": "GA",
    "src_bath_m": "Bathy mapped",
    "src_bath_i": "Bathy indicated",
    "src_cht_m": "Chart mapped",
    "src_cht_i": "Chart indicated",
}


def main():
    print(f"Loading: {ANALYSIS_SHP}")
    gdf = gpd.read_file(ANALYSIS_SHP)
    n_total = len(gdf)

    # Boolean columns for each source
    for col in ALL_SOURCES:
        gdf[col] = gdf[col].astype(bool)

    # Combined: matched by at least one source
    gdf["any_t1"] = gdf[TIER1_SOURCES].any(axis=1)
    gdf["any_mapped"] = gdf[TIER1_SOURCES + TIER2_MAPPED].any(axis=1)
    gdf["any_all"] = gdf[ALL_SOURCES].any(axis=1)

    n_any_t1 = int(gdf["any_t1"].sum())
    n_any_mapped = int(gdf["any_mapped"].sum())
    n_any_all = int(gdf["any_all"].sum())

    print("\n" + "=" * 60)
    print(f" Dataset Contribution Analysis — {version}")
    print("=" * 60)

    print(f"\nTotal countable reef clusters: {n_total}")
    print(f"Matched by at least one Tier 1 source:      {n_any_t1}")
    print(f"Matched by at least one mapped source:       {n_any_mapped}")
    print(f"Matched by at least one source (all):        {n_any_all}")
    print(f"Not matched by any source:                   {n_total - n_any_all}")

    # ── 1. Individual coverage ─────────────────────────────────────────────
    print("\n--- Individual dataset coverage ---")
    print("  Tier 1 (automated):")
    for col in TIER1_SOURCES:
        n = int(gdf[col].sum())
        print(f"    {LABELS[col]:<18} {n:>5}  ({100 * n / n_total:.1f}%)")
    print("  Tier 2 (manual — mapped):")
    for col in TIER2_MAPPED:
        n = int(gdf[col].sum())
        print(f"    {LABELS[col]:<18} {n:>5}  ({100 * n / n_total:.1f}%)")
    print("  Tier 2 (manual — indicated):")
    for col in TIER2_INDICATED:
        n = int(gdf[col].sum())
        print(f"    {LABELS[col]:<18} {n:>5}  ({100 * n / n_total:.1f}%)")

    # ── 2. Cumulative (additive) contribution ──────────────────────────────
    # Tier 1 sorted by coverage, then Tier 2 mapped sorted by coverage,
    # then Tier 2 indicated sorted by coverage.
    print("\n--- Cumulative contribution (adding datasets by coverage) ---")
    t1_order = sorted(TIER1_SOURCES, key=lambda c: gdf[c].sum(), reverse=True)
    t2m_order = sorted(TIER2_MAPPED, key=lambda c: gdf[c].sum(), reverse=True)
    t2i_order = sorted(TIER2_INDICATED, key=lambda c: gdf[c].sum(), reverse=True)
    cumulative_order = t1_order + t2m_order + t2i_order

    cumulative = pd.Series(False, index=gdf.index)
    for col in cumulative_order:
        prev_total = cumulative.sum()
        cumulative = cumulative | gdf[col]
        new_total = cumulative.sum()
        added = new_total - prev_total
        print(
            f"  + {LABELS[col]:<18} → {int(new_total):>5} matched "
            f"(+{int(added):>4} new, {100 * new_total / n_total:.1f}% cumulative)"
        )

    # ── 3. Marginal drop analysis ──────────────────────────────────────────
    # If we removed each dataset, how many clusters would lose all matches?
    print("\n--- Marginal drop (clusters lost if this dataset were removed) ---")
    for col in cumulative_order:
        others = [c for c in ALL_SOURCES if c != col]
        with_all = int(gdf[ALL_SOURCES].any(axis=1).sum())
        without = int(gdf[others].any(axis=1).sum())
        drop = with_all - without
        print(f"  Remove {LABELS[col]:<18} → lose {drop:>4} clusters ({100 * drop / n_total:.1f}%)")

    print()


if __name__ == "__main__":
    main()
