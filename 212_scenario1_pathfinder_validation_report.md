# Scenario 1 + Pathfinder Validation

- Scope: system-level Scenario 1 (`常规突发`) with Pathfinder-derived waiting-zone geometry and distance data.
- Compared methods: `ACO`, `PaperImprovedAStar`, `AdaptiveSingleNextHop`.
- Ablations: remove `upstream load penalty`, `downstream load penalty`, `exit pressure penalty`, plus a `NoPredictivePenalties` lower-bound variant.

## What To Show In The Paper

- Macro comparison: [207_scenario1_pathfinder_macro_metrics.svg](C:/Users/帅美婷sweet baby/Desktop/network/207_scenario1_pathfinder_macro_metrics.svg)
- Line clearance comparison: [208_scenario1_pathfinder_line_clearance.svg](C:/Users/帅美婷sweet baby/Desktop/network/208_scenario1_pathfinder_line_clearance.svg)
- Reroute responsiveness: [209_scenario1_pathfinder_reroute_summary.svg](C:/Users/帅美婷sweet baby/Desktop/network/209_scenario1_pathfinder_reroute_summary.svg)
- Ablation sensitivity: [210_scenario1_pathfinder_ablation.svg](C:/Users/帅美婷sweet baby/Desktop/network/210_scenario1_pathfinder_ablation.svg)
- Mechanism attribution vs literature method: [211_scenario1_pathfinder_mechanism.svg](C:/Users/帅美婷sweet baby/Desktop/network/211_scenario1_pathfinder_mechanism.svg)

## High-Level Findings

- Fastest total evacuation among the three main methods: `AdaptiveSingleNextHop` = `319.50s`.
- Lowest queueing burden: `AdaptiveSingleNextHop` = `43807.50` person-s.
- Lowest moderate congestion exposure (`density > 3`): `AdaptiveSingleNextHop` = `24666.00` person-s.
- Lowest severe congestion exposure (`density > 5`): `AdaptiveSingleNextHop` = `16971.50` person-s.
- Lowest peak density: `AdaptiveSingleNextHop` = `19.05` person/m^2.
- `AdaptiveSingleNextHop` vs `ACO`: evacuation `-139.00s`, queueing `-9602.50` person-s, moderate congestion `-6332.50` person-s, severe congestion `-7583.00` person-s.
- `AdaptiveSingleNextHop` vs `PaperImprovedAStar`: evacuation `-30.50s`, queueing `-5142.50` person-s, moderate congestion `-1170.00` person-s, severe congestion `-1181.50` person-s.
- `congestion_exposure_time_person_s` is now interpreted as the moderate (`density > 3`) exposure metric for backward compatibility.
- Exit-approach effect should be read from the mechanism-attribution chart rather than the current `exit_usage` aggregate, because this bookkeeping path is not yet exposing usable totals in the system-level metrics.

## Why The Added Terms Matter

- `NoUpstreamLoadPenalty` relative to `AdaptiveSingleNextHop`: evacuation `+17.00s`, queueing `-2125.50` person-s, moderate congestion `-425.00` person-s, severe congestion `-2126.50` person-s.
- `NoDownstreamLoadPenalty` relative to `AdaptiveSingleNextHop`: evacuation `+0.00s`, queueing `+46.50` person-s, moderate congestion `+85.50` person-s, severe congestion `+96.50` person-s.
- `NoExitPressurePenalty` relative to `AdaptiveSingleNextHop`: evacuation `+0.00s`, queueing `+311.50` person-s, moderate congestion `+384.50` person-s, severe congestion `+334.00` person-s.
- `NoPredictivePenalties` relative to `AdaptiveSingleNextHop`: evacuation `+14.00s`, queueing `-1724.50` person-s, moderate congestion `+260.50` person-s, severe congestion `-1783.00` person-s.

## How To Explain Rerouting

- `AdaptiveSingleNextHop vs ACO`: divergence `2773`, baseline changes `0`, our changes `258`, affected sources `28`, guided lower-density share `24.7%`.
- `AdaptiveSingleNextHop vs PaperImprovedAStar`: divergence `7562`, baseline changes `0`, our changes `258`, affected sources `28`, guided lower-density share `11.4%`.

## Mechanism Interpretation

- Divergence samples used for `PaperImprovedAStar` vs `AdaptiveSingleNextHop`: `240`.
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
