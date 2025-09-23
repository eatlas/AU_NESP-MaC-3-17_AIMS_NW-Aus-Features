The following are questions that will be used to test the effectiveness of the LLM primer documentation associated with this dataset. The LLM primer documentation is intended to act as reference documentation that will impart a deep understanding of the dataset. Ideally it should contain enough information that an LLM with this documentation in its context should be act as a representative of the knowledge of the project team that produced the dataset.

These benchmark questions aims to test whether the documentation provides sufficient detail that a good LLM and answer the questions based on the LLM primer documentation. 

These benchmark questions would ideally come from users of the dataset and represent the true diversity of questions that people will ask. This is however not the case. The questions are created by the project team imagining what people might ask about the dataset. As such they will be a subset of the true range of questions. They are intended to provide a rough indication of documentation performance, rather than a full coverage test.

1. Does this dataset map habitats or reefs?
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

Questions from Emma Flukes:

1. How are the DepthCat calculated? I can see 'shallow' DepthCat with DEM50p >1,000m deep?
2.	How should I use the FeatConf and TypeConf attributes? If I wanted to only include features that you were "more confident" about, should I (for example) exclude "Very Low" confidence for both Feature and Type? Or would I include the low confidence FeatConf (acknowledging the boundaries might be inaccurate) but just excluding low confidence TypeConf?
3. "I am wanting to synthesise this dataset with other seafloor feature datasets (+/- biology) for the area. How could I decide, on a per-dataset or per-feature basis, how the confidence/accuracy of these features matches up to other datasets, to choose which to use as a point of truth for a given feature?"
