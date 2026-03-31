# Appendix: Assessment of previously unmapped reefs

## Problem statement

A key objective of this project was to produce comprehensive reef boundary mapping across northern and western Australia, covering regions where existing spatial datasets were limited or absent. A natural question arising from this work is: how many of the mapped reef features are newly mapped? That is, how many reefs in the North and West Australian Tropical Reef Features dataset (Lawrey et al., 2025) had no prior spatial representation in any published dataset?

Answering this question requires a clear and defensible definition of what it means for a reef to have been "previously mapped." Several spatial datasets exist that contain information about reef locations across the study area. These include the Australian Hydrographic Service (AHS) seabed area features derived from electronic navigational charts (Institute for Marine and Antarctic Studies, 2017), the ReefKIM geodatabase covering the Kimberley region (Kordi et al., 2016), the UNEP Global Distribution of Coral Reefs (UNEP-WCMC et al., 2021), the Allen Coral Atlas reef extent layer (Allen Coral Atlas, 2022), various regional habitat maps collated by Seamap Australia, and bathymetric datasets such as the multi-resolution bathymetry composite for Australian waters (Flukes, 2024). Each of these sources varies in spatial resolution, classification intent, and accuracy. None were produced with the same scope and objectives as the present dataset and so direct comparison requires careful treatment of scale, classification, and purpose.

The central challenge is that "previously mapped" exists on a continuum. At one extreme, a reef may have been precisely delineated in a published spatial dataset at a comparable resolution to our mapping. At the other extreme, a reef may be faintly visible in satellite imagery or bathymetry but has never been identified, delineated, or recorded in any dataset. Between these extremes lie many intermediate states. A reef may appear as a depth sounding on a marine chart, indicating that its existence was known, but without any boundary delineation. A reef may fall within a large, coarsely drawn polygon in the Allen Coral Atlas reef extent layer, but that polygon may cover an area many times the size of the actual reef and include substantial areas with no reef at all. A reef may be clearly visible in multibeam bathymetry but no boundary has ever been drawn around it. Each of these situations requires a judgment about whether the reef should be considered as already mapped.

This appendix sets out the criteria used to assess whether each reef feature in the dataset was previously mapped, describes the reference datasets used for comparison, explains the methods applied, and presents the results.


## Background

### The distinction between knowledge and mapping

In developing the assessment criteria we found it useful to distinguish between two related but separate claims. The first is that the existence of a reef at a particular location was previously known. The second is that the spatial extent and boundary of that reef was previously mapped. A depth sounding on a marine chart demonstrates that the presence of a shallow feature at that location was known, but it does not constitute a delineation of the reef boundary. Similarly, a reef that is clearly visible in a hillshade rendering of bathymetry data is in some practical sense "known," but it has not been mapped in the sense of having a boundary drawn around it in a spatial dataset that could be used for area calculations, management planning, or environmental accounting.

This distinction matters because the dataset we are assessing (Lawrey et al., 2025) is a boundary mapping product. Its contribution is the delineation of reef features as spatial polygons, not merely the identification of reef presence. The appropriate question is therefore whether each reef had a prior boundary delineation, not merely whether its existence was previously known.

At the same time, we recognise that claiming a reef as "newly mapped" when it was already well known and clearly resolved in widely available data would overstate the contribution of this project. Many reefs, particularly in coastal areas, are well known to local communities, fishers, and maritime operators even though they do not appear in any published spatial dataset. Furthermore, reefs that are clearly resolved in high-resolution bathymetry datasets have in a practical sense been characterised, even if no one has drawn a polygon around them. We therefore adopt a tiered classification that distinguishes between reefs that are genuinely new to the spatial record, reefs that were previously indicated but not delineated, and reefs that were already mapped.

### Reference datasets

The following datasets were used as references for the "previously mapped" assessment.

