#!/usr/bin/env python3
"""
04-v0-3-merge-rocky-reefs.py
───────────────────────────
Merge AIMS "semi-auto" intertidal rocky-reef polygons into the
North & West-Australia v0-3 master layer (NW-Aus-Features), dissolving ONLY where the 
new intertidal rocky reefs touch existing rocky reef reefs (Feat_L3 = 'Rocky Reef').
The AIMS rocky-reef polygons should be considers as an extension of the existing
rocky reef features in the NW-Aus-Features. 
The attributes of the dissolved polygons should come from the NW-Aus-Features layer.
Any *new* intertidal rocky-reef polygons (those that were not dissolved with existing
reefs) are added with default attributes. 
Other features in the NW-Aus-Features layer are copied across unchanged.

Input
-----
* working/03/NW-Aus-Features_v0-3-cross-walk.shp
* {download_path}/AU_AIMS_Rocky-reefs/
    AU_NESP-MaC-3-17_AIMS_Rocky-reefs_V1.shp        (EPSG:4326)

Output
------
* working/04/NW-Aus-Features_v0-3-rocks.shp

Notes
-----
•  Both inputs are already EPSG:4326 -> no re-projection.
"""

import os
import sys
import configparser
from pathlib import Path

import pandas as pd  # Add pandas import
import geopandas as gpd
from shapely.ops import unary_union

# -------------------------------------------------------------------- #
# 1. Resolve paths
# -------------------------------------------------------------------- #
NW_PATH = "working/03/NW-Aus-Features_v0-3-cross-walk.shp"

config = configparser.ConfigParser()
config.read("config.ini")
DL_PATH   = Path(config.get("general", "in_3p_path"))
AIMS_PATH = f"{DL_PATH}/AU_AIMS_Rocky-reefs/AU_NESP-MaC-3-17_AIMS_Rocky-reefs_V1.shp"

OUT_DIR   = Path("working/04")  # Convert to Path object
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH  = f"{OUT_DIR}/NW-Aus-Features_v0-3-rocks.shp"

print(f"Loading NW master layer …  ({NW_PATH})")
gdf_nw = gpd.read_file(NW_PATH)

print(f"Loading AIMS semi-auto rocky reefs …  ({AIMS_PATH})")
gdf_aims = gpd.read_file(AIMS_PATH)

# -------------------------------------------------------------------- #
# 1.5. Set up feature tracking for debugging
# -------------------------------------------------------------------- #
print("Setting up tracking for NW features debugging...")
# Verify DebugID exists in NW dataset
if 'DebugID' not in gdf_nw.columns:
    print("WARNING: DebugID column not found in NW dataset. Creating it...")
    gdf_nw['DebugID'] = [f"NW_{i}" for i in range(len(gdf_nw))]

# Add debug status for tracking
gdf_nw['debug_status'] = "original"

# Create a copy of original NW IDs for later comparison
nw_ids_original = set(gdf_nw['DebugID'])

# Store a copy of the original dataframe for reporting purposes
gdf_nw_original = gdf_nw.copy()

# -------------------------------------------------------------------- #
# 2. Prepare AIMS rocky‑reef attributes so they match NW schema
# -------------------------------------------------------------------- #
# Make sure *all* NW columns exist in the AIMS dataframe (as Nulls)
for col in gdf_nw.columns:
    if col not in gdf_aims.columns and col != "geometry":
        gdf_aims[col] = None

# Hard‑code defaults requested for NEW *intertidal* rocky reefs
default_vals = dict(
    EdgeSrc   = "Semi-auto rocky reef",
    Notes     = None,
    EdgeAcc_m = 40,
    RB_Type_L3= "Fringing Rocky Reef",
    Feat_L3   = "Rocky Reef",
    GeoAttach = "Fringing",
    Relief    = "Low",
    FlowInflu = "None",
    SO_L2     = "Terrigenous",
    Paleo     = "No",
    FeatConf  = "Medium",
    TypeConf  = "Medium",
    DepthCat  = "Very Shallow",
    DepthCatSr= "S2 Infrared"
)

# Make sure all default_vals keys exist as columns in AIMS dataframe
for col in default_vals.keys():
    if col not in gdf_aims.columns:
        gdf_aims[col] = None

# Apply defaults only to empty cells
for k, v in default_vals.items():
    if v is not None:
        gdf_aims[k] = gdf_aims[k].fillna(v)
    else:
        # For columns with None as default, use alternative approach
        gdf_aims.loc[gdf_aims[k].isna(), k] = None

# -------------------------------------------------------------------- #
# 3. Identify NW rocky‑reef polygons & build spatial index
# -------------------------------------------------------------------- #
nw_rock_mask = gdf_nw["Feat_L3"].str.fullmatch(r"Rocky Reef", na=False)
# Store original indices before resetting
gdf_nw_rock = gdf_nw[nw_rock_mask].copy()
original_indices = gdf_nw_rock.index.tolist()
gdf_nw_rock = gdf_nw_rock.reset_index(drop=True)  

