"""
Script: V04b - Analyse match lines for reef edge accuracy statistics

Scope
This script is the second processing stage in determining the distribution of boundary
errors. In this analysis we compare the v0-4 version of the dataset with a duplicate
independent mapping of the reefs (AU_AIMS_NESP-MaC-3-17_Rough-reef-shallow-mask_87hr.shp).
This comparison is limited to masked areas determined by Boundary-comp-regions_v0-4-to-v0-1-EL.shp.
This mask is to limit the comparison to areas where the Rough Reef Mask does not include
any shallow sediments areas and the digitisation accuracy is reasonably good.
This duplicate mapping allows us to understand the variability in the feature boundaries
and to understand the distribution in the boundary errors. The goal is to answer the question:
Given that we recorded a single EdgeAcc_m value for each reef feature, how does this single
value compare with the full distribution of errors. Does the EdgeAcc_m represent the worst
10% of the boundary error or align better with the worst 25%? How does it relate to the
typical boundary error. Can we calculate a scalar that estimates the typical boundary
error from the EdgeAcc_m value? The goal of this analysis is to allow us to estimate
the distribution of boundary errors from the estimated EdgeAcc_m value. This will allow
us to create Monte Carlo simulations that buffer the reef boundaries in and out to simulate
the uncertainty in the reef boundaries. This will be used to help estimate the uncertainty
in counting reefs, which is influenced by the reef area and the reef proximity to other reefs.

The processing was split into two scripts to limit the complexity of each script. This script
uses the matched line segments produced by V04-v0-4-assess-edgeacc.py. Summary statistics
are calculated for each reef feature and these statistics are joined back to the
NW-Aus-Feat_v0-4_RB_Type_L1_clip.shp, which is a filtered and dissolved version of the v0-4 reef features.

Limitations:
In this analysis we are comparing the v0-4 dataset (A) with the Rough Reef Mask (B). The Rough
Reef Mask is not a perfect representation of the true reef boundaries. It has boundary errors
that are greater than the v0-4 dataset. It is however an independent mapping and so it provides
a useful comparison. This means that the absolute error values are not a direct measure of the
true boundary error. However, the relative error values and the distribution of errors are still
informative for understanding the boundary accuracy.

Inputs (produced by V04 script)
  working/V04/NW-Aus-Feat_v0-4_RB_Type_L1_clip.shp
     - Polygon layer (A dissolved reef extents) with:
         FID (int) unique identifier
         EdgeAcc_m (float/int) aggregated max worst ~10% edge accuracy estimate
         geometry (Polygon)
  working/V04/sample_match_lines.shp
     - Line layer of matched sample segments with:
         FID (int) referencing dissolved polygon FID
         SID (int) sample index
         DIST_M (float, 0.1 m precision) distance from sample to nearest B boundary
         geometry (LineString)

Assumptions / confirmed conditions
  - All FIDs referenced in sample_match_lines exist in NW-Aus-Feat_v0-4_RB_Type_L1_clip.shp.
  - DIST_M values are already computed (trust stored attribute; no recomputation).
  - No null or capped SEARCH_RADIUS_M placeholder values present (DIST_M is direct distribution).
  - EdgeAcc_m has no nulls in the current dataset (if null encountered later: EdgePerc/EdgeTo50p set null).
  - Both input layers are stored in EPSG:4283 (processing does not require reprojection).
  - Features in the dissolved layer that have zero associated match lines (should not occur,
    but if encountered) will be dropped from the output (per user requirement).
  - Sample size per feature varies (due to land exclusion and geometry filtering).
  - In-memory processing is acceptable.

Target statistics per FID
  - Percentiles (metres, round to 0.1):
      p05, p10, p15, p20, p25, p30, p35, p40, p45,
      p50, p55, p60, p65, p70, p75, p80, p85, p90, p95, p100
    (Computed via numpy.percentile with default linear interpolation)
  - EdgePerc: Percentile rank (0–100, 0.1 precision) of EdgeAcc_m within the sorted DIST_M values.
      * 100.0 if EdgeAcc_m > max distance
      * 0.0 if EdgeAcc_m <= min distance
      * Linear interpolation between surrounding distances
  - EdgeTo50p: Ratio p50 / EdgeAcc_m when EdgeAcc_m > 0; else null.
      * Rounded to 4 decimal places
  - Optional counts (for internal QA – may add later):
      n_samples (count of DIST_M contributing to stats)

Processing outline
  1. Load polygons (dissolved) and match lines.
  2. Validate required fields: FID, EdgeAcc_m (polygons); FID, SID, DIST_M (lines).
  3. Group match lines by FID and compute percentile distribution and metrics.
  4. Join metrics back to polygon GeoDataFrame; drop polygons with no lines.
  5. Write output enriched polygon layer:
       working/V04b/reef_edge_metrics.shp
     (Overwrite if exists.)
  6. Progress logging every LOG_INTERVAL groups.

Edge cases / handling
  - Division by zero for EdgeTo50p avoided (EdgeAcc_m <= 0 → null).
  - Duplicate (FID, SID) lines ignored only if necessary (not expected).
  - If a feature ends up with only one distance value, all percentiles collapse to that value.
  - If unexpected empty line dataset → script aborts with clear error.

Future extensions (not yet implemented here)
  - No-match samples integration (if separate dataset of no-match points retained).
  - Proportion of distances exceeding EdgeAcc_m.
  - Plot generation (EdgeAcc_m vs p50, vs p90, vs EdgeTo50p).

Current step
  - Boilerplate plus data loading only (no computations performed yet).


Next development step after verification
  - Implement compute_metrics() to produce stats and write output.
"""

