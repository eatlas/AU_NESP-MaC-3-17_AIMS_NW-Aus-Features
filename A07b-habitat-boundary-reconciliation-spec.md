# A07b habitat and boundary reconciliation specification

## Purpose

Help the reader understand why the reef area from the AIMS reef boundary mapping
differs from the hard substrate area from the UQ benthic habitat mapping. Compare
`RB_Type_L2` in (`Coral Reef`, `Rocky Reef`) with the UQ benthic classes `Rock`,
`Rubble` and `Coral/Algae`. Use the same six Analysis-regions v1 subregions as A07.

We do not expect the two areas to match. The two mappings define a reef differently,
cover different depths and extents, and were made from different imagery. The
tables break the difference into parts that can each be explained.

## Inputs

- L3 boundaries:
  `data/{version}/out/full-classes/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_{version}.shp`.
- Subregions:
  `data/{version}/in-3p/nesp-3-17-analysis-regions/analysis-regions.shp`, field
  `subregion`.
- UQ benthic raster:
  `data/{version}/in-3p/UQ-shallow-habitat/NW_NESP-MaC-3-17_UQ_Shallow-habitat_Benthic_2025.tif`.
- UQ statistics:
  `data/{version}/in-3p/UQ-shallow-habitat/A02_Habitat-area-stats.csv`. These are
  used for class names and as a check only.

`01a-download-input-data.py` downloads the raster and the CSV.

## Method

### Overlay

Give each L3 feature an integer id (`rid`). Rasterise the `rid` values and the
subregions onto the 10 m benthic grid by pixel centre. Work in 4096 pixel tiles and
skip tiles that do not touch a subregion. Weight each pixel by its area on the
WGS84 ellipsoid, which is the method UQ used for A02. Record the area of each
(subregion, feature, benthic class) combination. Include pixels that have no
benthic class but fall inside a feature (`No habitat class`). Also include
classified pixels that fall outside all features (`No boundary feature`).

Cache the result in `working/{version}/A07b/benthic-by-feature.csv`. Rebuild it
when any input is newer than the cache.

### Polygon areas

Clip the coral and rocky reef polygons to each subregion. Measure the area in
EPSG:3577 (Australian Albers, equal-area). Do this twice, once for the whole
subregion and once for the subregion clipped to the raster bounding box. The
difference is the boundary area outside the habitat mapping extent.

### Checks

- Benthic class areas from the overlay must match the A02 CSV within 0.5% for each
  subregion and class.
- The rasterised coral and rocky reef area inside the raster extent must match the
  polygon area within 0.5% (plus 1 km²) for each subregion.
- The parts of Table A07b-1 must add up exactly to the overlap.

The script stops if a check fails.

## Outputs

Write the following to `data/{version}/out/stats/`:

- `A07b_Habitat-boundary-reconciliation_{version}.csv`: Table A07b-S1 with full
  precision.
- `A07b_Habitat-boundary-reconciliation_{version}.md`: Tables A07b-1, A07b-2 and
  A07b-S1 with captions. Tables A07b-1 and A07b-2 are sized for the report page.
  Table A07b-S1 is supporting detail.

### Table A07b-1: reconciliation for the report

The six subregions are combined into one column of areas. The table starts from
the boundary total. It then takes away each part of the boundary area that the
habitat mapping does not class as hard, which leaves the overlap. From the overlap,
it adds the hard substrate that lies outside the coral and rocky reef boundaries,
which gives the habitat total. Rows from the boundary total down to the overlap
are also shown as a % of the boundary total. Rows from the overlap down to the
habitat total are shown as a % of the habitat total. Each row has a short
explanation. There are no separate ratio rows.

All the `No habitat class` area is in one row. The explanation gives how much of
it is `Coral Reef Bank` and `Paleo Coast Rocky Reef`.

### Table A07b-2: make-up of each reef type

Show the percentages of hard substrate (Rock, Rubble and Coral/Algae combined),
Sand, and Seagrass, Light seagrass and Microalgal mats combined, for each
`RB_Type_L3`. Only use features that the habitat mapping covers almost completely.
A feature is included when it lies wholly inside the six subregions and the raster
extent, and at least 95% (`COVERAGE_MIN`) of its rasterised area has a habitat
class. This removes partly mapped features, such as fringing reefs whose deeper
outer edge is unmapped. Those features would otherwise bias the result towards
their shallow parts. Show how many features of each type were included. Do not
show types with fewer than 2 (`MIN_FEATURES`) included features, but count them in
the All rows.