**AHS seabed area features.** This dataset contains seabed area polygons derived from the Australian Hydrographic Service's S-57 electronic navigational chart series (Institute for Marine and Antarctic Studies, 2017). The polygons represent predominantly shallow seabed features that appear on marine charts. The dataset includes all seabed substrate types, not only reef features. For the purpose of this analysis we pre-filter the dataset to records classified as coral, rock, stone, or sand/mud/coral in the native classification field. This excludes non-reef substrate types such as sand, mud, and gravel. Marine charts are produced for navigational safety rather than ecological mapping. As a result, feature boundaries are often exaggerated to ensure that vessels maintain safe clearance from hazards. The scale of the marine charts is typically coarser than the reef mapping produced in this project. For example, a reef that is 200 m across in reality may be represented as a 500 m hazard area on the chart. Despite these limitations, the AHS dataset provides the most comprehensive existing spatial coverage of charted reef features across the study area. The AHS seabed area dataset only captures the shallowest portions of reef features. Deeper reefs, submerged shoals, and features indicated only by depth soundings or danger symbols on the charts are not represented as polygons in this dataset.

**ReefKIM.** The ReefKIM geodatabase provides the first comprehensive spatial compilation of reef features in the Kimberley bioregion of Western Australia (Kordi et al., 2016). The reef boundaries in ReefKIM were digitised at approximately 1:400k scale, roughly one half to one third the resolution of the mapping produced in this project. ReefKIM does not subdivide reef boundaries into finer classifications and so its features do not require dissolving prior to comparison. We treat ReefKIM similarly to the AHS data in that both are at a different scale to our mapping but represent deliberate delineations of reef features.

**UNEP Global Distribution of Coral Reefs.** This dataset is the most comprehensive global dataset of warm-water coral reefs, compiled from multiple sources by UNEP World Conservation Monitoring Centre and the WorldFish Centre, in collaboration with WRI and TNC (UNEP-WCMC et al., 2021). Approximately 85 percent of the dataset originates from the Millennium Coral Reef Mapping Project, which used 30 m resolution Landsat 7 imagery acquired between 1999 and 2002. In most parts of the world the UNEP dataset provides reef boundaries at a resolution derived from this Landsat mapping. In our study area, however, the reef features are not derived from the Millennium Coral Reef Mapping Project. Instead they originate from an unknown source that represented reefs as line features, which were then buffered to approximately 300 m width. As a result the reef polygons in northern and western Australia appear as elongated strips rather than as representations of the true reef shape or extent. In this respect the UNEP polygons in the study area are similar to the Allen Coral Atlas reef extent in that they indicate a reef could occur somewhere near the mapped line, without providing precision about the shape or structure. Despite this limitation, the UNEP dataset does attempt to identify individual reef features and their approximate locations. To be conservative in the results we treat the UNEP data in the same way as the ReefKIM and AHS datasets. Any reef in our mapping that spatially overlaps with a UNEP coral reef polygon is classified as previously mapped, regardless of the quality or scale of the UNEP delineation.

**GEODATA TOPO 250K Series 3 marine hazard areas.**  This dataset is not a dedicated reef-boundary mapping product (Geoscience Australia, 2006). Series 3 is the public release of Geoscience Australia's 1:250,000 National Topographic Database, compiled from the Series 2 working database and its associated NATMAP/NTMS-JOG revision workflow. The MarineHazardAreas reef subtype denotes rock or coral exposed near low tide, or just below it, that is visually prominent or hazardous to shipping. These features are best interpreted as topographic and navigational hazard representations of known shallow reefs, generalised from older map-production sources and later revisions. About 85 percent of the features in this dataset were mapped in the 1970s and early 1980s.

**AHO electronic navigational charts (WMS).** The AHS seabed area features described above capture only a subset of the information shown on marine charts. To assess deeper reef features and features indicated by symbols rather than polygons, we use the AHO electronic navigational chart raster imagery accessed via a Web Map Service (WMS). This is used for manual review only and cannot be processed automatically. We primarily refer to the depth soundings and drawn boundaries around features to assess alignment with mapped reef boundaries.

**Multi-resolution bathymetry composite.** The multi-resolution bathymetry composite for Australian waters (Flukes, 2024) provides mosaicked bathymetry from all publicly available sources within the Australian Exclusive Economic Zone. For this analysis we use the shallow zone (0 to 30 m) and mesophotic zone (30 to 70 m) mosaics, both at 10 m resolution. At this resolution almost none of the original source bathymetry data is lost, meaning the detail is limited by the source surveys rather than the mosaic gridding. Bathymetry data quality varies substantially across the study area. In regions with multibeam survey coverage, reef features are typically well resolved. In regions relying on interpolated soundings or satellite-derived bathymetry, reef features may be poorly resolved or indistinguishable from noise. The bathymetry is used during manual review to assess whether a reef feature was clearly discernible from existing data, and is not used as an automated input.

