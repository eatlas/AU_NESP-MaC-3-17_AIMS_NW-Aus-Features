## Validation sampling

This analysis was performed on the v0-4 dataset and is planned to be completed as part of the final dataset validation in v1-1. No additional work was done on this in v1-0.

To provide a basic level of validation to the dataset we perform an expert review of a random sample of reef features, looking to answer the following key questions:
1. Does the indicated feature exist? i.e. it is a reef or sand bank
2. Is the classification accurate?
3. Are there other errors associated with the feature such as boundary accuracy or other attributes?
The goal of this validation is to assess the number of false positives that are likely in the dataset. False positives are problematic as they could lead to proponents being sent to investigate non-existent features, leading to wasted time and money.

A significant challenge in validating the dataset is the small size of reefs relative to open water. Simply uninformed random sampling will result in over 99% samples of open water as the reef areas only represent 1.2% of the study area.

We instead assess the accuracy of mapped reefs by randomly selecting a number of reefs to perform a detailed review by two reef mapping experts. This ensures that the focus is on the small areas represented by the reefs. This approach does not assess the false negative rate, i.e. features that are not mapped. 

The density of reef features is not uniform along the coastline, with the Kimberley containing a much higher density of features per unit area. To ensure that each region receives sufficient features to review the study area was broken into 12 regions, each corresponding to segments of 350 - 600 km of coastline. Where possible the boundaries were chosen to closely align with existing named regions and with the natural boundaries of systems. All offshore reefs were clustered into a single group due to the low number of offshore features.

A Python script was used to randomly choose an equal number of features from each region. These were organised into batches of 10 features per region per batch. This allowed the team to work progressively, with each batch covering the full study area. 


Each feature to be reviewed is referenced by a point that exists close to the centroid of the feature being reviewed. The point is guaranteed to be inside the polygon. Each reviewer assigns the usual feature classifications, along with an indication of whether the feature is a false positive. This assignment of classifications is performed blind, without review of the existing assigned values. This allows a less biased assessment. 
1. Is there a feature of significance at the location indicated by the polygon (rocky reef, coral reef, sand bank)? (FeatExists)
2. What is an appropriate level of confidence in the feature existence (TypeConf)
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

To facilitate the automated validation the validation needs to be divided into three parts:
1. Feature-centroid: A feature centroid point that represents the feature and its attributes. 
This can be linked back to the mapped feature using a spatial join. This point must be 
central and inside the feature polygon to ensure this spatial join works correctly.
2. Polygon-extent: A simplified polygon that represents the extent of the feature. This 
polygon aims to assist the validator in understanding the extent of the feature without 
biasing them to the exact geometry of the feature. The geometry vertices should be randomly 
fuzzed by approximately 50 m and simplified to an approximately 50 m allowable error.
3. Boundary-error: One or more points that lie on a random point of the boundary of the feature polygon.
These points will be repositioned by the validator to lie on the closest best estimate of the 
true boundary of the feature. To reduce bias, these points should be randomly
chosen from the simplified version of the polygon. These points can lie on the lines
between vertices of the simplified polygon, or the vertices themselves.

The Feature-centroid, Polygon-extent and Boundary-error should be cross linked by a unique ID.

The Feature-centroid should have the following attributes:
- ValidID (Integer): Unique identifier for the validation feature. Used to cross-link between the
    centroid, extent and boundary-error features.
- FeatExists (String, values: 'True','False') 
    Is there a feature of significance at the location indicated by the polygon 
    (rocky reef, coral reef, sand bank)?
- TypeConf (String, values: 'High','Medium','Low','Very Low'): 
    What is an appropriate level of confidence in the feature existence (TypeConf)
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