from __future__ import annotations

import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt  # added
import math  # added

# Constants
PERCENTILES = [5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80,85,90,95,100]
# Canonical percentile field names (must match compute_metrics construction)
PERCENTILE_FIELDS = [f"p{str(p).zfill(2)}" if p < 100 else "p100" for p in PERCENTILES]
LOG_INTERVAL = 50

# Input paths (relative to project root)
DISSOLVE_SHP = "working/V04a/NW-Aus-Feat_v0-4_RB_Type_L1_clip.shp"
MATCH_LINES_SHP = "working/V04a/sample_match_lines.shp"

# Output path
OUTPUT_DIR = Path("working/V04b-dither")
OUTPUT_SHP = OUTPUT_DIR / "reef_edge_metrics.shp"

# Logging helpers
def log_info(msg: str) -> None:
    print(f"[INFO] {msg}")

def log_warn(msg: str) -> None:
    print(f"[WARN] {msg}", file=sys.stderr)

def log_error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)

def percentile_rank(edge_val: float, sorted_vals: np.ndarray) -> float:
    """
    Linear interpolation percentile rank (0-100) of edge_val in sorted_vals.
    If edge_val <= min -> 0.0; >= max -> 100.0.
    """
    n = len(sorted_vals)
    if n == 0:
        return np.nan
    if n == 1:
        v = sorted_vals[0]
        if edge_val <= v:
            return 0.0
        return 100.0
    if edge_val <= sorted_vals[0]:
        return 0.0
    if edge_val >= sorted_vals[-1]:
        return 100.0
    # position
    idx = np.searchsorted(sorted_vals, edge_val, side="right")
    j = idx - 1
    d0 = sorted_vals[j]
    d1 = sorted_vals[idx]
    if d1 == d0:
        # flat segment (duplicates)
        pos = j
    else:
        frac = (edge_val - d0) / (d1 - d0)
        pos = j + frac
    return (pos / (n - 1)) * 100.0

