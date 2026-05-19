from __future__ import annotations

import argparse
import csv
import json
import os
import warnings
from pathlib import Path

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    plt = None
    _MATPLOTLIB_IMPORT_ERROR = exc
else:
    _MATPLOTLIB_IMPORT_ERROR = None


SCENARIO_LABELS = {
    "weekday_nominal": "Weekday",
    "evening_peak_v2g": "Evening peak",
    "event_surge": "Event surge",
    "rural_degraded_isac": "Rural ISAC",
    "wan_outage_edge_only": "WAN outage",
}

COLORS = {
    "blue": "#2F6B8F",
    "green": "#3B7C5A",
    "red": "#B44E4E",
    "gold": "#B8872B",
    "gray": "#68717A",
    "purple": "#725C9A",
}


def plot_all(report_dir: str, output_dir: str) -> list[str]:
    require_matplotlib()
    os.makedirs(output_dir, exist_ok=True)
    scenario_rows = read_csv(os.path.join(report_dir, "scenario_comparison.csv"))
    station_rows = read_csv(os.path.join(report_dir, "station_metrics.csv"))
    detail = {
        row["scenario"]: load_json(os.path.join(report_dir, f"{row['scenario']}_detail.json"))
        for row in scenario_rows
    }

    figure_paths = [
        plot_scenario_performance(scenario_rows, output_dir),
        plot_latency_profile(scenario_rows, output_dir),
        plot_v2g_energy_revenue(scenario_rows, output_dir),
        plot_station_loads(station_rows, output_dir),
        plot_station_queues(station_rows, output_dir),
        plot_grid_stress_minutes(detail, output_dir),
        plot_event_surge_timeline(detail["event_surge"], output_dir),
        plot_charging_completion_rate(scenario_rows, output_dir),
        plot_v2g_participation_rate(scenario_rows, output_dir),
        plot_v2g_discharge_credits(scenario_rows, detail, output_dir),
    ]
    write_index(report_dir, figure_paths)
    return figure_paths


def require_matplotlib() -> None:
    if plt is None:
        raise RuntimeError("matplotlib is required to generate journal figures") from _MATPLOTLIB_IMPORT_ERROR


def plot_scenario_performance(rows: list[dict], output_dir: str) -> str:
    labels = labels_for(rows)
    x = range(len(rows))
    served = [float(row["served_ratio_pct"]) for row in rows]
    stress = [float(row["grid_stress_reduction_pct"]) for row in rows]
    forecast = [float(row["demand_prediction_accuracy_pct"]) for row in rows]

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    width = 0.25
    ax.bar([i - width for i in x], served, width, label="Served ratio", color=COLORS["blue"])
    ax.bar(x, stress, width, label="Grid stress reduction", color=COLORS["green"])
    ax.bar([i + width for i in x], forecast, width, label="Forecast accuracy", color=COLORS["gold"])
    ax.set_ylabel("Percentage value by metric (%)")
    set_padded_ylim(ax, served + stress + forecast, floor=20.0, ceiling=105.0, pad_ratio=0.10)
    ax.set_xticks(list(x), labels, rotation=18, ha="right")
    ax.set_title("Scenario-Level AEI-V2G Performance")
    ax.legend(frameon=False, ncols=3, loc="upper center", bbox_to_anchor=(0.5, 1.10))
    style_axes(ax)
    return save(fig, output_dir, "fig_01_scenario_performance.png")


def plot_latency_profile(rows: list[dict], output_dir: str) -> str:
    labels = labels_for(rows)
    p95 = [float(row["latency_ms_p95"]) for row in rows]
    max_values = [float(row["latency_ms_max"]) for row in rows]

    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    x = range(len(rows))
    ax.plot(x, p95, marker="o", linewidth=2.5, label="P95 latency", color=COLORS["blue"])
    ax.plot(x, max_values, marker="s", linewidth=2.5, label="Max latency", color=COLORS["red"])
    set_padded_ylim(ax, p95 + max_values, pad_ratio=0.22)
    ax.set_ylabel("Latency (ms)")
    ax.set_xticks(list(x), labels, rotation=18, ha="right")
    ax.set_title("LAVA Decision Latency by Scenario")
    ax.legend(frameon=False)
    style_axes(ax)
    return save(fig, output_dir, "fig_02_latency_profile.png")


