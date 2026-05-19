# AEI-V2G Development Log

This file is append-only. It records what happened in this repo and when so future agents can understand project movement without reading every detailed agent log.

## Entry Format

Each entry must use this format:

```text
## YYYY-MM-DDTHH:MM:SSZ - <Agent name> - <Task ID>
Summary: <One or two sentences describing what happened.>
Files touched:
- <path or "None">
Status: <Planned | In Progress | Blocked | Review | Done | Deferred>
Details: <Pointer to detailed entry in the agent's own log file>
```

Rules:

- Append new entries at the bottom only.
- Use UTC timestamps.
- Keep summaries factual and concise.
- List files the agent changed, not every file it read.
- If no files were changed, write `- None`.
- `Details` should point to a specific agent log path and entry anchor or timestamp, for example `.claude/agent-logs/builder-a.md#2026-05-13T02:15:00Z`.

## 2026-05-13T02:20:57Z - Codex - T000
Summary: Created the repo-level coordination files and initialized the project task board for the next AEI-V2G development phase.
Files touched:
- `tasks.md`
- `dev-log.md`
Status: In Progress
Details: `.claude/agent-logs/codex.md#2026-05-13T02:20:57Z`

## 2026-05-13T02:22:32Z - Codex - T000
Summary: Launched Builder-A for SoC tracking, Builder-B for metrics evaluator, Reviewer-A for scheduler integration review, and Auditor-A for DRL/repo architecture audit.
Files touched:
- `tasks.md`
- `dev-log.md`
Status: In Progress
Details: `.claude/agent-logs/codex.md#2026-05-13T02:22:32Z`

## 2026-05-13T02:22:52Z - Codex - T000
Summary: Added the project-lead detailed log so `dev-log.md` pointers resolve to a repo-local coordination record.
Files touched:
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T02:22:52Z`

## 2026-05-13T02:23:44Z - Codex - T000
Summary: Marked launched subagent assignments as in progress and confirmed the initial coordination setup is complete.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T02:23:44Z`

## 2026-05-13T02:26:20Z - Builder-A - T001
Summary: Hardened per-EV SoC tracking by centralizing battery updates on `EV`, preserving SoH/request/departure fields through distributed station snapshots, and adding SoC flow tests.
Files touched:
- `sim/entities.py`
- `sim/station_model.py`
- `integration/v2g_dispatcher.py`
- `integration/coordinator.py`
- `tests/test_soc_flow.py`
- `.claude/agent-logs/builder-a.md`
Status: Review
Details: `.claude/agent-logs/builder-a.md#2026-05-13T02:26:20Z`

## 2026-05-13T02:25:47Z - Builder-B - T002
Summary: Added a pure `metrics` package for PAR, TEC, SoC satisfaction, scheduling lag, battery degradation, and sensing-gain reward inputs, with focused evaluator tests.
Files touched:
- `metrics/__init__.py`
- `metrics/evaluator.py`
- `tests/test_metrics_evaluator.py`
- `.claude/agent-logs/builder-b.md`
Status: Review
Details: `.claude/agent-logs/builder-b.md#2026-05-13T02:25:47Z`

## 2026-05-13T02:24:07Z - Reviewer-A - T008
Summary: Reviewed scheduler pluggability and found distributed trainable schedulers do not learn, injected-scheduler metrics are still labeled as LAVA, and committed dummy-scheduler tests are missing.
Files touched:
- `.claude/agent-logs/reviewer-a.md`
Status: Done
Details: `.claude/agent-logs/reviewer-a.md#2026-05-13T11:24:07+09:00`

## 2026-05-13T02:23:30Z - Auditor-A - T004/T009
Summary: Audited DRL readiness and repo architecture; top blockers are invalid DRL transitions, missing terminal transitions, last-10-sample comparison metrics, and non-defensible reward proxy comparisons.
Files touched:
- `.claude/agent-logs/auditor-a.md`
Status: Done
Details: `.claude/agent-logs/auditor-a.md#2026-05-13T02:23:30Z`

## 2026-05-13T02:29:34Z - Codex - T000
Summary: Reconciled all completed agent statuses, updated `tasks.md`, and added follow-up tasks for full-episode metrics, DRL transition repair, scheduler injection tests, comparison protocol, and documentation drift.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T02:29:34Z`

## 2026-05-13T02:32:06Z - Codex - T000
Summary: Launched Reviewer-B for T001/T002 review, Builder-C for full-episode sample plumbing, and Builder-D for scheduler injection tests/distributed trainable policy behavior.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: In Progress
Details: `.claude/agent-logs/codex.md#2026-05-13T02:32:06Z`

