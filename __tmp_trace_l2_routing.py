"""Trace step-by-step: when does VN_L7toL2_Hall choose L2_3 over L2_2?

Simulates queue buildup at Gate_L2_N_West and computes costs each step.
"""
import sys, importlib.util, types, math

def _noop_mpl():
    if importlib.util.find_spec("matplotlib"): return
    m=types.ModuleType("matplotlib"); p=types.ModuleType("matplotlib.pyplot"); pt=types.ModuleType("matplotlib.patches")
    def _n(*a,**kw): return None
    p.figure=_n; p.subplots=lambda *a,**kw:(None,None); p.plot=_n; p.bar=_n; p.savefig=_n; p.close=_n
    p.tight_layout=_n; p.grid=_n; p.xlabel=_n; p.ylabel=_n; p.title=_n; p.legend=_n; p.suptitle=_n
    p.rcParams={}; pt.Patch=object; m.pyplot=p; m.patches=pt
    sys.modules["matplotlib"]=m; sys.modules["matplotlib.pyplot"]=p; sys.modules["matplotlib.patches"]=pt
_noop_mpl()
sys.path.insert(0,".")

import network
import single_path_routing as spr

# Build full Mode 1 population
BASE_LOADS = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}

pop = {}
for line, physics in network.TRAIN_PHYSICS.items():
    base = BASE_LOADS[line]
    pop[line] = {
        "train_1": 0, "train_2": 0,
        "platform_waiting": int(base["platform_waiting"]),
        "hall_people": int(base["hall_people"]),
        "transfer_people": int(base["transfer_people"]),
    }

print("Running simulation with exit_usage_by_source_group mode...")

# Run full simulation and get per-source exit usage
graph = network.build_graph()
metrics = network.run_simulation_for_metrics_timed(
    graph, pop, method=network.OUR_SINGLE_PATH_METHOD
)

exit_usage = metrics.get("exit_usage", {})

# Now compare vs Pathfinder target
TARGET = {
    "Exit_L18_12": 382, "Exit_L18_13": 44, "Exit_L18_17": 26,
    "Exit_L7_7": 394, "Exit_L7_8/9": 136,
    "Exit_L2_6": 111, "Exit_L2_2": 216, "Exit_L2_3": 365, "Exit_L2_4": 105,
    "Exit_L16_10": 53, "Exit_L16_11": 354,
}

print(f"\n{'Exit':<20s} {'Target':>7s} {'Actual':>7s} {'Diff':>8s}")
print("-" * 50)
l2_total = 0
for e in TARGET:
    actual = exit_usage.get(e, 0)
    diff = actual - TARGET[e]
    print(f"  {e:<20s} {TARGET[e]:7.0f} {actual:7.0f} {diff:+8.0f}")
    if "L2" in e:
        l2_total += actual

l2_target = sum(v for k,v in TARGET.items() if "L2" in k)
print(f"\n  L2 totals: target={l2_target}  actual={l2_total}")

# Now check per-source-group exit usage for L2
# Structure: exit_usage_by_source_group[exit_name][source_group_id] = count
src_usage = metrics.get("exit_usage_by_source_group", {})

# Gather all source group IDs across all L2 exits
all_source_groups = set()
for exit_name, group_map in src_usage.items():
    if "L2" not in exit_name:
        continue
    for sg_id in group_map:
        all_source_groups.add(sg_id)

print(f"\nL2-related source groups found: {sorted(all_source_groups)}")

# 1. Per-exit: which source groups contributed?
print(f"\n{'='*80}")
print(f"L2 EXITS: per-source-group breakdown")
print(f"{'='*80}")
for exit_name in sorted(src_usage):
    if "L2" not in exit_name:
        continue
    group_map = src_usage[exit_name]
    total = sum(group_map.values())
    print(f"\n  {exit_name}: total={total:.0f}")
    for sg_id, count in sorted(group_map.items(), key=lambda x: -x[1]):
        print(f"    {sg_id}: {count:.0f}")

# 2. Per-source-group: which exits did they go to?
print(f"\n{'='*80}")
print(f"L2 SOURCE GROUPS: per-exit breakdown")
print(f"{'='*80}")
# Aggregate by source group
source_group_totals = {}
for exit_name, group_map in src_usage.items():
    for sg_id, count in group_map.items():
        if sg_id not in source_group_totals:
            source_group_totals[sg_id] = {}
        source_group_totals[sg_id][exit_name] = count

# Only show L2 and L7 source groups
for sg_id in sorted(source_group_totals):
    if not ("L2" in sg_id or "L7" in sg_id):
        continue
    exit_counts = source_group_totals[sg_id]
    total = sum(exit_counts.values())
    print(f"\n  {sg_id}: total={total:.0f}")
    for exit_name, count in sorted(exit_counts.items(), key=lambda x: -x[1]):
        print(f"    -> {exit_name}: {count:.0f}")

# 3. Specifically show L7 transfer to L2 exits
print(f"\n{'='*80}")
print(f"L7 TRANSFER -> L2 EXITS (key insight)")
print(f"{'='*80}")
for sg_id in sorted(source_group_totals):
    if "L7" in sg_id and ("transfer" in sg_id.lower() or "hall" in sg_id.lower()):
        exit_counts = source_group_totals[sg_id]
        total = sum(exit_counts.values())
        l2_share = sum(v for k, v in exit_counts.items() if "L2" in k)
        print(f"\n  {sg_id}: total={total:.0f}, to L2 exits={l2_share:.0f}")
        for exit_name, count in sorted(exit_counts.items(), key=lambda x: -x[1]):
            print(f"    -> {exit_name}: {count:.0f}")
