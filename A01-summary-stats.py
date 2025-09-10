"""
This script outputs simple summary statistics about the area and number of mapped
features. It also performs a dissolve on the RB_Type_L2 classification to see the 
approximate effect of combining 'Coral Reef' and 'Coral Reef Flat'. This will also 
merge 'High Intertidal Coral Reefs' with surrounding 'Coral Reef' features. This 
makes the coral reefs larger, but less of them.

This script also outputs summary statistics  before and after the dissolved 
features. Additionally, it provides a breakdown by feature size class based on
Area_km2 with three classes:
 - Small (<0.01 km2)
 - Medium (0.01-1 km2)
 - Large (>1 km2)
It also prints a regional summary of RB_Type_L2 using the 'Dataset' field,
combining 'GBR Features' and 'Aus-Trop-Reef-Features_v0-1' as 'GBR'.
"""
import geopandas as gpd
import pandas as pd
import os

INPUT_SHP = "data/in-3p/Aus-Trop-Reef-Features_v0-1/AU_NESP-MaC-3-17_AIMS_Aus-Trop-Reef-Features_v0-1.shp"
OUTPUT_SHP = "working/A01/Aus-Trop-Reef-Features_v0-1_RB-Type-L2.shp"

# Ensure output directory exists
os.makedirs(os.path.dirname(OUTPUT_SHP), exist_ok=True)

# Load the shapefile
gdf = gpd.read_file(INPUT_SHP)

# Helper to classify features by size (Area_km2)
SIZE_LABELS = [
    "Very Small (<0.01 km2)",
    "Small (0.01-0.1 km2)",
    "Medium (0.1-1 km2)",
    "Large (>1 km2)",
]

def classify_size(area):
    if pd.isna(area):
        return None
    if area < 0.01:
        return SIZE_LABELS[0]
    elif area <= 0.1:
        return SIZE_LABELS[1]
    elif area <= 1.0:
        return SIZE_LABELS[2]
    else:
        return SIZE_LABELS[3]

# Group by RB_Type_L3, calculate total area and feature count
summary = (
    gdf.groupby("RB_Type_L3")
       .agg(
           Feature_Count=("RB_Type_L3", "count"),
           Total_Area_km2=("Area_km2", "sum")
       )
       .reset_index()
       .sort_values("Total_Area_km2", ascending=False)
)

# Print or export the summary
print(summary)

# L3 summary by size class
gdf["Size_Class"] = pd.Categorical(
    gdf["Area_km2"].apply(classify_size), categories=SIZE_LABELS, ordered=True
)
l3_by_size = (
    gdf.dropna(subset=["Size_Class"])  # drop rows where Area_km2 was missing
    .groupby(["RB_Type_L3", "Size_Class"], observed=True) 
       .agg(
           Feature_Count=("Size_Class", "count"),
           Total_Area_km2=("Area_km2", "sum")
       )
       .reset_index()
       .sort_values(["RB_Type_L3", "Size_Class"]) 
)
print("\nRB_Type_L3 summary by Size_Class:")
print(l3_by_size)

summary = (
    gdf.groupby("RB_Type_L2")
       .agg(
           Feature_Count=("RB_Type_L2", "count"),
           Total_Area_km2=("Area_km2", "sum")
       )
       .reset_index()
       .sort_values("Total_Area_km2", ascending=False)
)

# Print or export the summary
print(summary)

# L2 summary by size class (pre-dissolve)
l2_by_size_pre = (
    gdf.dropna(subset=["Size_Class"]) 
    .groupby(["RB_Type_L2", "Size_Class"], observed=True) 
       .agg(
           Feature_Count=("Size_Class", "count"),
           Total_Area_km2=("Area_km2", "sum")
       )
       .reset_index()
       .sort_values(["RB_Type_L2", "Size_Class"]) 
)
print("\nRB_Type_L2 summary by Size_Class (pre-dissolve):")
print(l2_by_size_pre)

# Regional summary by RB_Type_L2 using 'Dataset' mapping to regions
DATASET_TO_REGION = {
    "CS Features": "CS",
    "GBR Features": "GBR",
    "NW-Aus-Features_v0-4": "NW-Aus",
    "TS Features": "TS",
    "Aus-Trop-Reef-Features_v0-1": "GBR",  # combine with GBR
}

