This script aims to analyse the amount of mapped reef features in each of the areas covered by the the North and West Australian reef mapping dataset. It analyses the latest version of the dataset (based on config.ini). It lists the number of countable reefs and area per region. For these regions we will used the Integrated Marine and Coastal Regionalisation of Australia (IMCRA) v4.0 - Meso-scale Bioregions.

See config.ini for the the current version, this is `[general] version`.

## Metadata for IMCRA v4.0 - Meso-scale Bioregions:
An inshore regionalisation of Australian waters derived from biological and physical data, including the distribution of demersal fishes, marine plants and invertebrates, sea floor geomorphology and sediments, and oceanographic data.

The meso-scale regionalisation was compiled from information supplied to the Australian Government Department of Climate Change, Energy, the Environment and Water by the relevant State, Northern Territory and Commonwealth marine research and management agencies.

The seaward extent for the meso-scale IMCRA coverage is defined by the 200m isobath except where this boundary extends beyond the Australian Exclusive Economic Zone (AEEZ).

https://fed.dcceew.gov.au/datasets/erin::integrated-marine-and-coastal-regionalisation-of-australia-imcra-v4-0-meso-scale-bioregions/about

Location: data/{version}/in-3p/IMCRA-v4-0-Meso-Bioregions/IMCRA-v4-Mesoscale-Bioregions.shp

The IMCRA meso bioregions shapefile has a MESO_NAME attribute. This includes the name of the regions. There are 62 mesoscale regions, however the reef dataset only covers about half of them. We do not need to dissolve these regions as we are using the finest scale of the dataset. While there are three 'Victorian Embayments' polygons these are outside the study area.

## Metadata for Analysis-regions Shapefile 

The Analysis-regions shapefile was created by overlaying and dissolving multiple authoritative spatial datasets including the Commonwealth Marine Regions (DCCEEW, 2023b), Great Barrier Reef Marine Park boundaries (GBRMPA), Coral Sea Marine Park boundaries, and Natural Resource Management (NRM) regions for Torres Strait (DCCEEW, 2023a). The process began by using the outer boundary of the Australian Tropical Reef Features study area and performing a vector union with Commonwealth Marine Regions to create initial subdivisions.

Region attribute to spatially join: subregion. Examples: 'North (Offshore)', 'Temperate East (Offshore)'.

We do not need to dissolve these regions as we are using the finest scale of the dataset.

data/{version}/in-3p/nesp-3-17-analysis-regions/analysis-regions.shp

## Metadata for Collaborative Australian Protected Areas Database (CAPAD)
Department of Climate Change, Energy, the Environment and Water. (2025). 
Collaborative Australian Protected Areas Database (CAPAD) 2024 - Marine. [Data set].
https://fed.dcceew.gov.au/datasets/erin::collaborative-australian-protected-areas-database-capad-2024-marine/about

Location: `data/{version}/in-3p/CAPAD-2024/Collaborative_Australian_Protected_Areas_Database_(CAPAD)_2024_-_Marine.shp`

This contains protected areas including Australian Marine Parks, state marine parks, Indigenous Protected Areas and Fish Habitat Areas. Each area is subdivided based on zoning. For this analysis we want to dissolve by the `TYPE` and `NAME` attributes. Some Australian Marine Parks and state marine parks have the same name, so the two fields together identify a protected area. All zones belonging to one protected area should become a single geometry. Retain `TYPE` and `NAME` as separate fields through processing and in the final outputs; a display label such as `NAME - TYPE` can be constructed later. After dissolution, simplify each CAPAD geometry in EPSG:3112 using a 10 m tolerance with topology preservation. This reduces the unnecessarily fine land boundaries, especially in the Kimberley. If simplification makes a geometry invalid or empty, retain that area's original dissolved geometry. Use the resulting geometries for reef intersections, the CAPAD union used for 'No match', and the final CAPAD shapefile export. IMCRA and Analysis-regions are not simplified.

## Regionalisation - Spatial join with reef mapping
In this analysis we want to determine how many reefs are in each of the regionalisation datasets: IMCRA, Analysis-regions and CAPAD 2024 - Marine. Each of these different regionalisations should be processed independently (i.e. a reef can have membership in all three regionalisation datasets). We need to record which regions the reef exists in. Where a reef crosses a boundary, it can be a member of multiple regions. For each membership the reef should contribute to the count of reefs in that region, but for area calculations only the portion that exists with each region should be included in that region. CAPAD protected areas can overlap: the same reef portion should contribute its full intersected area and one count to each overlapping protected area, identified by (`TYPE`, `NAME`).

### Input reef dataset
For this analysis we will use the latest version of the RB_Type_L2 classification reef dataset produced by script 13-make-RB_Type_L2.py. This dataset is available from "data/{version}/out/simp-classes/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L2_{version}.shp". It contains attributes RB_Type_L2 ('Coral Reef','Rocky Reef', 'Sediment', ...), Area_km2, ReefID, and other attributes not needed in this analysis. For this analysis we will only use the 'Coral Reef', and 'Rocky Reef' features. 

