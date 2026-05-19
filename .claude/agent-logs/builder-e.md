# Builder-E Log

## 2026-05-13T02:42:15Z - T016 - V2G Discharge Completion Obligation

Summary: Fixed the V2G completion invariant so an active charging EV discharged for grid support cannot complete until it has recovered to its driver-requested SoC.

Context read:
- `tasks.md`: T016 requires preserving the 20% V2G floor and actual V2G kWh accounting while preventing completion below `SoC_req_k`.
- `dev-log.md`: confirmed prior T001 implementation and Reviewer-B follow-up task creation.
- `.claude/agent-logs/reviewer-b.md`: reproduced the stale `required_kwh` failure mode after V2G discharge.
- `.claude/agent-logs/builder-a.md`: confirmed existing SoC/SoH helpers, V2G actual-kWh accounting, and the known full-suite `matplotlib` blocker.

Changes made:
- Added EV helpers in `sim/entities.py` to compute kWh needed from current SoC to `SoC_req_k` using `SoH_k * NOMINAL_BATTERY_KWH`, refresh `required_kwh` without lowering an existing obligation, and check requested-SoC satisfaction with a small tolerance.
- Updated `sim/station_model.py` so every active charging tick refreshes the request obligation before charging and only completes an EV when both `required_kwh <= 0.1` and `battery_pct >= SoC_req_k`.
- Updated `integration/v2g_dispatcher.py` so after actual V2G energy is supplied, the EV's remaining completion obligation is increased to cover any new SoC deficit. The 20% floor and actual delivered `kwh` accounting remain inside `EV.discharge_v2g_kwh()` and the existing station/result counters.
- Added a regression in `tests/test_soc_flow.py` where an EV at 70% with `SoH_k=0.8` and `SoC_req_k=80` supplies 12 kWh through V2G, drops to 49.17%, has `required_kwh` raised to 17.76, and then completes only after charging back to the requested SoC.

Verification:
- Passed: `python -m pytest tests/test_soc_flow.py --basetemp=.pytest-tmp` (4 passed).
- Passed: `python -m pytest tests/test_soc_flow.py tests/test_v2g_trigger.py tests/test_sim_basic.py tests/test_e2e_basic.py --basetemp=.pytest-tmp` (7 passed).
- Passed: `python -m pytest tests/test_soc_flow.py tests/test_metrics_evaluator.py tests/test_v2g_trigger.py tests/test_sim_basic.py tests/test_e2e_basic.py --basetemp=.pytest-tmp` (11 passed).
- Full suite attempted: `python -m pytest --basetemp=.pytest-tmp` still blocked during collection by missing optional dependency `matplotlib` in `tests/test_plot_journal_results.py`, matching the pre-existing Reviewer-B note.

Files changed:
- `sim/entities.py`
- `sim/station_model.py`
- `integration/v2g_dispatcher.py`
- `tests/test_soc_flow.py`
- `.claude/agent-logs/builder-e.md`

Dev-log note: Project lead should append the matching `dev-log.md` entry for this Builder-E T016 turn.
