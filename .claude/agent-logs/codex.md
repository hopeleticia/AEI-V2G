# Codex Project Lead Log

## 2026-05-13T02:20:57Z

Initialized AEI-V2G coordination docs:

- Added `tasks.md` with priority tasks T001-T009, owners, dependencies, and acceptance checks.
- Added `dev-log.md` with the append-only entry format.
- Corrected the initial log timestamp to actual UTC before declaring the log append-only going forward.

## 2026-05-13T02:22:32Z

Started coordinated subagent work:

- Builder-A: T001, per-EV SoC tracking verification and hardening.
- Builder-B: T002, full metrics evaluator.
- Reviewer-A: T008, pluggable scheduler integration review.
- Auditor-A: T004/T009, DRL readiness and repo architecture audit.

Subagents were given bounded scopes and told to record detailed entries under `.claude/agent-logs/`.

## 2026-05-13T02:22:52Z

Added this project-lead log file so `dev-log.md` entries have a concrete detailed-log target.

## 2026-05-13T02:23:44Z

Updated `tasks.md` to mark T001, T002, T004, T008, and T009 as in progress under the launched subagents. Confirmed no subagent had completed within the initial 10-second check.

## 2026-05-13T02:29:34Z

Reconciled completed subagent work. Builder-A completed T001 with SoC tracking hardening and tests, Builder-B completed T002 with a new metrics evaluator package and tests, Reviewer-A completed T008 with findings on scheduler pluggability, and Auditor-A completed T004/T009 with DRL/repo risks. Updated `tasks.md` to move T001/T002 to Review, T004/T008/T009 to Done, and added follow-up tasks T010-T014.

## 2026-05-13T02:32:06Z

Launched the next execution batch:

- Reviewer-B for T015, reviewing T001/T002 patches.
- Builder-C for T010, full-episode sample persistence/evaluator-backed comparison plumbing.
- Builder-D for T012, scheduler injection tests and distributed trainable-scheduler behavior.

Updated `tasks.md` to mark T010/T012/T015 in progress.

## 2026-05-13T02:38:41Z

Reconciled the second subagent batch. Builder-C completed T010 with full-episode `full_samples` plumbing, Builder-D completed T012 with scheduler-injection tests and explicit rejection of distributed trainable schedulers, and Reviewer-B completed T015 with a blocking finding on V2G completion below `SoC_req_k` plus evaluator semantics concerns. Updated `tasks.md` to move T010/T012 to Review, T015 to Done, and added T016-T018.

## 2026-05-13T02:40:30Z

Launched the follow-up fix/review batch:

- Builder-E for T016, V2G discharge completion obligation.
- Builder-F for T017, evaluator SoC satisfaction and lag semantics.
- Reviewer-C for T018, review of T010/T012 patches.

Updated `tasks.md` to mark T016-T018 in progress.

## 2026-05-13T02:50:17Z

Reconciled the follow-up fix/review batch. Builder-E completed T016 for the V2G completion obligation, Builder-F completed T017 for evaluator denominator/lag semantics, and Reviewer-C completed T018 with no blockers for T010/T012. Updated `tasks.md` to mark T010/T012/T018 Done, move T016/T017 to Review, and add T019 for review of the latest fixes.

## 2026-05-13T02:54:56Z

Launched Reviewer-D for T019 to review the T016/T017 fixes, and Planner-A for T020 to prepare a concrete DRL transition-repair plan before T011 implementation. Updated `tasks.md` to mark T019/T020 in progress.

## 2026-05-13T02:57:17Z

Recorded a project constraint that Docker may replace Raspberry Pi hardware for experiments, but paper-facing experiment inputs must not use dummy data. Added T021 to remove dummy-data risk from the experiment path and require fail-fast data-source validation.

## 2026-05-13T02:57:46Z

Reconciled Reviewer-D and Planner-A completions. Reviewer-D cleared T001/T002/T016/T017 to Done, and Planner-A completed the T020 plan for DRL transition repair. Updated `tasks.md` to close T001/T002/T016/T017/T019/T020 and added T022 for the known optional `matplotlib` full-suite collection blocker.

## 2026-05-13T03:15:50Z

Launched Builder-G for T021 to make Docker simulation experiments capture reproducible generated inputs/outputs and fail fast on missing required data, and Builder-H for T022 to fix the optional `matplotlib` test-collection blocker. Updated `tasks.md` to mark T021/T022 in progress.

## 2026-05-13T07:22:08Z

Reconciled Builder-G and Builder-H completions. T021 moved to Review with Docker/journal artifact provenance and CAISO fail-fast validation implemented; T022 moved to Done after guarded optional `matplotlib` imports allowed full test collection. Added T023 to review the Docker experiment artifact contract.

## 2026-05-13T08:19:11Z

Implemented the three remaining objective gaps directly without subagents:

