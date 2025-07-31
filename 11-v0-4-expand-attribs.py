"""
Script: 11-v0-4-expand-attribs.py

Purpose:
    This script processes a shapefile of reef and sandbank features from northern Australia,
    enriching it with additional classification attributes from a crosswalk table. The goal is
    to harmonize the dataset with multiple external classification schemes (e.g., Seamap Australia,
    Natural Values Common Language, Queensland Wetlands Info) and prepare it for publication.

Processing Steps:
    1. Reads the input shapefile containing reef features and their attributes.
    2. Reads a crosswalk CSV table that maps the internal classification scheme (RB_Type_L3, Attachment, DepthCat)
       to external classification schemes. The crosswalk allows for multiple possible values in the
       Attachment and DepthCat columns (semicolon-separated).
    3. For each feature in the shapefile:
        - Matches it to a row in the crosswalk table using:
            * RB_Type_L3 (feature) == RB_Type_L3_v0-4 (crosswalk)
            * Attachment (feature) in Attachment_v0-4 (crosswalk, supports multiple values)
            * DepthCat (feature, defaulting to 'Shallow' if missing) in DepthCat_v0-4 (crosswalk, supports multiple values)
        - If a feature cannot be matched, it is collected for review.
    4. If any features are unmatched:
        - Saves these features to a separate shapefile for manual inspection and correction.
        - Prints a summary of mismatches and aborts further processing.
    5. For matched features:
        - Adds selected external classification attributes from the crosswalk table.
        - Retains key existing attributes from the input shapefile.
        - Converts the EdgeAcc_m attribute to integer type.
        - Recalculates the Area_km2 attribute using an equal-area projection (EPSG:3112).
        - Reprojects the final dataset to EPSG:4283 (GDA94) for publication.
        - Determines the maximum string length for each output text field and sets the output schema accordingly.
        - Saves the enriched dataset as a new shapefile.

Inputs:
    - Reef features shapefile: data/v0-4/in/Reef-Boundaries_v0-4_edit.shp
    - Crosswalk table: data/v0-4/in/RB_Type_L3_crosswalk.csv

Outputs:
    - Enriched features shapefile: working/11/NW-Features_v0-4.shp
    - Unmatched features shapefile (if any): working/11/Feature-mismatched.shp

Notes:
    - Requires the 'fiona' engine for shapefile writing to support custom field lengths.
    - Prints status messages at each major processing step.
    - Designed for use in the AIMS NESP 3.17 project for harmonizing reef boundary mapping data.
"""

import os
import pandas as pd
import geopandas as gpd
import numpy as np

# Input/output paths
INPUT_SHP = "working/10/NW-Aus-Features_v0-4.shp"
#INPUT_SHP = "data/v0-4/in/Reef-Boundaries_v0-4_edit.shp"
CROSSWALK_CSV = "data/v0-4/in/RB_Type_L3_crosswalk.csv"
MISMATCHED_SHP = "working/11/Feature-mismatched.shp"
OUTPUT_SHP = "working/11/NW-Features_v0-4.shp"

# Output fields from crosswalk to add
CROSSWALK_FIELDS = [
    'RB_Type_L2', 'RB_Type_L1', 'NvclEco', 'NvclEcoCom', 'INUNDTN', 'SMB_CMP',
    'AS_TidalZ', 'AS_Bdepth', 'AS_System', 'AS_SubSys',
    'BC_Level1', 'BC_Level2', 'BC_Level3', 'BC_Level4',
    'SO_Level1', 'SO_Level2', 'SO_Level3', 'SC_Level1'
]

# Existing fields to retain
RETAIN_FIELDS = [
    'FeatConf', 'TypeConf', 'DepthCat', 'DepthCatSr', 'RB_Type_L3',
    'Attachment', 'EdgeSrc', 'EdgeAcc_m'
]