## 2026-05-13T02:33:30Z - Builder-C - T010
Summary: Added complete `full_samples` and `sample_count` report fields while preserving compact `samples`, and updated comparison/evaluator plumbing to prefer full-episode samples.
Files touched:
- `integration/coordinator.py`
- `eval/run_comparison.py`
- `metrics/evaluator.py`
- `tests/test_full_episode_samples.py`
- `.claude/agent-logs/builder-c.md`
Status: Review
Details: `.claude/agent-logs/builder-c.md#2026-05-13T02:33:30Z`

## 2026-05-13T02:33:04Z - Builder-D - T012
Summary: Added committed scheduler-injection tests and made distributed lava-validator mode explicitly reject trainable schedulers until distributed reward plumbing exists.
Files touched:
- `integration/coordinator.py`
- `tests/test_scheduler_injection.py`
- `.claude/agent-logs/builder-d.md`
Status: Review
Details: `.claude/agent-logs/builder-d.md#2026-05-13T02:33:04Z`

## 2026-05-13T02:35:13Z - Reviewer-B - T015
Summary: Reviewed T001/T002 and found a blocking V2G completion bug plus evaluator issues around SoC satisfaction denominator and scheduling-lag fallback semantics.
Files touched:
- `.claude/agent-logs/reviewer-b.md`
Status: Done
Details: `.claude/agent-logs/reviewer-b.md#2026-05-13T02:35:13Z`

## 2026-05-13T02:38:41Z - Codex - T000
Summary: Reconciled the second subagent batch, moved T010/T012 to Review, moved T015 to Done, and created follow-up tasks T016-T018.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T02:38:41Z`

## 2026-05-13T02:40:30Z - Codex - T000
Summary: Launched Builder-E for the V2G completion invariant, Builder-F for evaluator semantics, and Reviewer-C for T010/T012 review.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: In Progress
Details: `.claude/agent-logs/codex.md#2026-05-13T02:40:30Z`

## 2026-05-13T02:42:15Z - Builder-E - T016
Summary: Fixed the V2G completion invariant so a discharged charging EV must recover to `SoC_req_k` before completion, with regression coverage.
Files touched:
- `sim/entities.py`
- `sim/station_model.py`
- `integration/v2g_dispatcher.py`
- `tests/test_soc_flow.py`
- `.claude/agent-logs/builder-e.md`
Status: Review
Details: `.claude/agent-logs/builder-e.md#2026-05-13T02:42:15Z`

## 2026-05-13T02:43:16Z - Builder-F - T017
Summary: Tightened evaluator semantics so SoC satisfaction accounts for routed/admitted/incomplete EVs and latency-only data no longer populates the physical lag metric.
Files touched:
- `metrics/evaluator.py`
- `tests/test_metrics_evaluator.py`
- `.claude/agent-logs/builder-f.md`
Status: Review
Details: `.claude/agent-logs/builder-f.md#2026-05-13T02:43:16Z`

## 2026-05-13T02:42:25Z - Reviewer-C - T018
Summary: Reviewed T010/T012 and found no blocking issues; full-sample plumbing and scheduler-injection coverage can move to Done.
Files touched:
- `.claude/agent-logs/reviewer-c.md`
Status: Done
Details: `.claude/agent-logs/reviewer-c.md#2026-05-13T11:42:25+09:00`

## 2026-05-13T02:50:17Z - Codex - T000
Summary: Reconciled the follow-up batch, closed T010/T012/T018, moved T016/T017 to Review, and created T019 for final review of the fixes.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T02:50:17Z`

## 2026-05-13T02:54:56Z - Codex - T000
Summary: Launched Reviewer-D for T019 review of T016/T017 and Planner-A for T020 DRL transition-repair planning.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: In Progress
Details: `.claude/agent-logs/codex.md#2026-05-13T02:54:56Z`

## 2026-05-13T02:57:17Z - Codex - T021
Summary: Recorded the no-dummy-data experiment constraint: Docker may replace Raspberry Pi hardware, but paper-facing inputs must be real, replayed, measured, or explicitly documented digital-twin sources.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Ready
Details: `.claude/agent-logs/codex.md#2026-05-13T02:57:17Z`