def plot_v2g_energy_revenue(rows: list[dict], output_dir: str) -> str:
    labels = labels_for(rows)
    x = range(len(rows))
    energy = [float(row["v2g_supplied_kwh"]) for row in rows]
    revenue = [float(row["v2g_revenue"]) for row in rows]

    fig, ax1 = plt.subplots(figsize=(10.5, 5.8))
    ax2 = ax1.twinx()
    ax1.bar(x, energy, color=COLORS["green"], alpha=0.86, label="V2G supplied")
    ax2.plot(x, revenue, marker="o", linewidth=2.5, color=COLORS["purple"], label="V2G revenue")
    ax1.set_ylabel("Energy supplied (kWh)")
    ax2.set_ylabel("Revenue units")
    set_padded_ylim(ax1, energy, floor=min(energy) * 0.82, pad_ratio=0.12)
    set_padded_ylim(ax2, revenue, floor=min(revenue) * 0.90, pad_ratio=0.14)
    ax1.set_xticks(list(x), labels, rotation=18, ha="right")
    ax1.set_title("V2G Energy Support and Settlement Value")
    style_axes(ax1)
    ax2.spines["top"].set_visible(False)
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, frameon=False, loc="upper left")
    return save(fig, output_dir, "fig_03_v2g_energy_revenue.png")


def plot_station_loads(rows: list[dict], output_dir: str) -> str:
    scenarios = ordered_scenarios(rows)
    stations = ["station_a", "station_b", "station_c"]
    labels = [SCENARIO_LABELS.get(item, item) for item in scenarios]
    x = range(len(scenarios))
    width = 0.24

    fig, ax = plt.subplots(figsize=(11.2, 5.8))
    all_values = []
    for offset, station in zip([-width, 0, width], stations):
        values = [metric(rows, scenario, station, "avg_load_kw") for scenario in scenarios]
        all_values.extend(values)
        ax.bar([i + offset for i in x], values, width, label=station.replace("_", " "), color=station_color(station))
    ax.set_ylabel("Average load (kW)")
    set_padded_ylim(ax, all_values, floor=min(all_values) * 0.82, pad_ratio=0.12)
    ax.set_xticks(list(x), labels, rotation=18, ha="right")
    ax.set_title("Individual Charging Station Load")
    ax.legend(frameon=False, ncols=3)
    style_axes(ax)
    return save(fig, output_dir, "fig_04_station_avg_load.png")


def plot_station_queues(rows: list[dict], output_dir: str) -> str:
    scenarios = ordered_scenarios(rows)
    stations = ["station_a", "station_b", "station_c"]
    labels = [SCENARIO_LABELS.get(item, item) for item in scenarios]
    x = range(len(scenarios))
    width = 0.24

    fig, ax = plt.subplots(figsize=(11.2, 5.8))
    all_values = []
    for offset, station in zip([-width, 0, width], stations):
        values = [metric(rows, scenario, station, "peak_queue_depth") for scenario in scenarios]
        all_values.extend(values)
        ax.bar([i + offset for i in x], values, width, label=station.replace("_", " "), color=station_color(station))
    ax.set_ylabel("Peak queued EVs")
    set_padded_ylim(ax, all_values, floor=0.0, pad_ratio=0.10)
    ax.set_xticks(list(x), labels, rotation=18, ha="right")
    ax.set_title("Peak Queue Depth by Station")
    ax.legend(frameon=False, ncols=3)
    style_axes(ax)
    return save(fig, output_dir, "fig_05_station_peak_queue.png")


