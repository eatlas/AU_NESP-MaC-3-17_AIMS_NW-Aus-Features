# In this standalone script we demonstrate that the reef mapping in this project had identified a lot of previously unmapped reefs, 
# particularly fringing reefs and rocky reefs. To gain an estimate for the presentation we mapped the AHO marine chart uncharted 
# areas from the ENC simplified series WMS service for the Gulf of Carpentaria, as these uncharted areas were pretty much 
# guaranteed to be areas where reefs had not been mapped. We knew from previous work that there were unmapped reefs in 
# GOC even in the charted areas and so this analysis would provide an underestimate, but representative estimate for the 
# number of reefs we had mapped that were previously unmapped.

# - Input data: AHO-Uncharted (AHO-Uncharted/AHO-Uncharted-areas_2025.shp)
# The boundary of the uncharted areas in the GOC were mapped manually from the ENC simplified series WMS service on 
# 13 March 2025. This covered the entire Gulf of Carpentaria. We did not map the whole of northern Australia.
# This dataset contains multiple polygons of each uncharted area. They have no attributes. Projection: EPSG:4368

# - Input data: GOC-Area (GOC-Area/GOC-Area.shp)
# The boundary of the GOC was digitised as a single polygon to cover the same area that was mapped by AHO-Uncharted. 
# The goal was to allow us to count the total number of mapped reefs in the same area covered by the AHO-Uncharted dataset. 
# This is a single polygon with no attributes. Projection: EPSG:4368

# - Input data: NW-Aus-Reef-Features
# This is the version of the reef mapping that we use for this analysis as it was the most up to date version at the
# time of development. Projection: EPSG:3857.

# In this script the features in Reef-Features combined with AHO-Uncharted and GOC-Area using spatial joins to work
# out the count of coral reefs and rocky reefs that are inside the uncharted area of the GOC and the GOC-Area. 
# This will help identify the percentage of reefs that were previously uncharted. The spatial join uses a simple 
# intersection which means that a reef feature that spans across the uncharted boundary will be counted as uncharted.
# 
# This script also provides a breakdown of the number of uncharted Fringing reefs (rocky and coral) as separate statistics
#
# This script outputs the counts and percentages for each reef type to standard out. It doesn't generate visualisations.
# This script uses Python, and GeoPandas
#
# Results:
# --- Reef Mapping Analysis Results ---
# Total Coral Reefs in GOC: 681
# Total Rocky Reefs in GOC: 481
# Total Reefs in GOC:       1162

# Reefs previously unmapped (in uncharted areas):
#   Coral Reefs:   329 (48.31%)
#   Rocky Reefs:   303 (62.99%)
#   Overall Reefs: 632 (54.39%)

# Breakdown of uncharted Fringing reefs:
#   Fringing Coral Reefs: 168
#   Fringing Rocky Reefs: 228

#!/usr/bin/env python3
import geopandas as gpd
import configparser
# Configuration ------------------------------------------------------
cfg = configparser.ConfigParser()
cfg.read("config.ini")
in_3p_path = cfg.get("general", "in_3p_path")
# in_3p_path = 'data/v1-0/in-3p'
version = cfg.get("general", "version")

