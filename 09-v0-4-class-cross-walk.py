"""
This script performs a cross walk between the original RB_Type_L3 used in version v0-3 of 
this dataset and version v0-4. The classification was adjusted to split the classification
into two parts: 
1. Named classification (RB_Type_L3) that communicates the key distinct quality of the feature
2. Attributes that describe variable qualities within a Named classification type. These
include: 
- Attachment: Indicates this feature is free standing or attached to the mainland or an island.
Possible values: Fringing, Isolated, Atoll, Land.
- DepthCat: Depth category of the feature. Possible values: Land, Intertidal, Very Shallow, Shallow, Deep.
This is unchanged from v0-3, except with the addition of 'Land' and 'Intertidal' categories.
In general the DepthCat will be automatically assigned based on the depth of the feature, derived
from bathymetry data, however where there is a additional source of information this category can
be set manually.

Previously in RB_Type_L3 the attachment and some of the depth categories were encoded in the name.
In v0-3 of the dataset we split the RB_Type_L3 into Feat_L3 and 5 attributes. The problem with this
approachs was that with so many attributes data entry was too time consuming. 

In this script we use a lookup table (data/v0-4/RB_Type_L3_v0-3_to_v0-4_cross_walk_LUT.csv) 
to map the old RB_Type_L3 to the new RB_Type_L3 and attributes.

The input shapefile data/v0-3_qc-1/NW-Aus-Features_v0-3.shp. The output shapefile is
data/v0-4/out/NW-Aus-Features_v0-4.shp.

We map the v0-3 RB_Type_L3 attribute using the 'RB_Type_L3_v0-3' attribute in the lookup table to
find the associated RB_Type_L3_v0-4 and Attachment attribute.

Loading the NW-Aus-Features_v0-3.shp is reporting that 

"""

import os
import pandas as pd
import geopandas as gpd

from shapely.geometry.polygon import orient
from shapely.geometry import Polygon, MultiPolygon

from shapely.geometry.polygon import orient

def is_ccw(ring):
    # Returns True if the ring is counter-clockwise
    # Shapely >=2.0: use .is_ccw, older: use signed_area
    try:
        return ring.is_ccw
    except AttributeError:
        # For older shapely
        from shapely.geometry.polygon import LinearRing
        return LinearRing(ring.coords).is_ccw
    

def fix_winding(geom):
    if isinstance(geom, Polygon):
        return orient(geom, sign=1.0)  # Ensures exterior is CCW
    elif isinstance(geom, MultiPolygon):
        return MultiPolygon([orient(poly, sign=1.0) for poly in geom.geoms])
    else:
        return geom