def compute_metrics(gdf_poly: gpd.GeoDataFrame, gdf_lines: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Group match lines by FID, compute percentiles & metrics, merge back to polygons.
    Polygons with no lines are dropped.
    Adds EdgeToXXp ratios (pXX / EdgeAcc_m) for all configured percentiles.
    """
    # Ensure numeric
    gdf_lines = gdf_lines.copy()
    gdf_lines["DIST_M"] = pd.to_numeric(gdf_lines["DIST_M"], errors="coerce")
    gdf_poly = gdf_poly.copy()
    gdf_poly["EdgeAcc_m"] = pd.to_numeric(gdf_poly["EdgeAcc_m"], errors="coerce")

    groups = gdf_lines.groupby("FID", sort=False)
    records = []
    total = len(groups)
    for idx, (fid, grp) in enumerate(groups, start=1):
        dists = grp["DIST_M"].dropna().to_numpy(dtype=float)
        if dists.size == 0:
            continue
        perc_vals = np.percentile(dists, PERCENTILES)
        perc_vals = np.round(perc_vals, 1)
        p_map = { (f"p{str(p).zfill(2)}" if p < 100 else "p100"): v for p, v in zip(PERCENTILES, perc_vals) }

        edge_acc_series = gdf_poly.loc[gdf_poly["FID"] == fid, "EdgeAcc_m"]
        if edge_acc_series.empty:
            continue
        edge_acc_val = edge_acc_series.iloc[0]
        sorted_d = np.sort(dists)

        if np.isnan(edge_acc_val):
            edge_perc = np.nan
            edge_to_map = { (f"EdgeTo{str(p).zfill(2)}p" if p < 100 else "EdgeTo100p"): np.nan for p in PERCENTILES }
        else:
            edge_perc = round(percentile_rank(edge_acc_val, sorted_d), 1)
            # EdgeToXXp ratios
            edge_to_map = {}
            for p in PERCENTILES:
                pname = f"p{str(p).zfill(2)}" if p < 100 else "p100"
                rname = f"EdgeTo{str(p).zfill(2)}p" if p < 100 else "EdgeTo100p"
                val = p_map[pname]
                edge_to_map[rname] = round(val / edge_acc_val, 4) if edge_acc_val > 0 else np.nan

        rec = {
            "FID": fid,
            "EdgePerc": edge_perc,
            "n_samples": int(dists.size)
        }
        rec.update(p_map)
        rec.update(edge_to_map)
        records.append(rec)

        if idx % LOG_INTERVAL == 0:
            log_info(f"Processed {idx}/{total} FIDs for metrics...")
    if not records:
        raise RuntimeError("No metrics computed (no valid distance groups).")

    metrics_df = pd.DataFrame(records)
    merged = gdf_poly.merge(metrics_df, on="FID", how="inner")
    log_info(f"Merged metrics: {len(merged)} polygons retained (dropped {len(gdf_poly)-len(merged)} without lines).")
    return merged

def load_inputs():
    """Load dissolved polygons and match lines; perform basic validation."""
    if not Path(DISSOLVE_SHP).exists():
        raise FileNotFoundError(f"Dissolved polygon file not found: {DISSOLVE_SHP}")
    if not Path(MATCH_LINES_SHP).exists():
        raise FileNotFoundError(f"Match lines file not found: {MATCH_LINES_SHP}")

    log_info(f"Loading dissolved polygons: {DISSOLVE_SHP}")
    gdf_poly = gpd.read_file(DISSOLVE_SHP)
    log_info(f"  Loaded {len(gdf_poly)} polygons.")

    log_info(f"Loading match lines: {MATCH_LINES_SHP}")
    gdf_lines = gpd.read_file(MATCH_LINES_SHP)
    log_info(f"  Loaded {len(gdf_lines)} match lines.")

    # Basic field checks
    for fld in ["FID", "EdgeAcc_m"]:
        if fld not in gdf_poly.columns:
            raise KeyError(f"Polygon layer missing required field '{fld}'.")

    for fld in ["FID", "SID", "DIST_M"]:
        if fld not in gdf_lines.columns:
            raise KeyError(f"Match lines layer missing required field '{fld}'.")

    # CRS check - informational only
    if gdf_poly.crs != gdf_lines.crs:
        log_warn(f"CRS mismatch: polygons={gdf_poly.crs}, lines={gdf_lines.crs} (processing will proceed).")

    return gdf_poly, gdf_lines

def generate_plots(gdf_metrics, gdf_lines):
    """Create log-scale ratio distributions (EdgeTo20p / EdgeTo50p / EdgeTo80p) with lognormal fits
       (overall + size classes), log-log scatter plots (EdgeAcc_m vs p20/p50/p80),
       and overall CDF of all DIST_M values."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def plot_edge_ratio(series, pct_label, title_suffix, filename_suffix):
        """
        Generic lognormal fit + histogram for an EdgeToXXp ratio series.
        pct_label: string like '20', '50', '80'
        """
        et = series.replace([np.inf, -np.inf], np.nan)
        et = et[(et > 0)].dropna()
        if et.empty:
            log_warn(f"EdgeTo{pct_label}p subset empty for {title_suffix}; plot skipped.")
            return
        min_ratio = 0.05
        max_ratio = 5
        et_clipped = et[(et >= min_ratio) & (et <= max_ratio)]
        if et_clipped.empty:
            log_warn(f"EdgeTo{pct_label}p subset (after clipping {min_ratio}–{max_ratio}) empty for {title_suffix}; plot skipped.")
            return

        ln_vals = np.log(et_clipped)
        if ln_vals.size < 2:
            log_warn(f"Not enough values to fit lognormal for EdgeTo{pct_label}p {title_suffix}; plot skipped.")
            return
        mu = ln_vals.mean()
        sigma = ln_vals.std(ddof=0)

        bins = np.logspace(np.log10(min_ratio), np.log10(max_ratio), 40)
        plt.figure(figsize=(6,4))
        plt.hist(et_clipped, bins=bins, color="#2c7fb8", edgecolor="white", alpha=0.65, density=True)

        x_grid = np.logspace(np.log10(min_ratio), np.log10(max_ratio), 400)
        pdf = (1 / (x_grid * sigma * math.sqrt(2 * math.pi))) * np.exp(-((np.log(x_grid) - mu) ** 2) / (2 * sigma ** 2))
        plt.plot(x_grid, pdf, color="#d62728", lw=2, label="Lognormal fit")

        plt.xscale("log")
        plt.xlim(min_ratio, max_ratio)
        plt.xlabel(f"EdgeTo{pct_label}p (p{pct_label} / EdgeAcc_m) [log scale]")
        plt.ylabel("Density")
        plt.title(f"EdgeTo{pct_label}p Distribution {title_suffix} ({min_ratio}–{max_ratio})")
        plt.grid(alpha=0.3, which="both")
        plt.text(
            0.98, 0.95,
            f"μ = {mu:.3f}\nσ = {sigma:.3f}",
            ha="right", va="top",
            transform=plt.gca().transAxes,
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#555", alpha=0.85)
        )
        plt.legend()
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / f"EdgeTo{pct_label}p_distribution{filename_suffix}.png", dpi=150)
        plt.close()

    # Percentile ratios to plot
    ratio_specs = [
        ("20", "EdgeTo20p"),
        ("50", "EdgeTo50p"),
        ("80", "EdgeTo80p"),
    ]

    # Overall + size classes
    if "Area_km2" in gdf_metrics.columns:
        areas = gdf_metrics["Area_km2"].astype(float)
        size_classes = [
            ("(All Reefs)", "", np.full(len(gdf_metrics), True, dtype=bool)),
            ("(<0.1 km²)", "_lt0p1", areas < 0.1),
            ("(0.1–1 km²)", "_0p1_to_1", (areas >= 0.1) & (areas <= 1.0)),
            ("(>1 km²)", "_gt1", areas > 1.0),
        ]
    else:
        size_classes = [("(All Reefs)", "", np.full(len(gdf_metrics), True, dtype=bool))]

    for pct_label, attr in ratio_specs:
        if attr not in gdf_metrics.columns:
            log_warn(f"{attr} missing; skipping EdgeTo{pct_label}p plots.")
            continue
        for title_suffix, file_suffix, mask in size_classes:
            subset_series = gdf_metrics.loc[mask, attr]
            plot_edge_ratio(subset_series, pct_label, title_suffix, f"{file_suffix}")

    # Scatter plots (unchanged)
    def scatter_plot(percent_field, color):
        if percent_field not in gdf_metrics.columns:
            return
        x = gdf_metrics["EdgeAcc_m"].astype(float)
        y = gdf_metrics[percent_field].astype(float)
        mask = (x > 0) & (y > 0)
        x = x[mask]; y = y[mask]
        if x.empty or y.empty:
            return
        x_min, x_max = x.min(), x.max()
        y_min, y_max = y.min(), y.max()
        min_lim = min(x_min, y_min)
        max_lim = max(x_max, y_max)
        plt.figure(figsize=(5.5,5.2))
        plt.scatter(x, y, s=12, alpha=0.6, c=color, edgecolors="none")
        plt.xscale("log"); plt.yscale("log")
        plt.plot([min_lim, max_lim], [min_lim, max_lim], ls="--", c="gray", lw=1)
        plt.xlim(min_lim * 0.9, max_lim * 1.1)
        plt.ylim(min_lim * 0.9, max_lim * 1.1)
        plt.xlabel("EdgeAcc_m (m, log)")
        plt.ylabel(f"{percent_field} (m, log)")
        plt.title(f"EdgeAcc_m vs {percent_field} (log-log)")
        plt.grid(alpha=0.3, which="both")
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / f"EdgeAcc_vs_{percent_field}.png", dpi=150)
        plt.close()

    scatter_plot("p20", "#1b9e77")
    scatter_plot("p50", "#d95f02")
    scatter_plot("p80", "#7570b3")

    # --- Cumulative distribution of all match line distances (DIST_M) on log scale 3–2000 m ---
    if "DIST_M" in gdf_lines.columns:
        dist_series = pd.to_numeric(gdf_lines["DIST_M"], errors="coerce").dropna()
        dist_series = dist_series[dist_series >= 0]
        # Filter to target plotting domain
        MIN_CDF = 3.0
        MAX_CDF = 2000.0
        dist_series = dist_series[(dist_series >= MIN_CDF) & (dist_series <= MAX_CDF)]
        if not dist_series.empty:
            d_sorted = np.sort(dist_series.to_numpy())
            n = d_sorted.size
            cdf_pct = np.linspace(0, 100, n, endpoint=False)
            d_sorted = np.append(d_sorted, d_sorted[-1])
            cdf_pct = np.append(cdf_pct, 100.0)
            plt.figure(figsize=(6.5,4.2))
            plt.plot(d_sorted, cdf_pct, color="#34495e", lw=1.8)
            plt.xscale("log")
            plt.xlim(MIN_CDF, MAX_CDF)
            plt.xlabel("Error Distance (m, log scale)")
            plt.ylabel("Cumulative percentage (%)")
            plt.title("Cumulative Distribution of Boundary Error Distances (3–2000 m)")
            plt.grid(alpha=0.35, which="both")
            plt.tight_layout()
            plt.savefig(OUTPUT_DIR / "DIST_M_CDF.png", dpi=150)
            plt.close()
        else:
            log_warn("No DIST_M values within 3–2000 m; CDF plot skipped.")
    else:
        log_warn("DIST_M field not found in gdf_lines; CDF plot skipped.")