**Allen Coral Atlas reef extent.** The Allen Coral Atlas reef extent layer represents a generalised depiction of the shallow coral reef environment visible from satellites (Allen Coral Atlas, 2022). It combines the Atlas's geomorphic zonation maps, a machine-learning-based coral reef habitat layer, and a smoothed extent layer with hole-filling. In our study area this layer closely approximates a continuous reef extent along most of the coastline perimeter. In regions where reefs are in fact discontinuous, separated by sandy bays or other non-reef substrate, the reef extent layer does not resolve individual reef features. The reef extent layer does not separate out most of the fringing reefs, but rather is predominantly representing fringing areas where reefs might occur, meaning we find that many large sandy bays with no reef are included within the reef extent. As a result, the reef extent layer does not constitute feature-level mapping. It indicates the general region in which reefs may occur but does not delineate individual reef boundaries or distinguish reef from non-reef substrate at the feature scale. We exclude the Allen Coral Atlas reef extent layer from the "previously mapped" assessment for this reason. A feature-level comparison is not meaningful when the reference dataset does not identify individual features. We note for context that the majority of our mapped reef features fall within the Allen Coral Atlas reef extent, which is expected given that both datasets target shallow reef environments visible from satellite imagery.


## Methods

### Reef unit definition

The reef mapping in this project uses a hierarchical classification scheme. The finest level, Reef Boundary Type Level 3 (RB_Type_L3), subdivides reefs into distinct structural and ecological zones. For example, a coral reef may be divided into an actively growing outer zone (classified as "Coral Reef" at L3) and a sandy inner flat that is geomorphically part of the same reef structure (classified as "Coral Reef Flat" at L3). At the coarser Level 2 (RB_Type_L2), both of these L3 types roll up into a single "Coral Reef" classification. Similarly, all rocky reef L3 types roll up into "Rocky Reef" at L2.

For the purpose of counting reefs and assessing whether they were previously mapped, we use the L2 classification. Adjacent reef features that share the same L2 class are dissolved into single polygons representing the full geological extent of each reef structure. This ensures that each reef is counted once regardless of its internal zonation. The dissolution also ensures that the reef count is conservative, because merging adjacent features produces fewer, larger reefs rather than many small sub-features. Only coral reefs and rocky reefs are included in the newly mapped assessment. Sand banks and other sediment features are excluded. This dissolution is performed by the script `12-make-RB_Type_L2.py`, where neighbouring features of the same L2 type are merged via a geometric union and then exploded back into singlepart polygons. Attributes are aggregated across the constituent L3 features for each dissolved L2 polygon.

### Countable reef clusters

A raw count of dissolved L2 polygons is sensitive to mapping resolution and classification granularity. Finer resolution reveals progressively more small features, and extending mapping to greater depths uncovers previously unseen structures. To produce a meaningful and repeatable reef count we apply the counting methodology of Lawrey, Bycroft and Hammerton (2026), which defines countable reefs using two parameters: a minimum separation distance and a minimum reef size threshold.

First, dissolved L2 polygons of the same reef type that are separated by less than 100 m are clustered into a single countable reef. This is implemented by buffering each polygon boundary by 50 m (half the clustering distance), computing the unary union of all buffered polygons, and exploding the result into singlepart polygons. Each singlepart polygon defines a cluster envelope. The original unbuffered polygons are then assigned to clusters based on which envelope they intersect, and the combined area of the originals within each cluster is computed. The 100 m clustering distance was chosen on the basis of grazing halo widths observed around patch reefs and reef channel widths in densely packed reef systems. The full justification is given in Lawrey, Bycroft and Hammerton (2026).

Second, each cluster is assessed against a minimum size threshold. The total reef area within the cluster is converted to an effective reef width, defined as the diameter of a circle with the same area:

$$W = 2\sqrt{\frac{A}{\pi}}$$

where $A$ is the combined area of all original polygons in the cluster. Clusters with an effective width below 100 m are excluded from the count. A 100 m effective width corresponds to an area of approximately 7,854 m². Features below this threshold represent isolated bommies or very small reef patches rather than countable reef structures.

