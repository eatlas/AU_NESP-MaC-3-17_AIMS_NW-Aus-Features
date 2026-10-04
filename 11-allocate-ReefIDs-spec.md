# 11-allocate-ReefIDs.py — Design Specification

## Purpose

Assign permanent, globally unique ReefIDs to reef features after land clipping. IDs are allocated at the L2 reef level (the whole geological structure). Where a reef consists of multiple L3 components, alphabetic sub-feature suffixes distinguish the parts. Where a reef consists of a single L3 component, no suffix is used. IDs persist across dataset versions via spatial matching against the previous version.

## ReefID Structure

```
R-9140-003a
│ │      │
│ │      └─ Sub-feature letter (L3 component within the reef)
│ └──────── Feature counter (sequential within grid cell, zero-padded to 3 digits)
└────────── Grid cell code (4-digit base-10, encodes centroid lon/lat)
```

In the L3 dataset, the ReefID uniquely identifies each feature. For single-component reefs the ReefID has no suffix (e.g. `R-9140-003`). For multi-component reefs each L3 part receives a letter suffix (e.g. `R-9140-003a`, `R-9140-003b`). In the L2 dataset, where components are dissolved into one polygon, the ReefID is always the unsuffixed form (`R-9140-003`). The base form (without letter) can always be derived by stripping any trailing letter, providing an implicit grouping key.

## Design Decisions

**Why allocate after land clipping (post script 10), not in the Edit file:**
Features are digitised loosely on the landward side. Land clipping can split one Edit polygon into multiple singlepart polygons. Allocating after clipping means each real polygon gets its own sub-feature identity without requiring the cartographer to pre-split features.

**Why allocate at L2 level:**
ReefIDs are intended as name-replacements for unnamed reefs. Users refer to "the reef" as a whole, not its sub-components. A coral reef edge and its adjacent reef flat are parts of the same reef and should share a base ID. The L2 product uses the base ID (no letter) directly. In the L3 dataset, each feature still has a unique ReefID because multi-component reefs receive letter suffixes.

**Why spatial matching (not stored in Edit file):**
The Edit file stores one polygon that may become multiple post-clip features. Storing IDs in the Edit file creates a one-to-many problem. Spatial matching against the previous version's output is the cleanest persistence mechanism.

**Why exclusive candidate pools (not independent per-group matching):**
A single previous reef can appear in the current version as several disconnected L2 groups — e.g. where the reef was split into multiple pieces, or where parts were reclassified to a different L2 class. If each group matched independently and inherited on its own threshold, every piece would inherit the same base ID and each single-member group would emit the same unsuffixed ReefID (observed in v1.2: six reefs, fourteen duplicated features). Candidates are therefore pooled per previous reef, and only the greatest-overlap group inherits.

**Why two-sided shares and a 10% candidate threshold (ported from the GBR remap):**
A single symmetric measure cannot distinguish a split (low share of the old polygon, high share of the new) from a merge (high share of the old, low share of the new). Two-sided shares, with a 0.1 floor on either side, establish a candidate relationship without requiring the old 50%-of-current-area rule, which misclassified in both directions: small break-off pieces each appeared to "match" at ~100% of their own area (one-to-many inheritance), while a 30%-overlap fragment fell below 50% and lost its lineage.

