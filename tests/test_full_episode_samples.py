import importlib.util
from pathlib import Path

from integration.coordinator import run
from metrics.evaluator import evaluate_episode


def _comparison_module():
    path = Path(__file__).resolve().parent.parent / "eval" / "run_comparison.py"
    spec = importlib.util.spec_from_file_location("run_comparison", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_coordinator_keeps_compact_samples_and_full_episode_samples(tmp_path):
    report = run(
        "config/corridor_config.yaml",
        1800,
        str(tmp_path / "metrics.json"),
        str(tmp_path / "chain.jsonl"),
    )

    assert report["sample_count"] == 30
    assert len(report["full_samples"]) == 30
    assert len(report["samples"]) == 10
    assert report["samples"] == report["full_samples"][-10:]


def test_comparison_metrics_prefer_full_samples_over_compact_tail():
    run_comparison = _comparison_module()
    report = {
        "metrics": {"evs_served": 4, "v2g_utilization_pct": 25.0},
        "samples": [
            {"actual_kw": 10.0, "grid_stress": 0.1, "latency_ms": 1.0, "v2g_revenue": 1.0},
        ],
        "full_samples": [
            {"actual_kw": 10.0, "grid_stress": 0.1, "latency_ms": 1.0, "v2g_revenue": 1.0},
            {"actual_kw": 90.0, "grid_stress": 0.9, "latency_ms": 3.0, "v2g_revenue": 2.0},
        ],
    }

    metrics = run_comparison._episode_metrics(report)

    assert metrics["sample_count"] == 2
    assert metrics["stress_peaks"] == 1
    assert metrics["v2g_revenue"] == 3.0
    assert metrics["mean_latency_ms"] == 2.0


def test_evaluator_prefers_full_samples_when_report_also_has_compact_tail():
    metrics = evaluate_episode(
        {
            "samples": [{"minute": 9, "actual_kw": 100.0}],
            "full_samples": [
                {"minute": 0, "actual_kw": 10.0},
                {"minute": 1, "actual_kw": 20.0},
            ],
        },
        tick_minutes=60.0,
    )

    assert metrics["par"]["sample_count"] == 2
    assert metrics["par"]["peak_kw"] == 20.0
