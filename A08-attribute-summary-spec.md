# A08: Overview of dataset attributes

## Purpose and reporting role

This analysis characterises the recorded depth and confidence attributes of the entire published L3 dataset. The output is intended for an appendix titled "Overview of dataset attributes". A short reference from the main Results is sufficient. These distributions describe the contents of the mapping product, not ecological distributions across a region or independently measured mapping accuracy.

All features and the full geographic extent are included. This covers coral and rocky reefs, sediment features, microbial and sediment reefs, and other classes. Offshore islands, shelf-edge reefs and partial Timor/Indonesian mapping remain included. There is no regionalisation, clipping, countable-reef filtering or area weighting.

The subsequent national dataset will combine the reef mapping sources and extract the best available bathymetry within each reef. That workflow can describe area within depth bands and flag the percentage of potentially unreliable bathymetry through inconsistencies with recorded feature depth categories. Bathymetry resolution, coverage and accuracy will still constrain those results. A08 does not duplicate that analysis or claim those checks have been completed for this report.

## What the tables measure

Each published L3 record counts once per attribute. A multipart geometry remains one record. Features subdivided into several L3 classes contribute several records. Small features and large complexes have equal weight. These are feature counts, not countable reefs, independent ecological units or habitat areas. Percentages use all published L3 records, including those with missing attribute values.

| Attribute | Meaning | Important distinction |
| :--- | :--- | :--- |
| DepthCat | Recorded depth category of the shallowest representative portion or peak of a feature | Does not describe the whole feature's depth range or area in a depth band |
| FeatConf | Digitiser-assessed confidence that a mapped feature is genuine rather than an image artefact or misinterpretation | Not a measured detection probability or estimate of completeness |
| TypeConf | Digitiser-assessed confidence that the assigned feature classification is correct | A genuine feature can have an uncertain type; not independently measured classification accuracy |

The confidence categories are expert assessments. They must not be converted into probabilities or presented as validation results. Identical labels in FeatConf and TypeConf refer to different questions. A high proportion of High feature confidence does not demonstrate a high proportion of correct reef classifications.

## Depth definitions and limitations

The shallowest portion may occupy only 5-10% of a feature's area. An intertidal fringing reef can continue into much deeper water. Reporting the whole feature area under its peak category would be misleading, so no depth-category areas are generated. The NW metadata describes the shallow portion using a percentile, while the Coral Sea methodology describes peak visibility. A08 uses the published attribute without recalculating either quantity.

| Category | Interpretation |
| :--- | :--- |
| Land | Recorded above-water land category; retained for non-reef feature types where present |
| Surface | Recorded water-surface category; retained where present |
| Intertidal | Features interpreted as exposed at low tide, typically using infrared imagery |
| Very Shallow | Very shallow submerged features, with a nominal threshold near 2.5 m below Lowest Astronomical Tide (LAT), generally using red-band visibility |
| Shallow | Features interpreted as shallower than the mesophotic division, generally visible in the green band |
| Deep | Features interpreted as mesophotic, generally not detectably visible in the green band |
| Unassigned | Null, blank or whitespace-only published attribute values |

The coarse categories support Parks Australia's Natural Values Common Language (NVCL). NVCL uses a nominal 30 m shallow/mesophotic division. The clear-water Coral Sea calibration found a green-band reef-peak detection threshold near 25 m LAT. These are different measurements and tidal references. The Coral Sea report explains their approximate correspondence through reef-peak versus pixel-averaged depths. A08 performs no tidal conversion and does not verify those limits locally.

Most depths were estimated directly from satellite imagery. The calibration of the spectral category limits has not been adapted to local conditions throughout this dataset. Turbidity, coloured dissolved organic matter, substrate reflectance, tides, feature size and image noise affect visibility. Few Deep features cannot be interpreted as evidence that deep reefs are scarce, nor can the percentage of missing reefs at depth be estimated from these tables.

Published processing in 12-expand-attribs.py defaults missing input DepthCat values to Shallow. Zero Unassigned published values therefore does not establish that every depth estimate was independently assessed. Checking this would require comparison with the editable source and depth-source records.

The calibration rationale is documented in Lawrey, Bycroft and Hammerton (2026), *Mapping the reefs of the Coral Sea*, sections "Assigning depth classification" and "Calibration Against AHO Marine Chart Depths". The final classification documentation remains the authority for attribute definitions. Coral Sea calibration accuracy must not be transferred to this dataset.

## Inputs and processing

Read [general] version from config.ini. Read attributes from data/{version}/out/full-classes/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_{version}.shp using GeoPandas with ignore_geometry=True. Paths resolve relative to the script directory. Required columns are DepthCat, FeatConf and TypeConf. Reject missing required columns and empty datasets.

For each attribute, trim surrounding whitespace and convert null and empty values to Unassigned. Do not merge different non-empty labels or change expert classifications. Retain additional categories not in the preferred order, print a diagnostic and append them alphabetically before Unassigned. This allows future categories to remain visible without silently removing features or changing the denominator.

Depth categories appear in the order Land, Surface, Intertidal, Very Shallow, Shallow and Deep where present. Surface is a possible value documented in the dataset metadata for floating man-made structures, not a value observed in v1-2. Confidence categories appear in the order Very Low, Low, Medium, High and Very High where present. Omit zero-count categories from both CSV and Markdown, except Unassigned, which is always retained to show whether published attribute values are missing. Preferred ordering is not evidence that a category occurs in the dataset. No geometry is loaded, repaired or processed.

Count records by category. Divide each count by the total number of published L3 records. Require each attribute's category counts to sum exactly to that total. Attributes are independent inventories of the same records; counts must not be added across attribute tables. The number of CSV rows depends on the categories recorded, with one Unassigned row for each attribute.

## Outputs and running

| Output | Path | Content |
| :--- | :--- | :--- |
| CSV | data/{version}/out/stats/A08_Attribute-summary_{version}.csv | Attribute, Category, Feature_count, Percent_of_all_features |
| Markdown | data/{version}/out/stats/A08_Attribute-summary_{version}.md | Three appendix-ready tables, full-extent provenance and shared interpretation notes |

Counts are integers. CSV percentages use six decimal places; table percentages use one. Rounded percentages may not sum exactly to 100. Table identifiers A08-1 to A08-3 are provisional and can be renumbered when inserted into Word. Captions and the overview identify the analysis script and dataset version.

```bash
conda activate nw-aus-feat-env
python A08-attribute-summary.py
python -m unittest discover -s tests -p 'test_A08_attribute_summary.py' -v
```

No caches are used. Every run regenerates outputs directly from published attributes. This supersedes the earlier A08-reef-depth-summary analysis and its regional depth outputs. It does not modify A04, A05, A06, the report draft or published input data.

## Appendix and main Results

Keep these descriptive tables together in the appendix. The main Results can note that depth and confidence attributes are supplied and summarised there, without presenting their distributions as regional ecological findings. EdgeAcc_m can be described in the attribute documentation, but is not added to this overview: it is an expert estimate with known inherited-value and review limitations, not independently measured positional accuracy.

The regional reef-count maps remain separate A05 products. A page can use up to four panels for Analysis-regions, IMCRA, CAPAD and a useful detail. Label count-based colour scales as number of countable coral reefs, not density per unit area. CAPAD areas overlap and their counts cannot be added. This is a figure proposal, not map generation by A08.