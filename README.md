# North and West Australia Reef Features - GIS Dataset
This repository contains utility scripts that were used in the development of the North and West Australia Reef Features dataset. For full information about this dataset see: 

Lawrey, E., Bycroft, R. (2025). North and West Australia Reef Features - Coral reefs, Rocky reefs, and Intertidal sediment (AIMS). [Data set]. eAtlas. https://doi.org/10.26274/xj4v-2739


It should be noted that this dataset was largely created manually and these scripts represent utilities that were used to process portions of the dataset production, and do not fully represent the full workflow associated with the dataset as much of the processing was performed in QGIS. It should also be noted that most of these scripts refer to files that were intermediate files during the production and thus will not work directly from the public files. They are provided as a form of documentation, rather than to allow a blind rerun of the processing from scratch.

# Version summaries
This provides a brief overview of each version of the dataset. A detailed log of changes made are provided in the [CHANGELOG.md](CHANGELOG.md).

## v0-4 - Draft national scale NVCL 
This version is intended to flow into the national scale reef dataset (Lawrey & Bycroft, 2025). This national scale dataset is intended to be classified to the Natural Values Common Language and will combine updated mapping of the GBR and Torres Strait, and existing mapping of the Coral Sea. In this version we drop the integration of the 'Shallow sediment' and the automated 'Intertidal Rocky Reef' datasets. Each of these need additional work to make them align with the NVCL definitions. We shift this integration to the national scale, so these feature types are treated uniformly at the national scale.

Lawrey, E., Bycroft, R. (2025). Australian Tropical Reef Features - Boundaries of coral and rocky reefs (NESP MaC 3.17, AIMS). [Data set]. eAtlas. https://doi.org/10.26274/4rrw-rr88

This version introduced the following classifications:
- `Coral Reef Inner Flat` classification to represent low ecologically active areas on reefs.
- `Limestone reef` and `Sandy Limestone Pavement` to better represent the limestone reefs around the Pilbra. 

This version includes the following improvements:
- The mapping of the paleo rocky reefs off Eighty mile beach, separating out sand banks from the rocky portions.
- Review and improvement of the 'Attachment' attribute. This found 6% error rate, with remanent errors estimated at 2%.
- Significant improvement to the mapping Cocos Keeling Island, Christmas Island, Norfolk Island, Middleton Reef, Elizabeth Reef, and Lord Howe Island.

### Known issues
- The `EdgeAcc_m` attribute is a string field when it should be a numeric field. Some features (~5%) do not have their edge accuracy assessed.
- The `DepthCat` and `DepthCatSr` is not assigned for most features, however most offshore features were assessed to allow their assignment to shallow or deep.
- Only limited review has been performed on the expert assessment of the `FeatConf` and `TypeConf`.  
- Many of the small inshore rocky reefs are not included, particularly in the Kimberley area. It was decided to defer the inclusion of the automated intertidal rocky reef mapping as it needs more work.
- The classification accuracy of the reefs in the Pilbra needs more work. This region has a lot of limestone reefs, with an overlay of active modern coral reefs. The division between coral reefs and limestone reefs has only been partly implemented.
- The `Coral Reef Inner Flat` has not been fully rolled out to the fringing reefs of Kimberley. As a result most of the fringing reefs only cover the active coral area, not the reef flat. As a result this version underestimates geological extent of the reefs.

## v0-3 - UQ Habitat classification masks
This version was developed to assist with the UQ habitat mapping. It consisted of the coral reefs, rocky reefs and shallow sediment. The rocky reefs included both the manually digitised rocky reefs and semi-automated intertidal rocky reef boundary (AU_NESP-MaC-3-17_AIMS_Rocky-reefs_V1) combined. The shallow sediment corresponded to optically shallow areas mapped to approximately LAT, except for seagrass areas where deeper waters were included. The training of the habitat mapping was split into coral reef, rocky reef and sediment areas based on these layers.

No additional validation was done on this version, above the review conducted as part of `v0-2`.

# Setup guide for running the scripts and editing the data
Most of the mapping in this dataset is perform manually in QGIS based on satellite imagery. The scripts are used to download the source data, and to perform transformations on the classification and clipping operations. 

