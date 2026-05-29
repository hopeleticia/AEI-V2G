from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from statistics import mean
from typing import Any

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError as exc:
    plt = None
    _MATPLOTLIB_IMPORT_ERROR = exc
else:
    _MATPLOTLIB_IMPORT_ERROR = None


DEPLOYMENT_PROOF_WARNING = (
    "Current report uses deployment_transaction proof; per-scenario settlement receipt metrics require a new experiment run."
)

REQUIRED_PERFORMANCE_FIELDS = (
    "transaction_submission_latency_ms",
    "transaction_confirmation_latency_ms",
    "transaction_total_latency_ms",
    "blockchain_throughput_tps",
    "successful_transactions",
    "failed_transactions",
    "pending_transactions",
    "settlement_success_rate_pct",
    "dispatch_latency_without_blockchain_ms",
    "dispatch_latency_with_async_blockchain_ms",
    "blockchain_overhead_pct",
)


def build_performance_rows(summary: dict, details: dict[str, dict]) -> list[dict]:
    rows = []
    for scenario in summary.get("scenarios", []):
        name = scenario["scenario"]
        detail = details.get(name, {})
        components = detail.get("components", {})
        settlement = components.get("blockchain_settlement", {})
        v2g = components.get("v2g_settlement", {})
        lava = components.get("lava_decision_engine", {})
        receipt = v2g.get("settlement_receipt") or {}
        missing_receipt = not isinstance(receipt, dict) or not receipt
        if not isinstance(receipt, dict):
            receipt = {}
        proof_type = settlement.get("proof_type", "missing")
        warning = DEPLOYMENT_PROOF_WARNING if proof_type == "deployment_transaction" else ""

        successful, failed, pending = transaction_counts(v2g, settlement, scenario.get("credit_ledger_mode"))
        success_rate = success_rate_pct(successful, failed, pending)
        submission_ms = number_or_none(receipt.get("transaction_submission_latency_ms"))
        confirmation_ms = number_or_none(receipt.get("transaction_confirmation_latency_ms"))
        total_ms = number_or_none(receipt.get("transaction_total_latency_ms"))
        throughput = throughput_tps(successful + failed, total_ms)
        dispatch_without = number_or_zero(lava.get("latency_ms_p95"))
        async_dispatch = number_or_zero(
            components.get("blockchain_performance", {}).get("dispatch_latency_with_async_blockchain_ms"),
            dispatch_without,
        )

        rows.append(
            {
                "scenario": name,
                "settlement_mode": components.get("blockchain_performance", {}).get("settlement_mode", "async_settlement"),
                "proof_type": proof_type,
                "warning": warning,
                "transaction_submission_latency_ms": submission_ms,
                "transaction_confirmation_latency_ms": confirmation_ms,
                "transaction_total_latency_ms": total_ms,
                "blockchain_throughput_tps": throughput,
                "successful_transactions": successful,
                "failed_transactions": failed,
                "pending_transactions": pending,
                "settlement_success_rate_pct": success_rate,
                "dispatch_latency_without_blockchain_ms": dispatch_without,
                "dispatch_latency_with_async_blockchain_ms": async_dispatch,
                "blockchain_overhead_pct": overhead_pct(dispatch_without, async_dispatch),
                "tx_hash": settlement.get("transaction_hash"),
                "block_number": settlement.get("block_number"),
                "receipt_status": "missing_receipt" if missing_receipt else settlement.get("status"),
                "contract_address": settlement.get("contract_address"),
                "chain_id": settlement.get("chain_id"),
            }
        )
    return rows