**Why a sliver test (ported from the GBR remap):**
Intersections that disappear when eroded by 10 m (or by 25% of the smaller feature's inscribed width, for small features) are digitising artefacts and are discarded before shares are computed. This prevents a new feature drawn along the edge of an old reef from forming a spurious candidate relationship. Ported unchanged from the GBR remap project (`02a-patch-TS-GBR-Features.py`), including its tolerance constants.

**Why match in Australian Albers (EPSG:3577):**
The sliver test requires metres, and pool-winner selection compares absolute overlap areas. Australian Albers is equal-area everywhere, so area comparisons remain valid across the full dataset extent, including the small fraction of features outside the nominal area of use. Same CRS and constants as the GBR remap project.

**Why greatest-absolute-overlap inherits (no dominance ratio):**
The GBR remap had a human confirmation stage and used a 3× dominance ratio, orphaning the ID where no candidate was dominant. This pipeline must allocate permanent IDs with no review stage, so the greatest-overlap successor always inherits. Near-tie splits remain visible in the QA output (both shares are recorded) and can be corrected with a manual override in a subsequent version.

**Why manual override is supported:**
When large boundary changes break spatial matching, the cartographer can set `ReefID` in the Edit file. This value propagates through clipping and forces the script to use it for the L2 group containing that feature.

**Base-10 encoding:**
Consistent with the Coral Sea mapping. Produces readable, speakable identifiers.

## Matching Parameters

| Parameter | Value | Purpose |
|---|---|---|
| `MATCH_CRS` | EPSG:3577 (GDA94 Australian Albers) | Equal-area, metres. All spatial matching is performed in this CRS. |
| `SLIVER_TOLERANCE_M` | 10 | Erosion distance (m) below which an intersection is treated as a digitising artefact |
| `SLIVER_WIDTH_FRACTION` | 0.25 | Cap on erosion distance as a fraction of the smaller feature's inscribed width |
| `CANDIDATE_SHARE` | 0.1 | Minimum share of either polygon's area for a candidate relationship |
| `LETTER_MATCH_SHARE` | 0.5 | Minimum share of the current feature's area for a feature to retain a previous letter (in-group letter matching) |

## Inputs

| Input | Source |
|-------|--------|
| Current clipped L3 features | `working/{version}/10/NW-Aus-Features_{version}.shp` (output of script 10) |
| Previous version L2 output | `config.ini` → `previous_processed_L2` |
| Previous version L3 output | `config.ini` → `previous_processed` |
| L3-to-L2 crosswalk | `data/{version}/in/RB_Type_L3_crosswalk.csv` |

## Outputs

| Output | Path |
|--------|------|
| L3 features with ReefID | `working/{version}/11/NW-Aus-Features_{version}.shp` |
| Poor-match QA shapefile | `working/{version}/11/ReefID-poor-matches.shp` |
| Allocation log | `working/{version}/11/ReefID-allocation-log.csv` |

## Processing Steps

1. Load current clipped features, explode multiparts to singleparts.
2. Determine each feature's RB_Type_L2 class from the crosswalk.
3. Dissolve touching features of the same L2 class to form L2 groups. Each group = one reef.
4. Compute centroid of each L2 group (for grid cell assignment).
5. If `--fresh`: allocate all ReefIDs from scratch (sorted by centroid lon+lat sum within each grid cell). For groups with multiple L3 components, assign letter suffixes by area descending (e.g. `R-9140-003a`, `R-9140-003b`). For single-component groups, the ReefID has no letter (e.g. `R-9140-003`). Done.
6. Otherwise, load previous L2 and L3 outputs.
7. **Project to the matching CRS:** Reproject current groups/features and the previous L2 and L3 outputs to `MATCH_CRS` (Australian Albers — equal-area, metres) for all spatial matching. Output files retain their original CRS.
8. **Score spatial relationships (L2 level):** For each pair (current L2 group, previous L2 feature) whose geometries intersect, apply the sliver test: erode the intersection by `SLIVER_TOLERANCE_M` (10 m), or by at most `SLIVER_WIDTH_FRACTION` (25%) of the inscribed width of the smaller feature; discard the pair if the intersection disappears. For surviving pairs, compute two-sided shares: `share_old` = intersection / previous feature area, `share_new` = intersection / current group area. The pair is a *candidate relationship* if either share ≥ `CANDIDATE_SHARE` (0.1).
9. **Allocate base IDs via candidate pools:** Candidates are grouped by previous L2 feature (one per previous reef component). A pool with a single candidate inherits the previous base ReefID. A pool with multiple candidates: the candidate with the greatest absolute overlap area inherits; the rest fall through to new-ID allocation (step 12). Inheritance is exclusive — at most one current group inherits per previous reef component. (A reef spanning several L2 classes has one pool per class; each may inherit the same base, which is intended.) If one current group is the top candidate for several previous reefs (a merge), it inherits the greatest and the other reefs' IDs are retired; the absorbed features carry their lineage via `PrevReefID` (step 11).
10. **Check manual overrides:** If any L3 feature within a group has `ReefID` set in the input (carried from Edit file through script 10), use that as the group's base ReefID. Manual override wins over spatial matching.
11. **Assign sub-feature letters and lineage:** For groups with a single L3 component, the ReefID has no letter suffix. For groups with multiple components: match current L3 features to previous L3 features (same base ReefID, overlap > `LETTER_MATCH_SHARE` of the current feature's area). Matched features inherit their previous letter. Unmatched features get the next unused letter (starting from 'b' when the group was previously single-component). Letters are permanent once assigned. If a group previously had a single component (no letter) and now has multiple components, the original feature is identified by spatial overlap and retains the unsuffixed base ID. New additions receive letter suffixes starting from 'b' ('a' is reserved to avoid future conflicts). Unmatched features record their best-overlapping previous feature's ReefID as `PrevReefID` for lineage tracking (this lookup is non-exclusive: multiple current features may reference the same previous ReefID). For groups that did **not** inherit their base (step 9): each L3 feature additionally records, in its `PrevReefID` set, every previous L3 feature (any base, in the matching CRS) whose intersection survives the sliver test and whose `share_old` or `share_new` ≥ `CANDIDATE_SHARE` — with letter suffix. When a base ID is shared by several L2 groups (a reef spanning multiple L2 classes), letters are drawn from a single per-base pool (letters used or retired by any group of the base, in the previous version or this run), and at most one feature per base is unsuffixed: the member of the largest single-member group. Other single-member groups receive letters.
12. **Allocate new base IDs** for non-inheriting groups: use the grid cell of the group centroid, increment the counter past all existing IDs in that cell (from previous version + newly allocated in this run). Previous bases with no inheriting group are retired and never reused.
13. **Uniqueness check:** Verify all allocated ReefIDs are unique across the output. If any duplicates exist, abort the build with an error listing the duplicates — no output files are written. A duplicate indicates a logic error in matching or letter assignment.
14. **Flag non-inheriting groups (QA):** Groups that did not inherit and were not overridden → write to QA shapefile (group geometry, new base ID, reason — no candidates or pool loser, `share_old`/`share_new`, best previous ReefID). The script does not stop.
15. Write output shapefile with fields: `ReefID` (unique per feature, includes letter suffix for multi-component reefs), `PrevReefID`, `ReefIDNote`, plus all original attribute fields.
16. Write allocation log CSV.

## Output Fields Added

| Field | Type | Description |
|-------|------|-------------|
| ReefID | String(15) | Unique reef identifier. No suffix for single-component reefs (e.g. `R-9140-003`). Letter suffix for multi-component reefs (e.g. `R-9140-003a`). The base form (strip trailing letter) groups L3 components into their parent reef. |
| PrevReefID | String(120) | Semicolon-separated set of previous ReefIDs accumulated across versions. Records lineage when a feature's ID changes due to split, merge, or reassignment. Inherited from the previous version's `PrevReefID` and extended with any new change. Self-references (current ReefID) are excluded. Lineage entries retain their letter suffix (a fragment split off from a lettered sub-feature records that sub-feature's ID, e.g. `R-9140-003a`). |
| ReefIDNote | String(120) | Semicolon-separated set of notes accumulated across versions. New features are tagged `new {version}` (e.g. `new v1-2`). Inherited from the previous version's `ReefIDNote` and extended with any new note. |

## Command-line Interface

```
python 11-allocate-ReefIDs.py [--fresh] [--base B10]
```

- `--fresh`: Allocate all IDs from scratch (no matching against previous version). Required for first-time allocation.
- `--base`: Character set for encoding (default: `B10`). Matches the Coral Sea convention.

All paths are derived from `config.ini`. No positional arguments needed for standard use.

## Downstream Consumption

- **Script 12 (expand-attribs):** Reads the output of this script. Includes `ReefID`, `PrevReefID`, `ReefIDNote` in `RETAIN_FIELDS`.
- **Script 13 (make-RB_Type_L2):** Strips the trailing letter from each feature's ReefID to produce the base form (e.g. `R-9140-003a` → `R-9140-003`). All L3 features in a dissolved group share the same base ReefID by construction. The L2 output stores this base form as the `ReefID`.

## Permanence Rules

- Once allocated, a ReefID is permanent. Boundary refinements do not change it.
- Retired IDs (false positives removed) are never reused.
- Additions: when a new feature is added adjacent to an existing single-component reef, the original feature retains its unsuffixed ReefID. The new feature receives a letter suffix (starting from 'b'). Letter 'a' is reserved. `PrevReefID` is not set on genuinely new features.
- Splits: when a sub-feature is split into two parts, the larger part retains the original letter. The smaller part receives a new letter suffix. `PrevReefID` on the smaller part records the original sub-feature's ReefID (the feature it was carved from). This lineage lookup is non-exclusive: multiple split fragments may reference the same previous ReefID.
- Splits into disconnected parts: when a reef is split into multiple disconnected parts, or parts are reclassified to a different L2 class, each part becomes a separate L2 group and all are candidates for the same previous reef (step 9). The part with the greatest absolute overlap keeps the reef's base ID; the others receive new base IDs with `PrevReefID` set to the previous feature(s) they overlap (with letter suffix). The non-inheriting parts' `ReefIDNote` records `new {version}`, and they appear in the QA shapefile as pool losers.
- Merges: group inherits the base ID with greatest absolute overlap; absorbed features get `PrevReefID` set. If the merged result is a single component, the letter suffix is dropped and the ReefID reverts to the unsuffixed base form.
- Multi-class reefs: a reef spanning several L2 classes yields one L2 group per class, all inheriting the same base ID where each class matches its previous feature. Letters are unique per base across all groups of the reef, and at most one feature per base is unsuffixed (the member of the largest single-member group).
- Sub-feature letters: permanent once assigned. New sub-features get next available letter. Removed sub-features leave a gap (letter retired). If all sub-features except one are removed, the remaining feature's ReefID reverts to the unsuffixed base form.
- `PrevReefID` accumulation: `PrevReefID` is a semicolon-separated set that accumulates across versions. When matching against the previous version, the script inherits the previous feature's `PrevReefID` set and adds any newly recorded previous ID. The current feature's own ReefID is excluded from the set. This ensures the full lineage chain is preserved across multiple version transitions.
