# Reviewer-B Log

## 2026-05-13T02:35:13Z - T015 - Review T001/T002

Summary: Reviewed completed T001/T002 patches for SoC-flow safety and paper-facing metric correctness. Targeted tests passed, but the review found one high-severity SoC/V2G correctness bug and two metric-defensibility issues that should block moving both tasks fully to Done without follow-up.

Context read:
- `tasks.md`: T001/T002 are in Review; battery safety and research metrics are explicit acceptance criteria.
- `dev-log.md`: Builder-A and Builder-B summaries and verification notes.
- `.claude/agent-logs/builder-a.md`: T001 implementation scope and known full-suite matplotlib blocker.
- `.claude/agent-logs/builder-b.md`: T002 evaluator scope and known limitations around truncated samples and missing arrival timestamps.
- `models.md`: checked the research definitions for PAR, TEC, SoC satisfaction, scheduling lag, and degradation.

Files reviewed:
- `sim/entities.py`
- `sim/station_model.py`
- `integration/v2g_dispatcher.py`
- `integration/coordinator.py`
- `tests/test_soc_flow.py`
- `metrics/__init__.py`
- `metrics/evaluator.py`
- `tests/test_metrics_evaluator.py`

Findings:
1. High - V2G discharge can make an active charging EV complete far below `SoC_req_k`.
   - `integration/v2g_dispatcher.py:23` discharges active station EVs through `ev.discharge_v2g_kwh()`.
   - `sim/station_model.py:11-13` only decrements `required_kwh` by subsequent charging energy and completes the session when `required_kwh <= 0.1`.
   - `sim/entities.py:50-56` lowers `battery_pct` for V2G but does not increase/recompute remaining charge obligation against `SoC_req_k`.
   - Repro probe: an EV at 70% with `SoC_req_k=80` and `required_kwh=7.2` supplies 12 kWh via V2G, falls to 53.33%, then one 7.2 kWh charge tick completes at 63.33%, still below the 80% request.
   - Impact: this breaks the T001 SoC/request flow and makes T002 SoC satisfaction results misleading after V2G. The 20% hard floor is preserved, but the driver-request invariant is not.
   - Suggested follow-up: after any V2G discharge, recompute/increase `required_kwh` from current SoC to `SoC_req_k` (SoH-adjusted) or make station completion check `battery_pct >= SoC_req_k` in addition to remaining kWh. Add a regression test where V2G occurs before completion.

2. Medium - SoC satisfaction denominator ignores non-completed/routed EVs, inflating the paper metric.
   - `metrics/evaluator.py:139-152` increments `total` only for sessions that already have final and required SoC.
   - `metrics/evaluator.py:355-365` derives sessions only from explicit session lists and `ev_completed` records.
   - `models.md:463` defines the denominator as `K_total`, not only completed sessions with complete fields.
   - Repro probe: an episode with two `route` events and one satisfied `ev_completed` event reports 100% satisfaction with `total_evs=1`; under the paper denominator, the incomplete routed EV should either count against `K_total` or be surfaced separately as censored/incomplete.
   - Impact: fixed-duration simulations can overstate driver satisfaction, especially when queues or late sessions remain incomplete at episode end.
   - Suggested follow-up: accept/derive `total_evs` or count unique routed/admitted EVs, and report incomplete/censored counts separately if the research decision is to exclude them.

3. Medium - Scheduling lag falls back to compute latency as `mean_lag_seconds`, which is not the paper's lag definition.
   - `metrics/evaluator.py:223-228` returns `latency_ms / 1000` in the main lag fields when no arrival/dispatch pairs exist.
   - `models.md:486-488` defines lag as physical arrival time to dispatch time.
   - Impact: current coordinator artifacts that lack arrival timestamps can appear to have near-zero scheduling lag because scheduler compute latency is tiny, overstating ISAC value. The evaluator does expose `ev_count=0` and `latency_fallback_ms_avg`, but downstream users may still consume `mean_lag_seconds` as a valid lag metric.
   - Suggested follow-up: return `mean_lag_seconds=None` when only latency fallback exists, or add an explicit `lag_source`/`is_fallback` flag and keep fallback out of the main paper metric.

Positive notes:
- T001 now preserves `SoH_k`, `SoC_req_k`, `T_dep_k`, and `soc_trajectory` through RSU sensing, station state snapshots, and completion logs.
- V2G actual-energy accounting correctly subtracts remaining dispatch by delivered kWh and enforces the 20% floor in the reviewed probe.
- T002 evaluator is pure for the tested in-memory sample cases and prefers `full_samples` before truncated `samples`.

Verification:
- Passed: `python -m pytest tests/test_soc_flow.py tests/test_metrics_evaluator.py --basetemp=.pytest-tmp-reviewer-b` (7 passed).
- Passed: `python -m pytest tests/test_soc_flow.py tests/test_metrics_evaluator.py tests/test_v2g_trigger.py tests/test_sim_basic.py tests/test_e2e_basic.py --basetemp=.pytest-tmp-reviewer-b` (10 passed).
- Full suite attempted: `python -m pytest --basetemp=.pytest-tmp-reviewer-b` blocked at collection by missing optional dependency `matplotlib` in `tests/test_plot_journal_results.py`; no additional tests ran.

Files changed:
- `.claude/agent-logs/reviewer-b.md`

Dev-log note: project lead should append the matching `dev-log.md` entry for this review turn.
