from Benchmark.run_fakhrooeian_pitz import run_benchmark


def test_fakhrooeian_pitz_benchmark_outputs(tmp_path):
    report = run_benchmark(str(tmp_path), seed=7, runs=3)

    assert len(report["scenarios"]) == 4
    assert (tmp_path / "scenario_summary.csv").exists()
    assert (tmp_path / "scenario_run_summary.csv").exists()
    assert (tmp_path / "timeseries.csv").exists()
    assert (tmp_path / "timeseries_runs.csv").exists()
    assert (tmp_path / "ev_sessions.csv").exists()
    assert (tmp_path / "README_RESULTS.md").exists()

    by_name = {row["scenario"]: row for row in report["scenarios"]}
    assert by_name["scenario_1_worst_case"]["v2g_discharged_kwh_avg"] == 0.0
    assert by_name["scenario_2_v2g_no_operator_control"]["v2g_discharged_kwh_avg"] > 0.0
    assert by_name["scenario_4_v2g_operator_limited_power"]["load_max_kw"] < by_name["scenario_1_worst_case"]["load_max_kw"]
