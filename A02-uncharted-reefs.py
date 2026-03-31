#!/usr/bin/env python3
import os
import configparser
import geopandas as gpd
import pandas as pd

cfg = configparser.ConfigParser()
cfg.read("config.ini")
in_3p_path = cfg.get("general", "in_3p_path")
version = cfg.get("general", "version")

# Inputs
L2_SHP = f"working/12/NW-Features_{version}_RB-Type-L2.shp"
AHO_UNCHARTED_SHP = f"data/{version}/in/AHO-Uncharted/AHO-Uncharted-areas_2025.shp"
REEFKIM_SHP = f"data/{version}/in-3p-mirror/WA_CU_WAMSI-2-1-3-1_ReefKIM/Reef_KIM.shp"
AHS_REEFS_SHP = f"{in_3p_path}/AU_NESP-D3_AHS_Reefs/sbdare_a_reefs-only.shp"

# Output
OUT_SHP = f"working/A02/NW-Features_{version}_uncharted-reefs.shp"

# Target CRS per instruction
TARGET_CRS = "EPSG:4283"

KEEP_L2 = {"Coral Reef", "Rocky Reef"}

def fix_geoms(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    return gdf



def main():
    os.makedirs(os.path.dirname(OUT_SHP), exist_ok=True)

    # Load layers
    l2 = gpd.read_file(L2_SHP)
    aho_uncharted = gpd.read_file(AHO_UNCHARTED_SHP)
    aho_reefs = gpd.read_file(AHS_REEFS_SHP)
    reefkim = gpd.read_file(REEFKIM_SHP)

    # Clean and reproject to EPSG:4283
    l2 = fix_geoms(l2).to_crs(TARGET_CRS)
    aho_uncharted = fix_geoms(aho_uncharted).to_crs(TARGET_CRS)
    aho_reefs = fix_geoms(aho_reefs).to_crs(TARGET_CRS)
    reefkim = fix_geoms(reefkim).to_crs(TARGET_CRS)

    # Filter to Coral/Rocky reefs only
    if "RB_Type_L2" not in l2.columns:
        raise ValueError("RB_Type_L2 column missing in L2 input.")
    l2_rr = l2[l2["RB_Type_L2"].isin(KEEP_L2)].copy()

    # Keep only features intersecting AHO-Uncharted
    j_unc = gpd.sjoin(l2_rr, aho_uncharted[["geometry"]], how="inner", predicate="intersects")
    l2_in_unc = l2_rr.loc[j_unc.index.unique()].copy()

    # Exclude features that intersect AHO reefs
    j_aho = gpd.sjoin(l2_in_unc, aho_reefs[["geometry"]], how="inner", predicate="intersects")
    ids_exclude = set(j_aho.index)

    # Exclude features that intersect ReefKIM reefs
    j_kim = gpd.sjoin(l2_in_unc, reefkim[["geometry"]], how="inner", predicate="intersects")
    ids_exclude.update(j_kim.index)

    result = l2_in_unc.drop(index=list(ids_exclude), errors="ignore").copy()

    # Save all original attributes (from L2 input)
    result.to_file(OUT_SHP)

    # Print counts by RB_Type_L2
    counts = result["RB_Type_L2"].value_counts()
    print("Counts (uncharted, excluding AHO and ReefKIM overlaps):")
    for k in ["Coral Reef", "Rocky Reef"]:
        print(f"  {k}: {int(counts.get(k, 0))}")
    print(f"Total: {len(result)}")

if __name__ == "__main__":
    main()
