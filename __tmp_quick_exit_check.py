"""Quick single-run exit distribution check vs Pathfinder target."""
import importlib.util
import sys
import types

def _install_noop_matplotlib_if_missing():
    if importlib.util.find_spec("matplotlib") is not None:
        return
    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    patches = types.ModuleType("matplotlib.patches")
    def _noop(*args, **kwargs):
        return None
    pyplot.figure = _noop
    pyplot.subplots = lambda *args, **kwargs: (None, None)
    pyplot.plot = _noop
    pyplot.bar = _noop
    pyplot.savefig = _noop
    pyplot.close = _noop
    pyplot.tight_layout = _noop
    pyplot.grid = _noop
    pyplot.xlabel = _noop
    pyplot.ylabel = _noop
    pyplot.title = _noop
    pyplot.legend = _noop
    pyplot.suptitle = _noop
    pyplot.rcParams = {}
    patches.Patch = object
    matplotlib.pyplot = pyplot
    matplotlib.patches = patches
    sys.modules["matplotlib"] = matplotlib
    sys.modules["matplotlib.pyplot"] = pyplot
    sys.modules["matplotlib.patches"] = patches

_install_noop_matplotlib_if_missing()
sys.path.insert(0, ".")

import network
import single_path_routing as spr

BASE_LOADS = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}

PATHFINDER_TARGET = {
    "Exit_L18_12": 382, "Exit_L18_13": 44, "Exit_L18_17": 26,
    "Exit_L7_7": 394, "Exit_L7_8/9": 136,
    "Exit_L2_6": 111, "Exit_L2_2": 216, "Exit_L2_3": 365, "Exit_L2_4": 105,
    "Exit_L16_10": 53, "Exit_L16_11": 354,
    "Exit_Maglev_18": 0, "Exit_Maglev_19": 0, "Exit_Maglev_20": 0, "Exit_Maglev_21": 1,
}

print("Current weights:")
for attr in [
    "OUR_GATE_QUEUE_WEIGHT", "OUR_GATE_SOURCE_RELEASE_WEIGHT",
    "OUR_GATE_SERVICE_RATE_WEIGHT", "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT",
    "OUR_PATH_EXIT_PRESSURE_WEIGHT", "OUR_DENSITY_MODERATE_FACTOR",
    "OUR_DENSITY_SEVERE_SURCHARGE", "OUR_GATE_OVERLOAD_FACTOR",
    "OUR_SERVICE_WAIT_TIME_WEIGHT",
]:
    print(f"  {attr} = {getattr(spr, attr)}")

# Build population (Mode 1: no train loads)
pop = {}
total = 0
for line, physics in network.TRAIN_PHYSICS.items():
    base = BASE_LOADS[line]
    pop[line] = {
        "train_1": 0, "train_2": 0,
        "platform_waiting": int(base["platform_waiting"]),
        "hall_people": int(base["hall_people"]),
        "transfer_people": int(base["transfer_people"]),
    }
    total += sum(pop[line].values())

print(f"\nRunning AdaptiveSingleNextHop Mode 1 (total={total})...")
graph = network.build_graph()
metrics = network.run_simulation_for_metrics_timed(graph, pop, method=network.OUR_SINGLE_PATH_METHOD)
exit_usage = metrics.get("exit_usage", {})

print(f"\n{'Exit':<20s} {'Target':>7s} {'Actual':>7s} {'Diff':>8s} {'Status':>8s}")
print("-" * 55)
mae_sum = 0
worst = []
for exit_name in PATHFINDER_TARGET:
    target = PATHFINDER_TARGET[exit_name]
    actual = exit_usage.get(exit_name, 0)
    diff = actual - target
    mae_sum += abs(diff)
    worst.append((exit_name, diff, target, actual))
    bar = "OVER " if diff > 0 else ("UNDER" if diff < 0 else " OK  ")
    print(f"  {exit_name:<20s} {target:7.0f} {actual:7.0f} {diff:+8.0f}  {bar}")

print(f"\nMAE = {mae_sum / len(PATHFINDER_TARGET):.1f}")
print(f"Worst 5 deviations:")
worst.sort(key=lambda x: abs(x[1]), reverse=True)
for name, diff, target, actual in worst[:5]:
    print(f"  {name:<20s} diff={diff:+6.0f}  target={target}  actual={actual}")