- T005: Added `sensing/soc_proxy.py` and wired RSU sensing to emit non-null `estimated_soc`, confidence, and ISAC proxy features.
- T024: Added station-level pre-arrival slot reservations and coordinator logging/release flow.
- T006: Added `contracts/CreditLedger.sol`, credit settlement output from V2G dispatch, and Python `ChainClient` hooks for award/redeem/query.

Added focused tests for SoC proxy/RSU features, slot reservation, and credit settlements/contract surface. Verification passed: focused 10-test set, broader 25-test set, and full suite (`32 passed, 1 skipped`).

## 2026-05-13T08:56:22Z

Added Purechain deployment setup for `CreditLedger.sol`:

- `.env` with Purechain RPC/chain ID and private-key placeholders.
- `package.json` and `hardhat.config.js`.
- `scripts/deploy_credit_ledger.js`, which deploys to Purechain and updates `.env`, `deploy/PURECHAIN_CREDIT_LEDGER.md`, and `deployments/purechain_credit_ledger.json`.
- Updated `logging_layer/chain_client.py` to accept `RPC_URL`/`PRIVATE_KEY` aliases and derive the account from the private key when `AEI_ETH_ACCOUNT` is blank.

Validation: `node --check` passed for the Hardhat config and deploy script; `python -m pytest tests\test_credit_ledger.py -q --basetemp=.pytest-tmp-purechain` passed.

## 2026-05-13T11:19:51Z

Fixed Docker build context exclusion after Docker failed on inaccessible local pytest temp directory `.pytest_tmp`. Updated `.dockerignore` to ignore `.pytest_tmp*` and `deployments/`.

## 2026-05-13T12:01:51Z

Created `isac-v2g.md`, a teammate-facing summary of project goals, completed work, Docker experiment artifacts, generated figures, key scenario metrics from `reports/docker_experiment_20260513_203811`, interpretation notes, limitations, and next steps.

## 2026-05-13T12:06:48Z

Expanded `isac-v2g.md` with a figure-by-figure explanation for the seven Docker experiment plots in `reports/docker_experiment_20260513_203811/figures`. Each explanation now states what the axes/series represent and the teammate-facing takeaway for scenario performance, latency, V2G settlement, station load, queue depth, peak-stress suppression, and event-surge response.

## 2026-05-13T12:15:46Z

Corrected the Figure 2 latency interpretation in `isac-v2g.md` after reviewing `scenario_comparison.csv`. The document now states that the latency values are nonzero but visually flattened by the 200 ms axis, and clarifies that this is an in-process simulation timing metric rather than end-to-end deployment latency.

## 2026-05-13T12:23:09Z

Added brief scenario definitions and a baseline explanation to `isac-v2g.md`. The document now identifies each Docker experiment scenario and clarifies that the current baseline is an internally defined reactive nearest-station counterfactual, not an externally replicated paper baseline.

## 2026-05-13T13:19:37Z

Updated `docker-compose.pi.yml` so local Docker Pi-role containers use the Compose MQTT service name `mqtt-broker` by default instead of the physical Raspberry Pi LAN IP. The setting remains overridable through `AEI_MQTT_BROKER` for real hardware deployments.

## 2026-05-13T14:03:05Z

Implemented the Fakhrooeian & Pitz 2023 V2G benchmark under `Benchmark/`. Added the four paper scenarios, deterministic EV session generation, scheduling logic for uncontrolled/V2G/operator-controlled charging, low-voltage feeder proxy metrics, report writers, documentation, and a focused pytest; generated sample artifacts under `reports/benchmark_fakhrooeian_pitz`.

## 2026-05-14T00:31:04Z

Added `Benchmark/plot_fakhrooeian_pitz.py` to generate a Fig. 5-style feeder load-profile comparison from benchmark `timeseries.csv`. Installed plotting dependencies, generated `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_reproduction.png`, and documented the plotting command in `Benchmark/README.md`.

## 2026-05-14T04:07:17Z

Fixed the benchmark Fig. 5 plot x-axis to use elapsed simulation hours instead of hour-of-day wrapping. Regenerated `reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_reproduction.png` so the plotted load profiles no longer contain artificial diagonal connections across midnight.

## 2026-05-14T04:25:05Z

Aligned the benchmark Fig. 5 reproduction with the paper's visual axes and labels: 48-hour 04.28 15:00 to 04.30 14:55 x-axis, 0-160 kW y-axis, paper-like scenario colors, and bottom legend. Regenerated `fig_05_load_profile_reproduction.png`, added `fig_05_load_profile_paper_style.png`, and documented missing exact-replication pieces in `FIGURES.md`.

## 2026-05-14T04:29:57Z