def plot_grid_stress_minutes(detail: dict[str, dict], output_dir: str) -> str:
    scenarios = list(detail.keys())
    labels = [SCENARIO_LABELS.get(item, item) for item in scenarios]
    managed = [detail[s]["components"]["grid_response"]["stress_minutes_over_0_80"] for s in scenarios]
    baseline = [detail[s]["components"]["grid_response"]["baseline_stress_minutes_over_0_80"] for s in scenarios]
    x = range(len(scenarios))
    width = 0.34

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    ax.bar([i - width / 2 for i in x], baseline, width, label="Reactive baseline", color=COLORS["red"], alpha=0.82)
    ax.bar([i + width / 2 for i in x], managed, width, label="AEI-V2G managed", color=COLORS["green"], alpha=0.88)
    ax.set_ylabel("Minutes with grid stress >= 0.80")
    set_padded_ylim(ax, managed + baseline, floor=min(managed) * 0.75, pad_ratio=0.10)
    ax.set_xticks(list(x), labels, rotation=18, ha="right")
    ax.set_title("Peak-Stress Event Suppression")
    ax.legend(frameon=False)
    style_axes(ax)
    return save(fig, output_dir, "fig_06_grid_stress_minutes.png")


def plot_event_surge_timeline(detail: dict, output_dir: str) -> str:
    rows = detail["last_15_minutes"]
    minutes = [int(row["minute"]) for row in rows]
    hours = [minute / 60.0 for minute in minutes]
    grid = [float(row["grid_stress"]) for row in rows]
    baseline = [float(row["baseline_grid_stress"]) for row in rows]
    v2g_kw = [float(row["v2g_kw"]) for row in rows]

    fig, ax1 = plt.subplots(figsize=(10.5, 5.6))
    ax2 = ax1.twinx()
    ax1.plot(hours, baseline, marker="s", linewidth=2.2, label="Reactive baseline stress", color=COLORS["red"])
    ax1.plot(hours, grid, marker="o", linewidth=2.2, label="AEI-V2G stress", color=COLORS["green"])
    ax2.bar(hours, v2g_kw, width=0.012, alpha=0.24, color=COLORS["blue"], label="V2G dispatch")
    ax1.set_ylabel("Grid stress index")
    ax2.set_ylabel("V2G dispatch (kW)")
    ax1.set_xlabel("Hour of day")
    ax1.set_xticks([hour for hour in hours if int(round(hour * 60)) % 2 == 0])
    ax1.set_xticklabels([hour_label(hour) for hour in hours if int(round(hour * 60)) % 2 == 0], rotation=0, ha="center")
    ax1.set_ylim(0.72, 1.0)
    set_padded_ylim(ax2, v2g_kw, floor=min(v2g_kw) * 0.90, pad_ratio=0.18)
    ax1.set_title("Event Surge: Final 15-Minute Grid Response")
    style_axes(ax1)
    ax2.spines["top"].set_visible(False)
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(
        handles1 + handles2,
        labels1 + labels2,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.13),
        ncols=3,
    )
    return save(fig, output_dir, "fig_07_event_surge_timeline.png")


def plot_charging_completion_rate(rows: list[dict], output_dir: str) -> str:
    labels = labels_for(rows)
    x = range(len(rows))
    served_ratio = [float(row["served_ratio_pct"]) for row in rows]
    spawned = [float(row["spawned_evs"]) for row in rows]
    served = [float(row["served_evs"]) for row in rows]

    fig, ax1 = plt.subplots(figsize=(10.5, 5.8))
    ax2 = ax1.twinx()
    bars = ax1.bar(x, served_ratio, color=COLORS["blue"], alpha=0.88, label="Completion rate")
    ax2.plot(x, served, marker="o", linewidth=2.2, color=COLORS["green"], label="Served EVs")
    ax2.plot(x, spawned, marker="s", linewidth=2.0, color=COLORS["gray"], label="Spawned EVs")
    ax1.set_ylabel("Completion rate (%)")
    ax2.set_ylabel("EV count")
    set_padded_ylim(ax1, served_ratio, floor=max(0.0, min(served_ratio) - 8.0), ceiling=100.0, pad_ratio=0.10)
    set_padded_ylim(ax2, served + spawned, floor=min(served + spawned) * 0.82, pad_ratio=0.12)
    ax1.set_xticks(list(x), labels, rotation=18, ha="right")
    ax1.set_title("Charging Completion Rate by Scenario")
    for bar, value in zip(bars, served_ratio):
        ax1.text(bar.get_x() + bar.get_width() / 2, value + 1.5, f"{value:.1f}%", ha="center", va="bottom", fontsize=8)
    style_axes(ax1)
    ax2.spines["top"].set_visible(False)
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, frameon=False, loc="upper center", ncols=3, bbox_to_anchor=(0.5, 1.09))
    return save(fig, output_dir, "fig_08_charging_completion_rate.png")


