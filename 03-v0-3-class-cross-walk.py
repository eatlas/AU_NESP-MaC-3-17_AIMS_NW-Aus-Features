#!/usr/bin/env python3
"""02-v0-3-class-cross-walk.py
Transform the RB_Type_L3 classification used in 'Reef Boundaries Review.shp' (v0-3_qc-1) 
to the refactored classification with the new attributes schema.

This script is a one off transformation applied to the data. 

Note (v0-4): In v0-4 of the dataset we updated the classification system and so this version
was only used in this v0-3 version of the dataset. In v0-4 we retained more of RB_Type_L3
and had less additional attributes. In 09-v0-4-class-cross-walk.py we redo the classification
starting from the same point as this script, but using the v0-4 classification system.

Usage
-----
python 02-v0-3-class-cross-walk.py
"""

import geopandas as gpd
import pandas as pd
import os
import sys

IN_PATH  = os.path.join('working', '02', 'Reef_Boundaries_Clean.shp')
OUT_DIR  = os.path.join('working', '03')
OUT_PATH = os.path.join(OUT_DIR, 'NW-Aus-Features_v0-3-cross-walk.shp')

# ------------------------------------------------------------------ #
# Mapping dictionary: RB_Type_L3  -->  new attribute set
# ------------------------------------------------------------------ #
MAP = {
    # Coral reefs ----------------------------------------------------
    'Platform Coral Reef':
        dict(Feat_L3='Coral Reef Shallow', GeoAttach='Isolated',
             Relief='High', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Deep Platform Coral Reef':
        dict(Feat_L3='Coral Reef Deep',    GeoAttach='Isolated',
             Relief=pd.NA, FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Fringing Coral Reef':
        dict(Feat_L3='Coral Reef Shallow', GeoAttach='Fringing',
             Relief='High', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'High Intertidal Coral Reef':
        dict(Feat_L3='High Intertidal Coral Reef', GeoAttach='Fringing',
             Relief='High', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Fringing Shallow Reef Flat':
        dict(Feat_L3='Reef Flat Shallow', GeoAttach='Fringing',
             Relief='Low', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Platform Shallow Reef Flat':
        dict(Feat_L3='Reef Flat Shallow', GeoAttach='Isolated',
             Relief='Low', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),

    # Stromatolite ---------------------------------------------------
    'Stromatolite Reef':
        dict(Feat_L3='Stromatolite Reef', GeoAttach='Fringing',
             Relief='Low', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),

    # Rocky reefs ----------------------------------------------------
    'Platform Rocky Reef':
        dict(Feat_L3='Rocky Reef', GeoAttach='Isolated',
             Relief='High', FlowInflu='No', SO_L2='Terrigenous', Paleo='No'),
    'Fringing Rocky Reef':
        dict(Feat_L3='Rocky Reef', GeoAttach='Fringing',
             Relief='High', FlowInflu='No', SO_L2='Terrigenous', Paleo='No'),
    'Low Relief Rocky Reef':
        dict(Feat_L3='Rocky Reef', GeoAttach='Isolated',
             Relief='Low', FlowInflu='No', SO_L2='Terrigenous', Paleo='No'),
    'Fringing Paleo Coast Rocky Reef':
        dict(Feat_L3='Rocky Reef', GeoAttach='Isolated',
             Relief='High', FlowInflu='No', SO_L2='Terrigenous', Paleo='Yes'),
    'Paleo Coast Rocky Reef':
        dict(Feat_L3='Rocky Reef', GeoAttach='Isolated',
             Relief='High', FlowInflu='No', SO_L2='Terrigenous', Paleo='Yes'),

    # Soft sediment --------------------------------------------------
    'Shallow Sediment':
        dict(Feat_L3='Shallow Sediment', GeoAttach='Fringing',
             Relief='NA', FlowInflu='No', SO_L2='Terrigenous', Paleo='No'),
    'Sand Bank':
        dict(Feat_L3='Sand Bank', GeoAttach='Isolated',
             Relief='Medium', FlowInflu='No', SO_L2='Terrigenous', Paleo='No'),

    # Atoll coral reefs ---------------------------------------------
    'Atoll Shallow Patch Coral Reef':
        dict(Feat_L3='Coral Reef Shallow', GeoAttach='Atoll Lagoon',
             Relief='High', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Atoll Deep Patch Coral Reef':
        dict(Feat_L3='Coral Reef Deep', GeoAttach='Atoll Lagoon',
             Relief='Medium', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Atoll Shallow Rim Coral Reef':
        dict(Feat_L3='Coral Reef Shallow', GeoAttach='Atoll Rim',
             Relief='High', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Atoll Shallow Flow Coral Reef':
        dict(Feat_L3='Coral Reef Shallow', GeoAttach='Atoll Rim',
             Relief='Medium', FlowInflu='Yes', SO_L2='Carbonate', Paleo='No'),
    'Atoll Deep Flow Coral Reef':
        dict(Feat_L3='Coral Reef Deep', GeoAttach='Atoll Rim',
             Relief='Medium', FlowInflu='Yes', SO_L2='Carbonate', Paleo='No'),
    'Atoll Shallow Platform Coral Reef':
        dict(Feat_L3='Coral Reef Shallow', GeoAttach='Atoll Platform',
             Relief='High', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Atoll Deep Platform Coral Reef':
        dict(Feat_L3='Coral Reef Deep', GeoAttach='Atoll Platform',
             Relief='Medium', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Atoll Platform':
        dict(Feat_L3='Atoll Platform', GeoAttach='Atoll Platform',
             Relief='High', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),

    # Islands / cays -------------------------------------------------
    'Vegetated Cay':
        dict(Feat_L3='Cay Vegetated', GeoAttach='Land',
             Relief='Medium', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Unvegetated Cay':
        dict(Feat_L3='Cay Unvegetated', GeoAttach='Land',
             Relief='Medium', FlowInflu='No', SO_L2='Carbonate', Paleo='No'),
    'Island':
        dict(Feat_L3='Island', GeoAttach='Land',
             Relief='High', FlowInflu='No', SO_L2='Terrigenous', Paleo='No'),
    'Mainland':
        dict(Feat_L3='Mainland', GeoAttach='Land',
             Relief='High', FlowInflu='No', SO_L2='Terrigenous', Paleo='No'),
    'Man Made':
        dict(Feat_L3='Artificial Structure', GeoAttach='Isolated',
             Relief='High', FlowInflu='No', SO_L2='NA', Paleo='No'),
}

# ------------------------------------------------------------------ #
def load_data(path):
    if not os.path.exists(path):
        sys.exit(f"Input shapefile not found: {path}")
    return gpd.read_file(path)

def ensure_outdir(path):
    d = os.path.dirname(path)
    if not os.path.exists(d):
        os.makedirs(d)

def translate_row(row):
    rb = row['RB_Type_L3']
    info = MAP.get(rb, None)
    if info is None:
        sys.stderr.write(f'Warning: RB_Type_L3 value not mapped: {rb}\n')
        info = dict(Feat_L3='Unknown', GeoAttach='Unknown', Relief='Unknown',
                    FlowInflu='Unknown', SO_L2='Unknown', Paleo='N')
    return info

def main():
    
    # don't overwrite any manual edits
    if os.path.exists(OUT_PATH):
        sys.exit(f"Output file already exists: {OUT_PATH}\n"
                 "Please move or delete it before running this script.")
                 
    gdf = load_data(IN_PATH)
    
    # Remove features with invalid or empty geometries
    initial_count = len(gdf)
    gdf = gdf[~gdf.geometry.is_empty & ~gdf.geometry.isna()]
    removed_count = initial_count - len(gdf)
    if removed_count > 0:
        print(f"Removed {removed_count} features with invalid or empty geometries")
    
    # Reproject from EPSG:3857 to EPSG:4326
    print(f"Original CRS: {gdf.crs}")
    gdf = gdf.to_crs(epsg=4326)
    print(f"Reprojected to CRS: {gdf.crs}")

    # Rename existing columns
    rename_map = {'ImgSrc': 'EdgeSrc', 'Edg_acc': 'EdgeAcc_m'}
    gdf = gdf.rename(columns=rename_map)

    # ---------------------------------------------------------------- #
    # Convert EdgeAcc_m (string) → nullable integer, 'NA' → <NA>, errors logged
    # ---------------------------------------------------------------- #
    for idx, row in gdf.iterrows():
        raw = row['EdgeAcc_m']
        if pd.isna(raw) or raw is None or str(raw).strip().upper() == 'NA' or str(raw).strip() == '':
            gdf.at[idx, 'EdgeAcc_m'] = pd.NA
        else:
            try:
                gdf.at[idx, 'EdgeAcc_m'] = int(raw)
            except Exception:
                sys.stderr.write(
                    f"Error converting EdgeAcc_m -> int at row index {idx}, "
                    f"RB_Type_L3='{row.get('RB_Type_L3')}', raw value='{raw}'\n"
                )
                gdf.at[idx, 'EdgeAcc_m'] = pd.NA

    # Cast to pandas' nullable Int64 dtype
    gdf['EdgeAcc_m'] = gdf['EdgeAcc_m'].astype('Int64')

    # Add new columns with defaults
    new_cols = ['Feat_L3', 'GeoAttach', 'Relief', 'FlowInflu', 'SO_L2', 'Paleo']
    for col in new_cols:
        gdf[col] = 'Unknown'

    # Populate from mapping
    for idx, row in gdf.iterrows():
        attrs = translate_row(row)
        for k, v in attrs.items():
            gdf.at[idx, k] = v

    # Reorder / keep only desired columns *and* keep the geometry
    keep = [
        'EdgeSrc', 'Notes', 'FeatConf', 'TypeConf', 'EdgeAcc_m',
        'RB_Type_L3', 'DepthCat', 'DepthCatSr'
    ] + new_cols + ['geometry']

    # Subset — this preserves the GeoDataFrame subclass
    gdf = gdf[keep]

    # Add DebugID field with format 'NW_{row number}'
    gdf['DebugID'] = ['NW_{}'.format(i) for i in range(len(gdf))]
    
    # Save
    ensure_outdir(OUT_PATH)
    gdf.to_file(OUT_PATH)

    print(f'Saved transformed shapefile to {OUT_PATH}')

if __name__ == '__main__':
    main()
