This script aims to analyse the amount of mapped reef features in each of the areas covered by the the North and West Australian reef mapping dataset. It analyses the latest version of the dataset (based on config.ini). It lists the number of countable reefs and area per region for three regionalisations: the Integrated Marine and Coastal Regionalisation of Australia (IMCRA) v4.0 - Meso-scale Bioregions, the NESP 3.17 Analysis-regions, and the Collaborative Australian Protected Areas Database (CAPAD) 2024 - Marine.

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
In this analysis we want to determine how many reefs are in each region of three regionalisation datasets: IMCRA, Analysis-regions and CAPAD 2024 - Marine. Each regionalisation is processed independently, so a reef is assigned once in each of the three datasets.

Each reef is counted once per regionalisation, in the region that holds the largest share of its area. Area is not assigned this way. Where a reef crosses a boundary its area is split between the regions it overlaps, so a region can hold reef area without holding the reef's count. This conserves both counts and areas: summed over all regions, including near regions and 'No match', they equal the countable reef totals with no regionalisation applied. An earlier version counted a reef in every region it touched. For IMCRA this gave 4585 coral reef memberships for 3616 countable coral reefs, mostly because small reef pieces fell outside the coastal boundary and were also counted in 'No match'. These unconserved totals were likely to be misread, so the single assignment replaces the membership count.

Readers interested in a single region also want to know about reefs that extend into it but are counted elsewhere. These are reported in a separate partial count. The partial count is not conserved and must not be summed across regions. For a single region the table reads as: X reefs counted in the region, plus Y reefs that extend into it, covering Z km2 of reef.

CAPAD protected areas can overlap. A reef within two overlapping protected areas can be counted in both, and its area in the overlap is reported in both. This is the only intended departure from conservation, and its size is reported in the checks output.

### Input reef dataset
For this analysis we will use the latest version of the RB_Type_L2 classification reef dataset produced by script 13-make-RB_Type_L2.py. This dataset is available from "data/{version}/out/simp-classes/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L2_{version}.shp". It contains attributes RB_Type_L2 ('Coral Reef','Rocky Reef', 'Sediment', ...), Area_km2, ReefID, and other attributes not needed in this analysis. For this analysis we will only use the 'Coral Reef', and 'Rocky Reef' features. 

## Processing
All processing should be done in EPSG:3112 for consistancy. Output 

We need to convert the L2 reef boundaries into countable reefs. In this analysis we want to determine the number of reefs that exist in each region. However a reef needs to be of sufficient size and separation to be considered significant enough to be included in the count. Counting reefs is problematic because as the mapping scale changes reefs tend to be mapped with more small fragements. This can inflate the reported number of reefs in a region. To help standardise and normalise the count, before we start counting reefs in region we cluster reefs that are closer than 100 m apart, merging them into a single multi-part feature, then drop all reefs that have an effective width (width of a circle that is the same area as the reef) of less than 100 m. This clustering and filtering out of small reef clusters means that the there are less countable reefs than L2 reef features. This countable reefs processing should be done using reef_utils.cluster_countable with default values. This applies separate clustering for rocky reefs and coral reefs. Once we have countable reefs we simply need to divide them up into the different regions. Countability is determined once, globally, before any regionalisation processing.

Prior to cutting up the countable reef boundaries into regions they should each be given a CountFID. A temporary ID that makes it easy to determine that reef that is split into multiple parts in subsequent processing was from the same countable reef feature. This is not done by cluster_countable.

### Regionalisation settings
Each regionalisation is described by a settings record rather than global constants: short name, source path, identity field(s), slug, whether the between-region overlap check applies, and the near distance in metres. A near distance of `None` disables near regions for that regionalisation. For this analysis the settings are:

| Short name | Identity | Slug | Overlap check | Near distance |
|---|---|---|---|---|
| IMCRA v4.0 Meso-scale Bioregions (2023) | `MESO_NAME` | imcra | Yes | None |
| Analysis-regions v1 | `subregion` | analysis-region | Yes | None |
| CAPAD 2024 - Marine | `TYPE`, `NAME` | capad | No | 300 m |

### Near regions
Some regionalisation boundaries do not follow the true coastline. In CAPAD, the landward boundary of areas such as North Kimberley sits up to 400 m seaward or 300 m landward of the coastline, varying with the source used for each area. Some of these offsets look intentional, such as boundaries drawn around the outer edge of a fringing reef, so we do not reinterpret the boundaries. Instead, reefs just outside a region are assigned to a near region. This allows the report to state how many reefs lie just outside a protected area and to ask whether their exclusion is intentional or a product of boundary mapping precision. No land test is applied. Reefs are already clipped to the coastline in 10-clip-land.py, so near regions over land contain no reef.

