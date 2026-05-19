# Builder-G Log

## 2026-05-13T03:19:56Z - T021

Summary: Implemented reproducible Docker/journal experiment artifact capture and CAISO data-source validation for paper-facing AEI-V2G runs.

Files touched:
- `eval/run_journal_study.py`
- `tests/test_journal_study.py`
- `docker-compose.pi.yml`
- `deploy/run_docker_experiment.ps1`
- `deploy/DOCKER_EXPERIMENTS.md`
- `README.md`
- `tasks.md`
- `.claude/agent-logs/builder-g.md`

Details:
- Added fail-fast validation in `eval.run_journal_study` for `grid.load_profile_csv`. If the config references the default CAISO profile and the CSV is absent, the runner raises a clear `FileNotFoundError` with the downloader command.
- Added first-class reproducibility artifacts under each report directory:
  - `provenance.json` with runner, command, Python/platform, scheduler identity, seed, config hash, required data-source hashes, and generated artifact hashes.
  - `inputs/corridor_config.yaml` plus LAVA weights/rules/constraints snapshots.
  - `inputs/resolved_inputs.json` with required data-source manifest and dummy-fixture exclusion policy.
  - `*_trace.csv` per scenario, preserving full generated minute traces alongside existing summary/detail/chain outputs.
- Marked journal summaries and scenario details as paper-facing deterministic digital-twin artifacts using LAVA, with explicit exclusion of test-only dummy scheduler fixtures.
- Added `deploy/run_docker_experiment.ps1` so Docker experiments build/run the image, mount `reports/` and `data/`, write a new report directory, and run validation without requiring real Raspberry Pis.
- Added a `docker-experiment` Compose profile for repeatable containerized journal runs with `data/` mounted read-only.
- Documented the artifact contract and CAISO requirement in `deploy/DOCKER_EXPERIMENTS.md` and the README Docker/journal sections.
- Added focused tests for artifact creation and the missing-CAISO failure path.

Verification:
- `python -m pytest tests/test_journal_study.py tests/test_validate_journal_results.py -q --basetemp=.pytest-tmp` passed, 3 tests.
- Parsed `deploy/run_docker_experiment.ps1` with the PowerShell AST parser successfully.
- `python -m eval.run_journal_study --config config/corridor_config.yaml --duration 600 --output-dir .pytest-tmp/manual_journal` completed and emitted the new artifacts.
- `python -m eval.validate_journal_results --report-dir .pytest-tmp/manual_journal --output .pytest-tmp/manual_journal/VALIDATION_DEFENSE.md` passed for 5 scenarios.

Notes for project lead:
- Append a concise `dev-log.md` entry for T021 pointing here: `.claude/agent-logs/builder-g.md#2026-05-13T03:19:56Z`.
- The initial pytest attempt without `--basetemp` failed before test execution because `C:\Users\HOPE\AppData\Local\Temp\pytest-of-HOPE` was not accessible; rerunning with workspace-local `.pytest-tmp` resolved it.
