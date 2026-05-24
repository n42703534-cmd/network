import csv
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(r"C:\Users\帅美婷sweet baby\Desktop\network")
PYTHON_CURVE_CSV = ROOT / "01_system_evacuation_curve.csv"

OUTPUT_FILES = {
    "aco_single": ROOT / "301_evacuation_curve_aco.png",
    "paper_single": ROOT / "302_evacuation_curve_improved_astar.png",
    "our_single": ROOT / "303_evacuation_curve_our_single_path.png",
    "our_vs_pathfinder": ROOT / "304_evacuation_curve_our_vs_pathfinder.png",
    "all_vs_pathfinder": ROOT / "305_evacuation_curve_all_vs_pathfinder.png",
    "merged_csv": ROOT / "306_evacuation_curve_comparison_data.csv",
    "aco_single_smooth": ROOT / "311_evacuation_curve_aco_smooth.png",
    "paper_single_smooth": ROOT / "312_evacuation_curve_improved_astar_smooth.png",
    "our_single_smooth": ROOT / "313_evacuation_curve_our_single_path_smooth.png",
    "our_vs_pathfinder_smooth": ROOT / "314_evacuation_curve_our_vs_pathfinder_smooth.png",
    "all_vs_pathfinder_smooth": ROOT / "315_evacuation_curve_all_vs_pathfinder_smooth.png",
    "merged_smooth_csv": ROOT / "316_evacuation_curve_comparison_data_smooth.csv",
}

METHOD_ORDER = ["ACO", "ImprovedAStar", "OurSinglePath"]
METHOD_COLORS = {
    "ACO": "#E63946",
    "ImprovedAStar": "#F4A261",
    "OurSinglePath": "#457B9D",
    "Pathfinder": "#2A9D8F",
}