## 2026-05-13T03:00:00Z - Reviewer-D - T019
Summary: Reviewed T016/T017 and cleared the SoC tracking plus metrics foundation; T001, T002, T016, and T017 can move to Done.
Files touched:
- `.claude/agent-logs/reviewer-d.md`
Status: Done
Details: `.claude/agent-logs/reviewer-d.md#2026-05-13T03:00:00Z`

## 2026-05-13T02:55:44Z - Planner-A - T020
Summary: Produced the T011 DRL transition-repair plan covering true next states, terminal transitions, reward context, coordinator update strategy, and focused tests.
Files touched:
- `.claude/agent-logs/planner-a.md`
Status: Done
Details: `.claude/agent-logs/planner-a.md#2026-05-13T02:55:44Z`

## 2026-05-13T02:57:46Z - Codex - T000
Summary: Reconciled T019/T020, closed T001/T002/T016/T017/T019/T020, and added T022 for the known optional `matplotlib` test-collection blocker.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T02:57:46Z`

## 2026-05-13T03:15:50Z - Codex - T000
Summary: Launched Builder-G for Docker simulation artifact/provenance capture and Builder-H for the optional `matplotlib` test-collection blocker.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: In Progress
Details: `.claude/agent-logs/codex.md#2026-05-13T03:15:50Z`

## 2026-05-13T03:17:07Z - Builder-H - T022
Summary: Guarded optional `matplotlib` imports so full test collection no longer fails when plotting dependencies are absent; plotting tests skip only when plotting is unavailable.
Files touched:
- `eval/plot_journal_results.py`
- `tests/test_plot_journal_results.py`
- `.claude/agent-logs/builder-h.md`
Status: Done
Details: `.claude/agent-logs/builder-h.md#2026-05-13T03:17:07Z`

## 2026-05-13T03:19:56Z - Builder-G - T021
Summary: Added reproducible Docker/journal experiment artifact capture, provenance, input snapshots, required data-source hashes, trace CSVs, and CAISO missing-file validation.
Files touched:
- `eval/run_journal_study.py`
- `tests/test_journal_study.py`
- `docker-compose.pi.yml`
- `deploy/run_docker_experiment.ps1`
- `deploy/DOCKER_EXPERIMENTS.md`
- `README.md`
- `tasks.md`
- `.claude/agent-logs/builder-g.md`
Status: Review
Details: `.claude/agent-logs/builder-g.md#2026-05-13T03:19:56Z`

## 2026-05-13T07:22:08Z - Codex - T000
Summary: Reconciled T021/T022 status, moved T022 to Done, left T021 in Review, and added T023 for Docker experiment artifact review.
Files touched:
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T07:22:08Z`

## 2026-05-13T08:19:11Z - Codex - T005/T006/T024
Summary: Implemented SoC proxy inference, pre-arrival slot reservation, and credit-point ledger/settlement scaffolding directly without subagents; full test suite passed with one optional plotting skip.
Files touched:
- `sensing/__init__.py`
- `sensing/soc_proxy.py`
- `sim/rsu_model.py`
- `sim/entities.py`
- `sim/station_model.py`
- `integration/coordinator.py`
- `integration/v2g_dispatcher.py`
- `logging_layer/chain_client.py`
- `contracts/CreditLedger.sol`
- `tests/test_soc_flow.py`
- `tests/test_prearrival_reservation.py`
- `tests/test_credit_ledger.py`
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Review
Details: `.claude/agent-logs/codex.md#2026-05-13T08:19:11Z`

## 2026-05-13T08:56:22Z - Codex - T025
Summary: Added Purechain CreditLedger deployment setup with `.env`, Hardhat config, deploy script, deployment document/JSON, and chain-client environment alias support.
Files touched:
- `.env`
- `.dockerignore`
- `package.json`
- `hardhat.config.js`
- `scripts/deploy_credit_ledger.js`
- `deploy/PURECHAIN_CREDIT_LEDGER.md`
- `deployments/purechain_credit_ledger.json`
- `logging_layer/chain_client.py`
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Review
Details: `.claude/agent-logs/codex.md#2026-05-13T08:56:22Z`

