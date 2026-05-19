# AEI-V2G Task Board

This file is the shared coordination surface for AEI-V2G. Keep work traceable to the research objectives in `AEI_V2G_Claude_Code_Context.pdf`, especially Obj-3, Obj-7, Obj-8, Obj-9, and Obj-10. Do not modify research artifacts such as existing JSONL chain logs or `reports/cluster_metrics.json`.

## Operating Rules

- Every implementation task must map to at least one research objective.
- The scheduler must remain pluggable through `scheduling/base_scheduler.py`.
- MQTT topic names and field names are fixed unless all producers and consumers are updated together.
- Battery safety is non-negotiable: no V2G action may drive SoC below `20%`.
- New outputs should go to new files or new report directories.
- Every agent turn ends with an append-only entry in `dev-log.md`.
- Each agent keeps detailed notes in its own log under `.claude/agent-logs/`.
- Experimental runs must not use dummy data. Docker may replace Raspberry Pi hardware for repeatable deployment, but paper-facing inputs must be real, replayed, measured, or explicitly documented digital-twin data sources.

## Roles

| Role | Focus | Current Owner |
|---|---|---|
| Project Lead | Scope, sequencing, integration decisions, dev-log hygiene | Codex |
| Code Builder | Implement bounded feature slices with tests | Builder subagents |
| Code Reviewer | Review code changes for bugs, test gaps, research alignment | Reviewer subagents |
| Code Auditor | Check architecture, invariants, artifacts, and paper defensibility | Auditor subagents |

## Priority Queue

