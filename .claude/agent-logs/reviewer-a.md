# Reviewer-A Log

## 2026-05-13T11:24:07+09:00 - T008 Pluggable Scheduler Integration Review

Scope reviewed:

- `tasks.md` T008 acceptance criteria and scheduler-related operating rules.
- `scheduling/base_scheduler.py`
- `scheduling/lava_scheduler.py`
- `scheduling/drl_scheduler.py`
- `integration/coordinator.py`
- `integration/node_comms.py`
- `integration/metrics.py`
- Scheduler-adjacent tests under `tests/`
- Obvious scheduler consumers in `eval/run_comparison.py` and `eval/run_journal_study.py`

Commands run:

- `python -m pytest tests/test_e2e_basic.py tests/test_v2g_trigger.py tests/test_sim_basic.py -q` failed at setup because pytest tried to use `C:\Users\HOPE\AppData\Local\Temp\pytest-of-HOPE`, which is not accessible in this sandbox.
- `python -m pytest tests/test_e2e_basic.py tests/test_v2g_trigger.py tests/test_sim_basic.py -q --basetemp=.pytest_tmp` passed: `3 passed in 0.06s`.
- Ad hoc dummy scheduler injection into `integration.coordinator.run(...)` for standalone mode completed successfully and returned metrics, confirming the simplest injected scheduler path works when the dummy returns the LAVA-shaped minimum fields.

Findings:

1. High: Distributed mode accepts an injected trainable scheduler but never calls `update()` or `train()`.
   - Standalone mode has a reward/update/train block guarded by `scheduler.is_trainable` at `integration/coordinator.py:130-138`.
   - `_run_lava_validator()` also accepts `scheduler: BaseScheduler | None` and uses it for `route_ev()` / `dispatch_v2g()` at `integration/coordinator.py:508` and `integration/coordinator.py:524`, but there is no matching reward/update/train block before the loop advances.
   - For DRL or any future online scheduler, distributed deployment silently collects decisions without learning. This is an interface mismatch because `run(..., scheduler=...)` and the role path imply scheduler substitution works in both standalone and distributed paths.
   - Research impact: Obj-8/Obj-9 distributed DRL-vs-LAVA comparison would not be equivalent to standalone training/evaluation.

2. Medium: Metrics and sample fields still label injected scheduler behavior as LAVA, which can contaminate research interpretation.
   - `_run_standalone()` records the injected scheduler's wait metric under `lava_wait` and emits `lava_wait_min` at `integration/coordinator.py:101`, `integration/coordinator.py:113`, and `integration/coordinator.py:147`.
   - `integration/metrics.py:7` and `integration/metrics.py:20` consume `lava_wait_min` to compute `ev_wait_time_reduction_pct`.
   - With `DRLScheduler` or a dummy/baseline scheduler injected, the values are not LAVA values, but report consumers will read them as LAVA. This is not a runtime crash, but it weakens Obj-9/Obj-10 paper defensibility because scheduler identity is lost in the report.

3. Medium: Hidden LAVA coupling remains in distributed topic and role names.
   - `integration/coordinator.py:49-50` selects the decision node only for `_NODE_ROLE == "lava-validator"`.
   - `integration/coordinator.py:258`, `integration/coordinator.py:416`, and `integration/coordinator.py:545` describe/report the role as LAVA-specific even when another scheduler is injected.
   - `integration/node_comms.py:14-15` defines `TOPIC_LAVA_ROUTE` and `TOPIC_LAVA_V2G`, and station validators subscribe to those at `integration/coordinator.py:282-283`.
   - The operating rules say MQTT names are fixed unless all producers and consumers change together, so this may be intentionally preserved wire compatibility. Still, the abstraction boundary is not scheduler-neutral, and new scheduler deployments will look like LAVA in telemetry and operational logs.

4. Medium: There is no committed dummy-scheduler coverage for the pluggability contract.
   - `tests/test_e2e_basic.py:4-8` calls `run(...)` without `scheduler=`, so it only covers the default `LAVAScheduler`.
   - The current suite has no test asserting that an injected scheduler's `route_ev()` and `dispatch_v2g()` are called, no test that `None` station fallback works for a non-LAVA scheduler, and no test that a trainable injected scheduler receives `update()` / `train()` in standalone mode.
   - This is exactly the T008 acceptance gap; the ad hoc dummy scheduler run passed, but that protection should be committed.

5. Low: `config_path` is accepted by `_default_scheduler(config_path)` but ignored.
   - `integration/coordinator.py:26-30` always loads `config/lava_weights.yaml`, `config/rules.yaml`, and `config/constraints.yaml`.
   - This preserves existing LAVA defaults, but for a pluggable configuration story it is misleading: scenario-specific coordinator config does not influence default scheduler construction.

Positive notes:

- `BaseScheduler` is narrow and the standalone coordinator path does use the injected object for both routing and V2G.
- `LAVAScheduler` is a thin adapter and delegates without adding extra behavior.
- A minimal ad hoc non-LAVA scheduler works in standalone mode when it returns the documented fields (`station_id`, `value_kw`, `latency_ms`, etc.).

Recommended next actions:

- Add `tests/test_scheduler_injection.py` with a `DummyScheduler` that counts calls, returns `station_id=None` for routing fallback, returns zero V2G, and asserts standalone reports still complete.
- Add a `TrainableDummyScheduler` asserting `update()` and `train()` are called in standalone mode.
- Decide whether distributed trainable schedulers are in scope now. If yes, add scheduler-neutral reward plumbing or explicitly reject trainable schedulers in `_run_lava_validator()` with a clear error.
- Rename internal/report fields from `lava_wait_min` to scheduler-neutral names while preserving legacy aliases if existing artifacts depend on them.
- Project lead should append the matching high-level entry to `dev-log.md`.
