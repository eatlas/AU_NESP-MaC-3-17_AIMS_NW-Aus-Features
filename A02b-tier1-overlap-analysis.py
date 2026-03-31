"""Script: A02b-tier1-overlap-analysis.py

Analyses the overlap between Tier 1 automated reference datasets (AHS, ReefKIM,
UNEP, GA) in terms of which countable reef clusters each dataset matches.

Reads the annotated reef clusters output from A02-unmapped-reefs.py and produces:
  - Unique contribution of each dataset (clusters matched by that source only).
  - Full intersection breakdown (UpSet-style) showing all 2^4 - 1 combinations.
  - Cumulative contribution when adding datasets in order of coverage.

Usage:
    python A02b-tier1-overlap-analysis.py
"""

import configparser
import os
from itertools import combinations

import geopandas as gpd
import pandas as pd

# ── Configuration ──────────────────────────────────────────────────────────────
cfg = configparser.ConfigParser()
cfg.read("config.ini")
version = cfg.get("general", "version")

ANALYSIS_SHP = f"working/{version}/A02/unmapped-reefs-analysis.shp"

SOURCES = ["src_AHS", "src_KIM", "src_UNEP", "src_GA"]
LABELS = {"src_AHS": "AHS", "src_KIM": "ReefKIM", "src_UNEP": "UNEP", "src_GA": "GA"}


def main():
    print(f"Loading: {ANALYSIS_SHP}")
    gdf = gpd.read_file(ANALYSIS_SHP)
    n_total = len(gdf)

    # Boolean columns for each source
    for col in SOURCES:
        gdf[col] = gdf[col].astype(bool)

    # Combined: matched by at least one Tier 1 source
    gdf["any_t1"] = gdf[SOURCES].any(axis=1)
    n_any = gdf["any_t1"].sum()
    n_none = n_total - n_any

    print("\n" + "=" * 60)
    print(f" Tier 1 Dataset Overlap Analysis — {version}")
    print("=" * 60)

    print(f"\nTotal countable reef clusters: {n_total}")
    print(f"Matched by at least one Tier 1 source: {n_any}")
    print(f"Not matched by any Tier 1 source: {n_none}")

    # ── 1. Individual coverage ─────────────────────────────────────────────
    print("\n--- Individual dataset coverage ---")
    for col in SOURCES:
        n = gdf[col].sum()
        print(f"  {LABELS[col]:<10} {n:>5}  ({100 * n / n_total:.1f}%)")

    # ── 2. Unique (exclusive) contribution ─────────────────────────────────
    print("\n--- Unique contribution (matched ONLY by this dataset) ---")
    for col in SOURCES:
        others = [c for c in SOURCES if c != col]
        mask = gdf[col] & ~gdf[others].any(axis=1)
        n = mask.sum()
        print(f"  {LABELS[col]:<10} {n:>5}  ({100 * n / n_total:.1f}%)")

    # ── 3. Pairwise overlap ────────────────────────────────────────────────
    print("\n--- Pairwise overlap (clusters matched by both) ---")
    for a, b in combinations(SOURCES, 2):
        n = (gdf[a] & gdf[b]).sum()
        print(f"  {LABELS[a]} ∩ {LABELS[b]:<10} {n:>5}")

    # ── 4. Full intersection breakdown (UpSet-style) ───────────────────────
    # Each cluster has a membership pattern like (True, False, True, False)
    # Group by that pattern and count.
    print("\n--- Full intersection breakdown ---")
    print(f"  {'AHS':<5} {'KIM':<5} {'UNEP':<5} {'GA':<5}  {'Count':>6}  {'%':>6}")
    print("  " + "-" * 40)

    gdf["_pattern"] = list(zip(*(gdf[c] for c in SOURCES)))
    breakdown = gdf.groupby("_pattern").size().reset_index(name="count")
    breakdown = breakdown.sort_values("count", ascending=False).reset_index(drop=True)

    for _, row in breakdown.iterrows():
        pattern = row["_pattern"]
        count = row["count"]
        flags = "  ".join(("Y" if v else ".").ljust(3) for v in pattern)
        print(f"  {flags}  {count:>6}  {100 * count / n_total:>5.1f}%")

    # ── 5. Cumulative (additive) contribution ──────────────────────────────
    # Add datasets one at a time in order of individual coverage (largest first)
    print("\n--- Cumulative contribution (adding datasets by coverage) ---")
    coverage_order = sorted(SOURCES, key=lambda c: gdf[c].sum(), reverse=True)
    cumulative = pd.Series(False, index=gdf.index)
    for col in coverage_order:
        prev_total = cumulative.sum()
        cumulative = cumulative | gdf[col]
        new_total = cumulative.sum()
        added = new_total - prev_total
        print(
            f"  + {LABELS[col]:<10} → {int(new_total):>5} matched "
            f"(+{int(added):>4} new, {100 * new_total / n_total:.1f}% cumulative)"
        )

    # ── 6. Marginal drop analysis ──────────────────────────────────────────
    # If we removed each dataset, how many clusters would become unmatched?
    print("\n--- Marginal drop (clusters lost if this dataset were removed) ---")
    for col in SOURCES:
        others = [c for c in SOURCES if c != col]
        with_all = gdf[SOURCES].any(axis=1).sum()
        without = gdf[others].any(axis=1).sum()
        drop = with_all - without
        print(f"  Remove {LABELS[col]:<10} → lose {drop:>4} clusters ({100 * drop / n_total:.1f}%)")

    print()


if __name__ == "__main__":
    main()
