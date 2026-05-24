# Scenario 1 + Pathfinder Validation

- Scope: system-level Scenario 1 (`常规突发`) with Pathfinder-derived waiting-zone geometry and distance data.
- Compared methods: `ACO`, `PaperImprovedAStar`, `OurSinglePath`.
- Ablations: remove `source release`, `downstream release`, and `exit pressure` from `OurSinglePath` one at a time.

## What To Show In The Paper

- Macro comparison: [207_scenario1_pathfinder_macro_metrics.svg](C:/Users/帅美婷sweet baby/Desktop/network/207_scenario1_pathfinder_macro_metrics.svg)
- Line clearance comparison: [208_scenario1_pathfinder_line_clearance.svg](C:/Users/帅美婷sweet baby/Desktop/network/208_scenario1_pathfinder_line_clearance.svg)
- Reroute responsiveness: [209_scenario1_pathfinder_reroute_summary.svg](C:/Users/帅美婷sweet baby/Desktop/network/209_scenario1_pathfinder_reroute_summary.svg)
- Ablation sensitivity: [210_scenario1_pathfinder_ablation.svg](C:/Users/帅美婷sweet baby/Desktop/network/210_scenario1_pathfinder_ablation.svg)
- Mechanism attribution vs literature method: [211_scenario1_pathfinder_mechanism.svg](C:/Users/帅美婷sweet baby/Desktop/network/211_scenario1_pathfinder_mechanism.svg)

## High-Level Findings

- Fastest total evacuation among the three main methods: `OurSinglePath` = `279.00s`.
- Lowest queueing burden: `OurSinglePath` = `50225.00` person-s.
- Lowest moderate congestion exposure (`density > 3`): `OurSinglePath` = `18513.00` person-s.
- Lowest severe congestion exposure (`density > 5`): `ACO` = `8027.00` person-s.
- Lowest peak density: `PaperImprovedAStar` = `16.28` person/m^2.
- `OurSinglePath` vs `ACO`: evacuation `-67.00s`, queueing `-7109.00` person-s, moderate congestion `-562.00` person-s, severe congestion `+2895.00` person-s.
- `OurSinglePath` vs `PaperImprovedAStar`: evacuation `-3.00s`, queueing `-11582.00` person-s, moderate congestion `-1551.00` person-s, severe congestion `-1934.00` person-s.
- `congestion_exposure_time_person_s` is now interpreted as the moderate (`density > 3`) exposure metric for backward compatibility.
- Exit-approach effect should be read from the mechanism-attribution chart rather than the current `exit_usage` aggregate, because this bookkeeping path is not yet exposing usable totals in the system-level metrics.

## Why The Added Terms Matter

- `OurNoSourceRelease` relative to `OurSinglePath`: evacuation `+18.00s`, queueing `-21757.00` person-s, moderate congestion `-8984.00` person-s, severe congestion `-4492.00` person-s.
- `OurNoDownstreamRelease` relative to `OurSinglePath`: evacuation `+18.00s`, queueing `-21757.00` person-s, moderate congestion `-8984.00` person-s, severe congestion `-4492.00` person-s.
- `OurNoExitPressure` relative to `OurSinglePath`: evacuation `+18.00s`, queueing `-21757.00` person-s, moderate congestion `-8984.00` person-s, severe congestion `-4492.00` person-s.

## How To Explain Rerouting

- `OurSinglePath vs ACO`: divergence `4137`, baseline changes `2025`, our changes `58`, affected sources `27`, guided lower-density share `2.3%`.
- `OurSinglePath vs PaperImprovedAStar`: divergence `2162`, baseline changes `24`, our changes `58`, affected sources `21`, guided lower-density share `14.1%`.

## Mechanism Interpretation

- Divergence samples used for `PaperImprovedAStar` vs `OurSinglePath`: `79`.
- In the mechanism chart, compare `BaselineStylePath` and `OurChosenPath` under the same crowd state.
- If the blue/red added-penalty blocks are clearly higher on the baseline-style path, that is direct evidence that your three added terms are not decorative: they are the reason the algorithm avoids seemingly short but hard-to-release paths.

## Data Files

- [201_scenario1_pathfinder_method_summary.csv](C:/Users/帅美婷sweet baby/Desktop/network/201_scenario1_pathfinder_method_summary.csv)
- [202_scenario1_pathfinder_line_clearance.csv](C:/Users/帅美婷sweet baby/Desktop/network/202_scenario1_pathfinder_line_clearance.csv)
- [203_scenario1_pathfinder_exit_summary.csv](C:/Users/帅美婷sweet baby/Desktop/network/203_scenario1_pathfinder_exit_summary.csv)
- [203b_scenario1_pathfinder_exit_by_source_group.csv](C:/Users/帅美婷sweet baby/Desktop/network/203b_scenario1_pathfinder_exit_by_source_group.csv)
- [203c_scenario1_pathfinder_spatial_bottlenecks.csv](C:/Users/帅美婷sweet baby/Desktop/network/203c_scenario1_pathfinder_spatial_bottlenecks.csv)
- [204_scenario1_pathfinder_reroute_summary.csv](C:/Users/帅美婷sweet baby/Desktop/network/204_scenario1_pathfinder_reroute_summary.csv)
- [205_scenario1_pathfinder_ablation_summary.csv](C:/Users/帅美婷sweet baby/Desktop/network/205_scenario1_pathfinder_ablation_summary.csv)
- [206_scenario1_pathfinder_mechanism_detail.csv](C:/Users/帅美婷sweet baby/Desktop/network/206_scenario1_pathfinder_mechanism_detail.csv)