def plot_v2g_participation_rate(rows: list[dict], output_dir: str) -> str:
    labels = labels_for(rows)
    x = range(len(rows))
    utilization = [float(row["v2g_utilization_pct"]) for row in rows]
    supplied = [float(row["v2g_supplied_kwh"]) for row in rows]

    fig, ax1 = plt.subplots(figsize=(10.5, 5.8))
    ax2 = ax1.twinx()
    bars = ax1.bar(x, utilization, color=COLORS["purple"], alpha=0.88, label="V2G participation rate")
    ax2.plot(x, supplied, marker="o", linewidth=2.4, color=COLORS["green"], label="V2G supplied")
    ax1.set_ylabel("Participation rate (%)")
    ax2.set_ylabel("V2G supplied (kWh)")
    set_padded_ylim(ax1, utilization, floor=max(0.0, min(utilization) - 1.0), ceiling=min(100.0, max(utilization) + 1.0), pad_ratio=0.18)
    set_padded_ylim(ax2, supplied, floor=min(supplied) * 0.82, pad_ratio=0.12)
    ax1.set_xticks(list(x), labels, rotation=18, ha="right")
    ax1.set_title("V2G Participation Rate by Scenario")
    for bar, value in zip(bars, utilization):
        ax1.text(bar.get_x() + bar.get_width() / 2, value + 1.2, f"{value:.1f}%", ha="center", va="bottom", fontsize=8)
    style_axes(ax1)
    ax2.spines["top"].set_visible(False)
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, frameon=False, loc="upper center", ncols=2, bbox_to_anchor=(0.5, 1.09))
    return save(fig, output_dir, "fig_09_v2g_participation_rate.png")


def plot_v2g_discharge_credits(rows: list[dict], detail: dict[str, dict], output_dir: str) -> str:
    labels = labels_for(rows)
    scenarios = [row["scenario"] for row in rows]
    x = range(len(rows))
    accepted = []
    credits = []
    for row in rows:
        settlement = detail[row["scenario"]]["components"]["v2g_settlement"]
        accepted.append(float(settlement.get("acceptances", row.get("v2g_acceptances", 0.0))))
        if "credits_awarded" in settlement:
            credits.append(float(settlement["credits_awarded"]))
        elif "v2g_credits_awarded" in row:
            credits.append(float(row["v2g_credits_awarded"]))
        else:
            credits.append(float(settlement.get("supplied_kwh", row.get("v2g_supplied_kwh", 0.0))) / 0.5)

    fig, ax1 = plt.subplots(figsize=(10.5, 5.8))
    ax2 = ax1.twinx()
    bars = ax1.bar(x, accepted, color=COLORS["blue"], alpha=0.88, label="V2G accepted events")
    ax2.plot(x, credits, marker="o", linewidth=2.5, color=COLORS["gold"], label="Credits awarded")
    ax1.set_ylabel("Accepted V2G events")
    ax2.set_ylabel("Credit points awarded")
    set_padded_ylim(ax1, accepted, floor=0.0, pad_ratio=0.16)
    set_padded_ylim(ax2, credits, floor=0.0, pad_ratio=0.16)
    ax1.set_xticks(list(x), labels, rotation=18, ha="right")
    ax1.set_title("V2G Discharge Participation and Credit Awards")
    for bar, value in zip(bars, accepted):
        ax1.text(bar.get_x() + bar.get_width() / 2, value + max(1.0, max(accepted or [1]) * 0.02), f"{int(value)}", ha="center", va="bottom", fontsize=8)
    style_axes(ax1)
    ax2.spines["top"].set_visible(False)
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, frameon=False, loc="upper center", ncols=2, bbox_to_anchor=(0.5, 1.09))
    return save(fig, output_dir, "fig_10_v2g_discharge_credits.png")


