from eval.run_journal_study import run_study
from eval.validate_journal_results import validate_results


def test_validate_journal_results_passes(tmp_path):
    run_study("config/corridor_config.yaml", 1800, str(tmp_path))
    validation = validate_results(str(tmp_path))
    assert validation["passed"] is True
    assert validation["scenarios_checked"] == 5