## Processing
All processing should be done in EPSG:3112 for consistancy. Output 

We need to convert the L2 reef boundaries into countable reefs. In this analysis we want to determine the number of reefs that exist in each region. However a reef needs to be of sufficient size and separation to be considered significant enough to be included in the count. Counting reefs is problematic because as the mapping scale changes reefs tend to be mapped with more small fragements. This can inflate the reported number of reefs in a region. To help standardise and normalise the count, before we start counting reefs in region we cluster reefs that are closer than 100 m apart, merging them into a single multi-part feature, then drop all reefs that have an effective width (width of a circle that is the same area as the reef) of less than 100 m. This clustering and filtering out of small reef clusters means that the there are less countable reefs than L2 reef features. This countable reefs processing should be done using reef_utils.cluster_countable with default values. This applies separate clustering for rocky reefs and coral reefs. Once we have countable reefs we simply need to divide them up into the different regions. Countability is determined once, globally, before any regionalisation processing.

Prior to cutting up the countable reef boundaries into regions they should each be given a CountFID. A temporary ID that makes it easy to determine that reef that is split into multiple parts in subsequent processing was from the same countable reef feature. This is not done by cluster_countable.

Conceptually IMCRA and Analysis-regions should be applied as cookie cutters to the countable reefs dataset, assigning each cut area to its region. Where a reef crosses region boundaries, it can be counted in multiple regions, but its area is never double counted within either regionalisation. Any piece outside the regionalisation shapes is assigned to 'No match'. For CAPAD, intersect each protected area in turn with the original countable reef, not the reef remaining after intersection with other protected areas. Retain a separate portion for each (`TYPE`, `NAME`) membership, even where portions overlap. The summed area across CAPAD protected areas may therefore exceed the area of reefs inside protected areas.

To deal with slivers affecting counts (where only a sliver existing in a region), after slicing the countable reefs, any polygon or multi-polygon that does not exist after a 5 m negative buffer should be removed from the set moving forward. This is a test for each piece after the slice. For CAPAD, test each protected-area intersection separately and test the union-derived 'No match' portion separately; a sliver removed from one area's statistics must not be reclassified as 'No match'. If you are not big enough to remain after a 5 m negative buffer then you will not be included in the reef count or reef area associated with a region. If negative buffer test passes the original cut piece is retained. This means that a very long feature less than 10 m wide will be removed. This is intentional. No mapped reefs are this narrow.

If there is a complex shaped reef that is cut up into multiple segments by the regional slicing, it should still only be counted as one reef in that region. This should be able to be achieved by maintaining a multipart polygon through a slice. Alternatively, count distinct `CountFID` values per region. For CAPAD this grouping must use both `TYPE` and `NAME`, so two protected areas with the same name but different types remain separate.

For a given regionalisation dataset the portion of reefs that is not overlapped by any regional polygon should be apportioned to a 'No match' region (i.e. a count is recorded and the area outside the regionalisation polygons is recorded in 'No match'). For CAPAD, subtract the union of all dissolved protected areas from each original countable reef once to obtain its 'No match' portion; do not sum the outside portions of individual protected areas. A reef spanning the boundary of this union contributes one count inside one or more protected areas and one count to 'No match'. This 'No match' category includes reefs beyond the intended Australian reporting area (e.g. Timor), so it must not be used directly as the denominator for an inside-versus-outside comparison. For reporting, compare protected-area counts against the appropriate total for the Analysis-regions Commonwealth Marine Regions. Summed CAPAD counts are memberships, not a unique count of protected reefs; count distinct `CountFID` values across protected areas if a unique inside total is needed.

source reef polygons → filter Coral/Rocky → cluster_countable() → regional intersection → sliver removal → summary.

For IMCRA and Analysis-regions the reef area totals for all regions plus 'No match' should equal the total countable reef area, minus any slivers removed. Reef counts need not add to the total because a reef can cross region boundaries. Check the area balance within the tolerance expected from sliver removal. For CAPAD, do not compare the sum of individual protected-area areas plus 'No match' with the input area: overlapping protected areas intentionally double count their shared reef area. Instead, independently check that reef area within the union of all CAPAD areas plus reef area outside that union equals the input countable reef area, accounting for any slivers removed from these union-based portions. Per-protected-area totals remain separate from this union-based area check.

IMCRA and Analysis-regions should not contain overlapping polygons, though they may touch. Check these datasets early, save a shapefile of any problematic overlaps and abort. The maximum allowable overlap is 5 m: an overlap polygon surviving a 2.5 m negative buffer is an error. This check should remain optional (a global boolean constant) so vetted inputs need not be retested on every run. Do not run the between-region overlap check on CAPAD: overlaps between protected areas, including those with different (`TYPE`, `NAME`) values, are valid. Dissolving zones within each (`TYPE`, `NAME`) group handles their internal overlaps; no additional within-group overlap check is needed.

