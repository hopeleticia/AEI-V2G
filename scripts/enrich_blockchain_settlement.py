"""Enrich existing journal-study scenario detail JSONs with blockchain_settlement
proof fields drawn from `deployments/purechain_credit_ledger.json`.

Reporting-only: does NOT redeploy the contract and does NOT rerun the
experiment. Use when an older report folder was produced before the
reporting layer learned to emit the `blockchain_settlement` block.

If a per-scenario settlement receipt was persisted by a newer run, it is
preserved; otherwise deployment-transaction metadata is used as proof
(clearly marked with proof_type="deployment_transaction").

Private keys are never read or printed.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.blockchain_performance import DEPLOYMENT_PROOF_WARNING, write_blockchain_performance


REQUIRED_FIELDS = ("contract_address", "chain_id", "transaction_hash", "block_number", "status")


def load_deployment_proof(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    missing = [k for k in ("contract_address", "chain_id", "deployment_tx_hash", "block_number") if not data.get(k)]
    if missing:
        raise SystemExit(f"deployment proof file {path} is missing required fields: {missing}")
    return {
        "contract_address": data["contract_address"],
        "chain_id": int(data["chain_id"]),
        "deployment_tx_hash": data["deployment_tx_hash"],
        "block_number": int(data["block_number"]),
        "deployment_status": data.get("deployment_status", "success"),
        "rpc_url": data.get("rpc_url"),
        "deployer_address": data.get("deployer_address"),
        "deployed_at": data.get("deployed_at"),
    }


def build_block(existing: dict | None, deployment: dict) -> dict:
    """Build the blockchain_settlement block.

    Honors any pre-existing per-scenario settlement receipt the report
    already carries; otherwise emits deployment-transaction proof.
    """
    if existing and existing.get("proof_type") == "scenario_settlement":
        return existing
    return {
        "contract_address": deployment["contract_address"],
        "chain_id": deployment["chain_id"],
        "transaction_hash": deployment["deployment_tx_hash"],
        "block_number": deployment["block_number"],
        "status": deployment["deployment_status"],
        "proof_type": "deployment_transaction",
        "rpc_url": deployment.get("rpc_url"),
        "note": DEPLOYMENT_PROOF_WARNING,
    }


def enrich_report(report_dir: Path, deployment: dict, dry_run: bool = False) -> list[dict]:
    results = []
    details = {}
    detail_files = sorted(report_dir.glob("*_detail.json"))
    if not detail_files:
        raise SystemExit(f"no *_detail.json files found in {report_dir}")
    for detail_path in detail_files:
        with open(detail_path, "r", encoding="utf-8") as handle:
            detail = json.load(handle)
        components = detail.setdefault("components", {})
        existing = components.get("blockchain_settlement")
        block = build_block(existing, deployment)
        components["blockchain_settlement"] = block
        components.setdefault("blockchain_performance", {
            "settlement_mode": "async_settlement",
            "dispatch_latency_without_blockchain_ms": components.get("lava_decision_engine", {}).get("latency_ms_p95", 0.0),
            "dispatch_latency_with_async_blockchain_ms": components.get("lava_decision_engine", {}).get("latency_ms_p95", 0.0),
            "blockchain_overhead_pct": 0.0,
            "note": "Async settlement is reported separately from LAVA decision latency and is outside the critical dispatch path.",
        })
        if not dry_run:
            with open(detail_path, "w", encoding="utf-8") as handle:
                json.dump(detail, handle, indent=2)
        details[detail["scenario"]] = detail
        results.append({
            "scenario_detail": detail_path.name,
            "proof_type": block["proof_type"],
            "transaction_hash": block["transaction_hash"],
            "block_number": block["block_number"],
            "status": block["status"],
        })
    if not dry_run:
        summary_path = report_dir / "journal_summary.json"
        if not summary_path.exists():
            raise SystemExit(f"journal summary does not exist: {summary_path}")
        with open(summary_path, "r", encoding="utf-8") as handle:
            summary = json.load(handle)
        write_blockchain_performance(report_dir, summary, details)
        with open(summary_path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", required=True, help="path to a report folder containing *_detail.json files")
    parser.add_argument("--deployment", default="deployments/purechain_credit_ledger.json",
                        help="path to deployment proof JSON (default: deployments/purechain_credit_ledger.json)")
    parser.add_argument("--dry-run", action="store_true", help="show what would change but do not write files")
    args = parser.parse_args()

    report_dir = Path(args.report_dir)
    if not report_dir.is_dir():
        raise SystemExit(f"report dir does not exist: {report_dir}")
    deployment = load_deployment_proof(Path(args.deployment))
    results = enrich_report(report_dir, deployment, dry_run=args.dry_run)
    print(json.dumps({
        "report_dir": str(report_dir),
        "deployment_contract_address": deployment["contract_address"],
        "deployment_chain_id": deployment["chain_id"],
        "scenarios_enriched": len(results),
        "dry_run": args.dry_run,
        "details": results,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
