# Docker Experiment Artifacts

Use `deploy/run_docker_experiment.ps1` for paper-facing Docker simulation runs. The script does not require Raspberry Pis; Docker replaces the Pi hardware layer while the experiment runner still validates referenced real/replayed data sources.

```powershell
.\deploy\run_docker_experiment.ps1 -Build -DurationSeconds 86400
```

The runner fails fast when `config/corridor_config.yaml` references `grid.load_profile_csv` and the CAISO CSV is missing. Download the default profile first:

```powershell
python -m data_sources.download_caiso_load --start 2024-05-01 --end 2024-05-07 --output data/grid_profiles/caiso_2024-05-01_2024-05-07.csv
```

Each run writes a new report directory under `reports/docker_experiment_<timestamp>/` with first-class artifacts:

| Artifact | Purpose |
|---|---|
| `provenance.json` | Runner, command, Python/platform, scheduler, seed, input hashes, and generated artifact hashes |
| `inputs/corridor_config.yaml` | Exact experiment config used by the container |
| `inputs/lava_weights.yaml`, `inputs/rules.yaml`, `inputs/constraints.yaml` | LAVA decision configuration snapshots |
| `inputs/resolved_inputs.json` | Required data-source manifest and test-fixture exclusion policy |
| `journal_summary.json` | Top-level scenario summary and artifact manifest |
| `scenario_comparison.csv` | Cross-scenario metrics table |
| `component_metrics.csv` | Component-level metrics table |
| `station_metrics.csv` | Per-station operational metrics |
| `*_detail.json` | Per-scenario JSON component report |
| `*_trace.csv` | Per-minute generated trace for each scenario |
| `*_chain.jsonl` | Hash-chained decision log for each scenario |
| `VALIDATION_DEFENSE.md` | Reproducibility and consistency validation report |

Dummy schedulers and test-only fixtures remain in `tests/` for unit coverage, but `eval.run_journal_study` is hard-wired to LAVA and records that exclusion in `provenance.json`.
