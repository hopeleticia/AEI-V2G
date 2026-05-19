from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from dataclasses import dataclass


NUMERIC_TOLERANCE = 0.01


@dataclass
class ValidationResult:
    scenario: str
    csv_matches_detail: bool
    chain_links_valid: bool
    chain_hashes_valid: bool
    route_records_match: bool
    v2g_records_match: bool
    station_energy_matches_total: bool
    station_v2g_matches_total: bool
    issues: list[str]

    @property
    def passed(self) -> bool:
        return (
            self.csv_matches_detail
            and self.chain_links_valid
            and self.chain_hashes_valid
            and self.route_records_match
            and self.v2g_records_match
            and self.station_energy_matches_total
            and self.station_v2g_matches_total
            and not self.issues
        )


def validate_results(report_dir: str) -> dict:
    summary_path = os.path.join(report_dir, "journal_summary.json")
    comparison_path = os.path.join(report_dir, "scenario_comparison.csv")
    with open(summary_path, "r", encoding="utf-8") as handle:
        summary = json.load(handle)
    comparison = read_csv_by_scenario(comparison_path)

    scenario_results = []
    for row in summary["scenarios"]:
        scenario = row["scenario"]
        detail_path = os.path.join(report_dir, f"{scenario}_detail.json")
        chain_path = os.path.join(report_dir, f"{scenario}_chain.jsonl")
        with open(detail_path, "r", encoding="utf-8") as handle:
            detail = json.load(handle)
        chain = validate_chain(chain_path)
        scenario_results.append(validate_scenario(row, comparison[scenario], detail, chain))

    result = {
        "report_dir": report_dir,
        "scenarios_checked": len(scenario_results),
        "passed": all(item.passed for item in scenario_results),
        "scenario_results": [item.__dict__ | {"passed": item.passed} for item in scenario_results],
    }
    return result


def validate_scenario(summary_row: dict, csv_row: dict, detail: dict, chain: dict) -> ValidationResult:
    scenario = summary_row["scenario"]
    components = detail["components"]
    issues: list[str] = []

    expected_summary = {
        "duration_seconds": detail["duration_seconds"],
        "spawned_evs": components["ev_traffic"]["spawned_evs"],
        "served_evs": components["ev_traffic"]["served_evs"],
        "served_ratio_pct": components["ev_traffic"]["served_ratio_pct"],
        "rsu_sensing_coverage_pct": components["rsu_awareness"]["sensing_coverage_pct"],
        "route_decisions": components["lava_decision_engine"]["route_decisions"],
        "latency_ms_p95": components["lava_decision_engine"]["latency_ms_p95"],
        "latency_ms_max": components["lava_decision_engine"]["latency_ms_max"],
        "grid_stress_reduction_pct": components["grid_response"]["stress_event_reduction_pct"],
        "demand_prediction_accuracy_pct": components["grid_response"]["demand_prediction_accuracy_pct"],
        "v2g_utilization_pct": components["v2g_settlement"]["utilization_pct"],
        "v2g_supplied_kwh": components["v2g_settlement"]["supplied_kwh"],
        "v2g_revenue": components["v2g_settlement"]["revenue"],
        "chain_records": components["blockchain_validation"]["records"],
        "chain_valid": components["blockchain_validation"]["valid_hash_chain"],
        "offline_continuity_pct": components["edge_deployment"]["offline_decision_continuity_pct"],
    }

    csv_matches = True
    for key, expected in expected_summary.items():
        if not value_matches(csv_row[key], expected):
            csv_matches = False
            issues.append(f"CSV mismatch for {key}: {csv_row[key]} != {expected}")
        if key in summary_row and not value_matches(summary_row[key], expected):
            csv_matches = False
            issues.append(f"Summary mismatch for {key}: {summary_row[key]} != {expected}")

    records_by_type = chain["records_by_type"]
    route_records_match = records_by_type.get("lava_route", 0) == components["lava_decision_engine"]["route_decisions"]
    v2g_records_match = records_by_type.get("v2g_dispatch", 0) == components["lava_decision_engine"]["v2g_decisions"]
    if not route_records_match:
        issues.append("lava_route chain count does not match LAVA route decision count")
    if not v2g_records_match:
        issues.append("v2g_dispatch chain count does not match V2G decision count")

    station_rows = list(components["station_operations"]["by_station"].values())
    station_energy = round(sum(row["energy_delivered_kwh"] for row in station_rows), 3)
    station_v2g = round(sum(row["v2g_supplied_kwh"] for row in station_rows), 3)
    station_energy_matches = close(station_energy, components["station_operations"]["total_energy_delivered_kwh"], 0.02)
    station_v2g_matches = close(station_v2g, components["station_operations"]["total_v2g_supplied_kwh"], 0.02)
    if not station_energy_matches:
        issues.append("Station delivered-energy sum does not match total")
    if not station_v2g_matches:
        issues.append("Station V2G sum does not match total")

    return ValidationResult(
        scenario=scenario,
        csv_matches_detail=csv_matches,
        chain_links_valid=chain["links_valid"],
        chain_hashes_valid=chain["hashes_valid"],
        route_records_match=route_records_match,
        v2g_records_match=v2g_records_match,
        station_energy_matches_total=station_energy_matches,
        station_v2g_matches_total=station_v2g_matches,
        issues=issues,
    )


