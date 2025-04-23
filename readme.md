# North and West Australia Reef Features
This repository contains utility scripts that were used in the development of the North and West Australia Reef Features dataset. For full information about this dataset see: 

Lawrey, E., Bycroft, R. (2025). North and West Australia Reef Features - Coral reefs, Rocky reefs, and Intertidal sediment (AIMS). [Data set]. eAtlas. https://doi.org/10.26274/xj4v-2739


It should be noted that this dataset was largely created manually and this these scripts represent utilities that were used to process portions of the dataset production, and do not full represent the full workflow associated with the dataset as much of the processing was performed in QGIS. It should also be noted that most of these scripts refer to files that were intermediate files during the production and thus will not work directly from the public files. They are provided as a form of documentation, rather than to allow a blind rerun of the processing from scratch.

# Installation Guide

## 1. Prerequisites
- If using Conda, install [Miniconda](https://www.anaconda.com/docs/getting-started/miniconda/install) (Untested) or use Anaconda Navigator.

## 2. Clone the Repository
```bash
git clone https://github.com/eatlas/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features
cd AU_NESP-MaC-3-17_AIMS_NW-Aus-Features
```

## 3. Using Conda 
Conda is recommended because, in theory, it makes the installing of GDAL, PROJ and GEOS more straight forward across a wider range of platforms. In my testing on Windows both conda and pip worked just as well as each other. The only real difference is that conda can be used to install a specific version of Python into an environment, where as Pip will use the version of Python that is installed.

1. Create the Conda environment. This step can take 10 min. If you are using Anaconda open the default Anaconda Prompt, change to the 
    ```bash
    cd {path to the AU_NESP-MaC-3-17_AIMS_NW-Aus-Features dataset} 
    conda env create -f environment-3-13.yaml
    ```
2. Activate the environment
    ```bash
    conda activate venv_map_3-13
    ```
    
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
Downloads Sentinel-2 satellite imagery composites (15th percentile and low tide) for northern Australia and the Great Barrier Reef.

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

- **`09a-download-qaqc-data.py`**
   Downloads additional datasets for quality assurance and quality control (QAQC). This includes bathymetry datasets.

- **`09b-generate-qaqc-boundary-points.py`**
    Generates QAQC random points along polygon boundaries for accuracy assessment. The points created from this script must be manually aligned to the true position of the boundaries.

- **`09c-qaqc-assess-boundary-error.py`**
    Compares boundary points against ground truth to assess positional accuracy.

- **`09d-compare-reef-masks.py`**
    Compares manual and automated reef masks to evaluate true positives, false positives, and false negatives.

# Map stage notes
The following is a set of notes detailing the processing that was applied in the development of each phase of the mapping. This phased approach provides a record of what features were detected and mapped at each stage of the project, where each stage represents the incorporation of new information.

## Stage 1 - v0-1_dual-maps - Two independent mappings from satellite imagery
This stage involved manual digitisation of reefs predominantly from Sentinel 2 imagery, although some additional high resolution image sources were used for Reef-Features_Ref1_RB. This phase includes mapping of the reefs by two relatively independent cartographers. 
1. Reef-Features_Ref1_RB: Mapped by Rachel Bycroft. Full resolution reef mapping with the core focus on mapping coral reefs and rocky reefs, with sand banks as a lower priority. No intertidal sediment was mapped. This dataset is the base of the final dataset. The target for digitisation was 1:150k-250k scale with a maximum spatial error of 75 - 150 m. Features were mapped using the clustering rules developed for the Coral Sea Features mapping (approximately: features of the same type closer than 200 m are merged, sand between features is included, sand on the outside is included up to 50 m). Features were mapped and assigned as per the Reef Boundary Type classification (RB_Type_3). Complex areas were split based on types so that a coral reef growing outwards from a rocky reef would be mapped as two areas joined together. This mapping took approximately 450 hours.
2. Rough-reef-mask_Ref2_EL: Mapped by Eric Lawrey. Half resolution mapping, with no type classification, but with intertidal areas included. This dataset started out as the rough reef masking to developing a semi-automated approach for mapping reefs and the intertidal zone (Lawrey, 2025). This mapping was extended to more comprehensively map reef boundaries, including small reefs, to act as a cross reference check for the Reef-Features_Ref1 dataset. It could be used to identify reefs that were missed in the primary reef mapping, helping to determine detection rate for each cartographer. The reef features were mapping at a rapid pace, with an average of 40 sec per feature. The target maximum boundary error was 250 m, however little care was taken to make the mapped boundaries smooth. The goal of this mapping was to mask out an shallow area, regardless of the benthic type.

## Stage 2 - v0-2_merge-maps - Combining the reefs maps together
To improve the detection rate for small and hard to detect reefs in this stage Rachel combined the two reef maps (Reef-Features_Ref1_RB and Rough-reef-mask_Ref2_EL) by identifying features in the Rough-reef-mask_Ref2_EL that were missing in her mapping. The missing reefs were typically remapped from the satellite imagery rather than copying them from the Rough-reef-mask_Ref2_EL because the rough reef map features were typically too coarse in detail.

## Stage 3 - v0-3_qc-1 - Quality control
This was the first round of quality control applied to the dataset. The principal editing file for this version is `data/v0-3_qc-1/in/NW-Features_RB_Type_L3/Reef Boundaries Review.shp`. This involved a review of all features by Eric Lawrey, noting missing features, areas that needed trimming, classification changes. These issues were noded in data/v0-2_merge-maps/Issues-v0-2/Issues-v0-2_partA and partB. These were split to allow Rachel to start work on fixing issues, while further review was being conducted. The review was conducted using the project Sentinel 2 composite imagery, individual daily Sentinel 2 imagery using the [Copernicus Browser](https://browser.dataspace.copernicus.eu/) setting the cloud cover low (~10%) then reviewing the imagery over several years. Aerial imagery for part of the Gulf of Carpentaria were also used help identify features. The goal was to identify images that would show a clear view of the feature, or changes over time that would help with type classification. The daily imagery was only used to assist in identifying difficult to classify areas. Approximately 70% of the coastline was covered in this review and it took approximately 25 hours.

This review identified several key issues:
- Large sandy areas (>150 m across) were being included in the rocky reef features. This might degrade the quality of the UQ habitat mapping.
- Many (hundreds) smaller rocky reefs (100 - 200 m across) were identified. The conclusion was that most of these features were intertidal rocky reefs that could be reasonably identified from the Sentinel Low tide composite imagery. This led to the decision to produce an semi-automated mapping of intertidal rocky reefs using random forest classification.  
- The extent of the coral reefs in the Kimberley were being inconsistently being mapping. For fringing reefs the boundaries focused primarily on the active growth areas of coral, the outer strip of the fringing reef. While for some of the platform reefs the whole reef platform, including the inner, largely sandy, reef flat was being included in the boundary. The fringing reefs grow out laterally from the land and islands leaving an extensive reef flat that is largely devoid of any corals, just sand. These are however limestone reef frameworks, as we can tell from the presence of the occasional 'blue hole' formed by the limestone reef framework dissolving from rain water during a previous glacial period when sea levels were lower. From a geomorphic perspective the whole reef framwork should be included in the reef boundary, but from an biodiversity hotspot perspective we might be more interested in where there is active coral growth. To cover both bases we added a new classifcation 'Reef Flat Shallow'. This will cover the low diversity shallow portions of reefs that would have been excluded. This new classification was used extensively to describe the extensive reef areas around Barrow Island in Western Australia.
- The review identified a number of fish traps and oyster reefs that are relevant for [NESP MaC Project 4.13](https://catalogue.eatlas.org.au/geonetwork/srv/eng/catalog.search#/metadata/8050d5a5-6d8d-4dc5-ae18-9805fd401032).
- An issue was identified at a rate of about one issue per four mapped features. 

After the review Rachel worked on improving the high priority issues, resolving approximately 40% of them, the bulk of which was trimming out sediment areas from rocky reefs. 

Rachel then handed over the editing to Eric who then continues making priority improvements. Overall only approximately 60% of the priority issues were resolved due to limited time. 

### New reef classification scheme - Names and attributes
Some of the reefs near Montebellow Island are rocky in nature, however they have a biogenic carbonate origin, which could not be represented with the existing RB_Type_L3 classification scheme as all rocky reefs are assumed to be Terrigenous. To add a carbonate to rocky reefs would require potentially doubling of the rocky reef classification types. The RB_Type_L3 was intended to have a discrete named classification for every combination of attributes that are in use. This works up to a point. As more details are recorded about a reef, not all of this can be represented as a single classification name. To resolve this problem we retain named classes (Feat_L3) for all types that you would expect to put in a legend, i.e. feature names that an environmental manager is likely to care about. Additional qualifier attributes are then split into separate attributes. For this the relative position (Fringing, Platform), was moved into its own attribute. 

The new classification was automatically applied to the existing mapping using `03-v0-3-class-cross-walk.py`. 

### What to do with Montebellow / Barrow Island reefs
There are extensive shallow reef areas around Montebellow and Barrow Islands. These areas are each approximately 550 km2 each. Rachel had initially mapped them as rocky reefs with a few small patch coral reefs in areas where there was obvious coral reef accretion. This didn't seemed to be accurate.  

Research indicated that whole shallow plateau around the island is carbonate in origin. Coral monitoring sites showed that sites that did not look like a traditional coral reef in structure (rocky foundation, low amount of structural texture) had high levels of hard and soft coral cover. While many of the reef structures look rocky, they are covered in hard coral and thus should be considered as coral reefs. The large flat areas were converted to 'Reef Flat Shallow' to indicate that these areas are geomorphically related to and connected with the coral reef stuctures. 

### Reviewing the classification of offshore reefs
The classification of offshore reefs was review and corrected. Reefs were assigned as part of an atoll if the water around the reef was more than 200 m in depth. In some parts their were clusters of reefs near the 200 m contour. Given the uncertainty in the bathymetry dataset (Geoscience Australia AusBathy 250m 2024), only reefs that were significantly separated from clusters at the shelf edge were classified as atolls. 

Those with atolls were classified as atoll platforms. Where a reef (hard exposed reef) existed on these platforms then they were cut out from the atoll and classified based on the same process as for Coral Sea. 

The equivalent deep areas for reefs on the continental shelf were classified as Deep Platform Coral Reefs and the shallow portions as Platform Coral Reefs. Some of the Deep Platforms were actually just above the 30 m threshold and so these will still need some more work to treat the oceanic reefs and shelf reefs in a consistent manner.

### Cleaning up for publication.
To get the dataset ready for publication and use by UQ for the habitat mapping the following processing was done on the dataset:
1. Removing geometry errors created by manual editing. The `Vector / Geometry Tools / Check Geometry` tool in QGIS was used to find any issues. These were then fixed manually.
2. Removed overlaps in High Intertidal Coral Reefs with other features. (`02-v0-3-clean-overlaps.py`)
3. We apply the new classification scheme (`03-v0-3-class-cross-walk.py`).
4. Merge in the semi-automated intertidal rocky reef mapping. (`04-v0-4-merge-rocky-reefs.py`)
5. We remove overlaps between the rocky reef features and the coral reefs (`05-v0-3-clip-rocks-from-reefs.py`)
6. We use the semi-automated shallow mask to create an estimate for the shallow sediment areas. We first clean up this dataset by adding areas that were not mapped correctly (seagrass areas, and shallow foreshore in GOC) and removing spurious results, particularing narrow rivers.
7. We estimate the sediment areas by using clipping reefs from the shallow mask, leaving, in theory, just soft sediment.
8. We clip clean up the land edge of the shapefile by clipping against the land mask.

## TODO: Stage 4 - v0-4_merge-bathy - Check bathymetry and marine charts for reefs we missed
In this stage information from bathymetry sources was incorporated into the mapping. The AHO Marine Charts (Australian Hydrographic Office, 2021a, 2021b) and bathymetry datasets were reviewed to identify any reef features that were missed in the previous stages. For Marine Charts peaks and reefs identified in the charts were compared with the mapped reef boundaries. On the marine charts shallows reefs are marked as a hazard or as a peak, showing a depth sounding, with a contour around the peak.

Potential reefs identified from the bathymetry were reviewed in the satellite imagery. In general only potential reefs that could be confirmed visually from the satellite imagery added to the reef dataset. Where no confirmation imagery was found, the potential reef was recorded in a separate point dataset. These were used to help identify the number of potential reefs that were missed by the reef mapping. Features idenified only in the bathymetry were not included by default because the available bathymetry is highly variable in quality. Not all peaks in the bathymetry dataset are reefs. In some cases they appear as a peak due to the large spacing between the depth soundings. Reefs were only included directly from the bathymetry where there was good evidence that the source bathymetry was a high quality representation of the true bathymetry.

In this stage we also identified AHO marine chart depth soundings that did closely align with mapped reef centroids. These depths were recorded in the dataset and later used to calibrate and validate the depth classification of reefs.

In this stage we also identified whether the mapped reef feature corresponded to a reef feature that was already known about. For this we consider a reef to have already been known about if it appears as a distinct feature in the marine charts, or bathymetry, or part of ReefKIM (Kordi, et.al., 2016), Big Bank Shoals, or AIMS north west shoal benthic surveys.


# TODO: Stage 5 - v1_qaqc - Apply Quality Control 
In this stage we complete the assignment of all attributes including depth classifications estimated from satellite, and confidence settings. In this version we complete the remaining adjustments identified in stage 2 to the feature boundaries. This is the version that we used to perform validation assessment on. 

In this stage we gathered additional benthic information that was not used in the previous stages. This included additional georeference drone and underwater footage from YouTube, AIMS BRUVS and Tow video surveys, GOC seagrass surveys, and other in-situ datasets collated by UQ for the habitat mapping. These sources of information were converted into a point dataset of location and classification for direct comparison to the reef mapping. The available in-situ validation data was not evenly distributed, but concentrated at known reef sites, seafloor areas that excluded reefs or popular travel destinations.

# TODO: Stage 6 - v1-1_post-valid 
This stage included improvements made from what was learned from the validation stage. The validation is applied to v1_qaqc and v1-1_post-valid contains further improvements. As a result this version should be slightly better than the validation metrics.  


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