## 2026-05-13T11:19:51Z - Codex - T021
Summary: Fixed Docker build context exclusions after Docker failed on inaccessible local pytest temp directory `.pytest_tmp`.
Files touched:
- `.dockerignore`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T11:19:51Z`

## 2026-05-13T12:01:51Z - Codex - T000
Summary: Created `isac-v2g.md`, a brief teammate-facing explanation of the work completed and the Docker experiment figure/results directory.
Files touched:
- `isac-v2g.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T12:01:51Z`

## 2026-05-13T12:06:48Z - Codex - T000
Summary: Expanded `isac-v2g.md` with explanations for each of the seven Docker experiment figures and their main teammate-facing takeaways.
Files touched:
- `isac-v2g.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T12:06:48Z`

## 2026-05-13T12:15:46Z - Codex - T000
Summary: Corrected the Figure 2 latency interpretation to show the actual sub-millisecond values and clarify that they are in-process simulation timings, not end-to-end edge latency proof.
Files touched:
- `isac-v2g.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T12:15:46Z`

## 2026-05-13T12:23:09Z - Codex - T000
Summary: Added short explanations of each Docker experiment scenario and clarified the internally defined reactive nearest-station baseline.
Files touched:
- `isac-v2g.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T12:23:09Z`

## 2026-05-13T13:19:37Z - Codex - T021
Summary: Fixed local Docker Pi-role MQTT configuration so containers use the Compose broker service name by default instead of the physical Raspberry Pi LAN IP.
Files touched:
- `docker-compose.pi.yml`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T13:19:37Z`

## 2026-05-13T14:03:05Z - Codex - T026
Summary: Implemented the Fakhrooeian & Pitz 2023 V2G benchmark scenarios with deterministic outputs, docs, focused tests, and generated benchmark artifacts.
Files touched:
- `Benchmark/__init__.py`
- `Benchmark/README.md`
- `Benchmark/run_fakhrooeian_pitz.py`
- `tests/test_benchmark_fakhrooeian_pitz.py`
- `reports/benchmark_fakhrooeian_pitz/`
- `tasks.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-13T14:03:05Z`

## 2026-05-14T00:31:04Z - Codex - T026
Summary: Added a Fig. 5-style benchmark load-profile plotting script, installed plotting dependencies, and generated the benchmark figure artifact.
Files touched:
- `Benchmark/plot_fakhrooeian_pitz.py`
- `Benchmark/README.md`
- `reports/benchmark_fakhrooeian_pitz/figures/`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-14T00:31:04Z`

## 2026-05-14T04:07:17Z - Codex - T026
Summary: Corrected the benchmark Fig. 5 plot to use elapsed simulation hours instead of wrapped hour-of-day values, removing artificial diagonal line artifacts.
Files touched:
- `Benchmark/plot_fakhrooeian_pitz.py`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_reproduction.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-14T04:07:17Z`

## 2026-05-14T04:25:05Z - Codex - T026
Summary: Aligned the benchmark Fig. 5 reproduction with the paper-style axes, labels, colors, and legend, and documented remaining gaps from exact PowerFactory replication.
Files touched:
- `Benchmark/plot_fakhrooeian_pitz.py`
- `reports/benchmark_fakhrooeian_pitz/figures/FIGURES.md`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_reproduction.png`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_paper_style.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-14T04:25:05Z`

## 2026-05-14T04:29:57Z - Codex - T026
Summary: Updated the benchmark generator to repeat daily EV sessions across the two-day paper window and regenerated Fig. 5 so the second evening curves are present.
Files touched:
- `Benchmark/run_fakhrooeian_pitz.py`
- `Benchmark/plot_fakhrooeian_pitz.py`
- `reports/benchmark_fakhrooeian_pitz/scenario_summary.csv`
- `reports/benchmark_fakhrooeian_pitz/scenario_summary.json`
- `reports/benchmark_fakhrooeian_pitz/timeseries.csv`
- `reports/benchmark_fakhrooeian_pitz/ev_sessions.csv`
- `reports/benchmark_fakhrooeian_pitz/README_RESULTS.md`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_reproduction.png`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_paper_style.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-14T04:29:57Z`

## 2026-05-14T04:50:17Z - Codex - T026
Summary: Added published paper reference values for Tables 1-5 and generated a pattern report confirming our Table 2 peak-load ordering matches the benchmark paper.
Files touched:
- `Benchmark/paper_reference_values.json`
- `Benchmark/run_fakhrooeian_pitz.py`
- `Benchmark/README.md`
- `reports/benchmark_fakhrooeian_pitz/PATTERN_REPORT.md`
- `reports/benchmark_fakhrooeian_pitz/README_RESULTS.md`
- `reports/benchmark_fakhrooeian_pitz/scenario_summary.csv`
- `reports/benchmark_fakhrooeian_pitz/scenario_summary.json`
- `reports/benchmark_fakhrooeian_pitz/timeseries.csv`
- `reports/benchmark_fakhrooeian_pitz/ev_sessions.csv`
- `reports/benchmark_fakhrooeian_pitz/figures/FIGURES.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-14T04:50:17Z`