def main():
    try:
        gdf_poly, gdf_lines = load_inputs()
    except Exception as e:
        log_error(f"Input loading failed: {e}")
        sys.exit(1)

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        gdf_metrics = compute_metrics(gdf_poly, gdf_lines)
        metric_cols = [c for c in PERCENTILE_FIELDS if c in gdf_metrics.columns]
        # EdgeToXXp columns derived from PERCENTILES (ensure ordering matches)
        edge_to_cols = [
            (f"EdgeTo{str(p).zfill(2)}p" if p < 100 else "EdgeTo100p")
            for p in PERCENTILES if (f"EdgeTo{str(p).zfill(2)}p" if p < 100 else "EdgeTo100p") in gdf_metrics.columns
        ]
        ordered = ["FID", "EdgeAcc_m"] + metric_cols + edge_to_cols + ["EdgePerc", "n_samples", "geometry"]
        ordered = [c for c in ordered if c in gdf_metrics.columns]
        gdf_metrics[ordered].to_file(OUTPUT_SHP)
        log_info(f"Written metrics shapefile: {OUTPUT_SHP}")

        # Generate plots (now passing gdf_lines for CDF)
        generate_plots(gdf_metrics, gdf_lines)
        log_info("Plots written to output directory.")
    except Exception as e:
        log_error(f"Metric computation or write failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
