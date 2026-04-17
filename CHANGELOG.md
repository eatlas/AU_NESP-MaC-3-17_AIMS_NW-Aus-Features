# Map stage notes
The following is a set of notes detailing the processing that was applied in the development of each phase of the mapping. This phased approach provides a record of what features were detected and mapped at each stage of the project, where each stage represents the incorporation of new information. These are unstructured, unpolished notes. The time estimates are a record of time spent on the digitisation of the dataset, along with the number of features contained in the dataset.


# Stage 5 - v1-0
2026-05-17:
We prepared the dataset for publication. The file arrangement in v0-4 did not publish the RB_Type_L2 version of the dataset. This means that when someone downloads the available data the QGIS maps will not work until the `12-make-RB_Type_L2.py` script is run. It seems likely that some people will want the simplified classification version, without having to run the script and so I decided to include it in the published `out` folder. To allow each shapefile to be independently downloaded we need to ensure that each shapefile is in its own directory. We therefore move the primary dataset from `out/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_v1-0.shp` to `out/full-classes/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_v1-0.shp`. We then made the RB_Type_L2 classification version available from `out/simp-classes/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L2_v1-0.shp`. The paths in the scripts `11-expand-attribs.py` and `12-make-RB_Type_L2.py` were adjusted so that they save the outputs directly to the `out` directory, rather than to the `working` directory. This removes the need for the manual copy and rename that was needed in v0-4. The paths in QGIS were adjusted to the new locations.

2026-05-16:
- Time: 1 hr 15 min 11351 features 255 features without depths
- Time: 1 hr 52 min 11361 features 110 features without depths
- Time: 34 min 11360 features 35 features without depths
- Time: 1 hr 7 min 11373 features 0 features without depths
2026-05-15:
- Time: ~40 min 11289 features 506 features without depths
- Time: 1 hr 8 min 11295 features 321 features without depths
2026-04-14:
Using local contrast enhancement of the All Tide imagery we found quite a few unmapped isolated coral reefs through northern Kimberley. These became the focus for one 50 min session.
- Time: 50 min 11267 features 620 features without depths.
- Time: 1 hr 5 min 11276 features 542 features without depths

2026-04-13:
- Time: 1 hr 11141 features 1080 features without depths
- Time: 56 min 11157 features 1020 features without depths
- Time: 1 hr 11168 features 930 features without depths
- Time 34 min 11172 features 818 features without depths
- Time: 20 min 11172 features 759 features without depths
- Time: 32 min 11174 features 644 features without depths
2026-04-12:
- Time: 43 min 11121 features 1473 features without depths
- Time: 49 min 11135 features 1370 features without depths
- Time: 32 min 11134 features 1269 features without depths
2026-04-11:

- Time: 1 hr 19 min 11029 features 1599 features without depths
- Time: 33 min 11050 features 1576 features without depths.
- Time: 19 min 11061 features 1572 features without depths.
- Time: 32 min 11072 features 1546 features without depths.
- Time: 25 min 11087 features 1507 features without depths.
- Time: 32 min 11093 features 1471 features without depths.
2026-04-10:
Progressively improving the mapping in the Gulf of Carpentaria adding a significant number of near shore rocky reefs. What has really helped is adjusting the contrast of the All tide imagery to the local conditions, maximising the local contrast. We have also been assigning depth categories and making the occasional correction to existing depth classifications. For the depth classifications we know that the red and green channels will not be as sensitive as they would have been in the Coral Sea, i.e. they will not be seeing as deep into the water column in most of northern Australia as the Coral Sea due to the water turbidity and CDOM. We therefore need to push these methods to ensure we are not significantly over estimating the depths, i.e. assigning a reef to the 'shallow' category, when in fact it is 'very shallow'. To help in this process we are using red channel of both the low tide imagery and the all tide imagery, enhancing the contrast to local conditions, then enabling and disabling the reef boundaries to see if there is evidence in the imagery that the red channel is slightly brighter somewhere within the perimeter of the mapped reef. Turning the reef boundaries off, removes the visual disruption caused by the pale reef boundary line, allowing maximum sensitivity in determining the depth. If the feature is visible above the red channel noise in either the low tide or all tide imagery then it is classified as 'Very Shallow', otherwise it defaults to 'shallow', unless we are more offshore where we check for whether it is 'deep' based on the all tide imagery green channel. Where the feature looks like it might be intertidal (i.e. very bright in the red channel), then we check whether the feature is visible in the infrared imagery. Here we need to consider if the water is highly turbid and the tidal range in the region. If the water clarity is typical of northern Australia, i.e. better than a couple of metres, and the tidal range is typical, less than 4 m, then almost any signal in the infrared imagery will indicate that it is intertidal. Where the water is highly turbid in high tidal range areas then we see reflection in the B5 channel (blue in the infrared imagery) from the turbid water. This means that we need to slightly discount the signal and a brighter image is needed before we consider the place to be intertidal.

- Time: 1 hr 10951 features 1916 features without depths.
- Time: 1 hr 25 min 11010 features 1780 features with depths.
- Time: 32 min 11011 features 1664 features with depths.

2026-04-09:
Depth classifications and some additional small reefs near Houtman Abrolhos. We found a few more small reefs around Houtman Abrolhos based on the 
- Time: 1 hr 30 min 10933 features 1941 features without depths
- Time: 1 hr 40 min 10902 features 1996 features without depths.
- Time: 1 hr 10892 features 2162 features without depths
- Time: 1 hr 10847 features 2205 features without depths


2026-04-08:
Continued to mark off potential reefs based on the AHO Marine Charts, particularly locations indicated by the stars on the maps. 
Time: 45 min
1653 chart indicated
305 chart mapped

Time: 30 min
1414 chart indicated
274 chart mapped


2026-04-07:
Developing animations for the AIMS media video. For this I am using a custom plugin called "Map Animation Helper" which is not yet published. We needed to have a low resolution coastline for countries outside of Australia to combine with the Coastline 50k 2024 dataset. In the past we have just used the Natural Earth 50m Land shapefile. The problem with this is that we cannot remove the low resolution Australian Coastline. To solve this we switch to using the Natural Earth 50 m countries dataset and used filtering in QGIS to remove Australia from the land. This was then combined with the Coastline 50k dataset. 