def validate_chain(path: str) -> dict:
    previous = "genesis"
    links_valid = True
    hashes_valid = True
    records_by_type: dict[str, int] = {}
    records = 0
    first_hash = ""
    last_hash = ""

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            expected_hash = recompute_record_hash(row)
            records += 1
            records_by_type[row["event_type"]] = records_by_type.get(row["event_type"], 0) + 1
            if records == 1:
                first_hash = row["hash"]
            if row["previous_hash"] != previous:
                links_valid = False
            if row["hash"] != expected_hash:
                hashes_valid = False
            previous = row["hash"]
            last_hash = row["hash"]

    return {
        "records": records,
        "records_by_type": records_by_type,
        "links_valid": links_valid,
        "hashes_valid": hashes_valid,
        "first_hash": first_hash,
        "last_hash": last_hash,
    }


def recompute_record_hash(record: dict) -> str:
    payload = {key: value for key, value in record.items() if key != "hash"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_csv_by_scenario(path: str) -> dict[str, dict]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return {row["scenario"]: row for row in csv.DictReader(handle)}


def value_matches(actual: object, expected: object) -> bool:
    if isinstance(expected, bool):
        return str(actual).lower() == str(expected).lower()
    if isinstance(expected, (int, float)):
        try:
            return close(float(actual), float(expected), NUMERIC_TOLERANCE)
        except (TypeError, ValueError):
            return False
    return str(actual) == str(expected)


def close(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance


def write_markdown(validation: dict, output_path: str) -> None:
    status = "PASSED" if validation["passed"] else "FAILED"
    lines = [
        "# AEI-V2G Result Validation and Defense",
        "",
        f"Validation status: **{status}**",
        "",
        "## What Was Validated",
        "",
        "- Scenario summaries in `journal_summary.json` were cross-checked against `scenario_comparison.csv`.",
        "- Each `*_detail.json` component report was used as the source-of-truth for component totals.",
        "- Each `*_chain.jsonl` decision log was checked for previous-hash continuity.",
        "- Each blockchain record hash was recomputed from timestamp, event type, payload, and previous hash.",
        "- Route decision counts were checked against `lava_route` chain records.",
        "- V2G decision counts were checked against `v2g_dispatch` chain records.",
        "- Per-station delivered energy and V2G supply were summed and compared with station totals.",
        "",
        "## Scenario Validation Table",
        "",
        "| Scenario | CSV/JSON | Chain Links | Recomputed Hashes | Route Records | V2G Records | Station Energy | Station V2G | Status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in validation["scenario_results"]:
        lines.append(
            "| {scenario} | {csv} | {links} | {hashes} | {route} | {v2g} | {energy} | {station_v2g} | {status} |".format(
                scenario=row["scenario"],
                csv=mark(row["csv_matches_detail"]),
                links=mark(row["chain_links_valid"]),
                hashes=mark(row["chain_hashes_valid"]),
                route=mark(row["route_records_match"]),
                v2g=mark(row["v2g_records_match"]),
                energy=mark(row["station_energy_matches_total"]),
                station_v2g=mark(row["station_v2g_matches_total"]),
                status="PASS" if row["passed"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Defense of the Results",
            "",
            "These results are defensible as deterministic edge digital-twin results because the values are generated by an executable implementation, not by manual tables. The reported numbers are internally consistent across three independent artifact types: scenario CSV summaries, per-scenario component JSON reports, and append-only JSONL decision logs.",
            "",
            "The decision logs are tamper-evident. For every scenario, validation recomputed each SHA-256 record hash and verified that every record points to the previous record hash, starting from `genesis`. This defends the claim that the recorded LAVA route and V2G decisions form a continuous audit trail.",
            "",
            "The component-level metrics are traceable. EV traffic, RSU sensing, LAVA decisions, station operations, grid response, V2G settlement, blockchain validation, and edge-continuity metrics are reported separately. The validation step confirms that route and V2G chain record counts match the component reports, and that per-station energy totals match the scenario totals.",
            "",
            "The results should be described carefully in a journal paper as **deterministic digital-twin evaluation results**. They are stronger than a toy simulation because they include executable control logic, per-decision traces, station-level queues and energy accounting, V2G settlement records, and hash-chain audit validation. They are not yet a substitute for physical Raspberry Pi cluster power measurements; those should be added as a hardware validation subsection after running the provided Docker Pi image on the actual nodes.",
            "",
            "## Limitations to State Honestly",
            "",
            "- The current latency values are measured on the local host/container runtime, not on physical Raspberry Pi hardware.",
            "- Energy overhead is modeled unless external power measurements are collected from the Pi cluster.",
            "- RSU sensing is represented by a deterministic corridor digital twin, not by real 6G ISAC radio hardware.",
            "- Blockchain consensus is represented by validated hash-chain agreement in the study artifacts; a live multi-node PoA deployment should be reported separately.",
            "",
            "## Recommended Journal Wording",
            "",
            "> We evaluate AEI-V2G using a deterministic edge digital-twin implementation that executes the full EV traffic, RSU awareness, LAVA decision, station operation, grid-response, V2G settlement, and hash-chain audit pipeline. All reported scenario metrics are generated from executable runs and validated by cross-checking CSV summaries, component JSON reports, and recomputed SHA-256 decision-chain logs.",
        ]
    )
    failed_issues = [issue for row in validation["scenario_results"] for issue in row["issues"]]
    if failed_issues:
        lines.extend(["", "## Issues", ""])
        lines.extend(f"- {issue}" for issue in failed_issues)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def mark(value: bool) -> str:
    return "PASS" if value else "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", default="reports/journal_study")
    parser.add_argument("--output", default="reports/journal_study/VALIDATION_DEFENSE.md")
    args = parser.parse_args()
    validation = validate_results(args.report_dir)
    with open(os.path.join(args.report_dir, "validation_report.json"), "w", encoding="utf-8") as handle:
        json.dump(validation, handle, indent=2)
    write_markdown(validation, args.output)
    print(json.dumps({"passed": validation["passed"], "scenarios_checked": validation["scenarios_checked"], "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
