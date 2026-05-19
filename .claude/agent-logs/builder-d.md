# Builder-D Log

## 2026-05-13T02:33:04Z - T012 Scheduler Injection Tests and Distributed Trainable Decision

Scope:

- Read `tasks.md`, `dev-log.md`, and `.claude/agent-logs/reviewer-a.md`.
- Reviewed scheduler integration in `integration/coordinator.py`, metrics compatibility in `integration/metrics.py`, and the scheduler contract in `scheduling/base_scheduler.py`.
- Kept MQTT topic names unchanged.

Changes:

- Added `tests/test_scheduler_injection.py` with committed dummy scheduler coverage:
  - injected scheduler route and dispatch methods are called in standalone mode;
  - `station_id=None` route decisions complete through the standalone nearest-station fallback;
  - trainable dummy schedulers receive one `update()` and one `train()` call per standalone tick;
  - distributed lava-validator rejects trainable schedulers before subscribing or publishing.
- Updated `integration/coordinator.py` so `_run_lava_validator()` raises a clear `ValueError` and prints an operator-facing message when an injected scheduler reports `is_trainable=True`.

Decision:

- Distributed trainable schedulers are explicitly rejected for now. Supporting online learning safely would require distributed reward plumbing across RSU, station, and grid roles; silently accepting trainable schedulers is worse because it produces route/V2G decisions without learning.

Verification:

- `python -m pytest tests/test_scheduler_injection.py -q --basetemp=.pytest-tmp` passed: 4 tests.
- `python -m pytest tests/test_scheduler_injection.py tests/test_e2e_basic.py tests/test_v2g_trigger.py tests/test_sim_basic.py -q --basetemp=.pytest-tmp` passed: 7 tests.
- `python -m pytest tests -q --basetemp=.pytest-tmp` did not complete collection because `matplotlib` is not installed for `tests/test_plot_journal_results.py`; no T012 failure was observed before collection stopped.

Project lead reminder:

- Append the high-level T012 completion entry to `dev-log.md` after reviewing this Builder-D log.
