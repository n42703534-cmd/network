from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parent
CASE_RESULTS = ROOT / "15_single_path_case_results.csv"
LINE_SUMMARY = ROOT / "17_single_path_case_summary.csv"

OUT_SUMMARY_PNG = ROOT / "single_path_three_line_summary.png"
OUT_DELTA_PNG = ROOT / "single_path_three_line_delta.png"
OUT_REPORT_MD = ROOT / "single_path_three_line_report.md"

LINES = ["L2", "L7", "L18"]
METHODS = ["PaperImprovedAStar", "AntColony", "AdaptiveSingleNextHop"]
METHOD_LABELS = {
    "PaperImprovedAStar": "PaperImprovedAStar",
    "AntColony": "AntColony",
    "AdaptiveSingleNextHop": "AdaptiveSingleNextHop",
}
METHOD_COLORS = {
    "PaperImprovedAStar": "#9ecae1",
    "AntColony": "#74c476",
    "AdaptiveSingleNextHop": "#f4a582",
}

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Microsoft JhengHei"]
plt.rcParams["axes.unicode_minus"] = False


def fmt_num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_csv(CASE_RESULTS), pd.read_csv(LINE_SUMMARY)


def value(summary: pd.DataFrame, line: str, method: str, metric: str) -> float:
    row = summary[(summary["line"] == line) & (summary["method"] == method)]
    if row.empty:
        return float("nan")
    return float(row[metric].iloc[0])


def build_summary_chart(summary: pd.DataFrame) -> None:
    metrics = [
        ("mean_evacuation_time", "平均疏散时间 (s)"),
        ("mean_queueing_time", "平均排队时间 (person·s)"),
        ("mean_congestion_exposure", "平均拥挤暴露 (person·s)"),
        ("mean_avg_speed", "平均速度 (m/s)"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), dpi=200)
    axes = axes.ravel()
    x = list(range(len(LINES)))
    width = min(0.24, 0.8 / len(METHODS))

    for ax, (metric, title) in zip(axes, metrics):
        for idx, method in enumerate(METHODS):
            vals = [value(summary, line, method, metric) for line in LINES]
            offset = (idx - (len(METHODS) - 1) / 2) * width
            positions = [i + offset for i in x]
            ax.bar(
                positions,
                vals,
                width=width,
                color=METHOD_COLORS[method],
                label=METHOD_LABELS[method],
                edgecolor="black",
                linewidth=0.5,
            )
            for xpos, val in zip(positions, vals):
                ax.text(xpos, val, fmt_num(val), ha="center", va="bottom", fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels(LINES)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.2)

    axes[0].legend(loc="upper right", fontsize=9)
    fig.suptitle("三条线路的自适应引导算法层总览对比", fontsize=15, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT_SUMMARY_PNG, bbox_inches="tight")
    plt.close(fig)


def build_delta_chart(summary: pd.DataFrame) -> None:
    metrics = [
        ("mean_evacuation_time", "疏散时间差值 (s)"),
        ("mean_queueing_time", "排队时间差值 (person·s)"),
        ("mean_congestion_exposure", "拥挤暴露差值 (person·s)"),
        ("mean_avg_speed", "速度差值 (m/s)"),
    ]
    baselines = ["PaperImprovedAStar", "AntColony"]
    baseline_labels = {
        "PaperImprovedAStar": "Our - Paper",
        "AntColony": "Our - ACO",
    }
    baseline_colors = {
        "PaperImprovedAStar": "#4daf4a",
        "AntColony": "#377eb8",
    }

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), dpi=200)
    axes = axes.ravel()
    x = list(range(len(LINES)))
    width = 0.32

    for ax, (metric, title) in zip(axes, metrics):
        for idx, baseline in enumerate(baselines):
            deltas = [
                value(summary, line, "AdaptiveSingleNextHop", metric) - value(summary, line, baseline, metric)
                for line in LINES
            ]
            offset = (idx - 0.5) * width
            positions = [i + offset for i in x]
            ax.bar(
                positions,
                deltas,
                width=width,
                color=baseline_colors[baseline],
                label=baseline_labels[baseline],
                edgecolor="black",
                linewidth=0.5,
            )
            for xpos, val in zip(positions, deltas):
                ax.text(xpos, val, fmt_num(val), ha="center", va="bottom" if val >= 0 else "top", fontsize=8)
        ax.axhline(0, color="#444444", linewidth=1)
        ax.set_xticks(x)
        ax.set_xticklabels(LINES)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.2)

    axes[0].legend(loc="upper right", fontsize=9)
    fig.suptitle("AdaptiveSingleNextHop 相对 PaperImprovedAStar 与 AntColony 的差值", fontsize=15, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT_DELTA_PNG, bbox_inches="tight")
    plt.close(fig)


def case_table(cases: pd.DataFrame, line: str) -> str:
    rows = []
    for case_id in [f"{line}_C1", f"{line}_C2", f"{line}_C3", f"{line}_C4"]:
        case_rows = cases[cases["case_id"] == case_id]
        if case_rows.empty:
            continue
        origin = case_rows["origin"].iloc[0]
        time_parts = []
        exit_parts = []
        for method in METHODS:
            row = case_rows[case_rows["method"] == method]
            if row.empty:
                continue
            row = row.iloc[0]
            time_parts.append(f"{METHOD_LABELS[method]}={fmt_num(float(row['evacuation_time']), 0)}")
            exit_parts.append(f"{METHOD_LABELS[method]}={row['target_exit']}")
        rows.append(f"| {case_id} | {origin} | {'; '.join(exit_parts)} | {'; '.join(time_parts)} |")
    return "\n".join(
        [
            "| 案例 | 起点 | 目标出口 | 疏散时间 (s) |",
            "|---|---|---|---|",
            *rows,
        ]
    )