def crosswalk_classification():
    """
    Performs a cross walk between the original RB_Type_L3 used in version v0-3 of 
    this dataset and version v0-4. Maps the old classification to the new classification
    and attribute system based on a lookup table.
    """
    # Define input and output paths
    input_shapefile = "working/02/Reef_Boundaries_Clean.shp"
    lookup_table = "data/v0-4/in/RB_Type_L3_v0-3_to_v0-4_crosswalk.csv"

    # Save to the working output so we don't accidentally overwrite 
    # Any post manual edits to the v0-4 data
    output_shapefile = "working/09/Reef-Boundaries_v0-4.shp"
    warning_outfile = "working/09/Reef-Boundaries_v0-4_winding-warn.shp"

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_shapefile), exist_ok=True)

    # Read input data
    print(f"Reading input shapefile: {input_shapefile}")
    features_gdf = gpd.read_file(input_shapefile)

    features_gdf['geometry'] = features_gdf['geometry'].apply(fix_winding)

    # Check if the input data is valid as we were getting 
    # RuntimeWarning: data/v0-3_qc-1/out/NW-Aus-Features_v0-3.shp contains polygon(s) 
    # with rings with invalid winding order. Autocorrecting them, but that shapefile 
    # should be corrected using ogr2ogr for example.
    invalid_features = []
    for idx, geom in enumerate(features_gdf.geometry):
        if isinstance(geom, Polygon):
            # Exterior should be counter-clockwise (CCW)
            if not is_ccw(geom.exterior):
                invalid_features.append(idx)
        elif isinstance(geom, MultiPolygon):
            for poly in geom.geoms:
                if not is_ccw(poly.exterior):
                    invalid_features.append(idx)
                    break

    if invalid_features:
        print(f"Features with invalid winding order: {invalid_features}")
        # Save these features to a shapefile for inspection
        warning_gdf = features_gdf.iloc[invalid_features]
        
        os.makedirs(os.path.dirname(warning_outfile), exist_ok=True)
        print(f"Saving features with winding warnings to {warning_outfile}")
        warning_gdf.to_file(warning_outfile)
    else:
        print("No invalid winding order detected in polygon exteriors.")
    
    print(f"Reading lookup table: {lookup_table}")
    crosswalk_df = pd.read_csv(lookup_table)

    # Remove rows with blank RB_Type_L3_v0-3 (these are new classes, not needed for mapping)
    crosswalk_df = crosswalk_df.dropna(subset=['RB_Type_L3_v0-3'])

    # Expand rows where RB_Type_L3_v0-3 contains semicolons
    crosswalk_df['RB_Type_L3_v0-3'] = crosswalk_df['RB_Type_L3_v0-3'].astype(str)
    crosswalk_df['RB_Type_L3_v0_3_split'] = crosswalk_df['RB_Type_L3_v0-3'].str.split(';')
    crosswalk_df = crosswalk_df.explode('RB_Type_L3_v0_3_split')
    crosswalk_df['RB_Type_L3_v0-3'] = crosswalk_df['RB_Type_L3_v0_3_split'].str.strip()
    crosswalk_df = crosswalk_df.drop(columns=['RB_Type_L3_v0_3_split'])

    # Remove any rows that became empty after splitting
    crosswalk_df = crosswalk_df[crosswalk_df['RB_Type_L3_v0-3'] != '']

    # Print some information about the datasets
    print(f"Loaded {len(features_gdf)} features from {input_shapefile}")
    print(f"Loaded {len(crosswalk_df)} mappings from {lookup_table}")

    # Check if the required columns exist
    if 'RB_Type_L3' not in features_gdf.columns:
        raise ValueError(f"Input shapefile missing 'RB_Type_L3' column")

    if 'RB_Type_L3_v0-3' not in crosswalk_df.columns:
        raise ValueError(f"Crosswalk table missing 'RB_Type_L3_v0-3' column")
    
    if 'RB_Type_L3_v0-4' not in crosswalk_df.columns:
        raise ValueError(f"Crosswalk table missing 'RB_Type_L3_v0-4' column")
        
    if 'Attachment' not in crosswalk_df.columns:
        raise ValueError(f"Crosswalk table missing 'Attachment' column")

    # Check for duplicate mappings in the lookup table
    duplicates = crosswalk_df['RB_Type_L3_v0-3'].duplicated()
    if duplicates.any():
        duplicate_values = crosswalk_df.loc[duplicates, 'RB_Type_L3_v0-3'].tolist()
        raise ValueError(f"Duplicate mappings found in lookup table for: {duplicate_values}")

    # Rename the column in crosswalk_df to match the column in features_gdf for merging
    crosswalk_df = crosswalk_df.rename(columns={'RB_Type_L3_v0-3': 'RB_Type_L3'})

    # Count the frequency of each RB_Type_L3 value in the input data
    value_counts = features_gdf['RB_Type_L3'].value_counts()
    print("\nFeatures by RB_Type_L3 in input data:")
    for value, count in value_counts.items():
        print(f"  - {value}: {count}")

    # Merge the datasets on the RB_Type_L3 column
    print("\nMerging datasets...")
    merged_gdf = features_gdf.merge(crosswalk_df, on='RB_Type_L3', how='left')

    # Overwrite RB_Type_L3 with the new classification and keep Attachment
    merged_gdf['RB_Type_L3'] = merged_gdf['RB_Type_L3_v0-4']
    merged_gdf['Attachment'] = merged_gdf['Attachment']

    # Print the column names of the merged GeoDataFrame
    print("\n1. Columns in the merged GeoDataFrame:")
    print(merged_gdf.columns.tolist())

    # Rename existing columns
    rename_map = {'ImgSrc': 'EdgeSrc', 'Edg_acc': 'EdgeAcc_m'}
    merged_gdf = merged_gdf.rename(columns=rename_map)

    # Only keep the specified columns and geometry
    keep_cols = [
        'EdgeSrc', 'FeatConf', 'TypeConf', 'EdgeAcc_m',
        'DepthCat', 'DepthCatSr', 'RB_Type_L3', 'Attachment', 'geometry'
    ]
    # Only keep columns that exist in the dataframe (in case some are missing)
    keep_cols = [col for col in keep_cols if col in merged_gdf.columns]
    merged_gdf = merged_gdf[keep_cols]


    print("\n2. Columns in the merged GeoDataFrame:")
    print(merged_gdf.columns.tolist())

    # Check for unmapped values
    unmapped = merged_gdf[merged_gdf['RB_Type_L3'].isna()]


    if not unmapped.empty:
        print(f"\nWARNING: {len(unmapped)} features could not be mapped:")
        unmapped_types = unmapped['RB_Type_L3'].unique()
        for t in sorted(unmapped_types):
            count = unmapped[unmapped['RB_Type_L3'] == t].shape[0]
            print(f"  - {t} ({count} features)")
    else:
        print("\nAll features were successfully mapped!")

    # Count the frequency of each new RB_Type_L3_v0-4 value
    value_counts = merged_gdf['RB_Type_L3'].value_counts()
    print("\nFeatures by RB_Type_L3 in output data:")
    for value, count in value_counts.items():
        print(f"  - {value}: {count}")

    # Count the frequency of each Attachment value
    attachment_counts = merged_gdf['Attachment'].value_counts()
    print("\nFeatures by Attachment in output data:")
    for value, count in attachment_counts.items():
        print(f"  - {value}: {count}")

    # Save the updated GeoDataFrame to a new shapefile
    print(f"\nSaving updated features to {output_shapefile}")
    merged_gdf.to_file(output_shapefile)
    print(f"Done! Processed {len(features_gdf)} features.")

if __name__ == "__main__":
    crosswalk_classification()