def main():
    print("Reading input shapefile...")
    gdf = gpd.read_file(INPUT_SHP)
    print(f"  Loaded {len(gdf)} features.")

    print("Reading crosswalk table...")
    crosswalk = pd.read_csv(CROSSWALK_CSV, dtype=str).fillna('')
    print(f"  Loaded {len(crosswalk)} crosswalk rows.")

    # Prepare crosswalk for matching
    crosswalk['DepthCat_v0-4_list'] = crosswalk['DepthCat_v0-4'].str.split(';').apply(lambda lst: [x.strip() for x in lst if x.strip()])
    crosswalk['Attachment_v0-4_list'] = crosswalk['Attachment_v0-4'].str.split(';').apply(lambda lst: [x.strip() for x in lst if x.strip()])

    # Fill missing DepthCat with 'Shallow'
    gdf['DepthCat'] = gdf['DepthCat'].fillna('Shallow')
    gdf['DepthCat'] = gdf['DepthCat'].replace('', 'Shallow')

    # Convert EdgeAcc_m to integer (from string)
    gdf['EdgeAcc_m'] = pd.to_numeric(gdf['EdgeAcc_m'], errors='coerce').fillna(0).astype(int)

    # Prepare for matching
    print("Matching features to crosswalk...")
    match_indices = []
    crosswalk_indices = []
    mismatched_indices = []

    # Build a lookup for fast matching (by RB_Type_L3_v0-4)
    crosswalk_lookup = {}
    for idx, row in crosswalk.iterrows():
        key = row['RB_Type_L3_v0-4']
        crosswalk_lookup.setdefault(key, []).append((idx, row['Attachment_v0-4_list'], row['DepthCat_v0-4_list']))

    for i, feat in gdf.iterrows():
        key = feat['RB_Type_L3']
        attachment = feat['Attachment']
        depthcat = feat['DepthCat']
        candidates = crosswalk_lookup.get(key, [])
        found = False
        for idx, attachment_list, depthcat_list in candidates:
            if attachment in attachment_list and depthcat in depthcat_list:
                match_indices.append(i)
                crosswalk_indices.append(idx)
                found = True
                break
        if not found:
            mismatched_indices.append(i)

    print(f"  Matched {len(match_indices)} features.")
    print(f"  {len(mismatched_indices)} features could not be matched.")

    # If mismatches, save and abort
    if mismatched_indices:
        print("Saving mismatched features for review...")
        mismatched_gdf = gdf.iloc[mismatched_indices]
        os.makedirs(os.path.dirname(MISMATCHED_SHP), exist_ok=True)
        mismatched_gdf.to_file(MISMATCHED_SHP)
        print(f"  Mismatched features saved to {MISMATCHED_SHP}")
        print("Summary of mismatches (by RB_Type_L3, Attachment, DepthCat):")
        print(mismatched_gdf.groupby(['RB_Type_L3', 'Attachment', 'DepthCat']).size())
        print("Aborting further processing due to mismatches.")
        return

    # Prepare output dataframe
    print("Preparing output dataframe...")
    matched_gdf = gdf.iloc[match_indices].copy()
    crosswalk_matched = crosswalk.iloc[crosswalk_indices].reset_index(drop=True)
    matched_gdf = matched_gdf.reset_index(drop=True)

    # Add crosswalk fields
    for field in CROSSWALK_FIELDS:
        matched_gdf[field] = crosswalk_matched[field].values

    # Recalculate Area_km2
    print("Reprojecting to EPSG:3112 for area calculation...")
    matched_gdf_3112 = matched_gdf.to_crs(epsg=3112)
    matched_gdf['Area_km2'] = matched_gdf_3112.geometry.area / 1e6
    matched_gdf['Area_km2'] = matched_gdf['Area_km2'].round(4)

    # Reproject to EPSG:4283 for output
    print("Reprojecting to EPSG:4283 for output...")
    matched_gdf = matched_gdf.to_crs(epsg=4283)

    # Determine max string lengths for schema
    print("Determining field lengths for output schema...")
    schema = matched_gdf.schema if hasattr(matched_gdf, 'schema') else None
    properties = {}
    for field in RETAIN_FIELDS + CROSSWALK_FIELDS:
        if field in matched_gdf.columns:
            if matched_gdf[field].dtype == object:
                maxlen = matched_gdf[field].astype(str).map(len).max()
                properties[field] = f'str:{maxlen}'
            elif matched_gdf[field].dtype == int or np.issubdtype(matched_gdf[field].dtype, np.integer):
                properties[field] = 'int'
            elif matched_gdf[field].dtype == float or np.issubdtype(matched_gdf[field].dtype, np.floating):
                properties[field] = 'float:24.15'
    # Area_km2
    properties['Area_km2'] = 'float:24.4'

    # Geometry
    geometry_type = gpd.io.file.infer_schema(matched_gdf)['geometry']

    # Output columns order
    output_cols = RETAIN_FIELDS + CROSSWALK_FIELDS + ['Area_km2', 'geometry']
    output_cols = [col for col in output_cols if col in matched_gdf.columns or col == 'geometry']

    # Save output
    print(f"Saving output to {OUTPUT_SHP}...")
    os.makedirs(os.path.dirname(OUTPUT_SHP), exist_ok=True)
    # Fiona is needed for schema handling
    matched_gdf[output_cols].to_file(
        OUTPUT_SHP,
        driver='ESRI Shapefile',
        schema={'geometry': geometry_type, 'properties': properties},
        engine='fiona'
    )
    print(f"Done! Output saved to {OUTPUT_SHP}")

if __name__ == "__main__":
    main()