def build_report(cases: pd.DataFrame, summary: pd.DataFrame) -> None:
    report: list[str] = []
    report.append("# 三条代表线路的自适应引导算法层对比报告")
    report.append("")
    report.append("本文只比较自适应引导算法层，不讨论全站引导策略。新增 `AntColony` 作为第三类基准算法，与 `PaperImprovedAStar` 和 `AdaptiveSingleNextHop` 使用同一批起点、同一初始人数和同一评价指标。")
    report.append("")
    report.append("## 1. 实验设计")
    report.append("")
    report.append("- 三条线路：L2、L7、L18。")
    report.append("- 每条线路 4 个典型起点，共 12 个案例。")
    report.append("- 每个案例放置 100 人。")
    report.append("- 对比方法：`PaperImprovedAStar`、`AntColony`、`AdaptiveSingleNextHop`。")
    report.append("- 指标：路径长度、疏散时间、排队时间、拥挤暴露、平均速度。")
    report.append("")
    report.append("### 总览图")
    report.append("")
    report.append(f"![三条线路总览]({OUT_SUMMARY_PNG.as_posix()})")
    report.append("")
    report.append(f"![三条线路差值]({OUT_DELTA_PNG.as_posix()})")
    report.append("")
    report.append("### 线路级汇总")
    report.append("")
    report.append("| 线路 | 方法 | 平均路径长度 (m) | 平均疏散时间 (s) | 平均排队时间 (person·s) | 平均拥挤暴露 (person·s) | 平均速度 (m/s) |")
    report.append("|---|---|---:|---:|---:|---:|---:|")
    for line in LINES:
        for method in METHODS:
            report.append(
                f"| {line} | {METHOD_LABELS[method]} | "
                f"{fmt_num(value(summary, line, method, 'mean_path_length'))} | "
                f"{fmt_num(value(summary, line, method, 'mean_evacuation_time'))} | "
                f"{fmt_num(value(summary, line, method, 'mean_queueing_time'))} | "
                f"{fmt_num(value(summary, line, method, 'mean_congestion_exposure'))} | "
                f"{fmt_num(value(summary, line, method, 'mean_avg_speed'), 3)} |"
            )
    report.append("")

    line_notes = {
        "L2": "L2 的差异主要集中在 C1，说明算法在站台起点到垂直设施首跳选择上存在明显差异。",
        "L7": "L7 的排队与拥挤暴露改善最明显，适合说明强汇流场景下算法的拥堵规避能力。",
        "L18": "L18 路径链路更长，适合观察算法在长路径、多出口簇场景下的稳定性。",
    }
    for idx, line in enumerate(LINES, start=2):
        report.append(f"## {idx}. {line} 线路")
        report.append("")
        report.append("### 场景设计")
        report.append(f"- {line} 设置 4 个典型起点，分别覆盖站台、楼梯和扶梯等常见疏散出发位置。")
        report.append("- 每个起点释放 100 人，由算法在所有候选出口中选择目标出口和路径。")
        report.append("")
        report.append("### 过程与结果")
        report.append(f"- {line_notes[line]}")
        our_time = value(summary, line, "AdaptiveSingleNextHop", "mean_evacuation_time")
        paper_time = value(summary, line, "PaperImprovedAStar", "mean_evacuation_time")
        aco_time = value(summary, line, "AntColony", "mean_evacuation_time")
        report.append(f"- 平均疏散时间：Paper={fmt_num(paper_time)} s，ACO={fmt_num(aco_time)} s，Our={fmt_num(our_time)} s。")
        report.append(f"- Our 相对 Paper 的时间差为 {fmt_num(our_time - paper_time)} s，相对 ACO 的时间差为 {fmt_num(our_time - aco_time)} s。")
        report.append("")
        report.append(f"#### {line} 逐案例结果")
        report.append(case_table(cases, line))
        report.append("")

    report.append("## 5. 总结")
    report.append("")
    report.append("- `PaperImprovedAStar` 代表严格论文规则下的密度约束 A*。")
    report.append("- `AntColony` 代表群智能搜索基准，用信息素迭代寻找当前低代价路径。")
    report.append("- `AdaptiveSingleNextHop` 代表你的预测拥堵与下游负载感知算法。")
    report.append("- 这一组结果用于算法层验证，后续再单独讨论全站引导和分流效果。")
    report.append("")

    OUT_REPORT_MD.write_text("\n".join(report), encoding="utf-8-sig")


def main() -> None:
    cases, summary = load_data()
    build_summary_chart(summary)
    build_delta_chart(summary)
    build_report(cases, summary)
    print(f"Wrote {OUT_SUMMARY_PNG}")
    print(f"Wrote {OUT_DELTA_PNG}")
    print(f"Wrote {OUT_REPORT_MD}")


if __name__ == "__main__":
    main()
