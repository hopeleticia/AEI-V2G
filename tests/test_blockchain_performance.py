from eval.blockchain_performance import DEPLOYMENT_PROOF_WARNING, build_performance_rows, write_blockchain_performance


def test_deployment_proof_fallback_reports_warning(tmp_path):
    summary = {
        "outputs": {},
        "scenarios": [
            {
                "scenario": "weekday_nominal",
                "credit_ledger_mode": "on_chain",
            }
        ],
    }
    details = {
        "weekday_nominal": {
            "components": {
                "lava_decision_engine": {"latency_ms_p95": 0.024},
                "v2g_settlement": {
                    "credit_ledger_transactions": 1,
                    "credit_ledger_failures": 0,
                    "credit_ledger_statuses": {"success": 1},
                },
                "blockchain_settlement": {
                    "proof_type": "deployment_transaction",
                    "transaction_hash": "0x" + "1" * 64,
                    "block_number": 10,
                    "status": "success",
                    "contract_address": "0x" + "2" * 40,
                    "chain_id": 900520900520,
                },
            }
        }
    }

    payload = write_blockchain_performance(tmp_path, summary, details)

    assert DEPLOYMENT_PROOF_WARNING in payload["warnings"]
    assert payload["aggregate"]["successful_transactions"] == 1
    assert payload["aggregate"]["settlement_success_rate_pct"] == 100.0
    assert (tmp_path / "blockchain_performance.json").exists()
    assert (tmp_path / "blockchain_performance.csv").exists()
    assert (tmp_path / "figures" / "fig_blockchain_latency.png").exists()
    assert (tmp_path / "figures" / "fig_blockchain_throughput.png").exists()


def test_scenario_receipt_latency_fields_are_preserved():
    summary = {"outputs": {}, "scenarios": [{"scenario": "event_surge"}]}
    details = {
        "event_surge": {
            "components": {
                "lava_decision_engine": {"latency_ms_p95": 0.03},
                "v2g_settlement": {
                    "credit_ledger_transactions": 1,
                    "credit_ledger_failures": 0,
                    "credit_ledger_statuses": {"success": 1},
                    "settlement_receipt": {
                        "transaction_submission_latency_ms": 4.5,
                        "transaction_confirmation_latency_ms": 200.0,
                        "transaction_total_latency_ms": 205.0,
                    },
                },
                "blockchain_settlement": {
                    "proof_type": "scenario_settlement",
                    "transaction_hash": "0x" + "3" * 64,
                    "block_number": 20,
                    "status": "success",
                },
            }
        }
    }

    row = build_performance_rows(summary, details)[0]

    assert row["transaction_submission_latency_ms"] == 4.5
    assert row["transaction_confirmation_latency_ms"] == 200.0
    assert row["transaction_total_latency_ms"] == 205.0
    assert row["blockchain_throughput_tps"] == round(1 / 0.205, 6)
    assert row["warning"] == ""