if "Dataset" in gdf.columns:
    gdf["Region"] = gdf["Dataset"].map(DATASET_TO_REGION)

    def print_region_summary(region_code: str):
        sub = gdf[gdf["Region"] == region_code]
        if sub.empty:
            print(f"\nRegion {region_code}: no features found.")
            return
        reg_summary = (
            sub.groupby("RB_Type_L2")
               .agg(
                   Feature_Count=("RB_Type_L2", "count"),
                   Total_Area_km2=("Area_km2", "sum")
               )
               .reset_index()
               .sort_values("Total_Area_km2", ascending=False)
        )
        print(f"\nRB_Type_L2 summary for region {region_code} (pre-dissolve):")
        print(reg_summary)

    for region in ["TS", "CS", "NW-Aus", "GBR"]:
        print_region_summary(region)
else:
    print("\nNote: 'Dataset' column not found; skipping regional RB_Type_L2 summary.")

print("Cleaning geometry to fix topology errors.")
# Clean geometries to fix topology errors
gdf["geometry"] = gdf["geometry"].buffer(0)

print("Dissolving features by RB_Type_L2 to create summary features.")
# Dissolve by RB_Type_L2, keeping only the classification
# Ensure we don't merge features across datasets: dissolve by Dataset and RB_Type_L2
if "Dataset" not in gdf.columns:
    raise ValueError("Expected 'Dataset' column to be present for regional dissolve.")
dissolved = (
    gdf.dissolve(by=["Dataset", "RB_Type_L2"], as_index=False)[["Dataset", "RB_Type_L2", "geometry"]]
)

print("Exploding multipart polygons into singlepart polygons.")
# Explode multipart polygons into singlepart polygons
singleparts = dissolved.explode(index_parts=False).reset_index(drop=True)

# Reproject to EPSG:3112 for accurate area calculation (do not overwrite original geometry)
singleparts_proj = singleparts.to_crs(epsg=3112)
singleparts["Area_km2"] = singleparts_proj.geometry.area / 1e6

# Attach Region and Size_Class to post-dissolve singleparts
if 'DATASET_TO_REGION' not in globals():
    DATASET_TO_REGION = {
        "CS Features": "CS",
        "GBR Features": "GBR",
        "NW-Aus-Features_v0-4": "NW-Aus",
        "TS Features": "TS",
        "Aus-Trop-Reef-Features_v0-1": "GBR",
    }
singleparts["Region"] = singleparts["Dataset"].map(DATASET_TO_REGION)
singleparts["Size_Class"] = pd.Categorical(
    singleparts["Area_km2"].apply(classify_size), categories=SIZE_LABELS, ordered=True
)


# Save to shapefile (original CRS) with Dataset/Region/Size_Class and Area
singleparts.to_file("working/A01/Aus-Trop-Reef-Features_v0-1_RB-Type-L2.shp")

# Summarise by RB_Type_L2: count and total area
summary = (
    singleparts.groupby("RB_Type_L2")
    .agg(
        Feature_Count=("RB_Type_L2", "count"),
        Total_Area_km2=("Area_km2", "sum")
    )
    .reset_index()
    .sort_values("Total_Area_km2", ascending=False)
)

print(summary)

# L2 summary by size class (post-dissolve, singlepart features)
l2_by_size_post = (
    singleparts.dropna(subset=["Size_Class"]) 
    .groupby(["RB_Type_L2", "Size_Class"], observed=True) 
       .agg(
           Feature_Count=("Size_Class", "count"),
           Total_Area_km2=("Area_km2", "sum")
       )
       .reset_index()
       .sort_values(["RB_Type_L2", "Size_Class"]) 
)
print("\nRB_Type_L2 summary by Size_Class (post-dissolve):")
print(l2_by_size_post)

# Post-dissolve regional summary by RB_Type_L2 and Size_Class
def print_region_size_summary_post(region_code: str):
    sub = singleparts[singleparts["Region"] == region_code]
    if sub.empty:
        print(f"\nRegion {region_code} (post-dissolve): no features found.")
        return
    reg = (
        sub.dropna(subset=["Size_Class"]) 
           .groupby(["RB_Type_L2", "Size_Class"], observed=True)
           .agg(
               Feature_Count=("Size_Class", "count"),
               Total_Area_km2=("Area_km2", "sum")
           )
           .reset_index()
           .sort_values(["RB_Type_L2", "Size_Class"]) 
    )
    print(f"\nRB_Type_L2 by Size_Class (post-dissolve) for region {region_code}:")
    print(reg)

for region in ["TS", "CS", "NW-Aus", "GBR"]:
    print_region_size_summary_post(region)