A near region is the part of the area outside all regions of a dataset that is within the near distance of a region and closer to that region than to any other. Near regions are built outside the union of all regions, so a CAPAD near region never lies inside another protected area. Together the near regions partition the band between the union boundary and the near distance without overlap. Where two regions are both within the near distance of a location, the location belongs to the closer region. The near regions of two adjacent regions therefore meet along the line of equal distance rather than overlapping. Each near region carries the identity of its parent region (`RegionName`, or `TYPE` and `NAME` for CAPAD) and is flagged as near.

Near regions are only enabled for CAPAD, with a near distance of 300 m. Inspection of the CAPAD data indicates that 300 m captures more than 95% of reefs on the landward side of boundaries that probably should be within a marine park. Analysis-regions extends well landward of the coastline to include fringing reefs, so a near analysis is redundant. IMCRA land boundaries appear to be within about 60 m of the coastline, so almost no reefs fall completely outside it. Near regions can still be enabled for either dataset for debugging.

The near distance is approximate, so approximate near region shapes are acceptable where this makes them computationally feasible. Errors of a few tens of metres in the equal-distance line between two near regions are acceptable. Buffer each region by the near distance and subtract the union of all regions. Where only one region's buffer covers a location, the location belongs to that region's near region and the buffer is used directly. Only where buffers of two or more regions overlap does the nearest region need to be resolved. In these contested areas, sample points at about 10 to 25 m spacing along the boundaries of the competing regions, limited to boundary sections within the near distance of the contested area. Build Voronoi polygons from the samples, dissolve the cells by region and clip them to the contested area. This limits dense sampling to the small areas where regions compete, rather than the long coastal boundaries. The near region shapes should be cached and saved for review.

### Slicing
Each countable reef is cut into pieces: one per region it intersects, one per near region it intersects (where enabled), and a 'No match' piece for the remainder. For IMCRA and Analysis-regions, regions are applied as cookie cutters, removing each assigned piece from the reef so that area is never claimed twice. For CAPAD, intersect each protected area in turn with the original countable reef, not the reef remaining after intersection with other protected areas. Retain a separate piece for each (`TYPE`, `NAME`), even where pieces overlap. Then subtract the union of all protected areas from each reef once and divide this outside part between the near regions and 'No match'. Because near regions partition the outside band, outside pieces never overlap.

If a complex shaped reef is cut into multiple segments by a single region, the segments are merged into one multipart piece for that region before any further test. For CAPAD this grouping uses both `TYPE` and `NAME`, so two protected areas with the same name but different types remain separate. Near region pieces are grouped by their parent identity in the same way.

To deal with slivers, any merged piece that does not survive a 5 m negative buffer is removed. Test each region, near region and 'No match' piece separately. A removed sliver contributes no area, cannot receive the reef's count, and must not be reclassified as 'No match'. If the negative buffer test passes, the original cut piece is retained. This means that a very long feature less than 10 m wide will be removed. This is intentional. No mapped reefs are this narrow.

### Count assignment
After sliver removal, each reef's count is assigned to the piece with the largest area. Regions, near regions and 'No match' compete equally; 'No match' behaves as a region without a polygon. For example, a reef that is 40% in a protected area and 60% in its near region is counted in the near region, while its area is split 40% and 60% between them. Ties are resolved in favour of a region, then a near region, then 'No match'. Every reef must receive exactly one assignment; a reef with no surviving pieces is an error.

A reef is also counted in any other region that holds more than half of the reef's area. This treats each region as though it were the only region in the dataset: a reef must be more than half inside to out-compete 'No match'. The largest-piece rule is still needed so that every reef is counted somewhere. A reef split 40%, 35% and 25% between two adjacent protected areas and 'No match' would otherwise not be counted anywhere. For IMCRA and Analysis-regions, regions do not overlap, so the extra rule never applies. For CAPAD it applies to overlapping protected areas. In the Gulf of Carpentaria, two coral reefs fully within both the Gulf of Carpentaria Australian Marine Park and the Thuwathu/Walalu Indigenous Protected Area are counted in both. The rocky reef R-8840-340 is fully within the Indigenous Protected Area but only 13% within the Australian Marine Park, so it is counted in the Indigenous Protected Area and is a partial reef for the Australian Marine Park. These extra counts are the double counting accepted for overlapping protected areas.

The partial count of a region is the number of reefs with a surviving piece in that region that are not counted in it. A region's count and partial count never include the same reef. Near regions and 'No match' have partial counts in the same way.

'No match' includes reefs beyond the intended Australian reporting area (e.g. Timor), so it must not be used directly as the denominator for an inside-versus-outside comparison. For reporting, compare protected-area counts against the appropriate total for the Analysis-regions Commonwealth Marine Regions. Summed CAPAD counts include the overlap double counting; the checks output reports its size.

