# Planner-A Log

## 2026-05-13T02:55:44Z - T020/T011 preparation - DRL transition semantics repair plan

Scope: Planning only. No source files were modified. Read `tasks.md`, `dev-log.md`, `.claude/agent-logs/auditor-a.md`, `scheduling/drl_scheduler.py`, `scheduling/replay_buffer.py`, `integration/coordinator.py`, `metrics/evaluator.py`, `scheduling/base_scheduler.py`, `integration/v2g_dispatcher.py`, and the existing tests.

Summary:
- T011 should repair DRQN experience construction before any paper-defensible DRL comparison is attempted.
- The current DRL scheduler records self-loop transitions at `scheduling/drl_scheduler.py:386` and `scheduling/drl_scheduler.py:428`, then stores every transition as non-terminal at `scheduling/drl_scheduler.py:449` and `scheduling/drl_scheduler.py:455`.
- `SequenceReplayBuffer` already supports terminal transitions by closing an episode when `done=True` at `scheduling/replay_buffer.py:62-67`; the missing piece is that DRL never passes `done=True` during normal coordinator-driven episodes.

Recommended implementation plan for T011:

1. Add a backward-compatible richer update path.
   - Preferred change: update `scheduling/base_scheduler.py:88` from `update(self, reward: float)` to `update(self, reward: float, **context: object)`.
   - Update the docstring at `scheduling/base_scheduler.py:89-101` to define optional context keys:
     - `next_stations`: station mapping after routing, arrival admission, V2G application, and station mutation for the tick.
     - `next_grid_state`: post-action grid state; in standalone this should be `relieved_grid`.
     - `done`: true only on the final simulation tick for the episode.
     - `reward_components`: optional dict for traceability of PAR/TEC/degradation/SoC terms.
   - To preserve third-party/simple schedulers with `update(reward)` only, either:
     - Use `inspect.signature` in the coordinator before passing context, or
     - Add a private coordinator helper that calls rich update only when the scheduler override accepts `**context`; otherwise falls back to `scheduler.update(tick_reward)`.
   - Avoid a broad `try/except TypeError` around scheduler update because that can hide real implementation errors inside scheduler code.

2. Capture enough pending metadata in `DRLScheduler`.
   - Replace `_pending_route_states` declared at `scheduling/drl_scheduler.py:360` with route transition records that include at least `(state, action_idx, ev_feature)` rather than `(state, action_idx, placeholder_next_state)`.
   - Replace `_pending_v2g_state` at `scheduling/drl_scheduler.py:361` with `(state, action_idx)`.
   - Remove `_last_v2g_state` at `scheduling/drl_scheduler.py:363-364` unless the implementation keeps it strictly for diagnostics; it does not currently solve next-state construction.
   - In `route_ev()` at `scheduling/drl_scheduler.py:384-386`, append the copied EV feature and selected action. Do not store `state` as its own next state.
   - In `dispatch_v2g()` at `scheduling/drl_scheduler.py:428`, store only the pre-action V2G state and effective/safety-remapped action.

3. Build true next states in `DRLScheduler.update()`.
   - Change `DRLScheduler.update()` at `scheduling/drl_scheduler.py:443-456` to accept the optional context.
   - For every pending route transition, build `next_state = self._build_route_state(ev_feature, next_stations, next_grid_state)`.
   - For pending V2G, build `next_state = self._build_v2g_state(next_stations, next_grid_state)`.
   - If `next_stations` or `next_grid_state` is absent, use a conservative fallback for compatibility: build from the original state only as a last resort and mark/log this path in code comments or decision trace. The coordinator path used for training must provide the real context.
   - Store with `done=bool(context.get("done", False))` so final transitions have zero bootstrapped target via existing `td_target = rewards + GAMMA * q_next * (1.0 - dones)` at `scheduling/drl_scheduler.py:250`.

4. Mark terminal transitions from standalone coordinator.
   - In `_run_standalone()`, compute `last_tick = minute == (duration // 60) - 1` near the loop at `integration/coordinator.py:80`.
   - At `integration/coordinator.py:137`, call the rich update with:
     - `reward=tick_reward`
     - `next_stations=corridor.stations`
     - `next_grid_state=relieved_grid`
     - `done=last_tick`
     - `reward_components={...}`
   - Keep `scheduler.train()` at `integration/coordinator.py:138` after update.
   - Do not add trainable distributed support in `_run_lava_validator()`: `integration/coordinator.py:447-453` explicitly rejects trainable schedulers until distributed reward plumbing exists. T011 should leave that invariant intact.

