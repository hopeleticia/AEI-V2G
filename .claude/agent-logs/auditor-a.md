# Auditor-A Log

## 2026-05-13T02:23:30Z - T004/T009 - DRL scheduler and repo architecture audit

Scope: Read-only audit of DRL scheduler readiness, replay buffer behavior, LAVA-vs-DRL comparison fairness, repository architecture/artifact state, safety invariants, and paper defensibility. Source files were not modified.

Files read:
- `tasks.md`
- `dev-log.md`
- `requirements.txt`
- `README.md`
- `scheduling/base_scheduler.py`
- `scheduling/lava_scheduler.py`
- `scheduling/drl_scheduler.py`
- `scheduling/replay_buffer.py`
- `integration/coordinator.py`
- `integration/v2g_dispatcher.py`
- `integration/metrics.py`
- `sim/entities.py`
- `sim/station_model.py`
- `config/constraints.yaml`
- `eval/run_comparison.py`
- `reports/journal_study/VALIDATION_DEFENSE.md`

Summary:
- DRL code exists and fits the `BaseScheduler` surface, but it is not ready for fair DRL-vs-LAVA paper claims.
- Highest risks are invalid DRQN transition construction, weak/biased comparison metrics, lack of complete episode samples in reports, and missing tests for DRL/replay/comparison behavior.
- Current validated artifacts are defensible as deterministic LAVA/digital-twin outputs, not as learned-policy superiority evidence.

Prioritized risks:
1. P0: `scheduling/drl_scheduler.py` stores each transition with `next_state == state` for both routing and V2G, so TD targets do not reflect environment dynamics. See `_pending_route_states.append((state, action_idx, state))` and `_pending_v2g_state = (state, action_idx, state)`, then `update()` stores those placeholders.
2. P0: DRL experiences are never marked terminal through normal coordinator flow. `update()` always passes `done=False`, while episode closure only happens at external `reset_episode()`. The final transition of each episode has no terminal target and no true final next state.
3. P0: `integration/coordinator.py` returns only `samples[-10:]`. `eval/run_comparison.py` computes PAR, TEC, latency, and revenue from `report["samples"]`, so comparisons use the last 10 ticks rather than the full episode.
4. P0: `eval/run_comparison.py` uses a reward proxy of `v2g_revenue - par_proxy * 10.0`, not the coordinator's DRL tick reward or the Section 5.5 formula stated in comments. `sensing_gain_delta_j` is therefore not defensible as reward(DRL+ISAC) - reward(LAVA/no sensing).
5. P1: Fairness risk: LAVA and DRL evaluation share seeds, but DRL trains on the same seed prefix used for evaluation. That creates train/eval leakage unless explicitly framed as on-policy adaptation.
6. P1: `--drl-only` leaves `lava_metrics` and `lava_rewards` empty, then `build_comparison_table()` indexes missing LAVA averages. This CLI path is broken.
7. P1: `--load-drl` skips training but leaves `training_log` empty; the summary loses checkpoint provenance and cannot report training status.
8. P1: DRL safety layer caps aggregate requested kW with a coarse `1 kW per battery percent headroom` proxy, while `apply_v2g()` enforces real SoC using battery capacity and per-EV 12 kW allocation. The final invariant is protected by `apply_v2g()`, but the DRL action/logged reason may overstate what can actually be supplied.
9. P1: Route/V2G hidden states persist across many independent EV routing decisions within a tick/episode. That may be intended for POMDP memory, but per-EV routing hidden state can mix unrelated vehicles unless justified and tested.
10. P2: Replay buffer samples with replacement from as few as 4 eligible episodes and does not include the currently open episode. This is acceptable for a small scaffold but weak for convergence claims and should be reported as such.
11. P2: DRL files have no dedicated tests in `tests/`; `rg` found no tests for `DRLScheduler`, `SequenceReplayBuffer`, checkpoint load/save, or `eval/run_comparison.py`.
12. P2: Documentation and several source comments contain mojibake/encoding artifacts (`â€”`, `Îµ`, box drawing corruption). This is not a runtime blocker, but it hurts paper/repo professionalism and traceability.
13. P2: README final folder structure lists `blockchain/`, `logging/`, `dashboard/`, and `lava/cost_functions.py`, but actual repo has `logging_layer/`, no dashboard, no blockchain package, and no `lava/cost_functions.py`. Mark those as planned/missing or correct paths.
14. P2: Validated journal artifacts are strong for LAVA deterministic digital-twin claims, but there is no `reports/comparison/` DRL artifact set present. Avoid claiming DRL comparison results until generated and validated.

Recommended sequencing:
1. Finish T001/T002 first so per-EV SoC and a real evaluator provide trustworthy state/reward/metrics.
2. Fix coordinator/evaluation data plumbing before DRL experiments: return or persist full episode samples, compute evaluator metrics from complete runs, and isolate train/eval seeds.
3. Repair DRL transition semantics: true next states, terminal transitions, reward attribution, and tests for route/V2G buffer entries.
4. Add focused unit tests for `SequenceReplayBuffer`, DRL safety action remapping, checkpoint save/load, and comparison CLI edge cases.
5. Only then run a small DRL smoke comparison, followed by full N-train/N-eval runs under a new `reports/comparison_*` directory.
6. After DRL artifacts exist, add validation similar to `reports/journal_study/VALIDATION_DEFENSE.md` and clearly separate deterministic LAVA results from learned-policy results in the paper.

Status: Audit complete. No source changes made. This log file was created as the allowed Auditor-A artifact.
