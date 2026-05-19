from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
from dataclasses import asdict, dataclass
from statistics import mean


STEP_MINUTES = 5
SIM_HOURS = 48
SIM_STEPS = SIM_HOURS * 60 // STEP_MINUTES
START_HOUR = 15.0
PEAK_START = 17.0
PEAK_END = 24.0
READY_BY = 8.0 + 24.0
EV_COUNT = 15
BATTERY_KWH = 62.0
EV_ACCEPTANCE_KW = 6.6
CHARGER_KW = 7.4
LIMITED_CHARGER_KW = 3.7
SOC_MIN = 30.0
SOC_MAX = 80.0
DEFAULT_RUNS = 30


SCENARIOS = {
    "scenario_1_worst_case": {
        "label": "Scenario 1 - worst-case uncontrolled charging",
        "arrival": "normal_peak",
        "initial_soc_min": 5.0,
        "initial_soc_max": 45.0,
        "mode": "uncontrolled",
        "charger_kw": CHARGER_KW,
    },
    "scenario_2_v2g_no_operator_control": {
        "label": "Scenario 2 - V2G without grid-operator control",
        "arrival": "uniform_15_18",
        "initial_soc_min": 35.0,
        "initial_soc_max": 75.0,
        "mode": "v2g_no_control",
        "charger_kw": CHARGER_KW,
    },
    "scenario_3_v2g_operator_full_power": {
        "label": "Scenario 3 - V2G with operator control, full power",
        "arrival": "uniform_15_18",
        "initial_soc_min": 35.0,
        "initial_soc_max": 75.0,
        "mode": "operator_full_power",
        "charger_kw": CHARGER_KW,
    },
    "scenario_4_v2g_operator_limited_power": {
        "label": "Scenario 4 - V2G with operator control, limited power",
        "arrival": "uniform_15_18",
        "initial_soc_min": 35.0,
        "initial_soc_max": 75.0,
        "mode": "operator_limited_power",
        "charger_kw": LIMITED_CHARGER_KW,
    },
}


REFERENCE_PATH = os.path.join(os.path.dirname(__file__), "paper_reference_values.json")


@dataclass
class EVSession:
    run: int
    ev_id: str
    arrival_minute: int
    ready_by_minute: int
    initial_soc_pct: float
    target_soc_pct: float
    min_soc_pct: float
    max_soc_pct: float
    charger_kw: float
    scenario: str


def minute_to_hour(minute: int) -> float:
    return START_HOUR + minute / 60.0


def hour_of_day(minute: int) -> float:
    return minute_to_hour(minute) % 24.0


def hour_to_minute(hour: float) -> int:
    return int(round((hour - START_HOUR) * 60))


def is_peak(minute: int) -> bool:
    hour = hour_of_day(minute)
    return PEAK_START <= hour < PEAK_END


def base_load_kw(minute: int) -> float:
    """Deterministic LV feeder proxy calibrated to paper-scale kW values."""
    hour = hour_of_day(minute)
    evening = math.exp(-((hour - 19.5) / 3.0) ** 2)
    morning = 0.45 * math.exp(-((hour - 7.0) / 2.2) ** 2)
    overnight_dip = 0.35 * math.exp(-((hour - 3.0) / 2.4) ** 2)
    load = 13.2 + 22.0 * evening + 9.0 * morning - 4.5 * overnight_dip
    return round(max(8.5, load), 3)


def make_sessions(scenario: str, config: dict, seed: int) -> list[EVSession]:
    rng = random.Random(seed)
    sessions: list[EVSession] = []
    for day in range(2):
        day_offset = day * 24.0
        for idx in range(EV_COUNT):
            if config["arrival"] == "normal_peak":
                # Paper-aligned stochastic behavior: worst-case EV use occurs
                # during the 17:00-24:00 peak window, with random arrival spread.
                arrival_hour = day_offset + min(20.75, max(19.0, rng.gauss(19.8, 0.35)))
            else:
                # V2G cases assume EVs are connected before the critical peak
                # period so they can discharge first and recover overnight.
                arrival_hour = day_offset + rng.uniform(15.0, 18.0)
            initial_soc = rng.uniform(config["initial_soc_min"], config["initial_soc_max"])
            target_soc = min(SOC_MAX, max(SOC_MIN + 5.0, rng.gauss(SOC_MAX - 3.0, 2.5)))
            sessions.append(
                EVSession(
                    run=0,
                    ev_id=f"day{day + 1}_ev_{idx + 1:02d}",
                    arrival_minute=max(0, hour_to_minute(arrival_hour)),
                    ready_by_minute=hour_to_minute(day_offset + READY_BY),
                    initial_soc_pct=round(initial_soc, 3),
                    target_soc_pct=round(target_soc, 3),
                    min_soc_pct=SOC_MIN,
                    max_soc_pct=round(target_soc, 3),
                    charger_kw=min(config["charger_kw"], EV_ACCEPTANCE_KW),
                    scenario=scenario,
                )
            )
    return sessions