# Create mapping between new and original indices
idx_mapping = {new_idx: orig_idx for new_idx, orig_idx in enumerate(original_indices)}

sindex = gdf_nw_rock.sindex

# -------------------------------------------------------------------- #
# 4. Split AIMS polygons into "touches NW" and "new"
# -------------------------------------------------------------------- #
touch_idxs = set()          # indices of AIMS rows that touch NW rocky reefs
nw_groups  = {}             # NW index ➜ list of touching AIMS geometries
nw_connections = {}         # Track which NW features are connected via AIMS polygons

# Add a dictionary to track which NW features each AIMS polygon was merged with
merge_tracking = {}  # AIMS_id -> list of NW_ids

print("Tagging AIMS polygons that touch existing NW rocky-reef …")
for i, row in gdf_aims.iterrows():
    # candidate NW indices via bbox query, then precise test
    possibles = list(sindex.intersection(row.geometry.bounds))
    touched_nws = []  # Track which NW features this AIMS polygon touches
    
    for nw_idx in possibles:
        if row.geometry.touches(gdf_nw_rock.at[nw_idx, "geometry"]) or \
           row.geometry.intersects(gdf_nw_rock.at[nw_idx, "geometry"]):
            touch_idxs.add(i)
            nw_groups.setdefault(nw_idx, []).append(row.geometry)
            
            # Track which NW features this AIMS polygon will merge with
            aims_id = gdf_aims.at[i, 'DebugID'] if 'DebugID' in gdf_aims.columns else f"AIMS_{i}"
            nw_id = gdf_nw_rock.at[nw_idx, 'DebugID']
            
            # Store all NW ids this AIMS polygon connects to
            touched_nws.append(nw_idx)
            
            # Update connection tracking for network analysis
            if len(touched_nws) > 1:
                # Connect all touched NW features with each other
                for idx1 in touched_nws:
                    for idx2 in touched_nws:
                        if idx1 != idx2:
                            nw_connections.setdefault(idx1, set()).add(idx2)
                            nw_connections.setdefault(idx2, set()).add(idx1)
    
    # Update status of this AIMS polygon
    if touched_nws:
        # Join all NW IDs this AIMS polygon connects to
        connected_nw_ids = [gdf_nw_rock.at[idx, 'DebugID'] for idx in touched_nws]
        gdf_aims.at[i, 'debug_status'] = "merged_with_" + "_and_".join(connected_nw_ids)
        
        # Also update merge tracking
        aims_id = gdf_aims.at[i, 'DebugID'] if 'DebugID' in gdf_aims.columns else f"AIMS_{i}"
        merge_tracking[aims_id] = connected_nw_ids

# Update status of AIMS polygons that don't touch NW
gdf_aims.loc[~gdf_aims.index.isin(touch_idxs), 'debug_status'] = "new_feature"

aims_touch = gdf_aims.loc[list(touch_idxs)]
aims_new   = gdf_aims.drop(list(touch_idxs))

print(f"    • {len(aims_touch)} AIMS polygons dissolve into {len(nw_groups)} NW rocky-reef features")
print(f"    • {len(aims_new)} AIMS polygons are NEW intertidal rocky reefs")

# -------------------------------------------------------------------- #
# 5. Find connected components (NW features that need to be dissolved together)
# -------------------------------------------------------------------- #
print("Finding connected NW rocky reef features...")

# Function to find connected components in graph
def find_connected_components(graph):
    visited = set()
    components = []
    
    def dfs(node, component):
        visited.add(node)
        component.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, component)
    
    for node in graph:
        if node not in visited:
            component = []
            dfs(node, component)
            components.append(component)
    
    return components

# Find connected components
connected_components = find_connected_components(nw_connections)
print(f"Found {len(connected_components)} groups of connected NW rocky reef features")

# Track NW features that will be removed (dissolved into others)
nw_features_to_remove = set()

# -------------------------------------------------------------------- #
# 6. Dissolve geometries where AIMS + NW touch
# -------------------------------------------------------------------- #
if nw_groups:
    print("Dissolving geometries …")
    
    # For debugging
    modified_feat_types = {}

# First, handle isolated NW features (those that touch AIMS but not other NW features)
isolated_nw_indices = set(nw_groups.keys()) - set().union(*[set(comp) for comp in connected_components])
for nw_idx in isolated_nw_indices:
    # Get the original index in the full NW dataset
    original_idx = idx_mapping[nw_idx]
    
    # Optional verification step - record what types we're modifying
    feat_type = gdf_nw.at[original_idx, "Feat_L3"]
    modified_feat_types.setdefault(feat_type, 0)
    modified_feat_types[feat_type] += 1
    
    if feat_type != "Rocky Reef":
        print(f"WARNING: Attempting to modify non-rocky reef feature: {feat_type} (ID: {gdf_nw.at[original_idx, 'DebugID']})")
    
    all_geoms = [gdf_nw_rock.at[nw_idx, "geometry"]] + nw_groups[nw_idx]
    dissolved = unary_union(all_geoms)
    gdf_nw.at[original_idx, "geometry"] = dissolved
    gdf_nw.at[original_idx, "debug_status"] = "modified_isolated"