| ID | Priority | Task | Objective Mapping | Files / Scope | Status | Owner | Acceptance Checks |
|---|---:|---|---|---|---|---|---|
| T001 | P2 | Verify and harden per-EV SoC tracking | Obj-4, Obj-7, Obj-9 | `sim/entities.py`, `sim/station_model.py`, `sim/rsu_model.py`, `integration/coordinator.py`, tests | Done | Builder-A | SoC/SoH/request/departure fields flow from spawn to RSU feature to station admission to completion logs; trajectory updates on charge and V2G; tests cover the flow. |
| T002 | P3 | Build full metrics evaluator | Obj-7, Obj-9, Obj-10 | New `metrics/evaluator.py`, possible `metrics/__init__.py`, focused tests | Done | Builder-B | Computes PAR, TEC, SoC satisfaction, scheduling lag, degradation cost, sensing gain inputs from episode/log data without mutating artifacts. |
| T003 | P4 | Add fast simulation runner | Obj-8, Obj-9, Obj-10 | Prefer `sim/fast_sim.py` unless a new `simulation/` package is intentionally justified | Blocked by T002 | Builder | Runs headless without real-time sleeps; preserves scheduler interface; produces evaluator-compatible output. |
| T004 | P5 | Audit DRL scheduler readiness | Obj-8, Obj-9, Obj-10 | `scheduling/drl_scheduler.py`, `scheduling/replay_buffer.py`, `eval/run_comparison.py` | Done | Auditor-A | Findings identify correctness risks, missing tests, and whether current DRQN can support fair LAVA comparison. |
| T005 | P6 | Implement SoC proxy inference | Obj-1, Obj-2, Obj-4, Obj-9 | New `sensing/soc_proxy.py`, `sim/rsu_model.py`, tests | Review | Codex | RSU emits non-null `estimated_soc`, confidence, and ISAC proxy features from deterministic RSSI/Doppler/range/deceleration inputs; MAE can be evaluated later. |
| T006 | P7 | Add credit-point contract and client hooks | Obj-5, Obj-6 | New `contracts/CreditLedger.sol`, `logging_layer/chain_client.py`, tests/docs | Review | Codex | Contract supports award/redeem/query/history; Python client handles unavailable RPC gracefully. |
| T007 | P8 | Unify baseline evaluation | Obj-9, Obj-10 | Prefer new `eval/baselines.py`; reuse `eval/run_baseline.py`, `eval/run_comparison.py` | Blocked by T002/T003 | Builder | B1, B2, B3, and proposed system run under comparable seeds/configs and emit paper-ready metric tables. |
| T008 | P1/P3 | Review pluggable scheduler integration | Obj-3, Obj-8, Obj-9 | `scheduling/base_scheduler.py`, `scheduling/lava_scheduler.py`, `integration/coordinator.py`, tests | Done | Reviewer-A | Confirms scheduler injection has no hidden LAVA coupling and identifies any missing dummy-scheduler test coverage. |
| T009 | P1-P8 | Repo architecture and artifact audit | Obj-1 through Obj-10 | Whole repo, read-only | Done | Auditor-A | Produces current-state map, path corrections, artifact risks, and priority conflicts. |
| T010 | P3 | Persist/evaluate full-episode samples | Obj-7, Obj-9, Obj-10 | `integration/coordinator.py`, `eval/run_comparison.py`, `metrics/evaluator.py`, tests | Done | Builder-C | Comparison metrics must use complete episode samples, not `samples[-10:]`; existing compact report shape should remain available if needed. |
| T011 | P5 | Repair DRL transition semantics | Obj-8, Obj-9, Obj-10 | `scheduling/drl_scheduler.py`, `scheduling/replay_buffer.py`, tests | Ready | Unassigned | DRL stores true next states, terminal transitions, and reward attribution compatible with evaluator/reward formula. |
| T012 | P1/P5 | Add scheduler injection tests and distributed trainable policy decision | Obj-3, Obj-8, Obj-9 | `integration/coordinator.py`, `tests/test_scheduler_injection.py` | Done | Builder-D | Dummy scheduler tests cover injection, fallback routing, update/train calls; distributed trainable behavior is either supported or rejected clearly. |
| T015 | P2/P3 | Review T001/T002 implementation patches | Obj-4, Obj-7, Obj-9, Obj-10 | T001/T002 touched files and tests | Done | Reviewer-B | Findings decide whether T001/T002 can move from Review to Done or need follow-up fixes. |
| T016 | P2 | Fix V2G discharge completion obligation | Obj-4, Obj-7, Obj-9 | `sim/entities.py`, `sim/station_model.py`, `integration/v2g_dispatcher.py`, tests | Done | Builder-E | V2G discharge must update/recompute remaining required energy or completion checks so EVs cannot complete below `SoC_req_k`; regression test covers V2G before completion. |
| T017 | P3 | Tighten evaluator SoC satisfaction and lag semantics | Obj-7, Obj-9, Obj-10 | `metrics/evaluator.py`, tests | Done | Builder-F | SoC satisfaction denominator accounts for total/routed/admitted EVs or reports censored counts; scheduling lag does not present compute-latency fallback as physical lag without an explicit source flag. |
| T018 | P3/P5 | Review T010/T012 patches | Obj-3, Obj-8, Obj-9, Obj-10 | T010/T012 touched files and tests | Done | Reviewer-C | Findings decide whether T010/T012 can move from Review to Done or need follow-up fixes. |
| T019 | P2/P3 | Review T016/T017 fixes | Obj-4, Obj-7, Obj-9, Obj-10 | T016/T017 touched files and tests | Done | Reviewer-D | Findings decide whether T001/T002/T016/T017 can close together or need additional fixes. |
| T020 | P5 | Plan DRL transition repair | Obj-8, Obj-9, Obj-10 | `scheduling/drl_scheduler.py`, `scheduling/replay_buffer.py`, coordinator/evaluator interfaces | Done | Planner-A | Produces an implementation plan for true next states, terminal transitions, reward attribution, and tests before T011 code changes begin. |
| T021 | P0 | Remove dummy-data risk from experiment path | Obj-1, Obj-2, Obj-9, Obj-10 | Config, Docker experiment docs/scripts, evaluation runners, data-source validation | Review | Builder-G | Docker simulation experiments capture generated inputs/outputs as first-class artifacts with config/seed/provenance, fail fast on missing required data, and keep test-only fixtures out of reports. |
| T022 | P0 | Fix full-suite collection blocker | Obj-9 | `tests/test_plot_journal_results.py`, `eval/plot_journal_results.py`, requirements/docs | Done | Builder-H | Full test collection should not fail solely because optional plotting dependency `matplotlib` is absent; either declare dependency for experiment image or skip plotting tests when unavailable. |
| T023 | P0 | Review Docker experiment artifacts | Obj-1, Obj-2, Obj-9, Obj-10 | T021 touched files and generated artifact contract | Ready | Unassigned | Findings decide whether T021 can move from Review to Done or needs fixes before Docker experiments become the standard run path. |
| T024 | P3 | Implement pre-arrival slot reservation | Obj-3, Obj-4, Obj-9 | `sim/entities.py`, `sim/station_model.py`, `integration/coordinator.py`, tests | Review | Codex | Routing creates a station reservation before arrival, reservations hold capacity, arrival releases the reservation, and route logs include reservation records. |
| T025 | P7 | Add Purechain CreditLedger deployment setup | Obj-5, Obj-6, Obj-7 | `.env`, Hardhat config, deploy script, deployment docs | Review | Codex | Purechain network config exists for chain ID `900520900520`; deploy script updates contract address and deployment transaction hash in docs and `.env` after deployment. |
| T026 | P0 | Implement Fakhrooeian & Pitz benchmark scenarios | Obj-9, Obj-10 | `Benchmark/`, `tests/test_benchmark_fakhrooeian_pitz.py`, `reports/benchmark_fakhrooeian_pitz/` | Done | Codex | Reproduces the paper's four V2G scheduling cases with deterministic stochastic inputs, writes summary/timeseries/session artifacts, documents the DIgSILENT/proxy scope, and passes focused tests. |
| T013 | P8 | Make comparison protocol paper-defensible | Obj-9, Obj-10 | `eval/run_comparison.py`, `metrics/evaluator.py`, report generation | Blocked by T010/T011/T012 | Unassigned | Held-out train/eval seeds, evaluator-backed metrics, Section 5.5 reward alignment, robust `--drl-only`/`--load-drl` behavior. |
| T014 | P1-P8 | Correct documentation/path drift | Obj-1 through Obj-10 | `README.md`, `models.md`, possibly task docs | Ready | Unassigned | Docs distinguish built vs planned components and use actual repo paths such as `eval/`, `logging_layer/`, and missing contract/dashboard paths. |