def write_blockchain_performance(report_dir: str | Path, summary: dict, details: dict[str, dict]) -> dict:
    report_path = Path(report_dir)
    rows = build_performance_rows(summary, details)
    aggregate = aggregate_rows(rows)
    payload = {
        "research_framing": (
            "AEI-V2G keeps real-time decisions at the edge. PureChain is evaluated as asynchronous "
            "settlement, auditability, credit accountability, and transaction verification."
        ),
        "default_settlement_mode": "async_settlement",
        "comparison_modes": {
            "async_settlement": "Dispatch continues immediately; blockchain settlement is outside the critical path.",
            "sync_settlement": "Dispatch waits for blockchain confirmation; comparison baseline only.",
        },
        "warnings": sorted({row["warning"] for row in rows if row.get("warning")}),
        "aggregate": aggregate,
        "scenarios": rows,
    }
    with open(report_path / "blockchain_performance.json", "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    write_performance_csv(report_path / "blockchain_performance.csv", rows)
    write_blockchain_figures(report_path, rows)
    summary["outputs"]["blockchain_performance_json"] = "blockchain_performance.json"
    summary["outputs"]["blockchain_performance_csv"] = "blockchain_performance.csv"
    summary["outputs"]["blockchain_latency_figure"] = "figures/fig_blockchain_latency.png"
    summary["outputs"]["blockchain_throughput_figure"] = "figures/fig_blockchain_throughput.png"
    summary["blockchain_performance"] = aggregate | {"warnings": payload["warnings"]}
    return payload


def write_performance_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_blockchain_figures(report_dir: Path, rows: list[dict]) -> list[str]:
    if plt is None:
        raise RuntimeError("matplotlib is required to generate blockchain performance figures") from _MATPLOTLIB_IMPORT_ERROR
    figure_dir = report_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    return [
        plot_latency(rows, figure_dir / "fig_blockchain_latency.png"),
        plot_throughput(rows, figure_dir / "fig_blockchain_throughput.png"),
    ]


def plot_latency(rows: list[dict], path: Path) -> str:
    labels = [label(row["scenario"]) for row in rows]
    dispatch = [float(row["dispatch_latency_without_blockchain_ms"] or 0.0) for row in rows]
    confirmation = [float(row["transaction_confirmation_latency_ms"] or 0.0) for row in rows]
    total = [float(row["transaction_total_latency_ms"] or 0.0) for row in rows]
    x = range(len(rows))
    width = 0.25
    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    ax.bar([i - width for i in x], dispatch, width, label="Edge dispatch P95", color="#2F6B8F")
    ax.bar(x, confirmation, width, label="Chain confirmation", color="#B8872B")
    ax.bar([i + width for i in x], total, width, label="Chain total", color="#725C9A")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("PureChain Settlement Latency vs Edge Dispatch")
    ax.set_xticks(list(x), labels, rotation=18, ha="right")
    ax.legend(frameon=False)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def plot_throughput(rows: list[dict], path: Path) -> str:
    labels = [label(row["scenario"]) for row in rows]
    throughput = [float(row["blockchain_throughput_tps"] or 0.0) for row in rows]
    success_rate = [float(row["settlement_success_rate_pct"] or 0.0) for row in rows]
    x = range(len(rows))
    fig, ax1 = plt.subplots(figsize=(10.5, 5.5))
    ax2 = ax1.twinx()
    ax1.bar(x, throughput, color="#3B7C5A", alpha=0.88, label="Throughput")
    ax2.plot(x, success_rate, marker="o", linewidth=2.4, color="#B44E4E", label="Success rate")
    ax1.set_ylabel("Transactions per second")
    ax2.set_ylabel("Settlement success rate (%)")
    ax1.set_title("PureChain Settlement Throughput and Success Rate")
    ax1.set_xticks(list(x), labels, rotation=18, ha="right")
    style_axes(ax1)
    ax2.spines["top"].set_visible(False)
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def aggregate_rows(rows: list[dict]) -> dict:
    successful = sum(int(row["successful_transactions"]) for row in rows)
    failed = sum(int(row["failed_transactions"]) for row in rows)
    pending = sum(int(row["pending_transactions"]) for row in rows)
    totals = [row["transaction_total_latency_ms"] for row in rows if row["transaction_total_latency_ms"] is not None]
    throughput_values = [row["blockchain_throughput_tps"] for row in rows if row["blockchain_throughput_tps"] is not None]
    overhead_values = [float(row["blockchain_overhead_pct"] or 0.0) for row in rows]
    return {
        "transaction_submission_latency_ms": avg_non_null(row["transaction_submission_latency_ms"] for row in rows),
        "transaction_confirmation_latency_ms": avg_non_null(row["transaction_confirmation_latency_ms"] for row in rows),
        "transaction_total_latency_ms": avg_non_null(totals),
        "blockchain_throughput_tps": round(sum(throughput_values), 6) if throughput_values else None,
        "successful_transactions": successful,
        "failed_transactions": failed,
        "pending_transactions": pending,
        "settlement_success_rate_pct": success_rate_pct(successful, failed, pending),
        "dispatch_latency_without_blockchain_ms": avg_non_null(row["dispatch_latency_without_blockchain_ms"] for row in rows),
        "dispatch_latency_with_async_blockchain_ms": avg_non_null(row["dispatch_latency_with_async_blockchain_ms"] for row in rows),
        "blockchain_overhead_pct": round(mean(overhead_values), 6) if overhead_values else 0.0,
    }


def transaction_counts(v2g: dict, settlement: dict, credit_ledger_mode: str | None = None) -> tuple[int, int, int]:
    statuses = v2g.get("credit_ledger_statuses", {})
    successful = int(statuses.get("success", 0) or 0)
    failed = int(v2g.get("credit_ledger_failures", 0) or statuses.get("failed", 0) or 0)
    pending = int(statuses.get("submitted", 0) or statuses.get("pending", 0) or 0)
    if successful == 0 and credit_ledger_mode == "on_chain" and settlement.get("status") == "success":
        successful = int(v2g.get("credit_ledger_transactions", 0) or 1)
    if failed == 0 and settlement.get("status") == "failed":
        failed = 1
    return successful, failed, pending


def success_rate_pct(successful: int, failed: int, pending: int) -> float:
    total = successful + failed + pending
    return round(successful / total * 100.0, 2) if total else 0.0


def throughput_tps(transaction_count: int, total_latency_ms: float | None) -> float | None:
    if total_latency_ms is None or total_latency_ms <= 0 or transaction_count <= 0:
        return None
    return round(transaction_count / (total_latency_ms / 1000.0), 6)


def overhead_pct(dispatch_without: float, dispatch_with: float) -> float:
    if dispatch_without <= 0:
        return 0.0
    return round((dispatch_with - dispatch_without) / dispatch_without * 100.0, 6)


def avg_non_null(values: Any) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    return round(sum(numeric) / len(numeric), 6) if numeric else None


def number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def number_or_zero(value: Any, default: float = 0.0) -> float:
    parsed = number_or_none(value)
    return default if parsed is None else parsed


def label(scenario: str) -> str:
    labels = {
        "weekday_nominal": "Weekday",
        "evening_peak_v2g": "Evening peak",
        "event_surge": "Event surge",
        "rural_degraded_isac": "Rural ISAC",
        "wan_outage_edge_only": "WAN outage",
    }
    return labels.get(scenario, scenario)


def style_axes(ax) -> None:
    ax.grid(axis="y", color="#D7DCE0", linewidth=0.8, alpha=0.75)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
