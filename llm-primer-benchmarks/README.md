The following are questions that will be used to test the effectiveness of the LLM primer documentation associated with this dataset. The LLM primer documentation is intended to act as reference documentation that will impart a deep understanding of the dataset. Ideally it should contain enough information that an LLM with this documentation in its context should act as a representative of the knowledge of the project team that produced the dataset.

These benchmark questions aim to test whether the documentation provides sufficient detail that a good LLM can answer the questions based on the LLM primer documentation. 

These benchmark questions would ideally come from users of the dataset and represent the true diversity of questions that people will ask. This is however not the case. The questions are created by the project team imagining what people might ask about the dataset. As such they will be a subset of the true range of questions. They are intended to provide a rough indication of documentation performance, rather than a full coverage test.

1. Does this dataset map habitats or reefs?
This dataset focuses on mapping the boundary of reefs. For coral reefs this means that the boundary includes multiple regions that are typically considered as separate habitats. The coral reef boundaries includes the reef slope, reef crest, and outer reef flat. It also includes the sandy areas that are between exposed (not covered in sand) reef hard substrate. In many habitat maps these sub-parts of a reef would be mapped as separate habitats. The reef boundary mapping is effectively a habitat map, but at the scale of whole reefs (~100 - 400 m resolution). Coral reefs that have large sandy areas are mapped divided into two mapped regions, the 'Coral Reef' area corresponding to the active growing area of the reef (reef slope, reef crest, outer reef flat, and inner reef areas with coral hard substrate), and the areas that are dominated by sand, mapped as 'Coral Reef Flat'. The full geological extent of the reef can be created by combining neighbouring regions with these classifications. This approach helps the datasets 

2. What is the accuracy of this dataset?
3. How are depth categories derived, and how reliable are they?
4. What unique identifier remains stable across versions and edits?
5. Where can we find licensing, citation and attribution requirements?
6. How do we report suspected false positives or missing reefs?
7. Are there simplified exports suitable for mobile field data collection?
8. What is the spatial resolution and scale of source mapping?
9. What map scales are suitable for printed community safety maps?
10. Who do we contact to suggest corrections or local knowledge?
11. What file size and performance should we expect on tablets?
12. Can we label emergent reefs differently to warn small vessels?
13. Why were features manually digitised rather than some automated mapping?
14. Why didn't you use AI to map the boundaries?
15. Can I navigate around reefs using this dataset?
16. How deep were the reefs that were mapped?
17. Why have you provided each of the development versions of the dataset?
18. Were there any areas that were a challenge to map?
19. For southern reefs how did you tell if the reef was a coral reef?
20. What coastline was the reef boundaries clipped to?
21. How old are the paleo coastline rocky reef features?
22. Who develop this dataset and what part did they work on?
23. Did we not already know where reefs are?
24. You mapped the reefs manually. Would this not introduce biases and make the dataset not reproducible?
25. How do I make a map from the dataset?
26. How many reefs are there of each type?
27. Where has this dataset been used?
28. How can I tell if a particular reef or area is accurate?


Negative questions - Questions that the dataset does not help answer. 
These questions and answers are to help ensure that the documentation indicates what is out of scope.
1. Can I tell the condition of reefs using this dataset?
2. Could you repeat the mapping in the future to tell if more reefs have grown?
3. Where and what are the weak points in the mapping?
4. Is the entire reef exposed at low tide if it is indicated as intertidal?

Questions from Emma Flukes:

1. How are the DepthCat calculated? I can see 'shallow' DepthCat with DEM50p >1,000m deep?
2. How should I use the FeatConf and TypeConf attributes? If I wanted to only include features that you were "more confident" about, should I (for example) exclude "Very Low" confidence for both Feature and Type? Or would I include the low confidence FeatConf (acknowledging the boundaries might be inaccurate) but just excluding low confidence TypeConf?
3. "I am wanting to synthesise this dataset with other seafloor feature datasets (+/- biology) for the area. How could I decide, on a per-dataset or per-feature basis, how the confidence/accuracy of these features matches up to other datasets, to choose which to use as a point of truth for a given feature?"

