The following are validation questions used to test the LLM primer documentation. These questions should not be addressed directly by the documentation, and should only be reviewed and assessed once the documentation is considered complete and ready for benchmarking. The training questions provided in the README.md can be considered in the documentation and used to test and optimised the response from LLMs during the development of the documentation.

These questions are filed in a separate file to limit exposure to these questions during the development of the documentation. Because the documentation and benchmarking is developed manually by a single individual the act of writting the answers to the benchmark questions would pollute the development process. Knowledge of the questions that will be asked will bias the documentation to directly answer these questions. This will result in the documentmentation appearing to perform well, whilst not actually performing well on unseen user questions.

To limit exposure to the validation questions once the questions were collected from users, or created, they were split into one third training and two thirds validation questions. The validation questions were moved copy and pasted into this file without reading them. This file was then not touched until the documentation was considered ready for benchmarking. There was at least a week between the creation of the questions and the creation of the documentation. This helped to ensure any knowledge of the questions faded from memory.


Questions below
======= vvvvvvv =========


19. How did you tell whether a feature is a coral reef or rocky reef?
21. Why were coral reefs mapped as 'Coral Reef' and 'Coral Reef Flat'?
23. Why weren't bathymetry datasets used as part of the initial mapping (version v0-1, to v0-4)?
25. Can this dataset help me find good fishing locations?
27. How many reefs did this mapping discover?
29. What enabled you to map reefs now? Could this mappping have been done in the past?
31. How do I download the dataset?
33. What is reef mapping?
35. What do the different reef types mean?
37. What is the intended purpose of this dataset?












2. How many reefs are likely to be missing from the dataset?
3. What reefs are in the Arnhem Marine Parks?





What exactly does this dataset map and what it excludes?
How do I dissolve sub types into a single coral reef extent?
Which attribute flags reefs outside Australia for easy filtering?


Does this dataset satisfy EPBC referral screening requirements?


Which attributes best distinguish shallow reef features that are most vulnerable to gear contact, and how should DepthCat be interpreted for gear specific planning given it reflects the shallowest 10 percent?


How do we filter reefs within Commonwealth marine parks only?

Wetlands
How do reef flats interface with seagrass and mangrove mapping?
Does the dataset indicate areas likely to support seagrass?
How frequently will updates occur and how are changes logged?


What licence and attribution should we include in assessment reports?
What default buffer distances are recommended for impact screening?
Where do we download the shapefile and supporting metadata?


How robust are depth categories where satellite methods were used?
Which field provides persistent unique IDs for longitudinal site tracking?


What offline or low bandwidth data access options are supported for use in ranger programs and community workshops?
How do we filter reefs within our sea country boundaries?
Can we add traditional place names?


Is there an offline friendly GeoPackage or GeoJSON available?
How accurate are boundaries in our patrol area?
How should we record and submit boundary or classification issues?


•	How does this relate to the Complete GBR & TS features 1b, Coral Sea features, and Coral Sea oceanic vegetation datasets? Does this dataset supersede all of those, or some, or none?
•	Why are there features with DepthCat = Land that have DEM10/50/90p values several hundred metres deep?
•	I'm an ecologist. Do I need to care about 'Attachment'?
•	I can see OrigType is very often different to RB_Type_L3. Sometimes it looks like the original feature class is a "more detailed" classification. Is OrigType just included for information purposes, and I should always use RB_Type_L3 as the "most correct" classification? Or is there a case where I should use OrigType in preference to RB_Type_L3?

•	Do the biological classifications for habitat-forming organisms (coral, macroalgae) mean we believe there is actually living coral & macroalgae on those features? Or do we just know these organisms are the origin of those features, and we don't really know if they are still living on these features? Is there any way to understand which features/regions are underpinned by actual validation data (eg grabs or imagery/visual survey) versus which are assumed based on similar topographic + spectral characteristics?
•	Where you had validation data, was any of this withheld for checking classification accuracy? Where you report approx 80-95% classification accuracy, is this compared to actual ground-truthing?
•	Are you more confident about some feature types than others? Or some regions than others?


•	"I am interested in the presence of raised seabed features that present a navigational hazard. What attributes should I care about, and how would I use this."
•	"I am an ecologist wanting to understand features that support biology or may be aggregation points for mobile species. What aspects and attributes in this dataset should I care about?"