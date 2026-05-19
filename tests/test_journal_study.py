import pytest
import yaml

from eval.run_journal_study import run_study


def test_journal_study_writes_component_reports(tmp_path):
    summary = run_study("config/corridor_config.yaml", 1800, str(tmp_path))
    assert summary["scenario_count"] == 5
    assert (tmp_path / "scenario_comparison.csv").exists()
    assert (tmp_path / "component_metrics.csv").exists()
    assert (tmp_path / "station_metrics.csv").exists()
    assert (tmp_path / "provenance.json").exists()
    assert (tmp_path / "inputs" / "corridor_config.yaml").exists()
    assert (tmp_path / "weekday_nominal_trace.csv").exists()
    assert summary["artifact_policy"].startswith("paper-facing")
    assert summary["required_data_sources"][0]["config_key"] == "grid.load_profile_csv"
    assert summary["scenarios"][0]["chain_valid"] is True


def test_journal_study_requires_referenced_caiso_csv(tmp_path):
    with open("config/corridor_config.yaml", "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    config["grid"]["load_profile_csv"] = "data/grid_profiles/missing_caiso_for_test.csv"
    config_path = tmp_path / "missing_caiso_config.yaml"
    with open(config_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle)

    with pytest.raises(FileNotFoundError, match="CAISO CSV was not found"):
        run_study(str(config_path), 1800, str(tmp_path / "report"))