def main():
    # File paths for input datasets
    aho_file = f"data/{version}/in/AHO-Uncharted/AHO-Uncharted-areas_2025.shp"
    goc_area_file = f"data/{version}/in/GOC-Area/GOC-Area.shp"
    reef_file = cfg.get("paths", "current_processed")
    #"data/stages/01-pre-merge/2025-03-09-Reef-Features_Ref1_RB/Reef Boundaries RB.shp"
    
    # Target CRS (the one used by AHO and GOC-Area, per project documentation)
    target_crs = "EPSG:4368"
    
    print("Loading datasets...")
    aho = gpd.read_file(aho_file)
    goc_area = gpd.read_file(goc_area_file)
    reef_features = gpd.read_file(reef_file)

    # ------------------------------------------------------------------------
    # Debugging info: Print initial CRS and bounding boxes
    print("\n--- Initial Dataset Information ---")
    print(f"AHO-Uncharted CRS: {aho.crs}")
    print(f"GOC-Area CRS:      {goc_area.crs}")
    print(f"Reef-Features CRS: {reef_features.crs}")
    
    print(f"\nAHO-Uncharted BBox: {aho.total_bounds}")
    print(f"GOC-Area BBox:      {goc_area.total_bounds}")
    print(f"Reef-Features BBox: {reef_features.total_bounds}")
    
    print(f"\nNumber of AHO polygons: {len(aho)}")
    print(f"Number of GOC polygons: {len(goc_area)}")
    print(f"Number of reef features: {len(reef_features)}")
    
    # ------------------------------------------------------------------------
    # Reproject datasets if needed
    if aho.crs is not None and aho.crs.to_string() != target_crs:
        print(f"\nReprojecting AHO from {aho.crs} to {target_crs}")
        aho = aho.to_crs(target_crs)
    if goc_area.crs is not None and goc_area.crs.to_string() != target_crs:
        print(f"Reprojecting GOC area from {goc_area.crs} to {target_crs}")
        goc_area = goc_area.to_crs(target_crs)
    if reef_features.crs is not None and reef_features.crs.to_string() != target_crs:
        print(f"Reprojecting Reef-Features from {reef_features.crs} to {target_crs}")
        reef_features = reef_features.to_crs(target_crs)

    # ------------------------------------------------------------------------
    # Debugging info: Print updated CRS and bounding boxes
    print("\n--- After Potential Reprojection ---")
    print(f"AHO-Uncharted CRS: {aho.crs}")
    print(f"GOC-Area CRS:      {goc_area.crs}")
    print(f"Reef-Features CRS: {reef_features.crs}")
    
    print(f"\nAHO-Uncharted BBox: {aho.total_bounds}")
    print(f"GOC-Area BBox:      {goc_area.total_bounds}")
    print(f"Reef-Features BBox: {reef_features.total_bounds}")
    
    # ------------------------------------------------------------------------
    # Spatial Analysis
    print("\nClipping reef features to GOC area...")
    # Use unary_union (deprecated in some versions, but still works):
    goc_union = goc_area.unary_union
    reef_in_goc = reef_features.clip(goc_union)
    
    print("Selecting reef features in uncharted areas...")
    aho_union = aho.unary_union
    reef_in_uncharted = reef_in_goc[reef_in_goc.geometry.intersects(aho_union)]
    
    # Define reef type categories
    coral_types = [
        'Coral Reef'
    ]
    rocky_types = [
        'Rocky Reef'
    ]
    
    # Count total reefs in the GOC area by type
    total_coral = reef_in_goc[reef_in_goc['RB_Type_L2'].isin(coral_types)].shape[0]
    total_rocky = reef_in_goc[reef_in_goc['RB_Type_L2'].isin(rocky_types)].shape[0]
    total_all = total_coral + total_rocky
    
    # Count reefs in the uncharted areas by type
    uncharted_coral = reef_in_uncharted[reef_in_uncharted['RB_Type_L2'].isin(coral_types)].shape[0]
    uncharted_rocky = reef_in_uncharted[reef_in_uncharted['RB_Type_L2'].isin(rocky_types)].shape[0]
    uncharted_all = uncharted_coral + uncharted_rocky
    

    
    # Calculate percentages
    perc_coral = (uncharted_coral / total_coral * 100) if total_coral > 0 else 0
    perc_rocky = (uncharted_rocky / total_rocky * 100) if total_rocky > 0 else 0
    perc_all = (uncharted_all / total_all * 100) if total_all > 0 else 0
    
    # Output the results
    print("\n--- Reef Mapping Analysis Results ---")
    print(f"Total Coral Reefs in GOC: {total_coral}")
    print(f"Total Rocky Reefs in GOC: {total_rocky}")
    print(f"Total Reefs in GOC:       {total_all}\n")
    
    print("Reefs previously unmapped (in uncharted areas):")
    print(f"  Coral Reefs:   {uncharted_coral} ({perc_coral:.2f}%)")
    print(f"  Rocky Reefs:   {uncharted_rocky} ({perc_rocky:.2f}%)")
    print(f"  Overall Reefs: {uncharted_all} ({perc_all:.2f}%)\n")
    

        # ------------------------------------------------------------------------
    # Additional Summary Statistics for Australian Reefs (Small vs Large)
    print("\n--- Additional Summary Statistics for Australian Reefs (Small vs Large) ---")
    
  
    reef_australia = reef_features.copy()
    
    # Create a new column 'size_cat' based on the Area_km2 threshold of 0.01 km²
    reef_australia['size_cat'] = reef_australia['Area_km2'].apply(lambda x: 'Large' if x > 0.01 else 'Small')
    
    
    # Filter Australian reefs by coral and rocky types
    coral_australia = reef_australia[reef_australia['RB_Type_L2'].isin(coral_types)]
    rocky_australia = reef_australia[reef_australia['RB_Type_L2'].isin(rocky_types)]
    
    # Group by the size category and calculate count and total area for coral reefs
    coral_stats = coral_australia.groupby('size_cat').agg(
        count=('size_cat', 'size'),
        total_area=('Area_km2', 'sum')
    )
    
    # Group by the size category and calculate count and total area for rocky reefs
    rocky_stats = rocky_australia.groupby('size_cat').agg(
        count=('size_cat', 'size'),
        total_area=('Area_km2', 'sum')
    )
    
    # Output the results
    print("\nAustralian Coral Reefs Summary:")
    print(coral_stats)
    
    print("\nAustralian Rocky Reefs Summary:")
    print(rocky_stats)


if __name__ == "__main__":
    main()
