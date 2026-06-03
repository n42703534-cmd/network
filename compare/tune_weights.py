"""
Automated weight tuning: compare AdaptiveSingleNextHop exit distribution
against Pathfinder's Mode 1 "Goto Any Exit" baseline.

Pathfinder target is static — we run profiles sequentially and rank by fit.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
import types
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs" / "tuning"


def _install_noop_matplotlib_if_missing() -> None:
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


def _bootstrap() -> None:
    sys.path.insert(0, str(ROOT))
    vendored = ROOT / "__vendor_site_packages"
    if vendored.exists():
        sys.path.insert(0, str(vendored))
    _install_noop_matplotlib_if_missing()


_bootstrap()
import network  # noqa: E402
import single_path_routing as spr  # noqa: E402

ALGORITHM = network.OUR_SINGLE_PATH_METHOD

BASE_LOADS = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}

# Pathfinder "Goto Any Exit" Mode 1 baseline (static target)
PATHFINDER_TARGET: dict[str, float] = {
    "Exit_L18_12": 382,
    "Exit_L18_13": 44,
    "Exit_L18_17": 26,
    "Exit_L7_7": 394,
    "Exit_L7_8/9": 136,
    "Exit_L2_6": 111,
    "Exit_L2_2": 216,
    "Exit_L2_3": 365,
    "Exit_L2_4": 105,
    "Exit_L16_10": 53,
    "Exit_L16_11": 354,
    "Exit_Maglev_18": 0,
    "Exit_Maglev_19": 0,
    "Exit_Maglev_20": 0,
    "Exit_Maglev_21": 1,
}

WEIGHT_ATTRS = [
    "OUR_GATE_QUEUE_WEIGHT",
    "OUR_GATE_SOURCE_RELEASE_WEIGHT",
    "OUR_GATE_SERVICE_RATE_WEIGHT",
    "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT",
    "OUR_PATH_EXIT_PRESSURE_WEIGHT",
    "OUR_DENSITY_MODERATE_FACTOR",
    "OUR_DENSITY_SEVERE_SURCHARGE",
    "OUR_GATE_OVERLOAD_FACTOR",
    "OUR_SERVICE_WAIT_TIME_WEIGHT",
]

BASE_WEIGHTS = {name: getattr(spr, name) for name in WEIGHT_ATTRS}

TOTAL_PEOPLE = 2187


def build_pop() -> tuple[dict, int]:
    pop = {}
    total = 0
    for line, physics in network.TRAIN_PHYSICS.items():
        base = BASE_LOADS[line]
        pop[line] = {
            "train_1": 0,
            "train_2": 0,
            "platform_waiting": int(base["platform_waiting"]),
            "hall_people": int(base["hall_people"]),
            "transfer_people": int(base["transfer_people"]),
        }
        total += sum(pop[line].values())
    return pop, total


@contextmanager
def temporary_weights(weights: dict):
    original = {name: getattr(spr, name) for name in WEIGHT_ATTRS}
    try:
        for name, value in weights.items():
            setattr(spr, name, value)
        yield
    finally:
        for name, value in original.items():
            setattr(spr, name, value)


def compute_error(exit_usage: dict) -> dict:
    mae_sum = 0.0
    rmse_sum = 0.0
    n = 0
    per_exit = {}
    for exit_name, target in PATHFINDER_TARGET.items():
        actual = float(exit_usage.get(exit_name, 0))
        diff = actual - target
        abs_diff = abs(diff)
        mae_sum += abs_diff
        rmse_sum += diff * diff
        per_exit[exit_name] = {"target": target, "actual": actual, "diff": diff, "abs_diff": abs_diff}
        n += 1
    mae = mae_sum / n
    rmse = (rmse_sum / n) ** 0.5

    # Top-3 worst mismatches
    worst = sorted(per_exit.items(), key=lambda x: x[1]["abs_diff"], reverse=True)[:3]

    return {"mae": mae, "rmse": rmse, "per_exit": per_exit, "worst": worst}


def format_error_report(profile_name: str, error: dict, metrics: dict) -> str:
    lines = [f"\n{'='*70}", f"  {profile_name}", f"{'='*70}"]
    lines.append(f"  Evac Time: {metrics.get('time', 0):.0f}s  |  MAE: {error['mae']:.1f}  |  RMSE: {error['rmse']:.1f}")
    lines.append(f"  Top-3 worst mismatches:")
    for exit_name, d in error["worst"]:
        direction = "OVER" if d["diff"] > 0 else "UNDER"
        lines.append(
            f"    {exit_name:20s}  target={d['target']:5.0f}  actual={d['actual']:5.0f}  "
            f"diff={d['diff']:+6.0f}  [{direction}]"
        )
    return "\n".join(lines)


def run_profile(name: str, weights: dict) -> tuple[dict, dict]:
    pop, total = build_pop()
    print(f"\n>>> {name} (total={total})")
    graph = network.build_graph()
    with temporary_weights(weights):
        metrics = network.run_simulation_for_metrics_timed(graph, pop, method=ALGORITHM)
    exit_usage = metrics.get("exit_usage", {})
    error = compute_error(exit_usage)
    print(f"    evac={metrics.get('time',0):.0f}s  mae={error['mae']:.1f}  rmse={error['rmse']:.1f}")
    return error, metrics


def write_tuning_csv(run_dir: Path, all_results: list[dict]) -> None:
    path = run_dir / "tuning_results.csv"
    fieldnames = [
        "rank", "profile", "mae", "rmse", "evac_time_s", "avg_travel_time_s",
        "queueing_time_person_s", "moderate_congestion_person_s",
        "severe_congestion_person_s", "exit_hhi", "active_exit_count",
    ]
    fieldnames += [f"exit_{e}_diff" for e in PATHFINDER_TARGET]
    fieldnames += WEIGHT_ATTRS
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nTuning results saved to: {path}")


def write_per_exit_csv(run_dir: Path, best_profile: str, error: dict) -> None:
    path = run_dir / "best_profile_exit_comparison.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["exit_name", "pathfinder_target", "our_actual", "diff", "abs_diff"])
        writer.writeheader()
        for exit_name in PATHFINDER_TARGET:
            d = error["per_exit"][exit_name]
            writer.writerow({
                "exit_name": exit_name,
                "pathfinder_target": d["target"],
                "our_actual": d["actual"],
                "diff": d["diff"],
                "abs_diff": d["abs_diff"],
            })
    print(f"Exit comparison saved to: {path}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_ROOT / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    profiles = [
        # ============================================================
        # Profile E0: Ultra-Extreme — everything near zero, pure distance
        # ============================================================
        {
            "name": "E0_UltraExtreme_PureDistance",
            "weights": {
                "OUR_GATE_QUEUE_WEIGHT": 0.05,
                "OUR_GATE_SOURCE_RELEASE_WEIGHT": 0.005,
                "OUR_GATE_SERVICE_RATE_WEIGHT": 0.3,
                "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT": 0.005,
                "OUR_PATH_EXIT_PRESSURE_WEIGHT": 0.20,
                "OUR_DENSITY_MODERATE_FACTOR": 0.02,
                "OUR_DENSITY_SEVERE_SURCHARGE": 0.05,
                "OUR_GATE_OVERLOAD_FACTOR": 0.02,
                "OUR_SERVICE_WAIT_TIME_WEIGHT": 0.05,
            },
        },
        # ============================================================
        # Profile E1: Extreme — minimal penalties, moderate exit pressure
        # ============================================================
        {
            "name": "E1_Extreme_MinimalPenalties",
            "weights": {
                "OUR_GATE_QUEUE_WEIGHT": 0.1,
                "OUR_GATE_SOURCE_RELEASE_WEIGHT": 0.01,
                "OUR_GATE_SERVICE_RATE_WEIGHT": 0.5,
                "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT": 0.01,
                "OUR_PATH_EXIT_PRESSURE_WEIGHT": 0.35,
                "OUR_DENSITY_MODERATE_FACTOR": 0.05,
                "OUR_DENSITY_SEVERE_SURCHARGE": 0.1,
                "OUR_GATE_OVERLOAD_FACTOR": 0.05,
                "OUR_SERVICE_WAIT_TIME_WEIGHT": 0.1,
            },
        },
        # ============================================================
        # Profile E2: High exit pressure to differentiate major/minor exits
        # ============================================================
        {
            "name": "E2_HighExitPressure",
            "weights": {
                "OUR_GATE_QUEUE_WEIGHT": 0.1,
                "OUR_GATE_SOURCE_RELEASE_WEIGHT": 0.01,
                "OUR_GATE_SERVICE_RATE_WEIGHT": 0.5,
                "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT": 0.01,
                "OUR_PATH_EXIT_PRESSURE_WEIGHT": 0.60,
                "OUR_DENSITY_MODERATE_FACTOR": 0.05,
                "OUR_DENSITY_SEVERE_SURCHARGE": 0.1,
                "OUR_GATE_OVERLOAD_FACTOR": 0.05,
                "OUR_SERVICE_WAIT_TIME_WEIGHT": 0.1,
            },
        },
        # ============================================================
        # Profile E3: Very high exit pressure
        # ============================================================
        {
            "name": "E3_VeryHighExitPressure",
            "weights": {
                "OUR_GATE_QUEUE_WEIGHT": 0.1,
                "OUR_GATE_SOURCE_RELEASE_WEIGHT": 0.01,
                "OUR_GATE_SERVICE_RATE_WEIGHT": 0.5,
                "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT": 0.01,
                "OUR_PATH_EXIT_PRESSURE_WEIGHT": 0.85,
                "OUR_DENSITY_MODERATE_FACTOR": 0.05,
                "OUR_DENSITY_SEVERE_SURCHARGE": 0.1,
                "OUR_GATE_OVERLOAD_FACTOR": 0.05,
                "OUR_SERVICE_WAIT_TIME_WEIGHT": 0.1,
            },
        },
        # ============================================================
        # Profile E4: High exit pressure + subtle density awareness
        # ============================================================
        {
            "name": "E4_HighExitPressure_LightDensity",
            "weights": {
                "OUR_GATE_QUEUE_WEIGHT": 0.2,
                "OUR_GATE_SOURCE_RELEASE_WEIGHT": 0.02,
                "OUR_GATE_SERVICE_RATE_WEIGHT": 0.6,
                "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT": 0.02,
                "OUR_PATH_EXIT_PRESSURE_WEIGHT": 0.70,
                "OUR_DENSITY_MODERATE_FACTOR": 0.15,
                "OUR_DENSITY_SEVERE_SURCHARGE": 0.30,
                "OUR_GATE_OVERLOAD_FACTOR": 0.10,
                "OUR_SERVICE_WAIT_TIME_WEIGHT": 0.15,
            },
        },
        # ============================================================
        # Profile E5: Balanced-light (reference — half of original weights)
        # ============================================================
        {
            "name": "E5_HalfOriginal",
            "weights": {
                "OUR_GATE_QUEUE_WEIGHT": 1.75,
                "OUR_GATE_SOURCE_RELEASE_WEIGHT": 0.09,
                "OUR_GATE_SERVICE_RATE_WEIGHT": 1.5,
                "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT": 0.22,
                "OUR_PATH_EXIT_PRESSURE_WEIGHT": 0.55,
                "OUR_DENSITY_MODERATE_FACTOR": 0.32,
                "OUR_DENSITY_SEVERE_SURCHARGE": 1.25,
                "OUR_GATE_OVERLOAD_FACTOR": 0.30,
                "OUR_SERVICE_WAIT_TIME_WEIGHT": 0.55,
            },
        },
    ]

    # Also include the already-run PathfinderCompatible_TimeOriented for reference
    pf_compat_weights = {
        "OUR_GATE_QUEUE_WEIGHT": 1.0,
        "OUR_GATE_SOURCE_RELEASE_WEIGHT": 0.03,
        "OUR_GATE_SERVICE_RATE_WEIGHT": 1.5,
        "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT": 0.08,
        "OUR_PATH_EXIT_PRESSURE_WEIGHT": 0.08,
        "OUR_DENSITY_MODERATE_FACTOR": 0.20,
        "OUR_DENSITY_SEVERE_SURCHARGE": 0.80,
        "OUR_GATE_OVERLOAD_FACTOR": 0.20,
        "OUR_SERVICE_WAIT_TIME_WEIGHT": 0.45,
    }
    profiles.insert(0, {"name": "P0_PathfinderCompat_Existing", "weights": pf_compat_weights})

    print(f"Running {len(profiles)} weight profiles for Mode 1...")
    print(f"Target: Pathfinder Goto Any Exit (2187 people)")
    print(f"Output dir: {run_dir}")

    all_results = []
    best_error = None
    best_profile_name = ""

    for i, profile in enumerate(profiles):
        name = profile["name"]
        weights = profile["weights"]
        error, metrics = run_profile(name, weights)

        result = {
            "rank": 0,
            "profile": name,
            "mae": error["mae"],
            "rmse": error["rmse"],
            "evac_time_s": metrics.get("time", 0),
            "avg_travel_time_s": metrics.get("avg_travel_time", 0),
            "queueing_time_person_s": metrics.get("queueing_time", 0),
            "moderate_congestion_person_s": metrics.get("congestion_exposure_time", 0),
            "severe_congestion_person_s": metrics.get("severe_congestion_exposure_time", 0),
            "exit_hhi": sum(
                (float(v) / TOTAL_PEOPLE) ** 2 for v in metrics.get("exit_usage", {}).values() if float(v) > 0
            ),
            "active_exit_count": len([v for v in metrics.get("exit_usage", {}).values() if float(v) > 0]),
        }
        for exit_name in PATHFINDER_TARGET:
            result[f"exit_{exit_name}_diff"] = error["per_exit"].get(exit_name, {}).get("diff", 0)
        for attr in WEIGHT_ATTRS:
            result[attr] = weights[attr]

        all_results.append(result)
        print(format_error_report(name, error, metrics))

        if best_error is None or error["mae"] < best_error["mae"]:
            best_error = error
            best_profile_name = name

    # Rank by MAE
    all_results.sort(key=lambda r: r["mae"])
    for i, r in enumerate(all_results):
        r["rank"] = i + 1

    print(f"\n{'='*70}")
    print(f"BEST PROFILE: {best_profile_name} (MAE={best_error['mae']:.1f}, RMSE={best_error['rmse']:.1f})")
    print(f"{'='*70}")

    # Print ranking
    print(f"\nRanking (by MAE):")
    for r in all_results:
        print(f"  #{r['rank']:2d}  {r['profile']:40s}  MAE={r['mae']:6.1f}  RMSE={r['rmse']:6.1f}  Evac={r['evac_time_s']:.0f}s")

    write_tuning_csv(run_dir, all_results)
    write_per_exit_csv(run_dir, best_profile_name, best_error)

    # Save best weights as a snippet
    best_weights = next(p["weights"] for p in profiles if p["name"] == best_profile_name)
    weights_path = run_dir / "best_weights.txt"
    with weights_path.open("w", encoding="utf-8") as f:
        for k, v in best_weights.items():
            f.write(f"{k} = {v}\n")
    print(f"Best weights saved to: {weights_path}")


if __name__ == "__main__":
    main()