## 1. Prerequisites
- If using Conda, install [Miniconda](https://www.anaconda.com/docs/getting-started/miniconda/install) (Untested) or use Anaconda Navigator.

## 2. Clone the Repository
```bash
git clone https://github.com/eatlas/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features
cd AU_NESP-MaC-3-17_AIMS_NW-Aus-Features
```

## 3. Using Conda 

1. Create the Conda environment. This step can take 10 min. If you are using Anaconda open the default Anaconda Prompt, change to the 
    ```bash
    cd {path to the AU_NESP-MaC-3-17_AIMS_NW-Aus-Features dataset} 
    conda env create -f environment-3-13.yaml
    ```
2. Activate the environment
    ```bash
    conda activate venv_map_3-13
    ```

## 4. Editing in QGIS
If you are making a new version of the dataset then you should start with the previous 'edit' version, not the final processed version. For example for v0-4 we needed to adjust the classification so `09-v0-4-class-cross-walk.py` was used to read `working/02/Reef_Boundaries_Clean.shp`, the previous editable version of the dataset. `v0-3` release didn't have a editable version because it focused on merging datasets together. This script created saved the conversion to `working/09/Reef-Boundaries_v0-4.shp`, which was manually copied to `data/v0-4/in/Reef-Boundaries_v0-4_edit.shp`. This manual copy was done to prevent an accidental overwrite of any manual edits if the script was run once again. `data/v0-4/in/Reef-Boundaries_v0-4_edit.shp` was then manually edited in QGIS to fix issues in the previous version. This shapefile is the current editable version. The final data file `data/v0-4/out/NW-Aus-Features_v0-4.shp` is derived from the edit version, by running `10-v0-4-clip-land.shp`.
    
## Debug:
ERROR conda.core.link:_execute(938): An error occurred while installing package 'conda-forge::libjpeg-turbo-3.0.0-hcfcfb64_1'.
Rolling back transaction: done

[Errno 13] Permission denied: 'C:\\Users\\elawrey\\Anaconda3\\pkgs\\libjpeg-turbo-3.0.0-hcfcfb64_1\\Library\\bin\\wrjpgcom.exe'
()

For some reason this particular cache of the library was set with administrator permissions, preventing conda for using this library in the setup. The fix is to switch to admin permissions, delete the `C:\\Users\\elawrey\\Anaconda3\\pkgs\\libjpeg-turbo-3.0.0-hcfcfb64_1` folder, which is safe since it is just a cache. 

I found that when this failure occurs the resulting conda environment ends up in a corrupted state and it must be manually removed, prior to recreating the environment.

In my case I needed to delete `C:\Users\elawrey\Anaconda3\envs\venv_map_3-13`

# Description of scripts

- **`01-download-input-data.py`**
This script downloads the third party datasets used in the preview maps, such as the world land area, the GBR reefs, the Coral Sea vegetation and bathymetry datasets. This script downloads the data directly from the original source data services and stores it in `C:\Data\2025\AU_NESP-MaC-3-17_AIMS_NW-Aus-Features\working`. This is the folder where the QGIS `preview-maps.qgz` will look for the data files. If you download to a different location you will need to adjust the paths in QGIS. This script should download all data files used to recreate the preview maps and plots used for reporting purposes. 
`data_downloader.py` is a utility library that is used by `01-download-preview-map-data.py`.

- **`01a-download-sentinel2.py`**
Downloads Sentinel-2 satellite imagery composites (15th percentile and low tide imagery) for northern Australia and the Great Barrier Reef.

- **`02-v0-3-clean-overlaps.py`**
Removes overlaps between different reef types according to specific hierarchy rules, particularly focusing on High Intertidal Coral Reef features.

- **`03-v0-3-class-cross-walk.py`**
Transforms the RB_Type_L3 classification to a new, refactored classification system with additional attribute fields.

- **`04-v0-3-merge-rocky-reefs.py`**
Merges semi-automated intertidal rocky reef polygons into the main dataset, dissolving only where they touch existing rocky reef features.

- **`05-v0-3-clip-rocks-from-reefs.py`**
Removes overlap between Rocky Reef polygons and other feature types by clipping underlying polygons.

- **`06-v0-3-correct-shallow-mask.py`**
Applies manual corrections to the semi-automated Shallow Marine Mask by adding missed areas and removing false positives.

- **`07-v0-3-clip-merge-shallow-sed.py`**
Creates shallow sediment features from areas in the Shallow-mask not covered by existing reef features and adds them to the dataset.

- **`08-v0-3-clip-land.py`**
Clips the reef features dataset against the Australian coastline to remove any portions that overlap with land.

- **`09-v0-4-class-cross-walk.py`**
This applies an updated `RB_Type_L3` that factors out `Attachment` and `DepthCat` from the RB_Type_L3 classifications. This also detects and corrects anyincorrect winding of the polygons. Manual edits were then applied to the output of this script.

- **`10-v0-4-clip-land.py`**
This script clips the Reef_boundaries_v0-4_edit to the coastline.

-**`20-v0-4-generate-validation-locations.py`**
This script generates a validation locations for review. This generates shapefiles that are then populated by experts based on the best available data. This includes setting the attributes, and adjusting the boundary estimates. After these adjustments we had a validation dataset that can then be compared with the mapped dataset.

- **`20a-download-qaqc-data.py` - Unused**
Downloads additional datasets for quality assurance and quality control (QAQC). This includes bathymetry datasets.

- **`20d-compare-reef-masks.py` - Unused**
Compares manual and automated reef masks to evaluate true positives, false positives, and false negatives.

## Validation sampling
To provide a basic level of validation to the dataset we perform an expert review of a random sample of reef features, looking to answer the following key questions:
1. Does the indicated feature exists? i.e. it is a reef or sand bank
2. Is the classification accurate?
3. Are there other errors associated with the feature such as boundary accuracy or other attributes?
The goal of this validation is to assess the number of false positives that are likely in the dataset. False positives are problematic as they could lead to proponents being sent to investigate non-existant features, leading to wasted time and money.

A significant challenge in validating the dataset is the small size of reefs relative to open water. Simply uninformed random sampling will result in over 99% samples of open water as the reef areas only represent 1.2% of the study area.

We instead assess the accuracy of mapped reefs by randomly selecting a number of reefs to perform a detailed review by two reef mapping experts. This ensures that the focus is on the small areas represented by the reefs. This approach does not assess the false negative rate, i.e. features that are not mapped. 

The density of reef features is not uniform along the coastline, with the Kimberley containing a much higher density of features per unit area. To ensure that each region receives sufficient features to review the study area was broken into 12 regions, each corresponding to segments of 350 - 600 km of coastline. Where possible the boundaries were chose to closely align with existing named regions and with the natural boundaries of systems. All offshore reefs were clustered into a single group due to the low number of offshore features.

A Python script was used to randomly choose an equal number of features from each region. These were organised into batches of 10 features per region per batch. This allowed the team to work progressively, with each batch covering the full study area. 


Each feature to be reviewed is referenced by a point that exists close to the centroid of the feature being reviewed. The point is guaranteed to be inside the polygon. Each reviewer assigns the usual feature classifications, along with an indication of whether the feature is a false positive. This assignment of classifications is performed blind, without review of the existing assigned values. This allows a less biased assessment. 
1. Is there a feature of significance at the location indicated by the polygon (rocky reef, coral reef, sand bank)? (FeatExists)
2. What is an appropriate level of confidence in the feature existance (TypeConf)
3. What is the classification of the feature, without knowing what the original classification? (RB_Type_L3)
4. What is an appropriate level of uncertainty in the classification? (FeatConf)
5. Is the feature fringing, isolated or on an atoll (off the continental shelf), (Attachment)

This script generates locations for validation of the reef features in this dataset.
This is done by dividing the study area into 12 regions as specified by the 
data/v0-4/in/NW-Aus-Features-validation-regions.shp file. Each of the reef features,
as specified in data/v0-4/out/NW-Aus-Features_v0-4.shp, is then assigned to one of these
regions based on the centroid of the feature's geometry. 

The goal is to create a validation dataset that can be reused and applied to updated
versions of the reef features dataset, without needing to reevaluate the mapped features.
The evaluation can be performed automatically by a validation script by comparing the
validation attributes with the mapped features, and comparing the distance between 
the mapped feature and the boundary validation point.

To faciliate the automated validation the validation needs to be divided into three parts:
1. Feature-centroid: A feature centroid point that represents the feature and its attributes. 
This can be linked back to the mapped feature using a spatial join. This point must be 
central and inside the feature polygon to ensure this spatial join works correctly.
2. Polygon-extent: A simplified polygon that represents the extent of the feature. This 
polygon aims to assist the validator in understanding the extent of the feature without 
biasing them to the exact geometry of the feature. The geometry verticies should be randomly 
fuzzed by approximately 50 m and simplified to a approximately 50 m allowable error.
3. Boundary-error: One or more points that line on a random point of the the boundary of the feature polygon. 
These points will be repositioned by the validator to lie on the closest best estimate of the 
true boundary of the feature. To reduce bias, these points should be randomly
chosen from the simplified version of the polygon. These points can line on the lines
between verticies of the simplified polygon, or the verticies themselves.. 

The Feature-centroid, Polygon-extent and Boundary-error should be cross linked by a unique ID.

The Feature-centroid should have the following attributes:
- ValidID (Integer): Unique identifier for the validation feature. Used to cross-link between the
    centroid, extent and boundary-error features.
- FeatExists (String, values: 'True','False') 
    Is there a feature of significance at the location indicated by the polygon 
    (rocky reef, coral reef, sand bank)?
- TypeConf (String, values: 'High','Medium','Low','Very Low'): 
    What is an appropriate level of confidence in the feature existance (TypeConf)
- RB_Type_L3 (String, values: 
    Coral Reef
    Deep Bank Coral Reef
    Coral Reef Inner Flat
    High Intertidal Coral Reef
    High Intertidal Sediment Reef
    Stromatolite Reef
    Rocky Reef
    Sandy Limestone Pavement
    Limestone Reef
    Low Relief Rocky Reef
    Paleo Coast Rocky Reef
    Intertidal Sediment
    Sand Bank
    Atoll Lagoon Patch Coral Reef
    Atoll Lagoon Coral Reef
    Atoll Rim Coral Reef
    Atoll Flow Coral Reef
    Atoll Platform Coral Reef
    Vegetated Cay
    Unvegetated Cay
    Island
    Mainland
    Seagrass on Coral Reef
    Seagrass on Sediment
    Oceanic vegetated sediments
    Atoll Platform
    Man Made
    Unknown)
    What is the classification of the feature, without knowing what the original classification?
- FeatConf (String, Values: High, Medium, Low, Very Low):
    What is an appropriate level of uncertainty in the classification? (FeatConf)
- Attachment (String, values: 
    Fringing
    Isolated
    Atoll)
Is the feature fringing, isolated or on an atoll (off the continental shelf), (Attachment)

The Polygon-extent should have the following attributes:
- ValidID (Integer): Cross-link back to the matching Feature-centroid.

The Boundary-error should have the following attributes:
- ValidID (Integer): Cross-link back to the matching Feature-centroid.

The script should save the generated validation shapefiles to
working/20/NW-Aus-Features-v0-4_Feature-centroid-{zero padded Batch number}.shp
working/20/NW-Aus-Features-v0-4_Polygon-extent-{zero padded Batch number}.shp
working/20/NW-Aus-Features-v0-4_Boundary-error-{zero padded Batch number}.shp

The script should generate 10 batches of validation data, each containing 10 features per region.


# Reference:

Australian Hydrographic Office. (2021a). AHO Electronic Navigation Charts Simplified Series service (ArcGIS ImageServer). Retrieved March 15 2025, from https://amsis-geoscience-au.hub.arcgis.com/datasets/geoscience-au::aho-enc-series/about

Australian Hydrographic Office. (2021b). AHO Chart Series chart service. Retrieved Nov 28 2024, from https://amsis-geoscience-au.hub.arcgis.com/datasets/geoscience-au::aho-chart-series/about

AHO. (n.d.). Electronic Navigation Charts Simplified Series (ArcGIS ImageServer) [Dataset]. Australian Hydrographic Office. Retrieved February 12, 2025, from https://services.hydro.gov.au/site1/rest/services/Basemaps/AHOENCSimplifiedSeries/ImageServer

Bancroft, K.P. (2009). Establishing long-term coral community monitoring sites in the Montebello/Barrow Islands
marine protected areas: Site descriptions and summary analysis of baseline data collected in December 2006.
Marine Science Program Data Report MSPDR9. June 2011. Marine Science Program, Department of Environment and Conservation, Perth, Western Australia, 91p
https://library.dbca.wa.gov.au/static/Journals/080598/080598-09.pdf

Kordi, M. N., Collins, L. B., O’Leary, M., & Stevens, A. (2016). ReefKIM: An integrated geodatabase for sustainable management of the Kimberley Reefs, North West Australia. Ocean & Coastal Management, 119, 234–243. https://doi.org/10.1016/j.ocecoaman.2015.11.004

Lawrey, E. (2025) Semi-automated Shallow Marine Mask for Northern Australia and GBR Derived from Sentinel-2 Imagery (NESP MaC 3.17, AIMS) (Version 1-1) [Data set]. eAtlas. https://doi.org/10.26274/x37r-xk75



