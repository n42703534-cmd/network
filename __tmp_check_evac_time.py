"""Check evacuation time for ScaleFix + NoPredictivePenalties vs baseline."""
import importlib.util, sys, time, types
if importlib.util.find_spec("matplotlib") is None:
    m = types.ModuleType("matplotlib"); p = types.ModuleType("matplotlib.pyplot")
    pt = types.ModuleType("matplotlib.patches")
    def _n(*a,**kw): return None
    p.figure=_n; p.subplots=lambda *a,**kw:(None,None); p.plot=_n; p.bar=_n; p.savefig=_n; p.close=_n
    p.tight_layout=_n; p.grid=_n; p.xlabel=_n; p.ylabel=_n; p.title=_n; p.legend=_n; p.suptitle=_n
    p.rcParams={}; pt.Patch=object; m.pyplot=p; m.patches=pt
    sys.modules["matplotlib"]=m; sys.modules["matplotlib.pyplot"]=p; sys.modules["matplotlib.patches"]=pt
sys.path.insert(0, ".")
import network, single_path_routing as spr

BASE_LOADS = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}

def build_pop():
    pop = {}
    for line, physics in network.TRAIN_PHYSICS.items():
        base = BASE_LOADS[line]
        pop[line] = {
            "train_1": 0, "train_2": 0,
            "platform_waiting": int(base["platform_waiting"]),
            "hall_people": int(base["hall_people"]),
            "transfer_people": int(base["transfer_people"]),
        }
    return pop

# ── NoPredictivePenalties (new) ──
print("Running NoPredictivePenalties + ScaleFix...")
t0 = time.time()
g1 = network.build_graph()
m1 = network.run_simulation_for_metrics_timed(g1, build_pop(), method=spr.OUR_NO_PREDICTIVE_PENALTIES_METHOD)
t1 = time.time() - t0

# ── Baseline (original) ──
print("Running Baseline AdaptiveSingleNextHop...")
t0 = time.time()
g2 = network.build_graph()
m2 = network.run_simulation_for_metrics_timed(g2, build_pop(), method=network.OUR_SINGLE_PATH_METHOD)
t2 = time.time() - t0

# ── Results ──
print()
print("=" * 70)
print(f"{'Metric':<30s} {'NoPredictive':>15s} {'Baseline':>15s}")
print("-" * 70)

for key in ["time", "queueing_time", "congestion_exposure_time",
            "avg_speed", "wall_clock_runtime_s"]:
    v1 = m1.get(key, "?")
    v2 = m2.get(key, "?")
    if isinstance(v1, (int, float)) and v1 != "?":
        print(f"{key:<30s} {v1:15.1f} {v2:15.1f}")
    else:
        print(f"{key:<30s} {str(v1):>15s} {str(v2):>15s}")

# L2 exit distribution
print()
print(f"{'Exit':<12s} {'NoPredictive':>12s} {'Baseline':>12s} {'Pathfinder':>12s}")
print("-" * 50)
pf = {"Exit_L2_2": 216, "Exit_L2_3": 365, "Exit_L2_4": 105, "Exit_L2_6": 111}
eu1 = m1.get("exit_usage", {})
eu2 = m2.get("exit_usage", {})
for ex in ["Exit_L2_2", "Exit_L2_3", "Exit_L2_4", "Exit_L2_6"]:
    print(f"{ex:<12s} {eu1.get(ex,0):12.0f} {eu2.get(ex,0):12.0f} {pf[ex]:12.0f}")

print(f"\nWall clock: NoPred={t1:.1f}s  Baseline={t2:.1f}s")