To help with debugging and checking of the results the intermediate cut up reef boundaries should be saved as shapefile for review. There should be one shapefile per regionalisation dataset. This should have attributes 'CountFID', 'RB_Type_L2', 'RegionName', 'Area_km2' for IMCRA and Analysis-regions. The CAPAD intermediate should retain `TYPE` and `NAME` separately with `CountFID`, `RB_Type_L2` and `Area_km2`; its 'No match' pieces have no protected-area type or name.

Processing by this script should be saved to working/{version}/A05

Filenames something along the lines of:
working/{version}/A05/reefs-by-imcra.shp
working/{version}/A05/reefs-by-analysis-region.shp
working/{version}/A05/regions-capad-10m.shp
working/{version}/A05/reefs-by-capad-10m.shp
working/{version}/A05/debug-overlap-imcra.shp (This for the overlap of the regionalisation dataset, if there is any problems with the dataset)

As we expect the processing to be slow (~hour) each significant intermediate step should cache its output, allowing that step to be skipped on a repeat run. This is to allow later stages of the script to be debugged without needing to wait for multiple reruns of early processing steps. We will manually invalidate the cache by manually deleting files. The 10 m suffix on both CAPAD caches prevents unsimplified region geometries or reef cuts from being reused; changing the simplification tolerance should change both cache names.

## Region summarisation
A CSV summary table should be generated that will have the following tall table:
Region_dataset, Region_type, Region_name, Coral_reef_count, Coral_reef_area_km2, Rocky_reef_count, Rocky_reef_area_km2

For CAPAD, `Region_type` and `Region_name` contain the original `TYPE` and `NAME` fields, respectively; aggregate by both. For IMCRA and Analysis-regions, leave `Region_type` blank. For each dataset's 'No match' row, leave `Region_type` blank and use 'No match' for `Region_name`.

Areas should be output with 6 digits of precision. Counts should be integers. The CSV should be ordered by Region_dataset, then Region_type and Region_name for CAPAD (Region_name for the other datasets). 'No match' should go at the bottom of the region names within a regional dataset.

Because the reef dataset will be cut up by the regionalisation datasets the areas will need to be recalculated from the intermediate cut up polygons. For this using the EPSG:3112 GDA94 / Geoscience Australia Lambert projection. Some of the reefs (Lord Howe, Norfolk, Coco Keeling, Christmas Islands) are outside the working are of this projection however the increased error is acceptable for this analysis. Each of the results for the 'No match' regions should be included as though it were a region.

Region_dataset: Short name of the regionalisation dataset: Full reference (don't include this in the CSV, just the short name)
 - `IMCRA v4.0 Meso-scale Bioregions (2023)`: DCCEEW (2023) IMCRA v4.0 - Meso-scale Bioregions (Version 17 Oct 2023) [Data set] https://fed.dcceew.gov.au/datasets/erin::integrated-marine-and-coastal-regionalisation-of-australia-imcra-v4-0-meso-scale-bioregions/about
 - `Analysis-regions v1`: Lawrey, E. (2025). Supporting datasets for estimating reef counts in the Coral Sea and northern Australia (NESP MaC 3.17, AIMS) (Version 1) [Data set]. eAtlas. https://doi.org/10.26274/xr0r-tb19
 - `CAPAD 2024 - Marine`: Department of Climate Change, Energy, the Environment and Water. (2025). Collaborative Australian Protected Areas Database (CAPAD) 2024 - Marine. [Data set]. https://fed.dcceew.gov.au/datasets/erin::collaborative-australian-protected-areas-database-capad-2024-marine/about


The CSV should only include regions that contain more than zero countable reefs (after sliver removal). This means that regions that are outside the study area will not have false zeros reported. This should be a natural by-product of slicing reef boundaries and assigning them a region. The regions in the region datasets that are outside of the study area will never be assigned to a reef and thus should not appear in the summary table.

Save this result to data/{version}/out/stats/NW-Aus-Features_Region-stats_{version}.csv

## Addendum 1
Along with saving the reef counts and areas to a CSV file. These amounts should be saved in an export of each of the regionalisations as a shapefile. This will allow the creation of maps that show the regionalisation and a label showing the number of reefs in that region. The shapefile should only contain regions that have more than 0 reefs. Since `No match` has no spatial extent these results remain only in the CSV. These saved shapefiles should be based on the prepared regions used for cutting reefs (including CAPAD dissolved by `TYPE` and `NAME`). CAPAD's exported shapefile must retain both `TYPE` and `NAME`, with statistics joined on both fields. These shapefiles should be saved to out/stats/NW-Aus-Features_Region-stats_{short region name}_{version}.shp, such as NW-Aus-Features_Region-stats_imcra_v1-2.shp and NW-Aus-Features_Region-stats_capad_v1-2.shp.


