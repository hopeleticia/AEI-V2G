from pathlib import Path

import pytest

from eval.plot_journal_results import plot_all
from eval.run_journal_study import run_study


def test_plot_journal_results_generates_figures(tmp_path):
    pytest.importorskip("matplotlib.pyplot", reason="matplotlib is optional for figure generation")
    report_dir = tmp_path / "study"
    figures_dir = report_dir / "figures"
    run_study("config/corridor_config.yaml", 1800, str(report_dir))
    paths = plot_all(str(report_dir), str(figures_dir))
    assert len(paths) == 10
    assert all(Path(path).exists() for path in paths)
    assert (figures_dir / "fig_08_charging_completion_rate.png").exists()
    assert (figures_dir / "fig_09_v2g_participation_rate.png").exists()
    assert (figures_dir / "fig_10_v2g_discharge_credits.png").exists()
    assert (report_dir / "FIGURES.md").exists()
