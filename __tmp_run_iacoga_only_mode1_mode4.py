from __future__ import annotations

# Work around a local Python/Windows platform.system() hang observed during
# network.py import. This is isolated to this temporary runner.
import platform

platform.system = lambda: "Windows"

from datetime import datetime
from pathlib import Path
import time

import pandas as pd

import __tmp_run_group1_iacoga_mode1_mode4 as base


def main():
    run_dir = Path("outputs") / (
        "iacoga_only_mode1_mode4_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"RUN_DIR={run_dir.resolve()}", flush=True)
    print("METHOD=IACO_GA_2026 only", flush=True)
    print("NOTE=standalone comparison baseline; main program files are unchanged", flush=True)
    print(f"CAPACITY_FACTOR={base.network.PATHFINDER_CAPACITY_CALIBRATION_FACTOR}", flush=True)

    original_get_step_moves = base.network.get_step_moves

    def patched_get_step_moves(G, method, shortest_dists):
        return base.iacoga_get_step_moves(original_get_step_moves, G, method, shortest_dists)

    base.network.get_step_moves = patched_get_step_moves

    summary_rows = []
    line_rows = []
    exit_rows = []
    bottleneck_rows = []

    try:
        for mode, scenario_label in base.SCENARIOS.items():
            pop, total_people = base.build_pop(mode)
            print(f"\nSCENARIO mode={mode} label={scenario_label} total={total_people}", flush=True)
            print(f"START {scenario_label} IACO_GA_2026", flush=True)
            graph = base.network.build_graph()
            start = time.perf_counter()
            metrics = base.network.run_simulation_for_metrics(graph, pop, method=base.IACOGA_METHOD)
            metrics["wall_clock_runtime_s"] = time.perf_counter() - start
            row = base._summary_row(metrics, mode, scenario_label, total_people, "IACO_GA_2026")
            summary_rows.append(row)
            print(
                f"DONE {scenario_label} IACO_GA_2026 "
                f"time={row['time']:.1f}s "
                f"avg_tt={row['avg_travel_time']:.2f}s "
                f"queue={row['queueing_time']:.1f} "
                f"moderate={row['moderate_congestion_exposure_time']:.1f} "
                f"severe={row['severe_congestion_exposure_time']:.1f} "
                f"peak_index={row['peak_congestion_index']:.3f} "
                f"wall={row['wall_clock_runtime_s']:.2f}s",
                flush=True,
            )

            pd.DataFrame(summary_rows).to_csv(
                run_dir / "iacoga_only_method_summary_partial.csv",
                index=False,
                encoding="utf-8-sig",
            )

            for line in base.network.TRAIN_PHYSICS:
                line_rows.append(
                    {
                        "scenario_mode": mode,
                        "scenario_label": scenario_label,
                        "total_people": total_people,
                        "method": "IACO_GA_2026",
                        "line": line,
                        "clearance_time": (
                            metrics["clearance_times_by_line"].get(line)
                            if metrics["clearance_times_by_line"].get(line) is not None
                            else metrics["time"]
                        ),
                        "core_clearance_time": metrics.get("clearance_times_by_line_core", {}).get(line),
                        "transfer_clearance_time": metrics.get("clearance_times_by_line_transfer", {}).get(line),
                        "moderate_congestion_exposure_time": metrics["congestion_exposure_by_line"].get(line, 0.0),
                        "severe_congestion_exposure_time": metrics["severe_congestion_exposure_by_line"].get(line, 0.0),
                    }
                )

            for exit_name, amount in sorted(metrics.get("exit_usage", {}).items()):
                if amount <= 0:
                    continue
                exit_rows.append(
                    {
                        "scenario_mode": mode,
                        "scenario_label": scenario_label,
                        "total_people": total_people,
                        "method": "IACO_GA_2026",
                        "exit": exit_name,
                        "evacuated_people": amount,
                        "share": amount / total_people if total_people else 0.0,
                    }
                )

            bottleneck_rows.extend(
                base._top_bottleneck_rows(metrics, mode, scenario_label, total_people, "IACO_GA_2026")
            )

    finally:
        base.network.get_step_moves = original_get_step_moves

    pd.DataFrame(summary_rows).to_csv(
        run_dir / "iacoga_only_method_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(line_rows).to_csv(
        run_dir / "iacoga_only_line_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(exit_rows).to_csv(
        run_dir / "iacoga_only_exit_usage.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(bottleneck_rows).to_csv(
        run_dir / "iacoga_only_top_bottlenecks.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(f"\nSAVED {run_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
