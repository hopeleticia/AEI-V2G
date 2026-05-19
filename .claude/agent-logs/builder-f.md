# Builder-F Agent Log

## 2026-05-13T02:43:16Z - T017

Summary: Tightened evaluator semantics for paper-facing SoC satisfaction and scheduling lag after Reviewer-B's probes. SoC satisfaction now uses an explicit/derived denominator when total, routed, or admitted EV counts are available and reports incomplete/censored EVs separately. Scheduling lag now keeps compute-latency-only fallback out of `mean_lag_seconds` and exposes source/fallback flags.

Context read:
- `tasks.md`: T017 scope, acceptance checks, write boundaries, and append-only coordination rules.
- `dev-log.md`: current project movement and T015/T017 context.
- `.claude/agent-logs/reviewer-b.md`: reviewed the exact SoC-denominator and lag-fallback probes.
- `.claude/agent-logs/builder-b.md`: original evaluator intent and known limitations.
- `models.md`: Section 6.3 SoC satisfaction denominator `K_total` and Section 6.4 physical arrival-to-dispatch lag definition.

Files changed:
- `metrics/evaluator.py`
- `tests/test_metrics_evaluator.py`
- `.claude/agent-logs/builder-f.md`

Implementation notes:
- Added `population` metadata support to `soc_satisfaction()` while preserving direct-call compatibility.
- `evaluate_episode()` now derives the SoC denominator from explicit `total_evs`/`K_total`, otherwise routed EVs, otherwise admitted EVs, otherwise session count.
- Route/admission/completion records are merged by `ev_id` so a routed-but-not-completed EV is visible to the satisfaction denominator instead of disappearing.
- Added satisfaction fields: `evaluable_evs`, `completed_evs`, `incomplete_evs`, `censored_evs`, `routed_evs`, `admitted_evs`, `denominator_source`, and `incomplete_ev_ids`.
- Changed latency-only scheduling lag behavior so `mean_lag_seconds` and `max_lag_seconds` remain `None` when no physical lag observation exists.
- Added scheduling-lag fields: `lag_source` and `is_latency_fallback`; retained `latency_fallback_ms_avg` for compatibility and diagnostic use.
- Sample-level explicit `scheduling_lag_s`/`lag_s` still populates the physical lag metric and is marked with `lag_source="sample_lag"`.

Regression coverage:
- Added a Reviewer-B reproduction where two route events and one satisfied completion now report 50% satisfaction, `total_evs=2`, and one incomplete/censored EV.
- Added a latency-only lag reproduction where compute latency is reported only as fallback metadata, not as physical `mean_lag_seconds`.

Verification:
- Passed: `python -m pytest tests/test_metrics_evaluator.py -q --basetemp=.pytest-tmp` (6 passed).
- Passed: `python -m pytest tests/test_full_episode_samples.py -q --basetemp=.pytest-tmp-full` (3 passed).
- Passed: `python -m pytest tests/test_soc_flow.py tests/test_metrics_evaluator.py tests/test_v2g_trigger.py tests/test_sim_basic.py tests/test_e2e_basic.py --basetemp=.pytest-tmp-builder-f` (13 passed).

Known notes:
- This turn did not edit `dev-log.md` because the requested write scope only allowed Builder-F's own detailed log. Project lead should append the matching `dev-log.md` entry for T017.