def simulate_scenario(scenario: str, config: dict, seed: int, run: int = 0) -> tuple[dict, list[dict], list[dict]]:
    sessions = make_sessions(scenario, config, seed)
    for session in sessions:
        session.run = run
    soc_by_ev = {session.ev_id: session.initial_soc_pct for session in sessions}
    power_by_step = {session.ev_id: [0.0 for _ in range(SIM_STEPS)] for session in sessions}

    for session in sessions:
        schedule_ev(session, config["mode"], power_by_step[session.ev_id], soc_by_ev)

    rows = []
    for step in range(SIM_STEPS):
        minute = step * STEP_MINUTES
        ev_kw = sum(power_by_step[session.ev_id][step] for session in sessions)
        base_kw = base_load_kw(minute)
        total_kw = base_kw + ev_kw
        loading_pct = feeder_loading_pct(total_kw)
        loss_kw = feeder_loss_kw(total_kw)
        min_voltage_pu = feeder_min_voltage_pu(total_kw)
        rows.append(
            {
                "run": run,
                "scenario": scenario,
                "minute": minute,
                "hour_of_day": round(hour_of_day(minute), 3),
                "base_load_kw": round(base_kw, 3),
                "ev_power_kw": round(ev_kw, 3),
                "total_load_kw": round(total_kw, 3),
                "loading_pct": round(loading_pct, 3),
                "loss_kw": round(loss_kw, 4),
                "min_voltage_pu": round(min_voltage_pu, 4),
            }
        )

    summary = summarize_scenario(scenario, config["label"], rows, sessions, power_by_step)
    summary["run"] = run
    ev_rows = [asdict(session) for session in sessions]
    return summary, rows, ev_rows


def schedule_ev(session: EVSession, mode: str, power: list[float], soc_by_ev: dict[str, float]) -> None:
    peak_end_minute = peak_end_for_session(session)
    operator_start_hour = minute_to_hour(peak_end_minute)
    if mode == "uncontrolled":
        charge_until_target(session, power, soc_by_ev, start_minute=session.arrival_minute)
        return

    discharge_during_peak(session, power, soc_by_ev)

    if mode == "v2g_no_control":
        charge_until_target(session, power, soc_by_ev, start_minute=peak_end_minute)
    elif mode == "operator_full_power":
        start_hour = operator_start_hour + [0.0, 1.0, 2.0, 3.0, 4.0][int(session.ev_id[-2:]) % 5]
        charge_until_target(session, power, soc_by_ev, start_minute=hour_to_minute(start_hour))
    elif mode == "operator_limited_power":
        start_hour = operator_start_hour + [0.0, 1.0, 2.0][int(session.ev_id[-2:]) % 3]
        charge_until_target(session, power, soc_by_ev, start_minute=hour_to_minute(start_hour))
    else:
        raise ValueError(f"Unknown benchmark mode: {mode}")


def peak_end_for_session(session: EVSession) -> int:
    absolute_arrival_hour = minute_to_hour(session.arrival_minute)
    day_anchor = math.floor(absolute_arrival_hour / 24.0) * 24.0
    return hour_to_minute(day_anchor + PEAK_END)