For reporting purposes, countable reef clusters are assigned to size classes based on effective width: small (100 to 300 m), medium (300 to 1,000 m), large (1,000 to 3,000 m), and very large (greater than 3,000 m). Coral reefs and rocky reefs are counted and reported separately throughout.

The clustering and size filtering are performed before comparison with reference datasets. This means that the unit of analysis for both automated spatial matching and manual review is the countable reef cluster, not the individual dissolved L2 polygon.

### Tier 1: Automated spatial matching

Each countable reef cluster is tested for spatial intersection against three reference datasets: the AHS seabed area features, ReefKIM, and the UNEP Global Distribution of Coral Reefs. All three datasets are matched against both coral reef and rocky reef clusters without distinguishing reef type. This avoids false negatives arising from classification mismatches between datasets. For example, the UNEP dataset classifies some rocky reef features as coral reefs, and the AHS native classification does not align directly with the ecological classification used in our mapping.

The intersection test uses a simple "intersects" predicate. Any degree of overlap, including partial overlap, is sufficient to classify a reef cluster as previously mapped. This is a deliberately conservative threshold. Because the reference datasets were produced at coarser scales than our mapping, positional offsets between corresponding features are expected. A strict area-overlap requirement (for example, 50 percent) would penalise the reference datasets for their lower resolution and risk incorrectly classifying well-known reefs as newly mapped. By accepting any intersection, we ensure that reefs with a prior spatial representation are not falsely claimed as new.

This conservative approach means that a reef cluster that is only grazed by the edge of an AHS polygon will be classified as previously mapped, even if the AHS polygon was not specifically intended to represent that reef. We accept this because the overall effect is to reduce the count of newly mapped reefs, making the final result more defensible.

The Tier 1 matching is implemented in the script `A02-unmapped-reefs.py`. All layers are reprojected to EPSG:4283 (GDA94 geographic) prior to spatial operations to ensure consistent geometry comparisons.

### Tier 2: Manual review against marine charts and bathymetry

The AHS seabed area features only capture the shallowest portions of charted reef features. Deeper reef features, and features indicated on marine charts by depth soundings, reef symbols, or danger boundaries rather than by polygons, are not represented in the AHS dataset. To account for these, reef clusters not matched in Tier 1 are manually reviewed against two additional sources: the AHO electronic navigational charts accessed via WMS and the multi-resolution bathymetry composite (Flukes, 2024) visualised as a hillshade.

The manual review follows a point-tagging workflow in QGIS. The countable reef clusters generated by the analysis script are loaded alongside the reference data source being assessed. The operator inspects each unmatched cluster and, where a match is identified, places a point within the cluster polygon. Four separate point shapefiles are used, one for each combination of source and confidence level: chart-mapped, chart-indicated, bathymetry-mapped, and bathymetry-indicated. The file into which a point is placed determines the classification assigned to that cluster. This workflow avoids the need to enter attributes for each point, which substantially reduces the time required to tag several thousand reef clusters.

The following rules guide the tagging decisions for marine charts. If a reef symbol, named reef feature, or charted danger or shoal boundary overlaps the cluster, the cluster is tagged as chart-mapped. This indicates that the feature had a prior spatial representation on the chart. If a depth sounding on the chart falls near the cluster but no boundary or reef symbol is present, the cluster is tagged as chart-indicated. The sounding demonstrates that the existence of a shallow feature at that location was known, but no boundary was delineated.

For bathymetry, the criterion is whether the shape and extent of the reef can be made out in the hillshade rendering to within approximately 50 percent of the reef cluster area. If so, the cluster is tagged as bathymetry-mapped. If the reef is partially discernible but the boundary cannot be reliably traced, the cluster is tagged as bathymetry-indicated. This assessment is performed visually rather than through automated analysis. Automated detection of reef features from bathymetry would require development and calibration of depth-dependent height thresholds, handling of resolution heterogeneity across the composite, and treatment of edge effects near land and reef clusters. This constitutes a substantial analysis effort in its own right and is beyond the scope of this appendix.

The manual review is necessary but labour-intensive. It is applied only to the subset of reef clusters not resolved by Tier 1, which substantially reduces the number of features requiring inspection.

### Classification

Based on the results of Tiers 1 and 2, each countable reef cluster is assigned one of the following statuses:

| Status | Criteria |
|---|---|
| **Previously mapped** | Spatial intersection with ReefKIM, AHS, or UNEP features (Tier 1), or tagged as chart-mapped or bathymetry-mapped (Tier 2). |
| **Previously indicated** | No Tier 1 match and no "mapped" tag, but tagged as chart-indicated or bathymetry-indicated (Tier 2). |
| **Newly mapped** | No prior spatial representation identified in any assessed reference dataset or manual review. |

This three-level classification allows reporting at multiple levels of confidence. The headline count of newly mapped reefs is the most conservative figure, representing only those reef clusters with no prior spatial indication in any dataset assessed. The "previously indicated" category captures reefs that were known to exist in some form but had never been spatially delineated as polygon boundaries. Coral reefs and rocky reefs are reported separately throughout.

### Exclusions

The Allen Coral Atlas reef extent layer (Allen Coral Atlas, 2022) is excluded from the "previously mapped" assessment. The reef extent layer does not constitute feature-level mapping. In the study area it approximates a continuous reef boundary along much of the coastline, including sandy bays and non-reef substrate. Individual reef features are not distinguished from one another and the layer includes all classification types without differentiation. As a result, a spatial intersection between the reef extent layer and a mapped reef does not demonstrate that the specific reef was previously delineated. Including this layer would lead to the conclusion that nearly all reefs were "previously mapped," which would be inconsistent with the practical meaning of that term. We note that the Allen Coral Atlas geomorphic and benthic habitat maps do provide feature-level classification within the reef extent, but these products were not available for the entirety of our study area and their use as a "previously mapped" reference is deferred to future work.

Regional habitat maps compiled by Seamap Australia are similarly not systematically incorporated into the automated assessment. Where such maps are available and provide feature-level reef delineations, they may be considered during manual review, but they are not used as a Tier 1 automated input due to the heterogeneity of their spatial coverage, classification schemes, and mapping scales.


## Results

### Countable reef clusters

Application of the clustering and size filtering methodology produced 6,531 countable reef clusters across the study area: 3,605 coral reef clusters and 2,926 rocky reef clusters. Each cluster represents a group of dissolved L2 reef polygons of the same type separated by less than 100 m, with a combined effective width of at least 100 m. These clusters form the unit of analysis for all subsequent matching and classification steps.

### Tier 1 automated matching coverage

The four reference datasets used for automated spatial matching (AHS, ReefKIM, UNEP, and GA Geotopo 250k) collectively matched 2,888 of the 6,531 countable reef clusters (44.2%). The remaining 3,643 clusters (55.8%) were not intersected by any Tier 1 reference dataset and required manual review against bathymetry and marine charts (Tier 2).

Individual dataset coverage varied considerably. Table 1 summarises the total number of clusters matched by each dataset, the percentage of all countable clusters this represents, and the unique contribution of each dataset. The unique contribution is the number of clusters matched exclusively by that dataset, with no spatial intersection from any other Tier 1 source. The individual totals sum to 5,223, substantially exceeding the 2,888 unique matches. This indicates substantial overlap between the reference datasets, with many reef clusters independently represented in more than one source. The sum of the unique contributions (1,322) accounts for less than half of the 2,888 matched clusters, confirming that the majority of matched clusters are covered by two or more sources.

**Table 1.** Individual and unique coverage of each Tier 1 reference dataset against 6,531 countable reef clusters.

| Dataset | Total matches | % of clusters | Unique matches | Unique % |
|---|---|---|---|---|
| AHS seabed area features | 2,019 | 30.9 | 570 | 8.7 |
| GA Geotopo 250k | 1,548 | 23.7 | 259 | 4.0 |
| ReefKIM | 1,016 | 15.6 | 306 | 4.7 |
| UNEP coral reefs | 640 | 9.8 | 187 | 2.9 |
| **Combined** | **2,888** | **44.2** | — | — |

Table 2 shows the pairwise overlap between datasets, that is, the number of clusters matched by both datasets in each pair. The largest overlap was between AHS and GA (1,173 clusters). This is expected given that both derive from Australian government sources representing charted shallow features. The overlap between AHS and ReefKIM (651 clusters) reflects the Kimberley region where both datasets provide coverage. Pairwise overlaps involving UNEP were smaller, consistent with the limited and coarse coverage of the UNEP dataset in the study area.

**Table 2.** Pairwise overlap between Tier 1 reference datasets (number of clusters matched by both).

