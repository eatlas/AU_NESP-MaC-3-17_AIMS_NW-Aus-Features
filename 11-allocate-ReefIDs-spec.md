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

**Why manual override is supported:**
When large boundary changes break spatial matching, the cartographer can set `ReefID` in the Edit file. This value propagates through clipping and forces the script to use it for the L2 group containing that feature.

**Base-10 encoding:**
Consistent with the Coral Sea mapping. Produces readable, speakable identifiers.

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
7. **Match L2 groups to previous version:** For each current L2 group, find the previous L2 feature with greatest area overlap. If overlap > 50% of current group area → inherit that ReefID.
8. **Check manual overrides:** If any L3 feature within a group has `ReefID` set in the input (carried from Edit file through script 10), use that as the group's base ReefID. Manual override wins over spatial matching.
9. **Flag poor matches:** Groups with best overlap ≤ 50% and no manual override → write to QA shapefile. Assign a new tentative ID (script does not stop).
10. **Assign sub-feature letters:** For groups with a single L3 component, the ReefID has no letter suffix. For groups with multiple components: match current L3 features to previous L3 features (same base ReefID, overlap > 50%). Matched features inherit their previous letter. Unmatched features get the next unused letter (starting from 'b' when the group was previously single-component). Letters are permanent once assigned. If a group previously had a single component (no letter) and now has multiple components, the original feature is identified by spatial overlap and retains the unsuffixed base ID. New additions receive letter suffixes starting from 'b' ('a' is reserved to avoid future conflicts). Unmatched features record their best-overlapping previous feature's ReefID as `PrevReefID` for lineage tracking (this lookup is non-exclusive: multiple current features may reference the same previous ReefID).
11. **Allocate new base IDs** for unmatched groups: use the grid cell of the group centroid, increment the counter past all existing IDs in that cell (from previous version + newly allocated in this run).
12. Write output shapefile with fields: `ReefID` (unique per feature, includes letter suffix for multi-component reefs), `PrevReefID`, `ReefIDNote`, plus all original attribute fields.
13. Write allocation log CSV.

## Output Fields Added

| Field | Type | Description |
|-------|------|-------------|
| ReefID | String(15) | Unique reef identifier. No suffix for single-component reefs (e.g. `R-9140-003`). Letter suffix for multi-component reefs (e.g. `R-9140-003a`). The base form (strip trailing letter) groups L3 components into their parent reef. |
| PrevReefID | String(120) | Semicolon-separated set of previous ReefIDs accumulated across versions. Records lineage when a feature's ID changes due to split, merge, or reassignment. Inherited from the previous version's `PrevReefID` and extended with any new change. Self-references (current ReefID) are excluded. |
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
- Merges: group inherits the base ID with best spatial overlap; absorbed features get `PrevReefID` set. If the merged result is a single component, the letter suffix is dropped and the ReefID reverts to the unsuffixed base form.
- Sub-feature letters: permanent once assigned. New sub-features get next available letter. Removed sub-features leave a gap (letter retired). If all sub-features except one are removed, the remaining feature's ReefID reverts to the unsuffixed base form.
- `PrevReefID` accumulation: `PrevReefID` is a semicolon-separated set that accumulates across versions. When matching against the previous version, the script inherits the previous feature's `PrevReefID` set and adds any newly recorded previous ID. The current feature's own ReefID is excluded from the set. This ensures the full lineage chain is preserved across multiple version transitions.