## 2026-05-14T04:55:58Z - Codex - T026
Summary: Renamed the preferred benchmark Fig. 5 output and title to pattern-reconstruction language and marked the older reproduction-named image as traceability-only.
Files touched:
- `Benchmark/plot_fakhrooeian_pitz.py`
- `reports/benchmark_fakhrooeian_pitz/figures/FIGURES.md`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_pattern_reconstruction.png`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_paper_style.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-14T04:55:58Z`

## 2026-05-14T05:50:31Z - Codex - T026
Summary: Upgraded the benchmark to run repeated stochastic EV arrival/SoC trials and regenerated Fig. 5/Table 2-style outputs from aggregate stochastic results. The pattern report now confirms the paper's Table 2 peak-load ordering is matched.
Files touched:
- `Benchmark/run_fakhrooeian_pitz.py`
- `Benchmark/plot_fakhrooeian_pitz.py`
- `Benchmark/README.md`
- `tests/test_benchmark_fakhrooeian_pitz.py`
- `reports/benchmark_fakhrooeian_pitz/scenario_summary.csv`
- `reports/benchmark_fakhrooeian_pitz/scenario_run_summary.csv`
- `reports/benchmark_fakhrooeian_pitz/scenario_summary.json`
- `reports/benchmark_fakhrooeian_pitz/timeseries.csv`
- `reports/benchmark_fakhrooeian_pitz/timeseries_runs.csv`
- `reports/benchmark_fakhrooeian_pitz/ev_sessions.csv`
- `reports/benchmark_fakhrooeian_pitz/README_RESULTS.md`
- `reports/benchmark_fakhrooeian_pitz/PATTERN_REPORT.md`
- `reports/benchmark_fakhrooeian_pitz/figures/FIGURES.md`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_pattern_reconstruction.png`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_paper_style.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-14T05:50:31Z`

## 2026-05-14T06:11:50Z - Codex - T026
Summary: Removed the title from the benchmark Fig. 5-style plot and regenerated the preferred pattern-reconstruction figure for paper-ready placement.
Files touched:
- `Benchmark/plot_fakhrooeian_pitz.py`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_pattern_reconstruction.png`
- `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_paper_style.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-14T06:11:50Z`

## 2026-05-14T08:07:03Z - Codex - T027
Summary: Reviewed the existing benchmark presentation and generated a revised 16-slide deck that tightens the story from benchmark replication to AEI-V2G necessity and simplified model equations. The improved deck adds missing benchmark scope, result interpretation, gap analysis, model-stack explanation, evaluation metrics, and experimental path.
Files touched:
- `reports/Signal_Processing_benchmark_improved.pptx`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-14T08:07:03Z`

## 2026-05-15T02:59:51Z - Codex - T028
Summary: Added explicit charging completion and V2G participation plots to the journal plotting script, regenerated the Docker experiment figures, and updated the plot test for the expanded nine-figure output.
Files touched:
- `eval/plot_journal_results.py`
- `tests/test_plot_journal_results.py`
- `reports/docker_experiment_20260513_203811/FIGURES.md`
- `reports/docker_experiment_20260513_203811/figures/fig_01_scenario_performance.png`
- `reports/docker_experiment_20260513_203811/figures/fig_02_latency_profile.png`
- `reports/docker_experiment_20260513_203811/figures/fig_03_v2g_energy_revenue.png`
- `reports/docker_experiment_20260513_203811/figures/fig_04_station_avg_load.png`
- `reports/docker_experiment_20260513_203811/figures/fig_05_station_peak_queue.png`
- `reports/docker_experiment_20260513_203811/figures/fig_06_grid_stress_minutes.png`
- `reports/docker_experiment_20260513_203811/figures/fig_07_event_surge_timeline.png`
- `reports/docker_experiment_20260513_203811/figures/fig_08_charging_completion_rate.png`
- `reports/docker_experiment_20260513_203811/figures/fig_09_v2g_participation_rate.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-15T02:59:51Z`