source reef polygons → filter Coral/Rocky → cluster_countable() → near regions (where enabled) → regional slicing → sliver removal → count assignment → checks → summary.

### Conservation checks
The slicing and assignment must be checked for conservation. Checks are not fatal: the script writes all outputs so that a failure can be debugged, records a `Status` of 'Pass' or 'Fail' for each check, and prints a summary of any failures at the end of the run. Only errors that prevent outputs being written, such as invalid geometry, stop the script. For every regionalisation, the number of assigned reefs, excluding CAPAD overlap extras, must equal the number of countable reefs for each reef type. For IMCRA and Analysis-regions, the area of all region, near region and 'No match' pieces plus removed slivers must equal the countable reef area. For CAPAD, do not compare the sum of individual protected-area areas with the input area, because overlapping protected areas intentionally double count their shared reef area. Instead, check that reef area within the union of all protected areas, plus near region area, plus 'No match' area, plus removed slivers, equals the countable reef area. Area checks use a tolerance of the larger of 1 m² and 1e-8 of the input area.

The check results should be printed and saved to working/{version}/A05/region-stats-checks.csv, with one row per regionalisation and reef type. Columns: Region_dataset, RB_Type_L2, Input_reef_count, Assigned_reef_count, Overlap_extra_count, Split_reef_count, Partial_count_sum, Near_assigned_count, No_match_assigned_count, Input_area_km2, Allocated_area_km2, Sliver_area_km2, Overlap_extra_area_km2, Status. `Assigned_reef_count` excludes overlap extras. `Split_reef_count` is the number of reefs with surviving pieces in more than one region, near region or 'No match'. `Partial_count_sum` is the sum of the partial counts over all rows, showing how far the old membership count would have exceeded the conserved count. `Overlap_extra_area_km2` is the summed protected-area reef area minus the reef area within the union of protected areas, and is zero for the other regionalisations.

IMCRA and Analysis-regions should not contain overlapping polygons, though they may touch. Check these datasets early, save a shapefile of any problematic overlaps and abort. The maximum allowable overlap is 5 m: an overlap polygon surviving a 2.5 m negative buffer is an error. This check is set per regionalisation, and a global boolean constant can disable it so vetted inputs need not be retested on every run. Do not run the between-region overlap check on CAPAD: overlaps between protected areas, including those with different (`TYPE`, `NAME`) values, are valid. Dissolving zones within each (`TYPE`, `NAME`) group handles their internal overlaps; no additional within-group overlap check is needed.

To help with debugging and checking of the results the intermediate cut up reef boundaries should be saved as shapefile for review. There should be one shapefile per regionalisation dataset. This should have attributes 'CountFID', 'RB_Type_L2', 'RegionName', 'Near', 'Assigned', 'Area_km2' for IMCRA and Analysis-regions. The CAPAD intermediate should retain `TYPE` and `NAME` separately in place of `RegionName`; its 'No match' pieces have no protected-area type or name. `Near` is 1 for near region pieces and 0 otherwise. `Assigned` is 1 for pieces that receive the reef's count, including CAPAD overlap extras, and 0 for pieces that only contribute area and a partial count. Filtering on `Assigned` = 1 shows where each reef was counted. Sliver pieces are kept in the intermediate shapefile with `Sliver` = 1 (and `Assigned` = 0) so that the area check can be recomputed from the cache; they are excluded from all counts and areas in the outputs.

Processing by this script should be saved to working/{version}/A05

Filenames something along the lines of:
working/{version}/A05/reefs-by-imcra.shp
working/{version}/A05/reefs-by-analysis-region.shp
working/{version}/A05/regions-capad-10m.shp
working/{version}/A05/near-regions-capad-10m-300m.shp
working/{version}/A05/reefs-by-capad-10m-near300m.shp
working/{version}/A05/region-stats-checks.csv
working/{version}/A05/debug-overlap-imcra.shp (This for the overlap of the regionalisation dataset, if there is any problems with the dataset)

As we expect the processing to be slow (~hour) each significant intermediate step should cache its output, allowing that step to be skipped on a repeat run. This is to allow later stages of the script to be debugged without needing to wait for multiple reruns of early processing steps. We will manually invalidate the cache by manually deleting files. The 10 m suffix on the CAPAD caches prevents unsimplified region geometries or reef cuts from being reused; changing the simplification tolerance should change the cache names. Likewise the near distance is part of the near region and reef cut cache names, so changing it, or enabling near regions for a regionalisation, does not reuse stale caches. Reef cut caches written before the `Near` and `Assigned` attributes existed must be deleted.