## Current Execution Plan

1. Start with verification and evaluator work because they unlock defensible research metrics.
2. Review scheduler injection in parallel, since later DRL/baseline work depends on a clean interface.
3. Audit DRL readiness and repo state in parallel, without blocking T001/T002.
4. Use results from T001/T002/T004/T008/T009 to decide whether fast simulation or SoC proxy should be the next implementation focus.

## Subagent Assignments

| Agent | Role | Assigned Task IDs | Expected Output |
|---|---|---|---|
| Builder-A | Code Builder | T001 | Patch or implementation plan for SoC tracking verification plus tests; detailed log in `.claude/agent-logs/builder-a.md`. |
| Builder-B | Code Builder | T002 | Patch or implementation plan for `metrics/evaluator.py` plus tests; detailed log in `.claude/agent-logs/builder-b.md`. |
| Reviewer-A | Code Reviewer | T008 | Review findings with file/line references and test gaps; detailed log in `.claude/agent-logs/reviewer-a.md`. |
| Auditor-A | Code Auditor | T004, T009 | DRL/repo audit findings, risk ranking, and sequencing recommendations; detailed log in `.claude/agent-logs/auditor-a.md`. |

## Status Legend

- Ready: Can start now.
- In Progress: Actively being worked.
- Blocked: Depends on another task or missing decision.
- Review: Patch exists and needs review.
- Done: Implemented, reviewed, and verified.
- Deferred: Intentionally postponed with reason.