## 2026-05-15T03:08:19Z - Codex - T028
Summary: Updated journal plot axes to use data-aware zoom ranges, moved the event-surge legend outside the data region, and regenerated Docker experiment figures so metric trends are easier to see.
Files touched:
- `eval/plot_journal_results.py`
- `reports/docker_experiment_20260513_203811/FIGURES.md`
- `reports/docker_experiment_20260513_203811/figures/fig_01_scenario_performance.png`
- `reports/docker_experiment_20260513_203811/figures/fig_02_latency_profile.png`
- `reports/docker_experiment_20260513_203811/figures/fig_03_v2g_energy_revenue.png`
- `reports/docker_experiment_20260513_203811/figures/fig_04_station_avg_load.png`
- `reports/docker_experiment_20260513_203811/figures/fig_05_station_peak_queue.png`
- `reports/docker_experiment_20260513_203811/figures/fig_06_grid_stress_minutes.png`
- `reports/docker_experiment_20260513_203811/figures/fig_07_event_surge_timeline.png`
- `reports/docker_experiment_20260513_203811/figures/fig_08_charging_completion_rate.png`
- `reports/docker_experiment_20260513_203811/figures/fig_09_v2g_participation_rate.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-15T03:08:19Z`

## 2026-05-15T03:34:50Z - Codex - T028
Summary: Changed the event-surge timeline x-axis from minute-of-day to hour-of-day labels and fixed the grid-stress y-axis ceiling at 1.0 for easier interpretation.
Files touched:
- `eval/plot_journal_results.py`
- `reports/docker_experiment_20260513_203811/FIGURES.md`
- `reports/docker_experiment_20260513_203811/figures/fig_01_scenario_performance.png`
- `reports/docker_experiment_20260513_203811/figures/fig_02_latency_profile.png`
- `reports/docker_experiment_20260513_203811/figures/fig_03_v2g_energy_revenue.png`
- `reports/docker_experiment_20260513_203811/figures/fig_04_station_avg_load.png`
- `reports/docker_experiment_20260513_203811/figures/fig_05_station_peak_queue.png`
- `reports/docker_experiment_20260513_203811/figures/fig_06_grid_stress_minutes.png`
- `reports/docker_experiment_20260513_203811/figures/fig_07_event_surge_timeline.png`
- `reports/docker_experiment_20260513_203811/figures/fig_08_charging_completion_rate.png`
- `reports/docker_experiment_20260513_203811/figures/fig_09_v2g_participation_rate.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-15T03:34:50Z`

## 2026-05-15T03:44:23Z - Codex - T028
Summary: Removed the 200 ms target annotation from the latency profile plot and regenerated the Docker experiment figures with the zoomed latency axis retained.
Files touched:
- `eval/plot_journal_results.py`
- `reports/docker_experiment_20260513_203811/FIGURES.md`
- `reports/docker_experiment_20260513_203811/figures/fig_01_scenario_performance.png`
- `reports/docker_experiment_20260513_203811/figures/fig_02_latency_profile.png`
- `reports/docker_experiment_20260513_203811/figures/fig_03_v2g_energy_revenue.png`
- `reports/docker_experiment_20260513_203811/figures/fig_04_station_avg_load.png`
- `reports/docker_experiment_20260513_203811/figures/fig_05_station_peak_queue.png`
- `reports/docker_experiment_20260513_203811/figures/fig_06_grid_stress_minutes.png`
- `reports/docker_experiment_20260513_203811/figures/fig_07_event_surge_timeline.png`
- `reports/docker_experiment_20260513_203811/figures/fig_08_charging_completion_rate.png`
- `reports/docker_experiment_20260513_203811/figures/fig_09_v2g_participation_rate.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-15T03:44:23Z`

## 2026-05-15T03:50:16Z - Codex - T028
Summary: Renamed the scenario-performance y-axis to `Percentage value by metric (%)` and regenerated the Docker experiment figures.
Files touched:
- `eval/plot_journal_results.py`
- `reports/docker_experiment_20260513_203811/FIGURES.md`
- `reports/docker_experiment_20260513_203811/figures/fig_01_scenario_performance.png`
- `reports/docker_experiment_20260513_203811/figures/fig_02_latency_profile.png`
- `reports/docker_experiment_20260513_203811/figures/fig_03_v2g_energy_revenue.png`
- `reports/docker_experiment_20260513_203811/figures/fig_04_station_avg_load.png`
- `reports/docker_experiment_20260513_203811/figures/fig_05_station_peak_queue.png`
- `reports/docker_experiment_20260513_203811/figures/fig_06_grid_stress_minutes.png`
- `reports/docker_experiment_20260513_203811/figures/fig_07_event_surge_timeline.png`
- `reports/docker_experiment_20260513_203811/figures/fig_08_charging_completion_rate.png`
- `reports/docker_experiment_20260513_203811/figures/fig_09_v2g_participation_rate.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-15T03:50:16Z`