## Region summarisation
A CSV summary table should be generated that will have the following tall table:
Region_dataset, Region_type, Region_name, Near_region, Label, Coral_reef_count, Coral_reef_partial_count, Coral_reef_area_km2, Rocky_reef_count, Rocky_reef_partial_count, Rocky_reef_area_km2

For CAPAD, `Region_type` and `Region_name` contain the original `TYPE` and `NAME` fields, respectively; aggregate by both. For IMCRA and Analysis-regions, leave `Region_type` blank. For each dataset's 'No match' row, leave `Region_type` blank and use 'No match' for `Region_name`. Counts are the assigned counts, partial counts are reefs extending into the region but counted elsewhere, and areas are the clipped piece areas, including the parts of partial reefs. `Near_region` is 'Yes' for near region rows, which repeat the parent region's `Region_type` and `Region_name`, and 'No' otherwise, including 'No match'.

`Label` combines the identifying fields for use in report tables, in the form `{Near: }{Region_name}{ - Region_type}`, omitting the 'Near: ' prefix for rows that are not near regions and the ' - Region_type' suffix where `Region_type` is blank. Examples: 'Eighty Mile Beach - Australian Marine Park', 'Near: Eighty Mile Beach - Australian Marine Park', 'Kimberley' and 'No match'.

Areas should be output with 6 digits of precision. Counts should be integers. The CSV should be ordered by Region_dataset, then Region_type and Region_name for CAPAD (Region_name for the other datasets), with each near region row directly after its parent region. 'No match' should go at the bottom of the region names within a regional dataset.

Because the reef dataset will be cut up by the regionalisation datasets the areas will need to be recalculated from the intermediate cut up polygons. For this using the EPSG:3112 GDA94 / Geoscience Australia Lambert projection. Some of the reefs (Lord Howe, Norfolk, Coco Keeling, Christmas Islands) are outside the working are of this projection however the increased error is acceptable for this analysis. Each of the results for the 'No match' regions should be included as though it were a region.

Region_dataset: Short name of the regionalisation dataset: Full reference (don't include this in the CSV, just the short name)
 - `IMCRA v4.0 Meso-scale Bioregions (2023)`: DCCEEW (2023) IMCRA v4.0 - Meso-scale Bioregions (Version 17 Oct 2023) [Data set] https://fed.dcceew.gov.au/datasets/erin::integrated-marine-and-coastal-regionalisation-of-australia-imcra-v4-0-meso-scale-bioregions/about
 - `Analysis-regions v1`: Lawrey, E. (2025). Supporting datasets for estimating reef counts in the Coral Sea and northern Australia (NESP MaC 3.17, AIMS) (Version 1) [Data set]. eAtlas. https://doi.org/10.26274/xr0r-tb19
 - `CAPAD 2024 - Marine`: Department of Climate Change, Energy, the Environment and Water. (2025). Collaborative Australian Protected Areas Database (CAPAD) 2024 - Marine. [Data set]. https://fed.dcceew.gov.au/datasets/erin::collaborative-australian-protected-areas-database-capad-2024-marine/about


The CSV should only include regions and near regions that contain reef area after sliver removal. Under single assignment a region can contain reef area but no assigned reef count; such rows are included with a count of zero, since that zero is a true result. Regions outside the study area will not have false zeros reported. This should be a natural by-product of slicing reef boundaries and assigning them a region. The regions in the region datasets that are outside of the study area will never be assigned to a reef and thus should not appear in the summary table.

Save this result to data/{version}/out/stats/NW-Aus-Features_Region-stats_{version}.csv

## Addendum 1
Along with saving the reef counts and areas to a CSV file. These amounts should be saved in an export of each of the regionalisations as a shapefile. This will allow the creation of maps that show the regionalisation and a label showing the number of reefs in that region. The shapefile should contain the same regions and near regions as the CSV. Since `No match` has no spatial extent these results remain only in the CSV. These saved shapefiles should be based on the prepared regions used for cutting reefs (including CAPAD dissolved by `TYPE` and `NAME`), plus the near region shapes where enabled. Near regions are extra features in the same shapefile, with a `Near` attribute (1 for near regions, 0 otherwise) so they can be filtered out of a map. CAPAD's exported shapefile must retain both `TYPE` and `NAME`, with statistics joined on `TYPE`, `NAME` and `Near`. Each shapefile also carries the `Label` from the CSV, alongside `CoralCount`, `CoralPart`, `CoralKm2`, `RockyCount`, `RockyPart` and `RockyKm2`. These shapefiles should be saved to out/stats/NW-Aus-Features_Region-stats_{short region name}_{version}.shp, such as NW-Aus-Features_Region-stats_imcra_v1-2.shp and NW-Aus-Features_Region-stats_capad_v1-2.shp.


