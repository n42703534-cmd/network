"""Step 1: Bare algorithm (NoPredictivePenalties + ScaleFix) vs Pathfinder comparison."""
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
from collections import defaultdict

# ── Pathfinder baseline data ──────────────────────────────────────────
PF = {
    "mode1": {
        "name": "Mode 1 (2,187人)",
        "total": 2187,
        "evac_max_s": 366.3,
        "evac_avg_s": 114.3,
        "travel_avg_m": 89.0,
        "exits": {
            "Exit_L2_2": 216, "Exit_L2_3": 365, "Exit_L2_4": 105, "Exit_L2_6": 111,
            "Exit_L7_7": 394, "Exit_L7_8/9": 136,
            "Exit_L16_10": 53, "Exit_L16_11": 328+26,
            "Exit_L18_12": 382, "Exit_L18_13": 44, "Exit_L18_17": 26,
            "Exit_Maglev_18": 0, "Exit_Maglev_19": 0, "Exit_Maglev_20": 0, "Exit_Maglev_21": 1,
        }
    },
    "mode4": {
        "name": "Mode 4 (17,905人)",
        "total": 17905,
        "evac_max_s": 1411.4,
        "evac_avg_s": 416.3,
        "travel_avg_m": 140.4,
        "exits": {
            "Exit_L2_2": 1710, "Exit_L2_3": 2536, "Exit_L2_4": 802, "Exit_L2_6": 769,
            "Exit_L7_7": 2066, "Exit_L7_8/9": 893,
            "Exit_L16_10": 452, "Exit_L16_11": 639+1821,
            "Exit_L18_12": 1891, "Exit_L18_13": 763, "Exit_L18_17": 1098,
            "Exit_Maglev_18": 481, "Exit_Maglev_19": 822, "Exit_Maglev_20": 261, "Exit_Maglev_21": 901,
        }
    }
}

# ── Population loads ───────────────────────────────────────────────────
BASE_LOADS_MODE1 = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}
BASE_LOADS_MODE4 = {
    "L2": {"platform_waiting": 1888, "hall_people": 2800, "transfer_people": 4208},
    "L7": {"platform_waiting": 1752, "hall_people": 896, "transfer_people": 1352},
    "L16": {"platform_waiting": 336, "hall_people": 120, "transfer_people": 216},
    "L18": {"platform_waiting": 1424, "hall_people": 1000, "transfer_people": 1504},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 409},
}

ALL_EXITS = ["Exit_L2_2","Exit_L2_3","Exit_L2_4","Exit_L2_6",
             "Exit_L7_7","Exit_L7_8/9",
             "Exit_L16_10","Exit_L16_11",
             "Exit_L18_12","Exit_L18_13","Exit_L18_17",
             "Exit_Maglev_18","Exit_Maglev_19","Exit_Maglev_20","Exit_Maglev_21"]

def build_pop(base):
    pop = {}
    for line, physics in network.TRAIN_PHYSICS.items():
        b = base[line]
        pop[line] = {"train_1": 0, "train_2": 0,
                     "platform_waiting": int(b["platform_waiting"]),
                     "hall_people": int(b["hall_people"]),
                     "transfer_people": int(b["transfer_people"])}
    return pop

def run_one(label, base, method):
    print(f"  Running {label}...", end=" ", flush=True)
    t0 = time.time()
    g = network.build_graph()
    m = network.run_simulation_for_metrics_timed(g, build_pop(base), method=method)
    elapsed = time.time() - t0
    print(f"{elapsed:.0f}s")
    return m, elapsed

# ── Run ────────────────────────────────────────────────────────────────
METHOD = spr.OUR_NO_PREDICTIVE_PENALTIES_METHOD  # bare algorithm

print("=" * 70)
print("STEP 1: Bare Algorithm (NoPredictivePenalties + ScaleFix)")
print("=" * 70)

m1, t1 = run_one("Mode1", BASE_LOADS_MODE1, METHOD)
m4, t4 = run_one("Mode4", BASE_LOADS_MODE4, METHOD)

# ── Report ─────────────────────────────────────────────────────────────
for mode_key, pf_data, metrics in [("mode1", PF["mode1"], m1), ("mode4", PF["mode4"], m4)]:
    pf = pf_data
    eu = metrics.get("exit_usage", {})
    evac_time = metrics.get("time", 0)

    print(f"\n{'='*70}")
    print(f"  {pf['name']}")
    print(f"{'='*70}")
    print(f"  {'Metric':<25s} {'Our Algorithm':>15s} {'Pathfinder':>15s}")
    print(f"  {'-'*55}")
    print(f"  {'Evacuation time (max,s)':<25s} {evac_time:15.1f} {pf['evac_max_s']:15.1f}")

    print(f"\n  {'Exit Distribution':}")
    print(f"  {'Exit':<16s} {'Our':>8s} {'PF':>8s} {'Diff':>8s}")
    print(f"  {'-'*40}")
    for ex in ALL_EXITS:
        our_val = eu.get(ex, 0)
        pf_val = pf["exits"].get(ex, 0)
        diff = our_val - pf_val
        print(f"  {ex:<16s} {our_val:8.0f} {pf_val:8.0f} {diff:+8.0f}")

    # Weighted MAE
    total_pf = sum(pf["exits"].values())
    mae = sum(abs(eu.get(ex, 0) - pf["exits"].get(ex, 0)) for ex in ALL_EXITS) / len(ALL_EXITS)
    wmae = sum(abs(eu.get(ex, 0) - pf["exits"].get(ex, 0)) * pf["exits"].get(ex, 0) / total_pf
               for ex in ALL_EXITS if pf["exits"].get(ex, 0) > 0)
    print(f"\n  MAE: {mae:.1f}  Weighted MAE: {wmae:.1f}")

    # L2-only analysis
    l2_exits = ["Exit_L2_2","Exit_L2_3","Exit_L2_4","Exit_L2_6"]
    our_l2 = sum(eu.get(ex, 0) for ex in l2_exits)
    pf_l2 = sum(pf["exits"].get(ex, 0) for ex in l2_exits)
    print(f"\n  L2 Total: Our={our_l2:.0f}  PF={pf_l2:.0f}")

print(f"\nTotal wall clock: Mode1={t1:.0f}s Mode4={t4:.0f}s")
