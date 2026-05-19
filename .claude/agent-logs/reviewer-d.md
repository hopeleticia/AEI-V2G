# Reviewer-D Log

## 2026-05-13T03:00:00Z - T019 - Review T016/T017 Fixes

Summary: Reviewed Builder-E's T016 V2G completion fix, Builder-F's T017 evaluator semantics fix, and the combined T001/T002 foundation. No blocking regressions found. T001/T002/T016/T017 can move to Done together, subject to the known full-suite collection blocker described below.

Context read:
- `tasks.md`: T001/T002 are in Review, T016/T017 are in Review, and T019 acceptance requires a close/no-close decision across all four tasks.
- `.claude/agent-logs/builder-e.md`: T016 claims V2G discharge now refreshes completion obligation and station completion checks requested SoC.
- `.claude/agent-logs/builder-f.md`: T017 claims SoC denominator and scheduling lag semantics now expose censored counts and latency fallback metadata.
- `.claude/agent-logs/reviewer-b.md`: prior T015 blockers were the stale V2G completion obligation, completed-only SoC satisfaction denominator, and compute-latency scheduling lag fallback.
- `.claude/agent-logs/builder-a.md` and `.claude/agent-logs/builder-b.md`: original T001/T002 implementation context and known full-suite `matplotlib` blocker.

Files reviewed:
- `sim/entities.py`
- `sim/station_model.py`
- `integration/v2g_dispatcher.py`
- `integration/coordinator.py`
- `metrics/evaluator.py`
- `tests/test_soc_flow.py`
- `tests/test_metrics_evaluator.py`
- `tests/test_full_episode_samples.py`
- `tests/test_v2g_trigger.py`

Findings:
- No blocking findings.

Review notes:
- Battery safety: `EV.discharge_v2g_kwh()` still caps V2G discharge at `MIN_V2G_SOC_PCT = 20.0`, records actual SoC changes only when kWh is supplied, and returns actual delivered kWh. `apply_v2g()` uses that actual kWh for station/result accounting and for decrementing remaining dispatch power.
- SoC_req completion correctness: T016 addresses Reviewer-B's failure mode in two places. `apply_v2g()` calls `ev.refresh_required_kwh_for_request()` after actual discharge, increasing the remaining obligation if V2G creates a new deficit. `update_station()` refreshes the request obligation before charging and only completes an EV when both `required_kwh <= 0.1` and `battery_pct >= SoC_req_k`.
- V2G actual kWh accounting: the reviewed path keeps `station.v2g_supplied_kwh`, result `supplied_kwh`, and revenue based on actual `kwh` returned by the EV discharge helper, not requested dispatch kWh.
- Evaluator SoC denominator: `evaluate_episode()` now passes `_ev_population()` into `soc_satisfaction()`. Population derives explicit `total_evs`/`K_total` first, then routed EVs, then admitted EVs, then sessions. The route/complete merge by `ev_id` makes a routed-but-not-completed EV count in the denominator and surface as censored/incomplete instead of disappearing.
- Evaluator lag semantics: `scheduling_lag()` keeps compute latency in `latency_fallback_ms_avg` and returns `mean_lag_seconds=None`/`max_lag_seconds=None` with `is_latency_fallback=True` when no physical arrival-dispatch or explicit sample lag is available.
- Backwards compatibility: direct `soc_satisfaction(sessions)` still works without population metadata; `evaluate_episode()` still accepts coordinator reports, JSONL records, sample dictionaries, and synthetic events. New evaluator fields are additive.
- Test adequacy: focused tests now cover the prior V2G completion regression, actual safe V2G energy accounting, routed denominator/censored SoC satisfaction, latency-only lag fallback, direct evaluator calls, and full-vs-compact sample preference. Remaining gap is not in these tasks: the full suite cannot collect until optional plotting dependency handling is fixed.

Additional probe:
- Ran a coordinator-shaped evaluator probe with route records carrying nested `ev_feature` plus one completion. Result: SoC satisfaction reported 50.0%, `total_evs=2`, `incomplete_ev_ids=['ev-b']`; scheduling lag reported `mean_lag_seconds=None`, `is_latency_fallback=True`, and latency fallback average 1.5 ms. This matches the intended T017 semantics for current coordinator artifacts that lack physical arrival timestamps.

Verification:
- Passed: `python -m pytest tests/test_soc_flow.py tests/test_metrics_evaluator.py tests/test_v2g_trigger.py tests/test_sim_basic.py tests/test_e2e_basic.py --basetemp=.pytest-tmp-reviewer-d` (13 passed).
- Passed: `python -m pytest tests/test_full_episode_samples.py --basetemp=.pytest-tmp-reviewer-d` (3 passed).
- Full suite attempted: `python -m pytest --basetemp=.pytest-tmp-reviewer-d` failed during collection because `tests/test_plot_journal_results.py` imports `eval.plot_journal_results`, which imports missing optional dependency `matplotlib`. This matches prior reviewer/builder notes and is not caused by T016/T017.

Decision:
- T001: can move to Done.
- T002: can move to Done.
- T016: can move to Done.
- T017: can move to Done.
- No T019 follow-up blocker is required for these four tasks. A separate backlog item should handle optional `matplotlib` dependency or test skipping for full-suite collection.

Dev-log note: project lead should append the matching `dev-log.md` entry for this Reviewer-D/T019 review turn.
