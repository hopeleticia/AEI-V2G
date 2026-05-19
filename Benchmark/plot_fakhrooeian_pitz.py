from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    plt = None
    _MATPLOTLIB_IMPORT_ERROR = exc
else:
    _MATPLOTLIB_IMPORT_ERROR = None


SCENARIO_LABELS = {
    "scenario_1_worst_case": "Scenario 1: uncontrolled",
    "scenario_2_v2g_no_operator_control": "Scenario 2: V2G no operator control",
    "scenario_3_v2g_operator_full_power": "Scenario 3: operator control, full power",
    "scenario_4_v2g_operator_limited_power": "Scenario 4: operator control, limited power",
}


COLORS = {
    "base": "#2E73C9",
    "scenario_1_worst_case": "#FF0000",
    "scenario_2_v2g_no_operator_control": "#7EA6E0",
    "scenario_3_v2g_operator_full_power": "#3F6F2A",
    "scenario_4_v2g_operator_limited_power": "#F0A500",
}


def require_matplotlib() -> None:
    if plt is None:
        raise RuntimeError("matplotlib is required to plot benchmark results") from _MATPLOTLIB_IMPORT_ERROR


def read_timeseries(report_dir: str) -> list[dict]:
    path = os.path.join(report_dir, "timeseries.csv")
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def plot_fig5(report_dir: str, output_dir: str) -> str:
    require_matplotlib()
    os.makedirs(output_dir, exist_ok=True)
    rows = read_timeseries(report_dir)
    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_scenario[row["scenario"]].append(row)

    first_scenario = next(iter(by_scenario.values()))
    hours = [float(row["minute"]) / 60.0 for row in first_scenario]
    base = [float(row["base_load_kw"]) for row in first_scenario]

    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    ax.plot(hours, base, color=COLORS["base"], linewidth=2.3, label="Without EVs")

    for scenario, scenario_rows in by_scenario.items():
        scenario_hours = [float(row["minute"]) / 60.0 for row in scenario_rows]
        total_load = [float(row["total_load_kw"]) for row in scenario_rows]
        ax.plot(
            scenario_hours,
            total_load,
            linewidth=2.1,
            label=SCENARIO_LABELS.get(scenario, scenario),
            color=COLORS.get(scenario),
        )

    ax.set_xlabel("Time")
    ax.set_ylabel("Active Power (kW)")
    ax.set_xlim(0, max(hours))
    ax.set_ylim(0, 160)
    ax.set_yticks([0, 20, 40, 60, 80, 100, 120, 140, 160])
    ax.set_xticks([0, 4, 8, 12, 16, 20, 24, 28, 32, 40, 47.92])
    ax.set_xticklabels(["04.28 15:00", "19:00", "23:00", "04.29 03:00", "7:00", "11:00", "15:00", "19:00", "04.30 03:00", "11:00", "14:55"])
    ax.grid(axis="y", color="#D8DDE3", linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=False, fontsize=9, ncols=3, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.22)

    path = os.path.join(output_dir, "fig_05_load_profile_pattern_reconstruction.png")
    fig.savefig(path, dpi=220, bbox_inches="tight")
    paper_style_path = os.path.join(output_dir, "fig_05_load_profile_paper_style.png")
    fig.savefig(paper_style_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    write_index(output_dir, path, paper_style_path)
    return path


def write_index(output_dir: str, figure_path: str, paper_style_path: str) -> None:
    with open(os.path.join(output_dir, "FIGURES.md"), "w", encoding="utf-8") as handle:
        handle.write("# Benchmark Figures\n\n")
        handle.write("## Fig. 5 Load Profile Reproduction\n\n")
        handle.write(
            "This figure recreates the benchmark paper's Fig. 5 comparison style using stochastic EV sessions and this repo's deterministic low-voltage feeder proxy. "
            "It plots the base feeder load without EVs and the total feeder load under the four implemented benchmark scenarios. "
            "The x-axis and y-axis are fixed to match the paper's 48-hour 04.28 15:00 to 04.30 14:55 window and 0-160 kW scale.\n\n"
        )
        handle.write(f"- `{os.path.basename(figure_path)}`: preferred file for reports.\n")
        handle.write(f"- `{os.path.basename(paper_style_path)}`: same figure retained as a paper-style alias.\n")

        handle.write("\n## Missing From Exact Paper Replication\n\n")
        handle.write("- DIgSILENT PowerFactory quasi-dynamic load-flow execution.\n")
        handle.write("- The exact Feeder 242 topology, line parameters, transformer model, and bus-level voltage calculations.\n")
        handle.write("- Original BDEW residential load-profile exports used by the paper.\n")
        handle.write("- Exact user-input GUI/mobile-app workflow; this repo implements the scheduling logic programmatically.\n")
        handle.write("- Exact per-line loading and bus-voltage tables from PowerFactory; this repo uses deterministic feeder proxy metrics.\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", default="reports/benchmark_fakhrooeian_pitz")
    parser.add_argument("--output-dir", default="reports/benchmark_fakhrooeian_pitz/figures")
    args = parser.parse_args()
    path = plot_fig5(args.report_dir, args.output_dir)
    print(path)


if __name__ == "__main__":
    main()
