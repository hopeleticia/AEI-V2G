# Builder-A Log

## 2026-05-13T02:26:20Z - T001 - Per-EV SoC Tracking

Summary: Hardened the per-EV battery-state flow from EV creation and RSU sensing through station admission, charging/V2G mutation, station state publication, and completion logs.

Context read:
- `tasks.md`: T001 acceptance requires SoC/SoH/SoC_req/T_dep flow from spawn to RSU feature to station admission to completion logs, with charge and V2G trajectory updates.
- `models.md`: Battery model defines per-EV SoC, SoH, SoC_req, T_dep, SoC satisfaction, and V2G 20% minimum SoC safety.
- Existing code already carried `SoH_k`, `SoC_req_k`, `T_dep_k` in RSU features and completion logs, but mutation logic was split across modules and V2G did not append `soc_trajectory`.

Changes made:
- Added EV-level battery helpers in `sim/entities.py`: usable SoH-adjusted capacity, initial trajectory seeding, trajectory recording, charge application, and V2G discharge with a 20% SoC floor.
- Updated `sim/station_model.py` to charge through the EV helper so SoH-aware charge delivery and `soc_trajectory` updates use one path.
- Updated `integration/v2g_dispatcher.py` to discharge through the EV helper, append V2G trajectory points, report actual safe kWh supplied, and continue dispatch allocation using actual delivered energy when a vehicle hits the SoC floor.
- Updated `integration/coordinator.py` standalone and distributed station paths so V2G calls include the current tick; route-to-station reconstruction uses `SoC_req_k` and `SoH_k` when computing fallback `required_kwh`; station state publications preserve `SoH_k`, `SoC_req_k`, `T_dep_k`, and `soc_trajectory`; lava-validator station snapshots reconstruct those fields instead of defaulting them away.
- Added `tests/test_soc_flow.py` to cover RSU feature fields, station charge trajectory/completion fields, and V2G trajectory/safety/actual-energy accounting.

Verification:
- Passed: `python -m pytest tests\test_soc_flow.py tests\test_v2g_trigger.py tests\test_sim_basic.py tests\test_e2e_basic.py --basetemp=.pytest-tmp`
- Broader `python -m pytest --basetemp=.pytest-tmp` is blocked at collection by missing optional dependency `matplotlib` imported by `tests/test_plot_journal_results.py`; this is unrelated to T001 and occurs before running the test suite.

Files changed:
- `sim/entities.py`
- `sim/station_model.py`
- `integration/v2g_dispatcher.py`
- `integration/coordinator.py`
- `tests/test_soc_flow.py`
- `.claude/agent-logs/builder-a.md`

Dev-log note: I did not append `dev-log.md` because the user's write scope named my own agent log but only read access for `dev-log.md`; project lead should append the matching entry.