def write_index(report_dir: str, paths: list[str]) -> None:
    rel_paths = [Path(path).relative_to(Path(report_dir)).as_posix() for path in paths]
    lines = [
        "# AEI-V2G Journal Figures",
        "",
        "Generated from `reports/journal_study` CSV and JSON artifacts.",
        "",
    ]
    captions = [
        "Scenario-level served ratio, grid-stress reduction, and forecast accuracy.",
        "LAVA P95 and maximum decision latency against the 200 ms target.",
        "V2G supplied energy and settlement value by scenario.",
        "Average load for each individual charging station.",
        "Peak queue depth for each individual charging station.",
        "Reactive baseline versus AEI-V2G peak-stress minutes.",
        "Event-surge final 15-minute grid response and V2G dispatch.",
        "Charging completion rate with served and spawned EV counts.",
        "V2G participation rate with supplied V2G energy.",
        "Accepted V2G discharge events compared with credit points awarded.",
    ]
    for index, (path, caption) in enumerate(zip(rel_paths, captions), start=1):
        lines.append(f"## Figure {index}")
        lines.append("")
        lines.append(f"![Figure {index}]({path})")
        lines.append("")
        lines.append(caption)
        lines.append("")
    with open(os.path.join(report_dir, "FIGURES.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def read_csv(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def labels_for(rows: list[dict]) -> list[str]:
    return [SCENARIO_LABELS.get(row["scenario"], row["scenario"]) for row in rows]


def ordered_scenarios(rows: list[dict]) -> list[str]:
    seen = []
    for row in rows:
        if row["scenario"] not in seen:
            seen.append(row["scenario"])
    return seen


def metric(rows: list[dict], scenario: str, station: str, key: str) -> float:
    for row in rows:
        if row["scenario"] == scenario and row["station_id"] == station:
            return float(row[key])
    return 0.0


def station_color(station: str) -> str:
    return {"station_a": COLORS["blue"], "station_b": COLORS["green"], "station_c": COLORS["gold"]}[station]


def hour_label(hour: float) -> str:
    hour_int = int(hour) % 24
    minute_int = int(round((hour - int(hour)) * 60)) % 60
    return f"{hour_int:02d}:{minute_int:02d}"


def style_axes(ax) -> None:
    ax.grid(axis="y", color="#D7DCE0", linewidth=0.8, alpha=0.75)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def set_padded_ylim(
    ax,
    values: list[float],
    *,
    floor: float | None = None,
    ceiling: float | None = None,
    pad_ratio: float = 0.12,
) -> None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return
    low = min(numeric)
    high = max(numeric)
    span = high - low
    if span <= 0:
        span = max(abs(high), 1.0)
    lower = low - span * pad_ratio
    upper = high + span * pad_ratio
    if floor is not None:
        lower = max(floor, lower)
    if ceiling is not None:
        upper = min(ceiling, upper)
    if lower >= upper:
        lower = low - span * pad_ratio
        upper = high + span * pad_ratio
    ax.set_ylim(lower, upper)


def save(fig, output_dir: str, filename: str) -> str:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Tight layout not applied.*", category=UserWarning)
        fig.tight_layout()
    path = os.path.join(output_dir, filename)
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", default="reports/journal_study")
    parser.add_argument("--output-dir", default="reports/journal_study/figures")
    args = parser.parse_args()
    paths = plot_all(args.report_dir, args.output_dir)
    print(json.dumps({"figures": paths, "index": os.path.join(args.report_dir, "FIGURES.md")}, indent=2))


if __name__ == "__main__":
    main()