Updated the Fakhrooeian & Pitz benchmark generator to repeat the 15-EV daily population across both days of the 48-hour paper window. Regenerated benchmark summaries and Fig. 5 plots so evening charging/V2G curves appear on the second day as in the paper, and adjusted the plot legend layout to avoid clipping.

## 2026-05-14T04:50:17Z

Added `Benchmark/paper_reference_values.json` with published Table 1-5 values from Fakhrooeian & Pitz and updated the benchmark to generate `PATTERN_REPORT.md`. The report now compares our peak-load ordering against Table 2 and confirms the scenario trend matches while documenting that Tables 3-5 remain proxy-supported without PowerFactory.

## 2026-05-14T04:55:58Z

Renamed the benchmark Fig. 5 output title and preferred filename from reproduction language to `Fig. 5-Style Pattern Reconstruction`. Regenerated `fig_05_load_profile_pattern_reconstruction.png`, retained the paper-style alias, and marked the older `fig_05_load_profile_reproduction.png` as traceability-only in `FIGURES.md`.

## 2026-05-14T05:50:31Z

Upgraded the Fakhrooeian & Pitz benchmark from a single seeded proxy run into an explicit stochastic EV scheduling replication. The runner now performs repeated stochastic arrival/SoC trials, writes aggregate and per-run summaries, regenerates Table 2-style load metrics from the mean profile, and confirms the Table 2 peak-load ordering matches the paper.

## 2026-05-14T06:11:50Z

Removed the in-figure title from the benchmark Fig. 5-style plot and regenerated the preferred pattern-reconstruction image for cleaner paper placement.

## 2026-05-14T08:07:03Z

Analyzed the benchmark presentation and generated a revised 16-slide deck at `reports/Signal_Processing_benchmark_improved.pptx`. The new deck starts from the benchmark implementation, explains the replicated parameters/equations and Table 2/Fig. 5 results, clarifies the reactive scheduling gap, then introduces a simplified AEI-V2G model stack with only the essential equations and evaluation metrics.

## 2026-05-15T02:59:51Z

Added two metric-specific Docker experiment plots to `eval.plot_journal_results`: charging completion rate and V2G participation rate. Regenerated the Docker experiment figures so the report now includes nine plots, and updated the plotting test to expect the new outputs.

## 2026-05-15T03:08:19Z

Adjusted the journal plotting axes to use data-aware zoom ranges instead of forcing all graphs to start at zero. Regenerated the Docker experiment figures, moved the event-surge legend outside the plotting area, annotated the latency target as out-of-range on the zoomed view, and verified the plotting test passes.

## 2026-05-15T03:34:50Z

Updated the event-surge timeline plot to use hour-of-day labels on the x-axis and fixed the grid-stress y-axis ceiling at 1.0 so the reactive baseline line remains visually inside the plot. Regenerated the Docker experiment figures and verified the plotting test passes.

## 2026-05-15T03:44:23Z

Removed the explanatory 200 ms target annotation from the latency profile plot and regenerated the Docker experiment figures while keeping the zoomed latency axis.

## 2026-05-15T03:50:16Z

Renamed the scenario-performance y-axis from `Percent` to `Percentage value by metric (%)` and regenerated the Docker experiment figures.

## 2026-05-19T02:20:14Z

Completed the missing blockchain runtime bridge. V2G credit settlements now carry local/on-chain ledger status, optional CreditLedger transaction hashes, aggregate credit/ledger metrics in journal outputs, and Docker Compose now uses Purechain/environment-driven chain settings instead of old hardcoded test-chain credentials. Verified with focused credit tests, plotting/validation tests, and a short journal smoke run at `reports/blockchain_smoke`.

## 2026-05-19T02:36:09Z

Added a journal figure comparing accepted V2G discharge events with credit points awarded. The scenario summary now includes V2G invitation/acceptance counts, the plotting suite generates `fig_10_v2g_discharge_credits.png`, and the current Docker experiment figures were regenerated with the new plot.

## 2026-05-19T02:44:39Z

Rewrote `isac-v2g.md` as a continuation handoff for the AEI-V2G work. The document now explains the project goal, implemented components, simulated versus real inputs, Docker experiment modes, station/scenario setup, current result snapshot, blockchain/Purechain status, benchmark status, limitations, commands, and recommended next steps.

## 2026-05-19T03:00:16Z

Updated `isac-v2g.md` with a Core Comparison Metrics section. The new section maps charging service, grid support, scheduling benefit, ISAC benefit, V2G participation, trust/blockchain, and responsiveness metrics to what each comparison is meant to prove.

## 2026-05-19T03:36:49Z

Prepared the project for publication to GitHub by adding `.gitignore` and `.env.example`, excluding local secrets/generated outputs, replacing hardcoded deployment credentials with environment-variable usage, creating the initial commit, adding `https://github.com/hopeleticia/AEI-V2G.git` as `origin`, and pushing `main`.