def _load_python_curves(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["time_s"] = pd.to_numeric(df["time_s"], errors="coerce")
    df["remaining_people"] = pd.to_numeric(df["remaining_people"], errors="coerce")
    df = df.dropna(subset=["method", "time_s", "remaining_people"]).copy()
    return df


def _find_pathfinder_rooms_csv(root: Path) -> Path:
    matches = sorted(root.glob("*_rooms.csv"))
    if not matches:
        raise FileNotFoundError("未找到 Pathfinder 的 *_rooms.csv 文件。")
    return matches[0]


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except Exception:
        return False


def _load_pathfinder_curve(path: Path) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    data_start = next(
        i
        for i, line in enumerate(lines)
        if len(line.split(",")) > 2 and _is_number(line.split(",")[1].strip().strip('"'))
    )

    df = pd.read_csv(path, skiprows=data_start, header=None, encoding="utf-8", engine="python")
    df = df.iloc[:, :3].copy()
    df.columns = ["_blank", "time_s", "remaining_people"]
    df["time_s"] = pd.to_numeric(df["time_s"], errors="coerce")
    df["remaining_people"] = pd.to_numeric(df["remaining_people"], errors="coerce")
    df = df.dropna(subset=["time_s", "remaining_people"]).copy()
    df["method"] = "Pathfinder"
    return df[["method", "time_s", "remaining_people"]]


def _base_style():
    plt.style.use("ggplot")
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False


def _smooth_curve(df: pd.DataFrame, window: int = 9) -> pd.DataFrame:
    out = df.sort_values("time_s").copy()
    out["remaining_people_smooth"] = (
        out["remaining_people"]
        .rolling(window=window, min_periods=1, center=True)
        .mean()
    )
    return out


def _plot_single_curve(df: pd.DataFrame, method: str, output_path: Path):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(
        df["time_s"],
        df["remaining_people"],
        linewidth=3.0,
        color=METHOD_COLORS[method],
        label=method,
    )
    ax.set_title(f"{method} 疏散曲线", fontsize=18, fontweight="bold", pad=12)
    ax.set_xlabel("时间 (s)", fontsize=13)
    ax.set_ylabel("站内剩余人数 (人)", fontsize=13)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _plot_single_curve_smooth(df: pd.DataFrame, method: str, output_path: Path):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(
        df["time_s"],
        df["remaining_people_smooth"],
        linewidth=3.0,
        color=METHOD_COLORS[method],
        label=f"{method} (smooth)",
    )
    ax.set_title(f"{method} 疏散曲线（平滑展示版）", fontsize=18, fontweight="bold", pad=12)
    ax.set_xlabel("时间 (s)", fontsize=13)
    ax.set_ylabel("站内剩余人数 (人)", fontsize=13)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _plot_dual_curve(df_a: pd.DataFrame, label_a: str, df_b: pd.DataFrame, label_b: str, title: str, output_path: Path):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df_a["time_s"], df_a["remaining_people"], linewidth=3.0, color=METHOD_COLORS[label_a], label=label_a)
    ax.plot(df_b["time_s"], df_b["remaining_people"], linewidth=3.0, color=METHOD_COLORS[label_b], label=label_b)
    ax.set_title(title, fontsize=18, fontweight="bold", pad=12)
    ax.set_xlabel("时间 (s)", fontsize=13)
    ax.set_ylabel("站内剩余人数 (人)", fontsize=13)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _plot_dual_curve_smooth(df_a: pd.DataFrame, label_a: str, df_b: pd.DataFrame, label_b: str, title: str, output_path: Path):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df_a["time_s"], df_a["remaining_people_smooth"], linewidth=3.0, color=METHOD_COLORS[label_a], label=f"{label_a} (smooth)")
    ax.plot(df_b["time_s"], df_b["remaining_people_smooth"], linewidth=3.0, color=METHOD_COLORS[label_b], label=f"{label_b} (smooth)")
    ax.set_title(title, fontsize=18, fontweight="bold", pad=12)
    ax.set_xlabel("时间 (s)", fontsize=13)
    ax.set_ylabel("站内剩余人数 (人)", fontsize=13)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _plot_all_curves(python_df: pd.DataFrame, pathfinder_df: pd.DataFrame, output_path: Path):
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for method in METHOD_ORDER:
        sub = python_df[python_df["method"] == method]
        ax.plot(sub["time_s"], sub["remaining_people"], linewidth=2.8, color=METHOD_COLORS[method], label=method)
    ax.plot(
        pathfinder_df["time_s"],
        pathfinder_df["remaining_people"],
        linewidth=3.0,
        color=METHOD_COLORS["Pathfinder"],
        label="Pathfinder",
    )
    ax.set_title("三算法与 Pathfinder 疏散曲线对比", fontsize=18, fontweight="bold", pad=12)
    ax.set_xlabel("时间 (s)", fontsize=13)
    ax.set_ylabel("站内剩余人数 (人)", fontsize=13)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _plot_all_curves_smooth(python_df: pd.DataFrame, pathfinder_df: pd.DataFrame, output_path: Path):
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for method in METHOD_ORDER:
        sub = python_df[python_df["method"] == method]
        ax.plot(sub["time_s"], sub["remaining_people_smooth"], linewidth=2.8, color=METHOD_COLORS[method], label=f"{method} (smooth)")
    ax.plot(
        pathfinder_df["time_s"],
        pathfinder_df["remaining_people_smooth"],
        linewidth=3.0,
        color=METHOD_COLORS["Pathfinder"],
        label="Pathfinder (smooth)",
    )
    ax.set_title("三算法与 Pathfinder 疏散曲线对比（平滑展示版）", fontsize=18, fontweight="bold", pad=12)
    ax.set_xlabel("时间 (s)", fontsize=13)
    ax.set_ylabel("站内剩余人数 (人)", fontsize=13)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    _base_style()
    python_df = _load_python_curves(PYTHON_CURVE_CSV)
    pathfinder_csv = _find_pathfinder_rooms_csv(ROOT)
    pathfinder_df = _load_pathfinder_curve(pathfinder_csv)
    python_smooth_df = pd.concat(
        [_smooth_curve(python_df[python_df["method"] == method]) for method in METHOD_ORDER],
        ignore_index=True,
    )
    pathfinder_smooth_df = _smooth_curve(pathfinder_df)

    merged = pd.concat(
        [
            python_df[["method", "time_s", "remaining_people"]],
            pathfinder_df[["method", "time_s", "remaining_people"]],
        ],
        ignore_index=True,
    )
    merged.to_csv(OUTPUT_FILES["merged_csv"], index=False, encoding="utf-8-sig")
    merged_smooth = pd.concat(
        [
            python_smooth_df[["method", "time_s", "remaining_people", "remaining_people_smooth"]],
            pathfinder_smooth_df[["method", "time_s", "remaining_people", "remaining_people_smooth"]],
        ],
        ignore_index=True,
    )
    merged_smooth.to_csv(OUTPUT_FILES["merged_smooth_csv"], index=False, encoding="utf-8-sig")

    for method, output_key in [
        ("ACO", "aco_single"),
        ("ImprovedAStar", "paper_single"),
        ("OurSinglePath", "our_single"),
    ]:
        method_df = python_df[python_df["method"] == method].copy()
        _plot_single_curve(method_df, method, OUTPUT_FILES[output_key])
        method_smooth_df = python_smooth_df[python_smooth_df["method"] == method].copy()
        smooth_key = f"{output_key}_smooth"
        _plot_single_curve_smooth(method_smooth_df, method, OUTPUT_FILES[smooth_key])

    our_df = python_df[python_df["method"] == "OurSinglePath"].copy()
    our_smooth_df = python_smooth_df[python_smooth_df["method"] == "OurSinglePath"].copy()
    _plot_dual_curve(
        our_df,
        "OurSinglePath",
        pathfinder_df,
        "Pathfinder",
        "OurSinglePath 与 Pathfinder 疏散曲线对比",
        OUTPUT_FILES["our_vs_pathfinder"],
    )
    _plot_dual_curve_smooth(
        our_smooth_df,
        "OurSinglePath",
        pathfinder_smooth_df,
        "Pathfinder",
        "OurSinglePath 与 Pathfinder 疏散曲线对比（平滑展示版）",
        OUTPUT_FILES["our_vs_pathfinder_smooth"],
    )

    _plot_all_curves(python_df, pathfinder_df, OUTPUT_FILES["all_vs_pathfinder"])
    _plot_all_curves_smooth(python_smooth_df, pathfinder_smooth_df, OUTPUT_FILES["all_vs_pathfinder_smooth"])

    print("已生成以下疏散曲线图：")
    for key in ["aco_single", "paper_single", "our_single", "our_vs_pathfinder", "all_vs_pathfinder"]:
        print(OUTPUT_FILES[key])
    print("已生成以下平滑展示版疏散曲线图：")
    for key in ["aco_single_smooth", "paper_single_smooth", "our_single_smooth", "our_vs_pathfinder_smooth", "all_vs_pathfinder_smooth"]:
        print(OUTPUT_FILES[key])
    print("已导出合并曲线数据：")
    print(OUTPUT_FILES["merged_csv"])
    print(OUTPUT_FILES["merged_smooth_csv"])


if __name__ == "__main__":
    main()