Continued to map the reefs indicated by the AHO ENC Series marine charts. The goal is to identify which reefs we have mapped can be considered as newly mapped, and to potentially identify reefs that we failed to map. There is a big problem determining which fringing areas should be considered as already mapped. The AHO ENC Series marine charts map the coastline based on depth, not the substrate type. It is therefore impossible to tell if a mapped shallow portion of the area near the coast is a reef or simply shallow sediment. Where there are rocky reefs the marine charts indicate this with a star shape '*'. We take this as a strong indication that there is a reef at these locations. We therefore marked these as indicating that there is a reef.

In shallow areas where there is an isolated shallow patch that is less than 5 m LAT we consider adding as indicating a potential reef site that should be checked.

Time: 1 hr 30 min Adding locations mapped on marine charts. 
1219 chart indicated
254 chart mapped
615 bathymetry indicated
453 bathymetry mapped.

2026-04-05:
Improving the digitisation in south west of Western Australia, adding depth classifications and adding some more deeper features. 

There was a challenge in classifying the fringing rocky reefs along the coast just south of Shark Bay. These rock reefs butt against the coastline. They appear to have a sharp drop off, similar to a cliff with a rocky reef below. Within the mapping resolution it is difficult to say what percentage of the rocky reef is in the intertidal zone, or the very shallow class. These rocky reefs quickly drop to 20 - 40 m. Most of these reefs are quite deep, however it is difficult to determine the transition. The original depth category classification used in the Coral Sea was based on the highest peak of a reef, which would mean by that definition any feature that touches the coast would be intertidal. However in this case the vast bulk of the feature is much deeper, and the intertidal transition is limited by the detail of the imagery. For these reefs the region neighbouring the coast is obscured by breaking waves. We therefore adopt an adjusted approach, which is that the reef is classified based on the highest 5% of its area. This is similar to the Coral Sea mapping, but helps reduce the problem with the deep, coastal reefs.

- Time: 50 min 10835 features 2346 features without depth categories.

2026-03-31:
Digitised locations from the bathymetry datasets and marine charts. The goal is to:
1. Determine all the reefs that are already known about, and thus should not be included in the count of newly mapped reefs.
2. Identify potential reefs that we did not map, helping to estimate the number of unmapped reefs. 

The challenges we faced were that the existing bathymetry and marine chart datasets are often very blurry, with features only resolved to 1 km. This makes it somewhat subjective to assess whether a reef should be considered as already mapped, or just indicated by the datasets. In general if the shape of the feature could be roughly determined (~50 percent correct) then we considered that a feature was mapped. If the feature was only indicated as a rough blob then it was recorded as being 'indicated'. 

The point files from the bathymetry and marine charts were also used to create maps to represent the current knowledge of reefs in an area. To prevent us from having duplicate points from the bathymetry dataset and the marine charts dataset we first marked off all the locations from the bathymetry datasets, then reviewed against the marine charts, recording any as yet unmarked reefs. This means that the marine charts-indicated and chart-mapped point files do not represent all the reefs from the marine charts, just the extra reefs that were not available in the bathymetry data.

We mainly used the AusBathyTopo Australia 2024 250m bathymetry dataset as this gave the most consistent bathymetry quality across the study area. We found it largely impossible to determine reef boundaries of inshore reefs from bathymetry datasets.

On the marine charts shallow hazards are often recorded as a star, or cross. This means that there is a known feature, but the boundary is not accurately mapped. We tried to capture most of these in the charted indication category. This helps to capture inshore rocky areas that are largely unmapped (there is no boundary indicating their shape), but they are represented in the map as a cross. 

After an initial round of marking off locations we created a map showing which reefs were classified as 'Newly mapped'. 'Previously indicated' and 'Previously mapped'. These classifications were generated by `A02-unmapped-reefs.py`. Where a reef was marked as 'Newly mapped' we scrutinised the marine charts to see if there was evidence for the reef, i.e. a marked rise on the chart. In general fringing reefs were difficult to determine if they should be considered as already mapped. For inshore areas we mainly marked off the crosses as an indication of a hard substrate inshore hazard.

We also marked prominent sand banks, as a way of marking off all the areas that should be included in the reef mapping. The marine charts and bathymetry make no classification of the substrate. It is therefore impossible to tell if a shallow area is soft sediment or a reef. Rather than marking off all fringing reefs with manual points, we focused on the manual points indicating areas that were not already indicated as mapped by one of the Tier 1 datasets (AHS Seabed Area Features, GA Marine Hazards, ReefKIM, or UNEP Global Coral Reefs). 

The manual tagging of the bathymetry and marine chart point datasets took 3.5 hours.

2026-03-20:
Improved rocky reefs just south of Shark Bay down to Gantheaume Bay. The main improvements were the trimming out of sandy areas from the inner portions of large rocky reefs, the trimming of the outer deep portion of the reef and checking the attributes of the features.

Added depth classifications to the reefs around the Houtman Abrolhos regions and adjusted the boundaries around the Houtman Abrolhos reefs. Separated out a large offshoot of the northern reef (Wallibi Group) and reclassified as a low relief rocky reef. 

There is a large reef feature off from Port Gregory that is about 9 km by 30 km in size. This feature contains ports of rocky reef and some paleo coastline. Many parts of this feature appear as though it might be some kind of submerged aquatic vegetation as the sandy gaps seem to be aligned with the currents, with some of them having a chevron shape. The boundary between the rocky portions and the vegetation only portions can not be determined from the available imagery. For now we have left this feature as a low relief rocky reef.

Improved the rocky reef mapping around Geraldton. The dredged shipping lane out from the port is reasonable evidence that the immediate surrounding seafloor is soft sediment and not rock. This indicates that a lot of the seafloor is covered in submerged vegetation that can not be easily distinguished from rocky reef.

Mapping time: 8:50 - 11:00
- 2 hr 10 min 10828 features, 2370 features with no depth category, 8458 features with a depth category.
11:22 - 11:44
- 22 min 10829 features