| | AHS | GA | ReefKIM | UNEP |
|---|---|---|---|---|
| **AHS** | — | 1,173 | 651 | 383 |
| **GA** | | — | 493 | 370 |
| **ReefKIM** | | | — | 122 |
| **UNEP** | | | | — |

A cumulative analysis, adding datasets in order of decreasing individual coverage, illustrates the diminishing marginal contribution of each source. AHS alone accounts for 2,019 matched clusters. Adding the GA Geotopo 250k contributes only 375 additional clusters beyond those already matched by AHS, despite its 1,548 individual matches. ReefKIM then adds 307 new clusters, and UNEP adds a further 187. This pattern reflects the high degree of redundancy between Australian navigational and topographic datasets, while ReefKIM and UNEP each contribute a modest but non-trivial number of clusters not captured by the other sources.

### Tier 2 manual review

_[To be completed. This section will report the results of manual tagging against bathymetry hillshade and AHO electronic navigational chart WMS imagery. It will describe how many of the 3,643 unmatched clusters were classified as chart-mapped, chart-indicated, bathymetry-mapped, or bathymetry-indicated through the point-tagging workflow.]_

### Classification summary

_[To be completed. This section will present the final three-tier classification (previously mapped, previously indicated, newly mapped) for all 6,531 countable reef clusters, broken down by reef type (coral reef and rocky reef) and by size class. It will combine the Tier 1 automated matches with the Tier 2 manual tags to produce the headline counts of newly mapped reefs.]_

### Size class distribution of newly mapped reefs

_[To be completed. This section will report the size class breakdown (small, medium, large, very large) of the newly mapped reef clusters, separately for coral reefs and rocky reefs. This provides context on whether the newly mapped reefs are predominantly small patch reefs or include larger reef structures.]_


## References

Allen Coral Atlas (2022). Imagery, maps and monitoring of the world's tropical coral reefs. https://doi.org/10.5281/zenodo.3833242

Flukes, E. (2024). Multi-resolution bathymetry composite surface for Australian waters (EEZ) [Data set]. Institute for Marine and Antarctic Studies (IMAS). https://metadata.imas.utas.edu.au/geonetwork/srv/eng/catalog.search#/metadata/69e9ac91-babe-47ed-8c37-0ef08f29338a

Geoscience Australia (2006). GEODATA TOPO 250K Series 3 (Shape file format). Geoscience Australia, Canberra. https://pid.geoscience.gov.au/dataset/ga/64058

Institute for Marine and Antarctic Studies. (2017). Seabed area on the Australian continental shelf and Lord Howe Island shelf derived and aggregated from Australian Hydrographic Service's (AHS) seabed area features (sbdare_a) from the 1 degree S57 file series [for NESP D3] [Data set]. University of Tasmania. https://metadata.imas.utas.edu.au/geonetwork/srv/eng/catalog.search#/metadata/f56d4f73-7444-4335-8c46-dce34db915f9

Kordi, M. N., Collins, L. B., O'Leary, M., & Stevens, A. (2016). ReefKIM: An integrated geodatabase for sustainable management of the Kimberley Reefs, North West Australia. Ocean & Coastal Management, 119, 234-243. https://doi.org/10.1016/j.ocecoaman.2015.11.004

Lawrey, E., Bycroft, R., & Markey, K. (2025). North and West Australian Tropical Reef Features - Boundaries of coral reefs, rocky reefs and sand banks (NESP-MaC 3.17, AIMS, Aerial Architecture) (Version 0-4) [Data set]. eAtlas. https://doi.org/10.26274/XJ4V-2739

Lawrey, E., Bycroft, R., & Hammerton, M. (2026). Mapping the reefs of the Coral Sea. Report prepared for Parks Australia. Australian Institute of Marine Science. https://doi.org/10.26274/96ft-5236

UNEP-WCMC, WorldFish Centre, WRI, TNC (2021). Global distribution of coral reefs, compiled from multiple sources including the Millennium Coral Reef Mapping Project. Version 4.1, updated by UNEP-WCMC. Includes contributions from IMaRS-USF and IRD (2005), IMaRS-USF (2005) and Spalding et al. (2001). Cambridge (UK): UN Environment Programme World Conservation Monitoring Centre. https://doi.org/10.34892/t2wk-5t34