## 2026-05-19T02:20:14Z - Codex - T029
Summary: Completed the blockchain runtime bridge by connecting V2G credit settlements to optional CreditLedger submission and adding credit/ledger status metrics to journal outputs.
Files touched:
- `logging_layer/chain_client.py`
- `integration/v2g_dispatcher.py`
- `integration/coordinator.py`
- `eval/run_journal_study.py`
- `docker-compose.pi.yml`
- `tests/test_credit_ledger.py`
- `reports/blockchain_smoke/*`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-19T02:20:14Z`

## 2026-05-19T02:36:09Z - Codex - T030
Summary: Added a journal figure comparing accepted V2G discharge events against credit points awarded and regenerated the current Docker experiment figures.
Files touched:
- `eval/run_journal_study.py`
- `eval/plot_journal_results.py`
- `tests/test_plot_journal_results.py`
- `reports/docker_experiment/FIGURES.md`
- `reports/docker_experiment/figures/fig_01_scenario_performance.png`
- `reports/docker_experiment/figures/fig_02_latency_profile.png`
- `reports/docker_experiment/figures/fig_03_v2g_energy_revenue.png`
- `reports/docker_experiment/figures/fig_04_station_avg_load.png`
- `reports/docker_experiment/figures/fig_05_station_peak_queue.png`
- `reports/docker_experiment/figures/fig_06_grid_stress_minutes.png`
- `reports/docker_experiment/figures/fig_07_event_surge_timeline.png`
- `reports/docker_experiment/figures/fig_08_charging_completion_rate.png`
- `reports/docker_experiment/figures/fig_09_v2g_participation_rate.png`
- `reports/docker_experiment/figures/fig_10_v2g_discharge_credits.png`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-19T02:36:09Z`

## 2026-05-19T02:44:39Z - Codex - T014
Summary: Rewrote `isac-v2g.md` into a practical handoff document so a teammate can understand the implemented system, run modes, artifacts, blockchain status, benchmark status, and next steps.
Files touched:
- `isac-v2g.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-19T02:44:39Z`

## 2026-05-19T03:00:16Z - Codex - T014
Summary: Added a Core Comparison Metrics section to `isac-v2g.md` so future readers know which results matter when comparing AEI-V2G with existing EV charging, V2G, and smart-charging works.
Files touched:
- `isac-v2g.md`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-19T03:00:16Z`

## 2026-05-19T03:36:49Z - Codex - T014
Summary: Published the project to the new GitHub repository after adding repo-safe ignore rules, a `.env.example`, and replacing hardcoded deployment credentials with environment-variable placeholders.
Files touched:
- `.gitignore`
- `.env.example`
- `deploy/_check_logs.ps1`
- `deploy/_check_procs.ps1`
- `deploy/_diag_paho.ps1`
- `deploy/_fix_dns_install.ps1`
- `deploy/_fix_dns_v2.ps1`
- `deploy/_install_apt.ps1`
- `deploy/_install_deps.ps1`
- `deploy/_install_system_wide.ps1`
- `deploy/_install_target.ps1`
- `deploy/_install_venv.ps1`
- `deploy/_launch_cluster.ps1`
- `deploy/_run_venv_setup.ps1`
- `deploy/_tailscale_from_pi2_time.ps1`
- `deploy/_test_coordinator.ps1`
- `deploy/aggregate_results.ps1`
- `deploy/run_pi_cluster.ps1`
- `.claude/agent-logs/codex.md`
- `dev-log.md`
Status: Done
Details: `.claude/agent-logs/codex.md#2026-05-19T03:36:49Z`

## 2026-05-19T03:45:12Z - Codex - T014
Summary: Removed the `.claude` folder from Git tracking and updated `.gitignore` so local agent logs remain private/local instead of being pushed to GitHub.
Files touched:
- `.gitignore`
- `dev-log.md`
Status: Done
Details: local-only `.claude/agent-logs/codex.md#2026-05-19T03:45:12Z`