2026-03-18:
One pressing question is to determine the number of previously unmapped reefs that have been mapped as part of this project. One key goal of this project was to identify unmapped reefs. The challenge is to determine what constitutes as an unmapped reef. The key datasets that contain reef mapping for northern Australia are the UNEP Global Coral Reef dataset, ReefKIM covering the Kimberley, various habitat maps in the Pilbara, highlighted by Seamap Australia, marine charts, bathymetry surveys and the Allen Coral Atlas reef extents. Each of these data sources have strengths and weaknesses. The marine charts have variable levels of mapping detail, with the boundaries sometimes being only loosely related to the actual boundary. Additionally the marine charts correspond to a map of marine hazards, not reef boundaries. The Allen Coral Atlas reef extent has a very high error rate, where large areas are mapped as reef extents where there are no reefs. In some cases just whole areas are marked as reef. If our mapping identifies two reefs within that subset area are these newly mapped reefs, or does the messy mapping count. If it does then we could just draw a polygon over the whole marine estate and claim it as reef area, then proclaim that all the reefs have been mapped. This implies that accuracy is needed in order for the mapping to count. How accurate does the mapping need to be to count towards being able to say that the reef boundary was mapped? On the inshore reef on the GBR there were mapped reef boundaries that did not even overlap the reef feature at all, but the intention was clear due to the lack of any reefs near by. We therefore need to be quite generous and tolerant of positional errors in the mapping before we consider a reef to be too poorly mapped to be counted.

If we have bathymetry data, how clear does the boundary need to be indicated for it to count. If we have a largely blank surrounding seafloor and a suggestive bump in the bathymetry, is that enough. Does it need to be resolved sufficiently that the approximate shape and size is reasonably accurate? What if we are looking at satellite derived bathymetry and the reef features are just about the noise, i.e. not a clear feature. 

For the marine charts we need to consider the scale difference between the marine charts and the reef mapping. Often the marine chart will exaggerate the size of features to ensure that vessels do not come close to the hazard. As a result the marine charts are not a true representation of the size of features, but rather more like a buffered version of the features. 

Does having the reef boundaries visible in satellite imagery count as the feature being mapped, even if nobody has looked at the images. This argument is an extension of how well does the reef need to be represented in bathymetry to count as being mapped, even if no boundary has ever been drawn around the feature. If someone creates a hill shade version of the bathymetry and the boundary of the feature is clearly visible in their maps, but no one has drawn a boundary around that feature then in some sense it is not mapped, but from a practical perspective it is mapped because it is clearly visible.

To assess if a mapped reef feature can be considered as a newly mapped we need some reasonable criteria that we can assess each reef against. Some principles:
1. The criteria should align with what most people would agree with as being a newly mapped reef. i.e. if you showed the existing evidence, a reasonable person would say that there was no reef in the map, and with the new evidence that there is now.
2. The existing mapped feature does not count if it is produced from just noise in the data or a mapped area that far exceeds the size of the actual reef, with consideration for the scale of the mapping. This criterion basically indicates that the mapped feature must be intentionally related to the underlying reef being mapped.

This work was captured in `A02-unmapped-reefs-spec.md` and `A02-unmapped-reefs.py`.

2026-03-12:
One limitation of the sand bank mapping is the line between what constitutes a sand bank and what is just part of the shallow fringing sediment connected to the coastline. Since our intention is to eventually map the shallow fringing sediment areas separately, the focus of the mapping of the sand banks is on isolated sand banks that are not connected to islands. Pretty much anything that would be a surprise to find. This is an imperfect approach and it will only be resolved when we map all the shallow sediment and integrate the two forms of shallow sediment mapping.

When classifying small features (coral reefs and rocky reefs) that are near another fringing reef then we are classifying those features as also fringing if they are within 200 m of a nearby large fringing reef.

Continued checking and fixing the `EdgeAcc_m` of features identified by having an `EAEWperc` greater than 50%. This will typically correspond to a small reef that has settings copied from a larger reef, leading to an `EdgeAcc_m` that is far too large. When checking we also reviewed neighbouring features, adding the DepthCat and checking the confidence settings. We also added sand banks and some small previously unmapped reefs. The review pass is complete from Houtman Abrolhos through to Tiwi Island in Northern Territory. This quality control pass is only looking at a small percentage of the features, focused around areas highlighted with `EAEWperc`. It looks like such a pass will take about 6 hours.

Mapping time: 
- 1 hr 30 min 10765 features, 2574 features with no depth category, 8191 features with depth category.
- 1 hr 10 min 10798 features, 2546 features with no depth category

## 2026-03-11:
We adjusted `10-clip-land.py`, `11-expand-attribs.py` and `12-make-RB_Type_L2.py` to be version agnostic. We also adjusted the paths to the data files in `data/v1-0/*-v1-0.qgz` to work with the new paths that are all relative to `in-3p`. Running `10-clip-land.py` script on the v1-0 draft we found that it took 41 min to process. We improved the performance by adding spatial prefiltering prior to land clipping and parallel processing using threads. This sped up the processing significantly, reducing the run time to 4 min.

Recalculated the `EffWidth_m` and `EAEWperc` and used styling on `EAEWperc` to identify features with a likely too large `EdgeAcc_m`. Spent time improving the mapping around these features, then updated the `EdgeAcc_m` to a more accurate figure. I improved the boundaries of the reefs around Houtman Abrolhos. There are still quite a few marginal features on the bottom that are not mapped, that are likely low relief rocky reef, or vegetation. I also added some marginal low relief rocky reefs along the near shore of Eighty Mile Beach, and made significant adjustments to the reef boundaries around the islands 7.5 km west south west of Sir Fredrick Island in Kimberley. The reefs were covering areas that were significantly covered in sediment and so did not count as reefs. I have only reviewed the questionable `EAEWperc` from Houtman Abrolhos to half way up the Kimberley.
Mapping time: 
- 1hr 25 min 10747 features 

