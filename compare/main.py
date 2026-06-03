from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
import types
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"


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


def _bootstrap_project_imports() -> None:
    sys.path.insert(0, str(ROOT))
    vendored = ROOT / "__vendor_site_packages"
    if vendored.exists():
        sys.path.insert(0, str(vendored))
    _install_noop_matplotlib_if_missing()


_bootstrap_project_imports()

import network  # noqa: E402


ALGORITHM_LABEL = "AdaptiveSingleNextHop"

BASE_LOADS = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}

SCENARIOS = {
    "1": {"mode": 1, "label": "mode1_regular_emergency", "name": "mode1 常规突发"},
    "4": {"mode": 4, "label": "mode4_bidirectional_full_train", "name": "mode4 双向满载"},
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

BASE_WEIGHTS = {name: getattr(network.spr, name) for name in WEIGHT_ATTRS}

PROFILES = {
    "1": {
        "label": "PathfinderCompatible_TimeOriented",
        "name": "Pathfinder-compatible / time-oriented",
        "description": "降低拥堵、下游释放和出口压力惩罚，使出口分配更接近静态最短路。",
        "weights": {
            "OUR_GATE_QUEUE_WEIGHT": 1.0,
            "OUR_GATE_SOURCE_RELEASE_WEIGHT": 0.03,
            "OUR_GATE_SERVICE_RATE_WEIGHT": 1.5,
            "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT": 0.08,
            "OUR_PATH_EXIT_PRESSURE_WEIGHT": 0.08,
            "OUR_DENSITY_MODERATE_FACTOR": 0.20,
            "OUR_DENSITY_SEVERE_SURCHARGE": 0.80,
            "OUR_GATE_OVERLOAD_FACTOR": 0.20,
            "OUR_SERVICE_WAIT_TIME_WEIGHT": 0.45,
        },
    },
    "2": {
        "label": "Balanced",
        "name": "Balanced",
        "description": "保持当前权重，兼顾时间、排队和拥堵暴露。",
        "weights": dict(BASE_WEIGHTS),
    },
    "3": {
        "label": "SafetyOriented",
        "name": "Safety-oriented",
        "description": "提高拥堵和瓶颈惩罚，优先降低高密度暴露和出口集中。",
        "weights": {
            "OUR_GATE_QUEUE_WEIGHT": 5.5,
            "OUR_GATE_SOURCE_RELEASE_WEIGHT": 0.28,
            "OUR_GATE_SERVICE_RATE_WEIGHT": 4.0,
            "OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT": 0.75,
            "OUR_PATH_EXIT_PRESSURE_WEIGHT": 0.90,
            "OUR_DENSITY_MODERATE_FACTOR": 1.00,
            "OUR_DENSITY_SEVERE_SURCHARGE": 4.00,
            "OUR_GATE_OVERLOAD_FACTOR": 1.00,
            "OUR_SERVICE_WAIT_TIME_WEIGHT": 1.60,
        },
    },
}


def choose_from_menu(title: str, options: dict[str, str], default: str) -> str:
    print()
    print(title)
    for key, text in options.items():
        print(f"  [{key}] {text}")
    while True:
        choice = input(f"请输入选项，直接回车默认 [{default}]: ").strip()
        if not choice:
            return default
        if choice in options:
            return choice
        print("输入无效，请重新输入。")


def selected_scenarios(choice: str) -> list[dict]:
    if choice == "all":
        return [SCENARIOS["1"], SCENARIOS["4"]]
    return [SCENARIOS[choice]]


def selected_profiles(choice: str) -> list[dict]:
    if choice == "all":
        return [PROFILES["1"], PROFILES["2"], PROFILES["3"]]
    return [PROFILES[choice]]


@contextmanager
def temporary_weight_profile(profile: dict):
    original = {name: getattr(network.spr, name) for name in WEIGHT_ATTRS}
    try:
        for name, value in profile["weights"].items():
            setattr(network.spr, name, value)
        yield
    finally:
        for name, value in original.items():
            setattr(network.spr, name, value)


def build_pop(mode: int) -> tuple[dict, int]:
    pop = {}
    total = 0
    for line, physics in network.TRAIN_PHYSICS.items():
        base = BASE_LOADS[line]
        train_total = int(round(network._train_total_people(physics)))
        if mode == 1:
            train_1, train_2 = 0, 0
        elif mode == 4:
            train_1, train_2 = train_total, train_total
        else:
            raise ValueError(f"Only mode1 and mode4 are supported, got mode={mode}")

        pop[line] = {
            "train_1": train_1,
            "train_2": train_2,
            "platform_waiting": int(base["platform_waiting"]),
            "hall_people": int(base["hall_people"]),
            "transfer_people": int(base["transfer_people"]),
        }
        total += sum(pop[line].values())
    return pop, total


def combo_output_dir(scenario: dict, profile: dict) -> Path:
    run_dir = OUTPUT_ROOT / scenario["label"] / profile["label"]
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def exit_hhi(exit_usage: dict) -> tuple[float, float, int]:
    total = sum(float(value) for value in exit_usage.values())
    if total <= 0:
        return 0.0, 0.0, 0
    shares = [float(value) / total for value in exit_usage.values() if float(value) > 0]
    return sum(share * share for share in shares), max(shares, default=0.0), len(shares)


def summary_row(scenario: dict, total_people: int, profile: dict, metrics: dict) -> dict:
    hhi, max_share, active_count = exit_hhi(metrics.get("exit_usage", {}))
    return {
        "scenario_mode": scenario["mode"],
        "scenario_label": scenario["label"],
        "total_people": total_people,
        "algorithm": ALGORITHM_LABEL,
        "guidance_mode": profile["label"],
        "guidance_description": profile["description"],
        "evacuation_time_s": metrics.get("time", 0.0),
        "avg_travel_time_s": metrics.get("avg_travel_time", 0.0),
        "queueing_time_person_s": metrics.get("queueing_time", 0.0),
        "moderate_congestion_exposure_person_s": metrics.get("congestion_exposure_time", 0.0),
        "severe_congestion_exposure_person_s": metrics.get("severe_congestion_exposure_time", 0.0),
        "peak_density_p_per_m2": metrics.get("peak_density", 0.0),
        "peak_congestion_index": metrics.get("peak_congestion_index", 0.0),
        "avg_speed_m_per_s": metrics.get("avg_speed", 0.0),
        "exit_hhi": hhi,
        "max_exit_share": max_share,
        "active_exit_count": active_count,
        "wall_clock_runtime_s": metrics.get("wall_clock_runtime_s", 0.0),
    }


def exit_rows(scenario: dict, profile: dict, metrics: dict) -> list[dict]:
    usage = metrics.get("exit_usage", {})
    total = sum(float(value) for value in usage.values())
    rows = []
    for exit_name, people in sorted(usage.items()):
        people = float(people)
        rows.append(
            {
                "scenario_mode": scenario["mode"],
                "scenario_label": scenario["label"],
                "algorithm": ALGORITHM_LABEL,
                "guidance_mode": profile["label"],
                "exit_name": exit_name,
                "people": people,
                "share": people / total if total > 0 else 0.0,
            }
        )
    return rows


def line_rows(scenario: dict, total_people: int, profile: dict, metrics: dict) -> list[dict]:
    rows = []
    for line in network.ALL_LINE_IDS:
        rows.append(
            {
                "scenario_mode": scenario["mode"],
                "scenario_label": scenario["label"],
                "total_people": total_people,
                "algorithm": ALGORITHM_LABEL,
                "guidance_mode": profile["label"],
                "line": line,
                "clearance_time_s": metrics.get("clearance_times_by_line", {}).get(line),
                "core_clearance_time_s": metrics.get("clearance_times_by_line_core", {}).get(line),
                "transfer_clearance_time_s": metrics.get("clearance_times_by_line_transfer", {}).get(line),
                "queueing_time_person_s": metrics.get("queueing_time_by_line", {}).get(line, 0.0),
                "moderate_congestion_exposure_person_s": metrics.get("congestion_exposure_by_line", {}).get(line, 0.0),
                "severe_congestion_exposure_person_s": metrics.get("severe_congestion_exposure_by_line", {}).get(line, 0.0),
            }
        )
    return rows


def bottleneck_rows(scenario: dict, profile: dict, metrics: dict, top_k: int = 20) -> list[dict]:
    node_stats = metrics.get("node_stats", {})
    ranked = sorted(
        node_stats.items(),
        key=lambda item: (
            float(item[1].get("queue_seconds", 0.0)),
            float(item[1].get("congestion_seconds", 0.0)),
            float(item[1].get("peak_congestion_index", 0.0)),
        ),
        reverse=True,
    )
    rows = []
    for rank, (node, stat) in enumerate(ranked[:top_k], start=1):
        rows.append(
            {
                "scenario_mode": scenario["mode"],
                "scenario_label": scenario["label"],
                "algorithm": ALGORITHM_LABEL,
                "guidance_mode": profile["label"],
                "rank": rank,
                "node": node,
                "queue_seconds_person_s": stat.get("queue_seconds", 0.0),
                "congestion_seconds_person_s": stat.get("congestion_seconds", 0.0),
                "peak_people": stat.get("peak_people", 0.0),
                "peak_density_p_per_m2": stat.get("peak_density", 0.0),
                "peak_load_ratio": stat.get("peak_load_ratio", 0.0),
                "peak_congestion_index": stat.get("peak_congestion_index", 0.0),
                "congestion_measure_type": stat.get("congestion_measure_type", ""),
            }
        )
    return rows


def run_once(scenario: dict, profile: dict) -> tuple[dict, list[dict], list[dict], list[dict]]:
    pop, total_people = build_pop(scenario["mode"])
    print()
    print(f"开始运行: {scenario['name']} | {ALGORITHM_LABEL} | {profile['name']} | 总人数 {total_people}")
    graph = network.build_graph()
    with temporary_weight_profile(profile):
        metrics = network.run_simulation_for_metrics_timed(graph, pop, method=network.OUR_SINGLE_PATH_METHOD)
    row = summary_row(scenario, total_people, profile, metrics)
    print(
        f"完成: 疏散 {row['evacuation_time_s']:.1f}s | "
        f"排队 {row['queueing_time_person_s']:.1f} person-s | "
        f"中度拥堵 {row['moderate_congestion_exposure_person_s']:.1f} person-s | "
        f"重度拥堵 {row['severe_congestion_exposure_person_s']:.1f} person-s"
    )
    return (
        row,
        exit_rows(scenario, profile, metrics),
        line_rows(scenario, total_people, profile, metrics),
        bottleneck_rows(scenario, profile, metrics),
    )


def write_combo_outputs(
    run_dir: Path,
    summary: dict,
    exits: list[dict],
    lines: list[dict],
    bottlenecks: list[dict],
) -> None:
    write_csv(
        run_dir / "summary_metrics.csv",
        [summary],
        [
            "scenario_mode",
            "scenario_label",
            "total_people",
            "algorithm",
            "guidance_mode",
            "guidance_description",
            "evacuation_time_s",
            "avg_travel_time_s",
            "queueing_time_person_s",
            "moderate_congestion_exposure_person_s",
            "severe_congestion_exposure_person_s",
            "peak_density_p_per_m2",
            "peak_congestion_index",
            "avg_speed_m_per_s",
            "exit_hhi",
            "max_exit_share",
            "active_exit_count",
            "wall_clock_runtime_s",
        ],
    )
    write_csv(
        run_dir / "exit_usage.csv",
        exits,
        ["scenario_mode", "scenario_label", "algorithm", "guidance_mode", "exit_name", "people", "share"],
    )
    write_csv(
        run_dir / "line_metrics.csv",
        lines,
        [
            "scenario_mode",
            "scenario_label",
            "total_people",
            "algorithm",
            "guidance_mode",
            "line",
            "clearance_time_s",
            "core_clearance_time_s",
            "transfer_clearance_time_s",
            "queueing_time_person_s",
            "moderate_congestion_exposure_person_s",
            "severe_congestion_exposure_person_s",
        ],
    )
    write_csv(
        run_dir / "top_bottlenecks.csv",
        bottlenecks,
        [
            "scenario_mode",
            "scenario_label",
            "algorithm",
            "guidance_mode",
            "rank",
            "node",
            "queue_seconds_person_s",
            "congestion_seconds_person_s",
            "peak_people",
            "peak_density_p_per_m2",
            "peak_load_ratio",
            "peak_congestion_index",
            "congestion_measure_type",
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AdaptiveSingleNextHop mode1/mode4 weight-profile comparison without charts."
    )
    parser.add_argument("--scenario", choices=["1", "4", "all"], help="1=mode1, 4=mode4, all=both")
    parser.add_argument(
        "--profile",
        choices=["1", "2", "3", "all"],
        help="1=Pathfinder-compatible/time-oriented, 2=Balanced, 3=Safety-oriented, all=all profiles",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenario_choice = args.scenario or choose_from_menu(
        "请选择场景",
        {
            "1": "mode1 常规突发",
            "4": "mode4 双向满载",
            "all": "两个场景都跑",
        },
        default="1",
    )
    profile_choice = args.profile or choose_from_menu(
        "请选择权重模式（算法固定为 AdaptiveSingleNextHop）",
        {
            "1": "Pathfinder-compatible / time-oriented",
            "2": "Balanced",
            "3": "Safety-oriented",
            "all": "三种权重模式都跑",
        },
        default="2",
    )

    written_dirs = []
    for scenario in selected_scenarios(scenario_choice):
        for profile in selected_profiles(profile_choice):
            summary, exits, lines, bottlenecks = run_once(scenario, profile)
            run_dir = combo_output_dir(scenario, profile)
            write_combo_outputs(run_dir, summary, exits, lines, bottlenecks)
            written_dirs.append(run_dir)
            print(f"已保存: {run_dir}")

    print()
    print("已输出目录:")
    for run_dir in written_dirs:
        print(f"  {run_dir}")


if __name__ == "__main__":
    main()
