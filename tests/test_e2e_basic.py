from integration.coordinator import run


def test_e2e_metrics_are_reported(tmp_path):
    report = run("config/corridor_config.yaml", 1800, str(tmp_path / "metrics.json"), str(tmp_path / "chain.jsonl"))
    metrics = report["metrics"]
    assert metrics["decision_latency_ms_max"] < 200
    assert "grid_stress_reduction_pct" in metrics
    assert metrics["blockchain_consensus_pct"] == 100.0