## 2026-03-10:
We adjusted the `01a-download-input-data.py` script to use the [data-downloader](https://github.com/open-AIMS/data-downloader/) library. We also included `01b-download-sentinel2.py` and `01c-create-virtual-raster.py` to allow the Sentinel 2 imagery used in the mapping to be downloaded and setup. We also added instructions to the readme for setting up symbolic links to the `in-3p` folder so that we can keep a fixed project relative path of `data/v1-0/in-3p` and have the contents of that folder actually stored elsewhere. This allows the project to be worked on in a Team area or One Drive area without the 3rd party datasets from being saved to One drive. 

## 2026-01-11:
Continued to check reef features with exceptionally high and low EAEWperc values.

Fixed up fringing coral reef and rocky reefs around Bickerton Island and Groote Eylandt
Time: 1 hr 10725 features
Time: 0.5 hr 10727 features
Time: 1 hr 10 min 10735 features

## 2026-01-10:
Improvements to rocky reefs and coral reef flats.
Time: 30 min 10705 features
Time: 10 min 10712 features

To identify features that have their EdgeAcc_m poorly set we estimate the EdgeAcc_m as a fraction of the Effective Width (width of a circle of the same area as the feature). This aims to identify features where the EdgeAcc_m is significantly high for their area. These errors can happen when the EdgeAcc_m was set to a cluster of reef features. To implement this extra attributes were added to Reef-boundaries_v1-0_Edit.shp. First we switch the projection to EPSG:3112 then use the FieldCalculator to add an integer field:
EffWidth_m (int) - Effective Width in metres
```
2*sqrt( $area / 3.14)
```

EAEWperc (int) - Edge Accuracy to Effective Width ratio
```
("EdgeAcc_m" / "EffWidth_m") * 100
```

The EffWidth_m identified 9 features that have an effective width that is less than 10 m, indicating that they are almost certainly slivers. EAEWperc identified 149 features where the EdgeAcc_m is larger than the effective width of the features. There are also 119 features where the EAEWperc is less than 1%. This indicates a high probability of a misattribution and that these features should be reviewed.

Time: 1 hr 10702 features

## 2026-01-08:
Continued to add rocky reefs in the same area as yesterday.
Time: 45 min 10686 features

## 2026-01-07:
Predominantly adding and improving the fringing rocky reef mapping along the northern Kimberley Coastline, north east of Bigge Island, south east of Bougainville Peninsula. There are many fringing intertidal rocky reefs in this area that have not previously been mapped. So far only a couple of them have been bigger than our target 150 m minimum feature width. I have been digitising at a scale of 1:5000 which results in a final map scale of approximately 1:50k.
Time: 1 hr 10646 features
Time: 17 min 10655 features

## 2026-01-06:
Focused on fixing up rocky reefs in the northern Kimberley region around Jungulu Island and on the Eastern side of Augustus Island. This involved trimming existing reef boundaries to cater for the many fringing reefs then checking the rocky reefs in Google Earth. In most cases rocky reefs were considered when the rocks were approximately 1 m across in the high resolution imagery. Most of these islands are surrounded by rocky rubble fields with boulders in the order of 1 m across. Even though these boulders are not consolidated we consider them a rocky reef because of the high density of large rocks that should act as a complex 3D environment. There are many rocky features that are still to be corrected.
We continued to focus on improving the rocky reef mapping in the Kimberley, working up to Bigge Island.

Time: 1 hr 15 min 10529 features 
Time: 8 min 10543 features
Time: 23 min 10552 features
Time: 1 hr 24 min 10608 features

## 2026-01-05:
We created a new layer to act as a depth proxy -("S2 All Tide@3" / "S2 All Tide@1") scaled between -1.35 to -1. This is effectively a rough satellite derived bathymetry. The minimum and maximum were scaled so that black roughly represents -10 m and white approximately -5 m. These depths were roughly calibrated for offshore sand banks in the southern Pilbara. This algorithm is highly affected by the water colour and so can only be used as a rough depth guide without local calibration. The goal was to help determine which sand banks should be digitised. A bonus of this depth estimator is that it highlighted a bunch of small (typically 50 m across) features in the North East of the Exmouth Gulf. These features that are barely visible showed as local high spots. Their classification as rocky reefs or coral reefs was highly uncertain due to their small size and their poor visibility. 

Time: 1.5 hr. v1-0 10455 features
Time: 1 hr v1-0 10483

## 2026-01-04:
Updated \data\v1-0\in\AHO-Uncharted\AHO-Uncharted-areas_2025.shp to include a complete set of uncharted areas, including Torres Strait and along the Queensland coastline. This mapping of the uncharted areas only includes Queensland, Northern Territory and Western Australia north of Geraldton. Most of the features were digitised with an onscreen scale of 1:30k - 1:50k resulting in a final scale of approximately 1:200k. For seaward areas the boundary was made to match the existing boundary as accurately as possible. Where boundaries touched land the landward boundary was made larger by 200 - 500 m to minimise the detail needed to represent the land boundary. The goal was that an accurate land boundary could be obtained by clipping the AHO-Uncharted-areas by a land mask. Where a boundary contain islands these were not removed as holes from the boundaries, again clipping by land can result in holes if this is needed. In some cases the boundaries pass under reef features at the edges. In most cases these reef features were not clipped out from the boundaries. The boundaries typically correspond to the simplest shape that covered the area assuming the reef mapping is on top of the regions. The AHO-Uncharted-areas was developed to help determine the number of newly mapped reefs that fall within uncharted areas. For this analysis we would use the AHO reefs dataset to ensure we detect the reefs that are mapped within the uncharted areas.

AHO reefs dataset:
http://catalogue.aodn.org.au/geonetwork/srv/eng/metadata.show?uuid=f56d4f73-7444-4335-8c46-dce34db915f9
Downloaded 17 April 2024
From Collation of existing shelf reef mapping data and gap identification
https://www.nespmarine.edu.au/system/files/Lucieer%20et%20al%20-%20Collation%20of%20existing%20shelf%20reef%20mapping%20data_Milestone_4_D3_RPv2_2016.pdf

## Comparison between AHOENCSeries Marine charts and mapped reefs
To help determine the false negative rate we reviewed the reef boundary mapping, digitised solely from satellite imagery, against the AHO Marine Charts. We review the marine charts for features raised above the seafloor, but at least 5 m, that were not already mapped as a reef. We then review the satellite imagery to determine if the feature could be detected in the imagery. Where the feature could be seen the feature was added to the Reef Boundaries dataset, recording the EdgeSrc as 'AHO, ...' to allow tracking of features that were added due to the assistance of the marine charts. Features were only added where they could be confirmed in the satellite imagery. This means that the dataset is still limited to the visible limit of the satellite imagery. Features were not copied from the AHO Marine Charts because the marine charts are a much lower resolution mapping resulting in the actual features being a significantly different shape to that shown in the marine chart. The main reason for not including marine chart features without confirmation from the satellite imagery is that the substrate type could not be determined, making it often impossible to tell the difference between a rise in the unconsolidated seafloor and a reef with a hard substrate. Only rise points where the peak was shallower than 40 m were reviewed as features deeper than this are generally not visible in the imagery.

Comparison time: 1 hr

## Misc changes
The outer edge of Ningaloo Reef near Point Cloates was extended by 2 km to cover a deep reef region.


2025-10-01:
Started making small edits to the dataset to correct errors that arose during the development of the scripts for counting reefs. This typically corresponded to fixing slivers that were created as part of trimming the land from the reef boundaries.

# Stage 4 - v0-4 - 2025-07-30
In stage 3 the focus of the scripts was to merge all the datasets (sediment, automated intertidal rocky reefs, manual reef boundaries) into a final dataset where features don't have any overlaps. My original plan was to use this new output as the basis for further improvements in this stage. However, manual editing of this final dataset is difficult and we determined that there were issues with the clipping around the intertidal rocky reef that should be reprocessed. We therefore shifted to maintaining a set of editable layers that are then combined to create the final dataset. These editable layers are based on the original inputs to the stage 3 scripts, but with some of the corrections applied to them, prior to the next stage of manual editing. 

## Improvements
In this stage we made improvements to the boundary accuracy and separation of Paleo Rocky Reef from Sand Banks in Eighty Mile Beach. Many northern features were previously classified as Paleo Rocky Reefs. These were switched to Sand Banks due to the lack of visual evidence that there was exposed rock.

Many 'High Intertidal Coral Reefs' were reclassified as 'High Intertidal Sediment Reefs' as they had no evidence of a hard substrate. These appear to form a continuum between these two classifications.

A partial reworking of the Barrow Island Shoals and reef areas around Montebello Islands and the Mary Anne Group was done, switching the classification from Coral Reef Inner Flat to Limestone Pavement. This area is not complete. This area was split into the categories 'Limestone Reef' to represent the old limestone reef areas not covered in sand and 'Sandy Limestone Pavement' for the rest of the platform, along with a 'Coral Reef' portion. The whole of the Pilbara needs to be reworked under these classifications, however, only a small amount has been done in this version. More of a proof of concept than a full implementation.

Significant improvements were made to all of the offshore islands and reefs (i.e. Cocos Keeling Island, Christmas Island, Norfolk Island, Middleton Reef, Elizabeth Reef, Lord Howe Island), however these areas need considerable additional time and consideration to map these features well. The satellite imagery in these areas is generally poor due to the low number of images that were available to incorporate into the composite images and the relatively low depth visibility of the imagery due to dissolved organics in the water. These areas should be considered as draft quality.

A review of the 'Attachment' attribute was conducted and 558 corrections were made of 8753 features (this was about half way through the development of v0-4). This indicates an error rate of approximately 6.4%. There are likely still errors of 1-2% relating to difficult cases and additional cases that were missed, as the review was done fairly quickly. The 'Attachment' attribute is one that has never been previously reviewed or checked. A further automated check could be performed by looking for features that are touched by a buffered version of the coastline.

Improvements were made to many of the rocky coastlines and sand banks of the Pilbara. Coral Inner Flat areas were added to reefs on the Cobourg Peninsula (NT) and sand banks were added to the Van Diemen Gulf. The boundaries of the small isolated reefs in the Gulf of Carpentaria were reviewed and adjusted, and 4 new small reefs identified. 

## Rocky reef handling
Version v0-4 is intended to be a draft for the national scale NVCL dataset. This dataset has 250 m pixels and so small intertidal rocky reefs will not contribute much to the result. The intertidal rocky reef mapping needs additional work to get the dataset to work at the national scale accurately. We therefore focus on the NW-Aus-Features dataset focusing on subtidal rocky reef mapping. The intertidal rocky reefs can then be spliced in at the national scale. 

## Shallow sediment
The same applied to the shallow sediment classification. The previous shallow sediment class that was added to version v0-3 was developed for the purpose of assisting the UQ habitat mapping, however its definition does not align accurately with the NVCL. Currently, it includes areas much deeper than the intertidal zone, while the NVCL needs the intertidal zone. We therefore publish v0-4 focusing on the reefs and don't include the shallow sediment. We would therefore defer adding in the intertidal sediment at the national scale (covering the GBR as well).


## Reef boundaries workflow
v0-4 of the reef boundaries starts from the editable version from v0-3. This is not the output `v0-3_qc-1\out\NW-Aus-Features_v0-3.shp` shapefile because this version is the final dataset that has had all its features clipped to the coastline. v0-3 was the version developed for the habitat mapping mask and it contains the merging with the shallow sediment. We roll back these modifications in v0-4 to focus on the reef boundaries and sand banks. We start with `v0-3_qc-1\in\NW-Features_RB_Type_L3\Reef Boundaries Review.shp`. This version still has some unresolved overlaps in features, and so we clean up the data with `02-clean-overlaps.py`. This is effectively performing the first set of v0-3. This produces `working\02\Reef_Boundaries_Clean.shp`. We then apply a cross walk of the attributes to bring them in line with the v0-4 classification scheme with the `09-v0-4-class-cross-walk.py`. This produces `working/09/Reef-Boundaries_v0-4.shp`, which we manually copy over to `data/v0-4/in/Reef-Boundaries_v0-4_edit.shp` as the new editable version of the mapping. We perform this manual copy to ensure that running the scripts will not accidentally overwrite any manual editing that had already been applied. The output version of the dataset has the land clipped from the features using `10-v0-4-clip-land.py`. `11-v0-4-expand-attribs.py` performs the crosswalk from the RB_Type_L3, Attachment and DepthCat attributes to the Natural Values Common Language, the Seamap Australia classification scheme and some of the Queensland Gov Wetlands Intertidal and Subtidal classification scheme. This saved the output to `working/11/NW-Features_v0-4.shp`. This is the new publication ready version of the dataset. We manually copy this version to the publication destination of `data/v0-4/out/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_v0-4.shp`, extending the name to add more metadata to it, adding the funding (NESP-MaC), project code (3.17) and institution (AIMS) to the name.

The RB_Type_L3 classification divides many reefs into an active growing region ('Coral Reef') and reef matrix covered in sand section ('Coral Reef Flat'). To calculate the size of reefs and the number of them we need to dissolve these features together. Both these features are classified as 'Coral Reef' under the RB_Type_L2 classification, which clusters the features at a higher level. This clusters all the RB_Type_L3 coral reef types to 'Coral Reef' and all the rocky reef types to 'Rocky Reef'. `12-v0-4-make-RB_Type_L2.py` dissolves neighbouring features together based on the RB_Type_L2 classification scheme. This merges the Coral Reef Flat and Coral Reef features together, creating larger polygons that represent the geological boundary of the reef structure. 



No rigorous time tracking was applied to the improvements being made, however the following are approximate total digitisation time:
v0-1 RB - 500 hours
v0-1 EL - 87 hours
v0-2 - (v0-1 RB +50 hours) 550 hours
v0-3 - (v0-2 +80 hours) 630 hours
v0-4 - (v0-3 +77 hours) 707 hours (up to 29/7/2025) 13,795 kB 10390 features 7624 depths 2896 rocky reefs



### Manual edit improvements
Added Non-reef Bank classification. Refined the boundary of reefs around Adele Island, Lacepede Islands and Baleine Bank. Changed the Coral Reef Inner Flat to just Coral Reef Flat so that it better represents sediment areas on reefs, such as Lacepede Islands reef, which can occur on the outside of the coral reef areas. Lacepede and Baleine Bank are still not that well represented. It is unclear whether the bank covered in sediment that is largely terrestrial in origin. Is this simply an area that is shallow, and a portion of it (Lacepede) formed a shallow reef. 

From v0-3 there were over 400 features that did not have an estimate for the `EdgeAcc_m`. Manual edits were focused on fixing digitisation errors and depth estimates of features around the features missing the EdgeAcc_m. Typically 5-10 features were improved for every feature missing the `EdgeAcc_m`. 

A significant percentage time was spent improving the boundary accuracy and coverage of sand banks.

The outlines of the stromatolite reefs in Shark bay were refined to focus on areas where there are some vertical structures. This included excluding areas that were likely to just be microbial pavement (see https://doi.org/10.1016/j.margeo.2012.02.009).

Some additional work was done to improve the coverage of rocky reefs and coral reef flats in the Kimberley region. While significant corrections were made it is far from complete. There is likely to be at least 1000 additional corrections on rocky reefs in this region.

## Partial edit log
This log is to help track the rate of improvements to the datasets over time. At various stages, the total time is incorporated into the running total and these details removed.

21/7/2025 8:54 - 10:28 1 hr 30 min 13,167 kB 9669 features 0 Edge 2702 depth

21/7/2025 4:19 - 5:21 1 hr  13,198 kB 9720 features 0 Edge 
5:22 - 6:22 1 hr 13,234 kB 9767 features 

23/7/2025
2 hr 13,314 kB 9824 features 3226 depth 448 not matched
12:06 - 1:01 55 min 9854 features 3311 depth 409 not match
2:00 - 3:00 1hr 9907 features 3370 depth 406 not match
3:04 - 4:14 1 hr 10 min 9926 3746 depth 403 not match
52 min 13,409kB 9936 features 3766 depth 312 not match 
3 hr 45 min 13,478kB 10024 features 4047 depths 153 not match
1 hr 18 min 13524 kB 10110 features 4139 depths 148 not match
2 hr 13611 kB 10192 features 4290 depths 104 not match
1 hr 4 min 13673 kB 10274 features 4372 depths 96 not match 2832 rocky reefs
1 hr 13721 kB 10343 features 4473 depths 85 not match 2860 rocky reefs

27/7/2025
1 hr 30 min 10377 features 4525 depths 75 not match 2880 rocky reefs
2 hr 15 min 10387 features 4773 depths 41 not match 2890 rocky reefs
1 hr 19 min 10397 features 4970 depths 0 not match 2899 rocky reefs
33 min 10391 13,791kB features 5300 depths 2893 rocky reefs
44 min 5721 depths

29/7/2025
1 hr 37 min 13,796 kB 10397 features 6674 depths 2899 rocky reefs
1 hr 50 min 13,795 kB 10390 features 7624 depths 2896 rocky reefs

### Known Limitations
Many of the Coral Reef Flats for the inshore fringing reefs have not yet been added to the dataset. This means that the area of the inshore reefs is substantially more than that indicated by this version of the dataset. It also means that there are likely to be less, but larger reefs, as the Coral Reef Flat regions will tie together coral reef areas.

There are many inshore rocky reefs that have not been added to the data. These rocky reefs are often the landward side of narrow fringing coral reefs. This leads to the size of some of these fringing coral reefs from being over estimated and an underestimate in the number of inshore rocky reefs. It is difficult to determine the true number of rocky reefs, but there are probably 1000 more rocky reefs that are less than 50 m across (land to ocean) that are not mapped. 
Rocky reefs include boulder reefs, not just bed rock.   

Only 64% of the features have had their depth estimated, and most of these estimates were a relatively quick initial assessment. Issues with the assessment occurred for fringing coral reefs where the landward side of the reef had not been carefully digitised, or there were small rocky reefs in the reef that were not digitised. These would often result in intertidal areas corresponding to the land or rocks that are not representative of the main feature being digitised. In some cases these overlaps were corrected and the feature split into coral reef and rocky reef. However due to time limitations there are at least 1000 cases where this editing was not completed. 

There are still many sand banks that are not digitised. While the number of mapped sand banks increased from 390 in v0-3 to 810 in v0-4 there are still hundreds not yet digitised. 

## Stage 3 - v0-3_qc-1 - Quality control - 2025-04-24 - Habitat Map boundaries
The goal of this version was to prepare the dataset to be used by the UQ team as constraints on the automated habitat mapping. UQ planned to use coral reefs, rocky reefs and sediment classifications to drive independent habitat classification models. While this version of the dataset contained many improvements over the previous version it still contains many known small issues that were unresolved. This was due to the limited time available to clean up the dataset.

This was the first round of quality control applied to the dataset. The principal editing file for this version is `data/v0-3_qc-1/in/NW-Features_RB_Type_L3/Reef Boundaries Review.shp`. This involved a review of all features by Eric Lawrey, noting missing features, areas that needed trimming, classification changes. These issues were noted in `data/v0-2_merge-maps/Issues-v0-2/Issues-v0-2_partA` and `partB`. The review was split into two parts to allow Rachel to start work on fixing issues, while further review was being conducted. The review was conducted using the project Sentinel 2 composite imagery and individual daily Sentinel 2 imagery using the [Copernicus Browser](https://browser.dataspace.copernicus.eu/). For daily imagery the cloud cover threshold was set to a low value (~10%) then for the area of interest the remaining images were reviewed over several years. Aerial imagery for part of the Gulf of Carpentaria was also used help identify features. The goal was to identify images that would show a clear view of the feature, or changes over time that would help with type classification. The daily imagery was only used to assist in identifying difficult to classify areas. Approximately 70% of the coastline was reviewed, taking approximately 25 hours. This review only identified and recorded the issues. It did not fix them.

This review identified several key issues with v0-2:
- Large sandy areas (>150 m across) were being included in the rocky reef features. This might degrade the quality of the UQ habitat mapping.
- Many (hundreds) smaller rocky reefs (100 - 200 m across) were identified. The conclusion was that most of these features were intertidal rocky reefs that could be reasonably identified from the Sentinel Low tide composite imagery. This led to the decision to produce semi-automated mapping of intertidal rocky reefs using random forest classification (AU_NESP-MaC-3-17_AIMS_Rocky-reefs).  
- The extent of the coral reefs in the Kimberley were inconsistent in their mapping. For fringing reefs the boundaries focused primarily on the active growth areas of coral, the outer strip of the fringing reef. While for some of the platform reefs the whole reef platform, including the inner, largely sandy, reef flat was being included in the boundary. In the Kimberley, the fringing reefs grow out laterally from the land and islands, leaving an extensive reef flat devoid of corals, consisting mostly of sand. These are however limestone reef frameworks, which we can verify from the presence of the occasional 'blue hole' formed by the limestone reef frameworks dissolving from rain water during a previous glacial period when sea levels were lower. From a geomorphic perspective the whole reef framework should be included in the reef boundary; however,  from a biodiversity hotspot perspective we might be more interested in where there is active coral growth. To cover both bases we added a new classification 'Reef Flat Shallow'. This will cover the low diversity shallow portions of reefs that would have been excluded. This new classification was used extensively to describe the extensive reef areas around Barrow Island in Western Australia. In this version the Kimberley fringing reefs were not adjusted to this new approach due to limited time.
- The review identified a number of fish traps and oyster reefs that are relevant for [NESP MaC Project 4.13](https://catalogue.eatlas.org.au/geonetwork/srv/eng/catalog.search#/metadata/8050d5a5-6d8d-4dc5-ae18-9805fd401032).
- An issue was identified at a rate of about one issue per four mapped features. In general these adjustments were generally adjustments to the boundary shape, generally requesting tighter mapping of the feature, rather than missing features or classification errors.

After the review Rachel worked on improving the high priority issues, resolving approximately 40% of them, the bulk of which was trimming out sediment areas from rocky reefs. 

Rachel then handed over the editing to Eric who then continued to make priority improvements. Overall only approximately 60% of the priority issues were resolved due to limited time. 

### New reef classification scheme - Names and attributes
Some of the reefs near Montebello Island are potentially rocky in nature, however they have a biogenic carbonate origin, which could not be represented with the existing RB_Type_L3 classification scheme as all rocky reefs are assumed to be Terrigenous. To add a carbonate to rocky reefs would require potentially doubling of the rocky reef classification types. The RB_Type_L3 was intended to have a discrete named classification for every combination of attributes that are in use. This works up to a point. As more details are recorded about a reef, not all of this can be represented as a single classification name. This triggered a reassessment of the existing classification scheme. 

The goal was to develop a hybrid classification scheme that uses both a named classification and attributes. The named classification would capture all types that would be expected to put in a legend, i.e. feature names that an environmental manager is likely to care about and qualifier attributes would capture any additional information. For this the relative position (Fringing, Platform), was moved into its own attribute. 

The new classification was automatically applied to the existing mapping using `03-class-cross-walk.py`. 

Note: v0-3 contained a first cut at adjusting the classification to make it more flexible. This was triggered by trying to classify the shallow areas around Barrow Island. We determined that the exposed hard substrate areas are rocky in nature, but limestone in origin, rather than normal terrestrial origin. This triggered the reshuffle of the classifications. The long-term coral community monitoring program results (Bancroft, 2011) showed that all the sites in this region had high levels of hard corals. This led to the false view that there was more coral than would have been expected. This led us to simply consider these limestone reefs as coral reefs. After publishing v0-3 we discovered Bancroft, 2009, which included a much more diverse range of locations. This highlighted that the monitoring sites were spatially biased towards locations of high coral cover and diversity. The reality was that most of the limestone reefs were very low in coral cover and mostly covered in sparse macroalgae. What we had called 'Coral Reef Inner Flat' was actually limestone pavement with a sandy veneer. So in v0-4 we added classifications for limestone reefs and limestone pavement with sand veneer to capture this nuance and these areas were reclassified.

v0-4 revisited the classification with a full analysis to ensure the classification information can be used to crosswalk to the Natural Values Common Language and the Seamap Australia Classification scheme.

Bancroft, K. (2009). Establishing long-term coral community monitoring sites in the Montebello/Barrow Islands marine protected areas: Data collected in December 2006 (No. MSPDR4; Marine Science Program Data Report Series, p. 68). Marine Science Program Science Division Department of Environment and Conservation.

Bancroft, K. (2011). Establishing long-term coral community monitoring sites in the Montebello/Barrow Islands marine protected areas: Site descriptions and summary analysis of baseline data collected in December 2006. Marine Science Program Data Report MSPDR9 (No. MSPDR9; Marine Science Program Data Report Series, p. 91). Marine Science Program, Science Division Department of Environment and Conservation. https://library.dbca.wa.gov.au/static/Journals/080598/080598-09.pdf



### What to do with Montebello / Barrow Island reefs
There are extensive shallow reef areas around Montebello and Barrow Islands. These areas are approximately 550 km2 each. Rachel had initially mapped them as rocky reefs with a few small patch coral reefs in areas where there was obvious coral reef accretion. This seemed to provide the wrong impression of the region.  

Research indicated that the whole shallow plateau around the island is carbonate in origin. Coral monitoring sites showed that sites that did not look like a traditional coral reef in structure as they had a rocky foundation with a low structural complexity, but still high levels of hard and soft coral cover. While many of the reef structures look rocky, they are covered in hard coral and thus should be considered as coral reefs. The large flat areas were converted to 'Reef Flat Shallow' to indicate that these areas are geomorphically related to and connected with the coral reef structures. 

Note: This was later adjusted in v0-4 because these monitoring sites were biased to sites with high coral cover.

### Reviewing the classification of offshore reefs
The classification of offshore reefs was reviewed and corrected. Reefs were assigned as part of an atoll if the water around the reef was more than 200 m in depth. In some parts there were clusters of reefs near the 200 m contour. Given the uncertainty in the bathymetry dataset (Geoscience Australia AusBathy 250m 2024), only reefs that were significantly separated from clusters at the shelf edge were classified as atolls. 

Those with atolls were classified as atoll platforms. Where a reef (hard exposed reef) existed on these platforms then they were cut out from the atoll and classified based on the same process as for Coral Sea. 

The equivalent deep areas for reefs on the continental shelf were classified as Deep Platform Coral Reefs and the shallow portions as Platform Coral Reefs. Some of the Deep Platforms were actually just above the 30 m threshold and so these will still need some more work to treat the oceanic reefs and shelf reefs in a consistent manner.

### Cleaning up for publication.
To get the dataset ready for publication and use by UQ for the habitat mapping the following processing was done on the dataset:
1. Removing geometry errors created by manual editing. The `Vector / Geometry Tools / Check Geometry` tool in QGIS was used to find any issues. These were then fixed manually.
2. Removed overlaps in High Intertidal Coral Reefs with other features. (`02-clean-overlaps.py`)
3. We apply the new classification scheme (`03-class-cross-walk.py`).
4. Merge in the semi-automated intertidal rocky reef mapping. (`04-v0-4-merge-rocky-reefs.py`)
5. We remove overlaps between the rocky reef features and the coral reefs (`05-clip-rocks-from-reefs.py`)
6. We use the semi-automated shallow mask to create an estimate for the shallow sediment areas. We first clean up this dataset by adding areas that were not mapped correctly (seagrass areas, and shallow foreshore in GOC) and removing spurious results, particularly narrow rivers.
7. We estimate the sediment areas by clipping reefs from the shallow mask, leaving just soft sediment (providing the rocky reef and coral reef mapping is accurate).
8. We clean up the land edge of the shapefile by clipping against the land mask.

## Stage 2 - v0-2_merge-maps - Combining the reefs maps together
To improve the detection rate for small and hard to detect reefs in this stage Rachel combined the two reef maps (Reef-Features_Ref1_RB and Rough-reef-mask_Ref2_EL) by identifying features in the Rough-reef-mask_Ref2_EL that were missing in her mapping. The missing reefs were typically remapped from the satellite imagery rather than copying them from the Rough-reef-mask_Ref2_EL because the rough reef map features were typically too coarse in detail.

## Stage 1 - v0-1_dual-maps - Two independent mappings from satellite imagery
This stage involved manual digitisation of reefs predominantly from Sentinel 2 imagery, although some additional high resolution image sources were used for Reef-Features_Ref1_RB. This phase includes mapping of the reefs by two relatively independent cartographers. 
1. Reef-Features_Ref1_RB: Mapped by Rachel Bycroft. Full resolution reef mapping with the core focus on mapping coral reefs and rocky reefs, with sand banks as a lower priority. No intertidal sediment was mapped. This dataset is the base of the final dataset. The target for digitisation was 1:150k-250k scale with a maximum spatial error of 75 - 150 m. Features were mapped using the clustering rules developed for the Coral Sea Features mapping (approximately: features of the same type closer than 200 m are merged, sand between features is included, sand on the outside is included up to 50 m). Features were mapped and assigned as per the Reef Boundary Type classification (RB_Type_3). Complex areas were split based on types so that a coral reef growing outwards from a rocky reef would be mapped as two areas joined together. This mapping took approximately 450 hours.
2. Rough-reef-mask_Ref2_EL: Mapped by Eric Lawrey. Half resolution mapping, with no type classification, but with intertidal areas included. This dataset started out as the rough reef mask for developing a semi-automated approach for mapping reefs and the intertidal zone (Lawrey, 2025). This mapping was extended to more comprehensively map reef boundaries, including small reefs, to act as a cross reference check for the Reef-Features_Ref1 dataset. It could be used to identify reefs that were missed in the primary reef mapping, helping to determine detection rate for each cartographer. The reef features were mapped at a rapid pace, with an average of 40 seconds per feature. The target maximum boundary error was 250 m, however little care was taken to make the mapped boundaries smooth. The goal of this mapping was to mask out a shallow area, regardless of the benthic type.


## TODO: Stage X - v0-X_merge-bathy - Check bathymetry and marine charts for reefs we missed
In this stage information from bathymetry sources was incorporated into the mapping. The AHO Marine Charts (Australian Hydrographic Office, 2021a, 2021b) and bathymetry datasets were reviewed to identify any reef features that were missed in the previous stages. For Marine Charts peaks and reefs identified in the charts were compared with the mapped reef boundaries. On the marine charts, shallow reefs are marked as a hazard or as a peak, showing a depth sounding, with a contour around the peak.

Potential reefs identified from the bathymetry were reviewed in the satellite imagery. In general only potential reefs that could be confirmed visually from the satellite imagery added to the reef dataset. Where no confirmation imagery was found, the potential reef was recorded in a separate point dataset. These were used to help identify the number of potential reefs that were missed by the reef mapping. Features identified only in the bathymetry were not included by default because the available bathymetry is highly variable in quality. Not all peaks in the bathymetry dataset are reefs. In some cases they appear as a peak due to the large spacing between the depth soundings. Reefs were only included directly from the bathymetry where there was good evidence that the source bathymetry was a high quality representation of the true bathymetry.

In this stage we also identified AHO marine chart depth soundings that did closely align with mapped reef centroids. These depths were recorded in the dataset and later used to calibrate and validate the depth classification of reefs.

In this stage we also identified whether the mapped reef feature corresponded to a reef feature that was already known about. For this we consider a reef to have already been known about if it appears as a distinct feature in the marine charts, or bathymetry, or part of ReefKIM (Kordi et al., 2016), Big Bank Shoals, or AIMS north west shoal benthic surveys.