def discharge_during_peak(session: EVSession, power: list[float], soc_by_ev: dict[str, float]) -> None:
    for step in range(session.arrival_minute // STEP_MINUTES, min(session.ready_by_minute // STEP_MINUTES, SIM_STEPS)):
        minute = step * STEP_MINUTES
        if not is_peak(minute):
            continue
        soc = soc_by_ev[session.ev_id]
        if soc <= session.min_soc_pct:
            continue
        # Paper Eq. 11-13: discharging power is the negative minimum of
        # charger power, EV acceptance power, and the load to be covered.
        # The paper obtains load from BDEW/PowerFactory. Here the base-load
        # proxy supplies that bound because the original profile is absent.
        headroom_pct = soc - session.min_soc_pct
        max_discharge_kwh = headroom_pct / 100.0 * BATTERY_KWH
        feeder_share_kw = base_load_kw(minute) * 0.9 / EV_COUNT
        step_kwh = min(session.charger_kw * STEP_MINUTES / 60.0, feeder_share_kw * STEP_MINUTES / 60.0, max_discharge_kwh)
        if step_kwh <= 0:
            continue
        power[step] = -round(step_kwh * 60.0 / STEP_MINUTES, 6)
        # Paper Eq. 14: next SoC after discharging.
        soc_by_ev[session.ev_id] = max(session.min_soc_pct, soc - step_kwh / BATTERY_KWH * 100.0)


def charge_until_target(session: EVSession, power: list[float], soc_by_ev: dict[str, float], start_minute: int) -> None:
    start_step = max(session.arrival_minute // STEP_MINUTES, start_minute // STEP_MINUTES)
    end_step = min(session.ready_by_minute // STEP_MINUTES, SIM_STEPS)
    for step in range(start_step, end_step):
        soc = soc_by_ev[session.ev_id]
        if soc >= session.max_soc_pct:
            break
        # Paper Eq. 8-10: charge toward user max SoC, limited by the lower
        # of charger rating and EV onboard acceptance rate.
        remaining_kwh = (session.max_soc_pct - soc) / 100.0 * BATTERY_KWH
        step_kwh = min(session.charger_kw * STEP_MINUTES / 60.0, remaining_kwh)
        if step_kwh <= 0:
            break
        power[step] = round(step_kwh * 60.0 / STEP_MINUTES, 6)
        soc_by_ev[session.ev_id] = min(session.max_soc_pct, soc + step_kwh / BATTERY_KWH * 100.0)


def feeder_loading_pct(total_kw: float) -> float:
    return total_kw / 122.0 * 100.0


def feeder_loss_kw(total_kw: float) -> float:
    return 0.00055 * total_kw * total_kw


def feeder_min_voltage_pu(total_kw: float) -> float:
    return max(0.86, 0.997 - 0.00078 * total_kw)


def summarize_scenario(
    scenario: str,
    label: str,
    rows: list[dict],
    sessions: list[EVSession],
    power_by_step: dict[str, list[float]],
) -> dict:
    total_loads = [float(row["total_load_kw"]) for row in rows]
    loadings = [float(row["loading_pct"]) for row in rows]
    losses = [float(row["loss_kw"]) for row in rows]
    voltages = [float(row["min_voltage_pu"]) for row in rows]
    ev_values = [value for values in power_by_step.values() for value in values]
    charged_kwh = sum(max(0.0, value) * STEP_MINUTES / 60.0 for value in ev_values)
    discharged_kwh = sum(abs(min(0.0, value)) * STEP_MINUTES / 60.0 for value in ev_values)
    return {
        "scenario": scenario,
        "label": label,
        "ev_count": len(sessions),
        "charged_kwh": round(charged_kwh, 3),
        "v2g_discharged_kwh": round(discharged_kwh, 3),
        "load_min_kw": round(min(total_loads), 3),
        "load_avg_kw": round(mean(total_loads), 3),
        "load_max_kw": round(max(total_loads), 3),
        "loading_min_pct": round(min(loadings), 3),
        "loading_avg_pct": round(mean(loadings), 3),
        "loading_max_pct": round(max(loadings), 3),
        "loss_min_kw": round(min(losses), 4),
        "loss_avg_kw": round(mean(losses), 4),
        "loss_max_kw": round(max(losses), 4),
        "voltage_min_pu": round(min(voltages), 4),
        "voltage_avg_pu": round(mean(voltages), 4),
        "voltage_max_pu": round(max(voltages), 4),
    }


def run_benchmark(output_dir: str, seed: int, runs: int = DEFAULT_RUNS) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    run_summary_rows: list[dict] = []
    raw_timeseries_rows: list[dict] = []
    ev_rows: list[dict] = []

    for run in range(runs):
        for offset, (scenario, config) in enumerate(SCENARIOS.items()):
            run_seed = seed + run * 1000 + offset
            summary, rows, sessions = simulate_scenario(scenario, config, run_seed, run=run + 1)
            run_summary_rows.append(summary)
            raw_timeseries_rows.extend(rows)
            ev_rows.extend(sessions)

    summary_rows = aggregate_summary_rows(run_summary_rows, raw_timeseries_rows, runs)
    timeseries_rows = aggregate_timeseries_rows(raw_timeseries_rows, runs)

    write_csv(os.path.join(output_dir, "scenario_summary.csv"), summary_rows)
    write_csv(os.path.join(output_dir, "scenario_run_summary.csv"), run_summary_rows)
    write_csv(os.path.join(output_dir, "timeseries.csv"), timeseries_rows)
    write_csv(os.path.join(output_dir, "timeseries_runs.csv"), raw_timeseries_rows)
    write_csv(os.path.join(output_dir, "ev_sessions.csv"), ev_rows)

    report = {
        "benchmark": "Fakhrooeian and Pitz 2023 V2G scheduling scenarios",
        "implementation_scope": "Stochastic scheduling-equation and scenario-pattern replication with deterministic LV feeder proxy; not DIgSILENT PowerFactory replication.",
        "seed": seed,
        "runs": runs,
        "step_minutes": STEP_MINUTES,
        "sim_hours": SIM_HOURS,
        "paper_reference_values": "Benchmark/paper_reference_values.json",
        "scenarios": summary_rows,
    }
    with open(os.path.join(output_dir, "scenario_summary.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    write_pattern_report(output_dir, summary_rows)
    write_readme(output_dir, report)
    return report


def aggregate_timeseries_rows(rows: list[dict], runs: int) -> list[dict]:
    grouped: dict[tuple[str, int], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["scenario"], int(row["minute"])), []).append(row)

    aggregated: list[dict] = []
    for (scenario, minute), group in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        aggregated.append(
            {
                "runs": runs,
                "scenario": scenario,
                "minute": minute,
                "hour_of_day": round(mean(float(row["hour_of_day"]) for row in group), 3),
                "base_load_kw": round(mean(float(row["base_load_kw"]) for row in group), 3),
                "ev_power_kw": round(mean(float(row["ev_power_kw"]) for row in group), 3),
                "total_load_kw": round(mean(float(row["total_load_kw"]) for row in group), 3),
                "loading_pct": round(mean(float(row["loading_pct"]) for row in group), 3),
                "loss_kw": round(mean(float(row["loss_kw"]) for row in group), 4),
                "min_voltage_pu": round(mean(float(row["min_voltage_pu"]) for row in group), 4),
            }
        )
    return aggregated


def aggregate_summary_rows(run_rows: list[dict], raw_timeseries_rows: list[dict], runs: int) -> list[dict]:
    timeseries_rows = aggregate_timeseries_rows(raw_timeseries_rows, runs)
    by_scenario: dict[str, list[dict]] = {}
    run_by_scenario: dict[str, list[dict]] = {}
    for row in timeseries_rows:
        by_scenario.setdefault(row["scenario"], []).append(row)
    for row in run_rows:
        run_by_scenario.setdefault(row["scenario"], []).append(row)

    aggregated: list[dict] = []
    for scenario, config in SCENARIOS.items():
        rows = by_scenario[scenario]
        run_group = run_by_scenario[scenario]
        total_loads = [float(row["total_load_kw"]) for row in rows]
        loadings = [float(row["loading_pct"]) for row in rows]
        losses = [float(row["loss_kw"]) for row in rows]
        voltages = [float(row["min_voltage_pu"]) for row in rows]
        aggregated.append(
            {
                "scenario": scenario,
                "label": config["label"],
                "runs": runs,
                "ev_count_avg": round(mean(float(row["ev_count"]) for row in run_group), 3),
                "charged_kwh_avg": round(mean(float(row["charged_kwh"]) for row in run_group), 3),
                "v2g_discharged_kwh_avg": round(mean(float(row["v2g_discharged_kwh"]) for row in run_group), 3),
                "load_min_kw": round(min(total_loads), 3),
                "load_avg_kw": round(mean(total_loads), 3),
                "load_max_kw": round(max(total_loads), 3),
                "load_max_kw_run_avg": round(mean(float(row["load_max_kw"]) for row in run_group), 3),
                "loading_min_pct": round(min(loadings), 3),
                "loading_avg_pct": round(mean(loadings), 3),
                "loading_max_pct": round(max(loadings), 3),
                "loss_min_kw": round(min(losses), 4),
                "loss_avg_kw": round(mean(losses), 4),
                "loss_max_kw": round(max(losses), 4),
                "voltage_min_pu": round(min(voltages), 4),
                "voltage_avg_pu": round(mean(voltages), 4),
                "voltage_max_pu": round(max(voltages), 4),
            }
        )
    return aggregated


def write_csv(path: str, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_readme(output_dir: str, report: dict) -> None:
    lines = [
        "# Benchmark Results",
        "",
        "Benchmark: Fakhrooeian and Pitz 2023 V2G scheduling scenarios.",
        "",
        "Scope: stochastic scheduling-equation and scenario-pattern replication with a deterministic low-voltage feeder proxy. This is not an exact DIgSILENT PowerFactory replication.",
        "",
        "Reference targets from the paper's Tables 2-5 are stored in `Benchmark/paper_reference_values.json`. Use them to compare trends and ordering, not exact values.",
        "",
        f"Stochastic runs: {report['runs']}. Aggregate rows are computed from the mean load profile across runs; per-run values are in `scenario_run_summary.csv` and `timeseries_runs.csv`.",
        "",
        "| Scenario | Load max (kW) | Loading max (%) | Loss max (kW) | Min voltage (p.u.) | V2G discharged (kWh) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["scenarios"]:
        lines.append(
            "| {label} | {load_max_kw:.3f} | {loading_max_pct:.3f} | {loss_max_kw:.4f} | {voltage_min_pu:.4f} | {v2g_discharged_kwh_avg:.3f} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "Use these outputs as the reactive V2G benchmark family for comparison with AEI-V2G.",
            "The most defensible paper comparison is against Table 2 load profile trends first, then Tables 3-5 as proxy-supported grid-impact trends.",
        ]
    )
    with open(os.path.join(output_dir, "README_RESULTS.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def load_reference_values() -> dict:
    with open(REFERENCE_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_pattern_report(output_dir: str, rows: list[dict]) -> None:
    reference = load_reference_values()
    paper_load = reference["tables"]["table_2_total_load_kw"]
    by_scenario = {row["scenario"]: row for row in rows}
    scenario_order = [
        "scenario_1_worst_case",
        "scenario_2_v2g_no_operator_control",
        "scenario_3_v2g_operator_full_power",
        "scenario_4_v2g_operator_limited_power",
    ]
    lines = [
        "# Benchmark Pattern Report",
        "",
        "This report compares our scheduling-level benchmark outputs with the paper's published Table 2 total-load pattern.",
        "Exact numerical matching is not expected because the original DIgSILENT Feeder 242 model and BDEW load-profile exports are not available.",
        "",
        "## Table 2 Pattern Target",
        "",
        "The paper's peak-load ordering is:",
        "",
        "```text",
        "Scenario 1 worst-case > Scenario 2 V2G no control > Scenario 3 operator full power > Scenario 4 operator limited power",
        "```",
        "",
        "| Scenario | Paper max load (kW) | Our max load (kW) |",
        "|---|---:|---:|",
    ]
    for scenario in scenario_order:
        lines.append(
            f"| {scenario} | {paper_load[scenario]['max']:.3f} | {by_scenario[scenario]['load_max_kw']:.3f} |"
        )
    our_order = sorted(scenario_order, key=lambda item: by_scenario[item]["load_max_kw"], reverse=True)
    paper_order = sorted(scenario_order, key=lambda item: paper_load[item]["max"], reverse=True)
    lines.extend(
        [
            "",
            f"Paper ordering: `{', '.join(paper_order)}`",
            f"Our ordering: `{', '.join(our_order)}`",
            "",
            "Pattern status: " + ("MATCH" if our_order == paper_order else "PARTIAL - inspect load-profile assumptions"),
            "",
            "## Defensible Use",
            "",
            "- Use Table 2 as the primary benchmark target because our implementation directly produces comparable total-load profiles.",
            "- Use Tables 3-5 only as qualitative/proxy-supported targets unless a real load-flow model is added.",
        ]
    )
    with open(os.path.join(output_dir, "PATTERN_REPORT.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="reports/benchmark_fakhrooeian_pitz")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    args = parser.parse_args()
    report = run_benchmark(args.output_dir, args.seed, runs=args.runs)
    print(json.dumps({"output_dir": args.output_dir, "scenarios": len(report["scenarios"])}, indent=2))


if __name__ == "__main__":
    main()