# Then, handle connected components (groups of NW features that need to be merged)
for component in connected_components:
    if not component:  # Skip empty components
        continue
        
    # Use the first NW feature's attributes for the result
    primary_nw_idx = component[0]
    primary_original_idx = idx_mapping[primary_nw_idx]
    
    # Collect all geometries: primary NW + all other NW features + all AIMS geometries
    all_geoms = [gdf_nw_rock.at[primary_nw_idx, "geometry"]]
    
    # Add AIMS geometries that touch the primary NW feature
    if primary_nw_idx in nw_groups:
        all_geoms.extend(nw_groups[primary_nw_idx])
    
    # Add other NW features and their touching AIMS geometries
    for other_nw_idx in component[1:]:
        all_geoms.append(gdf_nw_rock.at[other_nw_idx, "geometry"])
        if other_nw_idx in nw_groups:
            all_geoms.extend(nw_groups[other_nw_idx])
        
        # Mark this NW feature for removal (will be dissolved into primary)
        other_original_idx = idx_mapping[other_nw_idx]
        nw_features_to_remove.add(other_original_idx)
    
    # Record what types we're modifying
    feat_type = gdf_nw.at[primary_original_idx, "Feat_L3"]
    modified_feat_types.setdefault(feat_type, 0)
    modified_feat_types[feat_type] += 1
    
    if feat_type != "Rocky Reef":
        print(f"WARNING: Attempting to modify non-rocky reef feature: {feat_type} (ID: {gdf_nw.at[primary_original_idx, 'DebugID']})")
    
    # Dissolve all geometries
    dissolved = unary_union(all_geoms)
    gdf_nw.at[primary_original_idx, "geometry"] = dissolved
    gdf_nw.at[primary_original_idx, "debug_status"] = f"primary_with_{len(component)-1}_others"

# Print summary of modified feature types
if nw_groups:
    print("Summary of modified feature types:")
    for feat_type, count in modified_feat_types.items():
        print(f"  • {feat_type}: {count} features")
    
    if nw_features_to_remove:
        print(f"Removing {len(nw_features_to_remove)} NW features that were dissolved into others")
        gdf_nw = gdf_nw.drop(index=list(nw_features_to_remove))

# -------------------------------------------------------------------- #
# 7. Append NEW intertidal rocky reefs to NW dataframe
# -------------------------------------------------------------------- #
print("Appending NEW intertidal rocky-reef polygons …")
gdf_result = gpd.GeoDataFrame(
    pd.concat([gdf_nw, aims_new], ignore_index=True),  # Use pd.concat instead of gpd.concat
    crs="EPSG:4326",
)

# -------------------------------------------------------------------- #
# 7.5. Validate output for missing NW features
# -------------------------------------------------------------------- #
print("\nValidating output for missing NW features...")

# Extract IDs from the output
output_ids = set(gdf_result['DebugID'])

# Find missing NW IDs
missing_nw_ids = nw_ids_original - output_ids

# Generate validation report
print(f"Validation results:")
print(f"  • Total original NW features: {len(nw_ids_original)}")
print(f"  • Total NW features in output: {len(output_ids.intersection(nw_ids_original))}")
print(f"  • Missing NW features: {len(missing_nw_ids)}")

# Write detailed report for debugging
debug_report_path = f"{OUT_DIR}/missing_nw_features_report.csv"
if missing_nw_ids:
    print(f"\nWARNING: {len(missing_nw_ids)} NW features are missing from output!")
    print(f"These are expected to be missing because they were dissolved into other features.")
    print(f"Writing detailed report to {debug_report_path}")
    
    # Create report dataframe
    missing_features = []
    
    # Get details of missing NW features
    for nw_id in missing_nw_ids:
        # Look up in the original dataframe instead of the current one
        matches = gdf_nw_original[gdf_nw_original['DebugID'] == nw_id]
        if not matches.empty:
            feature_info = matches.iloc[0].to_dict()
            feature_info['geometry'] = str(feature_info['geometry'])  # Convert geometry to string
            missing_features.append(feature_info)
        else:
            print(f"  Warning: Could not find details for missing feature {nw_id}")
    
    # Create and save report
    if missing_features:
        missing_df = pd.DataFrame(missing_features)
        missing_df.to_csv(debug_report_path, index=False)
else:
    print("All NW features are accounted for in the output.")

# -------------------------------------------------------------------- #
# 8. Save
# -------------------------------------------------------------------- #
print(f"Writing result to {OUT_PATH}")
gdf_result.to_file(OUT_PATH)

print("Done - merged rocky-reef layer written.")