### Table A07b-S1: reconciliation by subregion

The Table A07b-1 rows with one column for each subregion, a total column, and a
Source column. The final four rows are ratios, and the Source column gives the
formula for each.

## Interpreting the results

### Source of each row

| Row | Source |
| :--- | :--- |
| Reef boundary mapping total | Boundary polygons only. |
| Outside the habitat mapping extent | Boundary polygons only. This is the part of each polygon beyond the edge of the habitat raster. |
| No habitat class, Sand, Seagrass etc. | Boundary polygons divided up by habitat pixels. |
| Overlap | Boundary polygons divided up by habitat pixels. |
| Hard substrate in other boundary types or outside all boundaries | Habitat pixels divided up by boundary polygons. |
| Habitat mapping total | Habitat pixels only. It matches the published UQ statistics. |

The comparison is not independent. The habitat classes are used to divide up the
boundary area, and the boundaries are used to divide up the habitat area. Only the
two totals come from one dataset alone.

### Outside the habitat mapping extent

This row is not all the boundary area that has no habitat pixels. It is only the
boundary area beyond the edge of the habitat raster. In this study area that edge is
the southern limit near 29.1°S, so the row is non-zero only in the South-west
subregions. Boundary area inside the raster that UQ did not classify, for example
because it was too deep or too turbid, is in the `No habitat class` row.

### No habitat class

This is reef boundary area inside the habitat raster where the raster has no class,
mostly because the seabed was too deep or turbid to see. About half of it is
`Coral Reef Bank` and `Paleo Coast Rocky Reef`. These types are mostly deeper than
the habitat mapping could see, so they are almost entirely unclassified. The rest
is the deeper or turbid parts of other reef types. The row does not show that the
mappings disagree. It shows where the habitat mapping has no data.

### Coverage of Tables A07b-1 and A07b-S1

These tables use every coral and rocky reef feature in the six subregions, clipped
to the subregions. No features are excluded. Table A07b-2 differs, because it only
uses features that the habitat mapping covers almost completely.

### Ratios

Table A07b-1 shows the first and last of these ratios in its two % columns. Table
A07b-S1 shows all four as rows.

#### Overlap as % of reef boundary area

This is the share of coral and rocky reef boundary area that the habitat mapping
classes as hard substrate. It is not the share of the boundary area that the
habitat mapping covers. The low value (about 45% overall) is mostly due to the
extent, the unclassified deep areas, and sand inside reef boundaries.

#### Reef boundary area with a habitat class, as % of reef boundary area

This is the habitat mapping's coverage of the reef boundaries. It is the share of
boundary area that has any habitat class. Use this row, not the overlap row, to
describe how much of the reef boundary area the habitat mapping covers.

#### Overlap as % of reef boundary area with a habitat class

This is the share of the boundary area that the habitat mapping classified as hard
rather than soft. It answers the question: where both mappings have data, how much
of the reef boundary is hard substrate? The rest is mostly sand within reef
boundaries. Examples include sand on reef flats, sand in lagoons and sand between
patch reefs that the boundary mapping drew as part of one reef. Table A07b-2 gives
the breakdown by reef type.

#### Overlap as % of habitat hard substrate

This is the share of habitat hard substrate that falls inside the coral and rocky
reef boundaries. A high value (about 91%) means the boundary mapping includes most
of the hard substrate that the habitat mapping found. The rest lies in other
boundary types or outside all boundaries. In other boundary types it is mostly in
Sand Bank and High Intertidal Sediment Reef, which are largely sediment. Outside
all boundaries, part of it may be in the shallow intertidal sediment zone along
the coast. The boundary mapping did not map this zone, but the habitat mapping did,
and may class parts of it as Rock, Rubble or Coral/Algae. The rest could be reefs
the boundary mapping missed or drew too small, often small or low relief rocky
reefs. It could also be false positives in the habitat
mapping. This table cannot tell these apart. Visual checks of the outside area are
needed for that.

### Table A07b-2

The percentages describe what a fully mapped feature of each type is made of,
according to the habitat mapping. They should not be multiplied by the type's total
area. The included features are biased towards shallow, clear water features,
because these are the ones the habitat mapping covers completely. A type with few
included features, or with little included area, should not be read too closely.