5. Reward attribution policy for T011.
   - Attribute the tick reward to every route decision made during that tick and to the V2G dispatch decision for that tick, but now the reward must be paired with post-action next states instead of placeholder states.
   - Add `reward_components` to the context for auditability. Suggested component keys are `par_penalty`, `tec_penalty`, `v2g_reward`, `stress_relief`, and, once T016/T017 are accepted, `degradation_penalty` and `soc_satisfaction_delta` if available.
   - Do not claim full Section 5.5 evaluator alignment unless the formula is harmonized with `metrics/evaluator.py` (`DEFAULT_REWARD_WEIGHTS` and `episode_reward()` at `metrics/evaluator.py:11-18` and `metrics/evaluator.py:339-353`). That broader comparison cleanup belongs with T013, but T011 should avoid making attribution less compatible with evaluator terminology.

6. Replay buffer changes.
   - No behavioral change is required in `SequenceReplayBuffer.push()` because `done=True` already closes the current episode at `scheduling/replay_buffer.py:62-67`.
   - Add focused tests for the existing terminal behavior instead of changing the buffer unless implementation discovers a bug.
   - If tests need visibility, inspect `_episodes` and `_current_episode` directly in unit tests; avoid adding public API solely for tests unless reviewers prefer it.

Focused tests to add:

1. New `tests/test_drl_transition_semantics.py`.
   - Use lightweight fake station and fake agent objects so tests do not require PyTorch.
   - Monkeypatch `scheduling.drl_scheduler._TORCH_AVAILABLE = True` only around transition-plumbing tests, or instantiate `DRLScheduler` via `__new__` and inject fake `_route_agent`/`_v2g_agent`.
   - Test route transition:
     - Call `route_ev()` with initial station/grid state.
     - Mutate station utilization/queue/availability or pass a separate post-state.
     - Call `update(reward, next_stations=post_stations, next_grid_state=post_grid, done=False)`.
     - Assert the recorded `Step.next_state` differs from `Step.state` and matches `_build_route_state(ev_feature, post_stations, post_grid)`.
   - Test V2G transition:
     - Call `dispatch_v2g()` with pre-action station/grid.
     - Apply post-action station/grid changes.
     - Call rich `update()`.
     - Assert next state matches `_build_v2g_state(post_stations, post_grid)`.
   - Test terminal transition:
     - Call rich `update(..., done=True)`.
     - Assert stored step has `done is True`.
     - Assert the fake buffer or real `SequenceReplayBuffer` closes/has one completed episode.

2. Extend `tests/test_scheduler_injection.py`.
   - Preserve `test_trainable_dummy_updates_and_trains_in_standalone()` expectations at `tests/test_scheduler_injection.py:108-121`.
   - Add a trainable dummy scheduler variant whose `update()` accepts `**context` and records `done` flags; run a short standalone episode and assert exactly the final tick has `done=True`.
   - Verify a legacy `update(reward)` trainable dummy still receives 10 rewards without context-related `TypeError`.

3. Add or extend replay buffer unit coverage.
   - New direct test for `SequenceReplayBuffer.push(..., done=True)`:
     - After terminal push, `len(buffer) == 1`.
     - `buffer.total_steps` includes the completed step.
     - `_current_episode` is empty.
   - Add a non-terminal close test showing `close_episode()` still stores partial episodes for explicit `reset_episode()` behavior.

Dependencies and sequencing:
- T011 is not structurally blocked by T016/T017 because it can pass next-state context and terminal flags independently.
- T016 matters for correctness of the post-action station state: without the V2G discharge completion fix, route/V2G next states and reward consequences can encode EVs as complete even when V2G pushed them below `SoC_req_k`. Prefer landing T011 after T016 review passes, or at least rerun T011 tests after T016 changes merge.
- T017 matters for reward wording and paper defensibility. T011 can add `reward_components`, but it should not finalize a new Section 5.5 reward formula until T017 evaluator semantics are accepted. If T017 changes evaluator names/denominators, keep T011 reward component names aligned.
- T013 remains blocked until T011 is complete, because comparison results should not be generated from self-loop, non-terminal DRL transitions.

Acceptance checklist for Builder implementing T011:
- `scheduling/drl_scheduler.py:386` and `scheduling/drl_scheduler.py:428` no longer store current state as placeholder next state.
- `scheduling/drl_scheduler.py:443-456` stores transitions with true post-action next states when coordinator context is present.
- Final tick in standalone training stores `done=True`; all earlier ticks store `done=False`.
- `SequenceReplayBuffer` terminal behavior is covered by tests.
- Existing scheduler injection tests still pass for both rich-context and legacy trainable schedulers.
- No distributed trainable scheduler behavior is introduced before distributed reward/state plumbing exists.
- Project lead should append a concise `dev-log.md` entry for this planning turn, because Planner-A was instructed not to edit `dev-log.md`.
