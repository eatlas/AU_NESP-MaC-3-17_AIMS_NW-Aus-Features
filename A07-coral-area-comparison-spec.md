# A07 coral area comparison specification

## Purpose

Compare the area classified as `Coral/Algae` in the UQ benthic habitat mapping
with the area classified as `RB_Type_L3 = Coral Reef` in the current version of
the AIMS reef boundary mapping. Report the six Analysis-regions v1 subregions
where the mapping coverage is reasonably comparable: North, North-west and
South-west, each divided into Nearshore and Offshore.

This is a comparison of mapped areas, not a comparison of countable reefs or an
estimate of live coral cover.

## Inputs and download

- Read the current boundary dataset version from `[general] version` in
  `config.ini`. Use its L3 shapefile in
  `data/{version}/out/full-classes/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_{version}.shp`.
- Use `data/{version}/in-3p/nesp-3-17-analysis-regions/analysis-regions.shp`,
  identifying subregions by `subregion`.
- Add a single-file download to `01a-download-input-data.py` for the published
  UQ statistics CSV at
  `https://nextcloud.eatlas.org.au/public.php/dav/files/QBRBYaisJCgXf7g/stats/A02_Habitat-area-stats.csv`.
  Save it under `data/{version}/in-3p/UQ-shallow-habitat/A02_Habitat-area-stats.csv`.
  A07 must read this downloaded copy, not the habitat-processing workspace.

## Selection and calculation

Process the following `subregion` values in this order:

1. `North (Nearshore)`
2. `North (Offshore)`
3. `North-west (Nearshore)`
4. `North-west (Offshore)`
5. `South-west (Nearshore)`
6. `South-west (Offshore)`

Select all L3 polygons whose `RB_Type_L3` is exactly `Coral Reef`, including
small features. Clip the selected polygons to each subregion boundary, calculate
the clipped area in EPSG:3577, and sum it in km2 for that subregion. Do not use
the A05 countable-reef cache, cluster features, include `Coral Reef Flat`, or
apply the A05 sliver filter. Use the L3 geometries for the calculation rather
than the rounded per-feature `Area_km2` attribute.

In the downloaded habitat CSV, match `Regionalisation = Analysis-regions v1`,
`Mapping = Benthic`, `Class_id = 15`, `Class_name = Coral/Algae` and each exact
`Region_name` above. Use its `Area_km2` value without recalculating raster area.
Require one habitat row per requested subregion; report missing or duplicate
matches as errors rather than silently substituting zero.

The UQ estimates sum areas of 10 m habitat pixels assigned to subregions by
pixel centre on the WGS84 ellipsoid. The boundary estimates clip vectors and
calculate their area in EPSG:3577. Small differences arising from these
methods are acceptable for this comparison. Do not restrict the boundary
polygons to the footprint of classified UQ pixels.

## Report context and interpretation

This comparison is a cross-check of the two mapping products. Within the
selected regions, the mapped areas should be of a similar order of magnitude
if both products capture broadly the same distribution of coral reef habitat.
Close agreement is not expected because the classifications and their mapping
extents differ. A difference between the totals is not, by itself, evidence
that one product is more accurate.

The benthic habitat mapping classifies shallow substrate as `Coral/Algae`,
whereas the reef boundary mapping identifies the spatial extent of reef types.
The benthic map does not extend as deep as the boundary mapping. This can lead
to a smaller mapped area in deeper parts of reefs. However, dark substrates in
deeper water were sometimes classified as `Coral/Algae` by the automated model,
which can increase its reported area. The benthic mapping was also clipped
using an earlier version of the reef boundaries. Those boundaries were relatively
loose around some complex rocky reefs and included more sand than intended.
This created opportunities for dark, deeper parts of those areas to be included
and classified as `Coral/Algae`.

The `Coral/Algae` class does not distinguish coral or algae on coral reefs from
macroalgae on rocky reefs. Its area can therefore exceed the area mapped as
`Coral Reef` even where both products cover the same location. It should not
be interpreted as an estimate of coral cover or of coral reef area alone.

The reef boundaries were digitised manually at a coarser scale than the
benthic classification. They roughly distinguish active coral reef areas
(`Coral Reef`) from low-biomass reef flats (`Coral Reef Flat`), which are
mostly sand. This distinction was generally made for larger areas rather than
every small sand patch within a coral reef. The `Coral Reef` boundary area can
therefore include sand that the benthic mapping classifies separately. In
contrast, rocky reefs are classified separately from coral reefs in the
boundary mapping. Excluding them from the A07 boundary total tends to reduce
that total relative to `Coral/Algae`, which can include macroalgae on rock.
These effects can act in opposite directions, so similar totals would support
a broad cross-check but would not demonstrate close spatial agreement.

## Outputs

Write a CSV and a report-ready Markdown table in `data/{version}/out/stats/`,
named `A07_Coral-area-comparison_{version}.csv` and
`A07_Coral-area-comparison_{version}.md`. Both have six rows in the order above
and exactly these three columns, with area values in km2 to one decimal place:

| Region | Habitat mapping: Coral/Algae area km2 | Boundary mapping: Coral Reef km2 |
| --- | ---: | ---: |

Do not add difference, percentage or total columns or rows. The CSV contains
only the header and six data rows; the Markdown includes the following table
description before the table:

> Area of `Coral/Algae` in the UQ benthic habitat classification compared with
> area classified as `RB_Type_L3 = Coral Reef` in the AIMS reef boundary mapping,
> within the North, North-west and South-west Analysis-regions v1 subregions.
> The reef boundary mapping roughly separates actively growing coral reef areas
> (`Coral Reef`) from `Coral Reef Flat`, which is excluded here. These classes
> are broadly, but not exactly, comparable: `Coral/Algae` may also include algae
> on rocky reefs, and the benthic mapping does not extend as deep as the reef
> boundary mapping. 

## Validation

Check that all six requested subregions exist in the Analysis-regions shapefile,
that the inputs have the required fields, and that every output row has exactly
one matching habitat value. Verify the CSV and Markdown have the same six
values in the same order, and that their boundary areas were calculated from
the clipped L3 geometries, not from A05's L2 results.