"""
scheduling/drl_scheduler.py
============================
DRQN (Deep Recurrent Q-Network) scheduler for AEI-V2G.

Architecture (from IBTD anchor paper, Zhao et al. IET Comms 2024, adapted for
V2G energy dispatch):

    Input features  →  Linear(input_dim, 128)  →  ReLU
                    →  LSTM(128, hidden_dim)
                    →  Linear(hidden_dim, n_actions)   [Q-values]

Two independent DRQN agents share this architecture:
  RouteDRQN : selects which charging station to assign an approaching EV.
  V2GDRQN   : selects a discrete V2G power level to dispatch to the grid.

Both agents are trained with:
  - Experience replay over fixed-length sequences (see replay_buffer.py).
  - Epsilon-greedy exploration decaying from 1.0 to 0.05.
  - Double DQN target network updated by soft copy every TARGET_UPDATE steps.
  - BPTT over SEQ_LEN steps with BURN_IN leading steps for LSTM warm-up.

State vectors
-------------
Route state (16 dims for 3 stations):
  [battery_pct/100, speed_kmh/120,
   eta_a/60, eta_b/60, eta_c/60,              ← ISAC sensing (Obj-2)
   util_a, util_b, util_c,
   qdepth_a/10, qdepth_b/10, qdepth_c/10,
   avail_a/slots_a, avail_b/slots_b, avail_c/slots_c,
   stress, (tariff-0.24)/0.20]

V2G state (12 dims for 3 stations):
  [active_a/slots_a, avg_batt_a, util_a,
   active_b/slots_b, avg_batt_b, util_b,
   active_c/slots_c, avg_batt_c, util_c,
   stress, (tariff-0.24)/0.20, (v2g_price-0.42)/0.22]

Action spaces
-------------
Route  : discrete station index → station_id (n_stations actions)
V2G    : discrete power level index → kW from V2G_POWER_LEVELS

Reward function (Section 5.5, context doc)
------------------------------------------
  r_t = -α·ΔPAR(t) - β·TEC(t) - γ·C_deg(t) + δ·SoC_sat(t)

Computed externally by the coordinator and passed via update(reward).

Safety layer
------------
Any V2G action that would drain a battery below min_battery_after_v2g (20%)
is vetoed and replaced with action=0 (no dispatch).  This mirrors the hard
constraint in config/constraints.yaml and is enforced inside dispatch_v2g()
before the action is returned.

Research objective mapping
--------------------------
  Obj-2  ISAC sensing features are explicit inputs to the route state vector.
  Obj-3  Pre-arrival routing decisions come from route_ev() called before plug-in.
  Obj-7  Reward directly penalises PAR, TEC, battery degradation.
  Obj-8  DRQN with LSTM handles the POMDP (partial observability).
  Obj-9  DRL vs LAVA baseline comparison is enabled by this class.
  Obj-10 Sensing gain delta-J = reward(DRL+ISAC) - reward(DRL, no sensing).
"""
from __future__ import annotations

import os
import time
from typing import Optional

from scheduling.base_scheduler import BaseScheduler
from scheduling.replay_buffer import SequenceReplayBuffer, Step

# ── Torch import (graceful degradation) ──────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    optim = None  # type: ignore[assignment]
    _TORCH_AVAILABLE = False


# ── Discrete V2G power levels (kW) ───────────────────────────────────────────
V2G_POWER_LEVELS: list[float] = [0.0, 12.0, 24.0, 36.0, 48.0, 60.0]

# ── Safety constraint (mirrors config/constraints.yaml) ──────────────────────
MIN_BATTERY_AFTER_V2G: float = 20.0

# ── Training hyper-parameters ─────────────────────────────────────────────────
GAMMA: float = 0.95          # discount factor
LR: float = 3e-4             # Adam learning rate
BATCH_SIZE: int = 32         # sequences per gradient step
SEQ_LEN: int = 8             # BPTT window length
BURN_IN: int = 4             # LSTM warm-up steps (no loss)
TARGET_UPDATE: int = 50      # soft-copy target net every N gradient steps
TAU: float = 0.01            # soft-copy interpolation coefficient
EPSILON_START: float = 1.0
EPSILON_MIN: float = 0.05
EPSILON_DECAY: float = 0.997 # per gradient step (not per tick)
BUFFER_CAPACITY: int = 500   # episodes


def _require_torch(method_name: str) -> None:
    if not _TORCH_AVAILABLE:
        raise RuntimeError(
            f"DRLScheduler.{method_name}() requires PyTorch. "
            "Install it with: pip install torch  (ARM64 wheels are available "
            "from https://pytorch.org — use the Linux ARM wheel for Raspberry Pi)."
        )


# ── Neural network ────────────────────────────────────────────────────────────
# The class is defined only when PyTorch is present so that the module can be
# imported without torch (DRL features simply degrade gracefully at runtime).

def _make_drqn_class():
    """Return the _DRQNNet class, creating it with live torch/nn references."""
    import torch
    import torch.nn as _nn

    class _DRQNNet(_nn.Module):
        """Shared DRQN architecture: Linear → ReLU → LSTM → Q-head."""

        def __init__(self, input_dim: int, n_actions: int, hidden_dim: int = 64) -> None:
            super().__init__()
            self.hidden_dim = hidden_dim
            self.feature = _nn.Sequential(
                _nn.Linear(input_dim, 128),
                _nn.ReLU(),
            )
            self.lstm = _nn.LSTM(128, hidden_dim, batch_first=True)
            self.q_head = _nn.Linear(hidden_dim, n_actions)

        def forward(self, x, hidden=None):
            batch, seq, _ = x.shape
            feat = self.feature(x.view(batch * seq, -1)).view(batch, seq, -1)
            out, hidden = self.lstm(feat, hidden)
            q = self.q_head(out)
            return q, hidden

        def init_hidden(self, batch_size: int = 1, device: str = "cpu"):
            h = torch.zeros(1, batch_size, self.hidden_dim, device=device)
            c = torch.zeros(1, batch_size, self.hidden_dim, device=device)
            return (h, c)

    return _DRQNNet


# ── Per-agent wrapper ─────────────────────────────────────────────────────────

class _DRQNAgent:
    """One DRQN agent (either routing or V2G).

    Manages its own online/target networks, optimizer, replay buffer,
    and LSTM hidden state.
    """

    def __init__(
        self,
        input_dim: int,
        n_actions: int,
        hidden_dim: int,
        device: str,
        buffer_capacity: int,
    ) -> None:
        self.n_actions = n_actions
        self.device = device
        _DRQNNet = _make_drqn_class()
        import torch.optim as _optim
        self.online = _DRQNNet(input_dim, n_actions, hidden_dim).to(device)
        self.target = _DRQNNet(input_dim, n_actions, hidden_dim).to(device)
        self.target.load_state_dict(self.online.state_dict())
        self.target.eval()
        self.optimizer = _optim.Adam(self.online.parameters(), lr=LR)
        self.buffer = SequenceReplayBuffer(
            capacity=buffer_capacity, seq_len=SEQ_LEN, burn_in=BURN_IN
        )
        self._hidden: Optional[tuple] = None       # persists across ticks
        self._pending: Optional[tuple] = None       # (state, action) awaiting reward
        self._grad_steps = 0

    def reset_episode(self) -> None:
        self._hidden = None
        self.buffer.close_episode()

    def act(
        self, state: list[float], epsilon: float
    ) -> tuple[int, list[float]]:
        """Epsilon-greedy action selection.  Updates LSTM hidden state."""
        _require_torch("act")
        import torch, random as _random
        if _random.random() < epsilon:
            action = _random.randrange(self.n_actions)
            # Still run a forward pass to advance the LSTM hidden state so
            # that inference-time behaviour is consistent with training.
            x = torch.tensor([[[state]]], dtype=torch.float32).squeeze(0)
            x = torch.tensor([[state]], dtype=torch.float32).to(self.device)
            with torch.no_grad():
                _, self._hidden = self.online(x, self._hidden)
        else:
            x = torch.tensor([[state]], dtype=torch.float32).to(self.device)
            with torch.no_grad():
                q_vals, self._hidden = self.online(x, self._hidden)
            action = int(q_vals[0, 0].argmax().item())
        self._pending = (state, action)
        return action, state

    def store_reward(
        self, reward: float, next_state: list[float], done: bool
    ) -> None:
        """Complete the pending experience with the received reward."""
        if self._pending is None:
            return
        state, action = self._pending
        self.buffer.push(state, action, reward, next_state, done)
        self._pending = None

    def train_step(self) -> Optional[float]:
        """One gradient update.  Returns scalar loss or None if buffer not ready."""
        if not self.buffer.can_train():
            return None
        batch = self.buffer.sample(BATCH_SIZE)
        if batch is None:
            return None
        _require_torch("train_step")
        import torch, torch.nn.functional as F

        # Build tensors: (batch, seq, dim)
        states      = torch.tensor([[s.state      for s in seq] for seq in batch], dtype=torch.float32).to(self.device)
        actions     = torch.tensor([[s.action     for s in seq] for seq in batch], dtype=torch.long).to(self.device)
        rewards     = torch.tensor([[s.reward     for s in seq] for seq in batch], dtype=torch.float32).to(self.device)
        next_states = torch.tensor([[s.next_state for s in seq] for seq in batch], dtype=torch.float32).to(self.device)
        dones       = torch.tensor([[float(s.done) for s in seq] for seq in batch], dtype=torch.float32).to(self.device)

        # Online Q-values (all steps; we mask out burn-in in the loss)
        q_online, _ = self.online(states)          # (B, seq, n_actions)
        q_taken     = q_online.gather(2, actions.unsqueeze(-1)).squeeze(-1)  # (B, seq)

        # Double DQN target: online selects action, target evaluates it
        with torch.no_grad():
            q_next_online, _ = self.online(next_states)
            best_actions      = q_next_online.argmax(dim=2, keepdim=True)
            q_next_target, _  = self.target(next_states)
            q_next            = q_next_target.gather(2, best_actions).squeeze(-1)
            td_target         = rewards + GAMMA * q_next * (1.0 - dones)

        # Loss only on non-burn-in steps
        loss_full = F.smooth_l1_loss(q_taken, td_target, reduction="none")
        loss = loss_full[:, BURN_IN:].mean()

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.online.parameters(), max_norm=10.0)
        self.optimizer.step()

        self._grad_steps += 1
        if self._grad_steps % TARGET_UPDATE == 0:
            self._soft_update_target()

        return float(loss.item())

    def _soft_update_target(self) -> None:
        for p_online, p_target in zip(self.online.parameters(), self.target.parameters()):
            p_target.data.copy_(TAU * p_online.data + (1.0 - TAU) * p_target.data)

    def save(self, path: str) -> None:
        _require_torch("save")
        torch.save({
            "online": self.online.state_dict(),
            "target": self.target.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "grad_steps": self._grad_steps,
        }, path)

    def load(self, path: str) -> None:
        _require_torch("load")
        checkpoint = torch.load(path, map_location=self.device)
        self.online.load_state_dict(checkpoint["online"])
        self.target.load_state_dict(checkpoint["target"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self._grad_steps = checkpoint.get("grad_steps", 0)


# ── Public scheduler class ────────────────────────────────────────────────────

class DRLScheduler(BaseScheduler):
    """DRQN-based V2G scheduler.

    Parameters
    ----------
    station_ids     : list[str]  — station IDs in the corridor (from YAML config).
                      Order is sorted alphabetically and frozen at construction;
                      the state vector layout depends on this order.
    device          : str        — "cpu" or "cuda" (Pi uses cpu).
    eval_mode       : bool       — if True, epsilon is fixed at 0 (no exploration).
    buffer_capacity : int        — max episodes in replay buffer per agent.

    Typical usage (training)
    ------------------------
        sched = DRLScheduler(["station_a", "station_b", "station_c"])
        for episode in range(1000):
            sched.reset_episode()
            result = coordinator.run(config, duration, scheduler=sched)
            # coordinator calls update(reward) and train() each tick internally.
        sched.save("models/drl_checkpoint.pt")

    Typical usage (evaluation)
    --------------------------
        sched = DRLScheduler(..., eval_mode=True)
        sched.load("models/drl_checkpoint.pt")
        result = coordinator.run(config, duration, scheduler=sched)
    """

    def __init__(
        self,
        station_ids: list[str],
        device: str = "cpu",
        eval_mode: bool = False,
        buffer_capacity: int = BUFFER_CAPACITY,
    ) -> None:
        if not _TORCH_AVAILABLE and not eval_mode:
            raise RuntimeError(
                "PyTorch is required for DRLScheduler in training mode. "
                "pip install torch"
            )
        self._station_ids = sorted(station_ids)   # deterministic, alphabetical
        self._n_stations = len(self._station_ids)
        self._device = device
        self._eval_mode = eval_mode

        # State dimensions
        # Route: 2 (EV) + n (ETAs) + n*3 (station features) + 2 (grid)
        route_input_dim = 2 + self._n_stations + self._n_stations * 3 + 2
        # V2G:  n*3 (station features) + 3 (grid)
        v2g_input_dim   = self._n_stations * 3 + 3

        if _TORCH_AVAILABLE:
            self._route_agent = _DRQNAgent(
                route_input_dim, self._n_stations, hidden_dim=64,
                device=device, buffer_capacity=buffer_capacity,
            )
            self._v2g_agent = _DRQNAgent(
                v2g_input_dim, len(V2G_POWER_LEVELS), hidden_dim=32,
                device=device, buffer_capacity=buffer_capacity,
            )
        else:
            self._route_agent = None  # type: ignore[assignment]
            self._v2g_agent   = None  # type: ignore[assignment]

        self._epsilon = EPSILON_START if not eval_mode else 0.0
        self._train_step_count = 0

        # Pending reward accumulator: route and V2G experiences from the
        # current tick wait here until update() delivers the tick reward.
        self._pending_route_states: list[tuple[list[float], int, list[float]]] = []
        self._pending_v2g_state: Optional[tuple[list[float], int, list[float]]] = None

        # Last known next-states (updated each tick)
        self._last_v2g_state: list[float] = [0.0] * v2g_input_dim

    # ── BaseScheduler interface ───────────────────────────────────────────────

    def route_ev(self, ev_feature: dict, stations: dict, grid_state: dict) -> dict:
        """Select a charging station using the routing DRQN."""
        started = time.perf_counter()
        state = self._build_route_state(ev_feature, stations, grid_state)

        if _TORCH_AVAILABLE:
            action_idx, _ = self._route_agent.act(state, self._epsilon)
        else:
            # No-torch fallback: pick station with most available slots.
            action_idx = max(
                range(self._n_stations),
                key=lambda i: stations[self._station_ids[i]].available_slots,
            )

        station_id = self._station_ids[action_idx]

        # Build next_state placeholder (will be updated on next route_ev call;
        # for now we store the current state as a stand-in).
        self._pending_route_states.append((state, action_idx, state))

        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "action": "route",
            "station_id": station_id,
            "value_kw": 0.0,
            "confidence": 1.0 - self._epsilon,
            "divergence": 0.0,
            "deferred": False,
            "reason": f"DRQN Q-argmax action={action_idx} ε={self._epsilon:.3f}",
            "latency_ms": latency_ms,
            "ev_id": ev_feature.get("ev_id", ""),
            "trace": [],
        }

    def dispatch_v2g(self, stations: dict, grid_state: dict) -> dict:
        """Select a V2G power level using the V2G DRQN.

        The safety layer vetoes any action that would drain any active EV
        battery below MIN_BATTERY_AFTER_V2G (20 %).
        """
        started = time.perf_counter()
        state = self._build_v2g_state(stations, grid_state)
        self._last_v2g_state = state

        if _TORCH_AVAILABLE:
            action_idx, _ = self._v2g_agent.act(state, self._epsilon)
        else:
            # No-torch fallback: dispatch only when stress >= 0.8.
            action_idx = 3 if grid_state.get("stress", 0.0) >= 0.8 else 0

        power_kw = V2G_POWER_LEVELS[action_idx]

        # ── Safety layer ──────────────────────────────────────────────────────
        power_kw = self._apply_safety_constraint(power_kw, stations)
        # Remap to the nearest allowed power level after safety clip.
        action_idx = min(
            range(len(V2G_POWER_LEVELS)),
            key=lambda i: abs(V2G_POWER_LEVELS[i] - power_kw),
        )

        self._pending_v2g_state = (state, action_idx, state)

        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "action": "v2g",
            "station_id": None,
            "value_kw": round(power_kw, 3),
            "confidence": 1.0 - self._epsilon,
            "divergence": 0.0,
            "deferred": False,
            "reason": f"DRQN V2G level={action_idx} ({power_kw} kW) ε={self._epsilon:.3f}",
            "latency_ms": latency_ms,
            "trace": [],
        }

    def update(self, reward: float) -> None:
        """Distribute the tick reward to all pending experiences."""
        if not _TORCH_AVAILABLE:
            return
        # Route experiences — each routing decision this tick gets the reward.
        for state, action, next_state in self._pending_route_states:
            self._route_agent.store_reward(reward, next_state, done=False)
        self._pending_route_states.clear()

        # V2G experience.
        if self._pending_v2g_state is not None:
            state, action, next_state = self._pending_v2g_state
            self._v2g_agent.store_reward(reward, next_state, done=False)
            self._pending_v2g_state = None

    def train(self) -> float | None:
        """One gradient step for each agent.  Returns average loss or None."""
        if self._eval_mode or not _TORCH_AVAILABLE or self._route_agent is None:
            return None
        route_loss = self._route_agent.train_step()
        v2g_loss   = self._v2g_agent.train_step()
        if route_loss is not None or v2g_loss is not None:
            self._train_step_count += 1
            # Decay epsilon after each gradient step.
            self._epsilon = max(
                EPSILON_MIN, self._epsilon * EPSILON_DECAY
            )
            losses = [l for l in (route_loss, v2g_loss) if l is not None]
            return sum(losses) / len(losses)
        return None

    def reset_episode(self) -> None:
        """Reset LSTM hidden states and close the current episode in the buffer."""
        if self._route_agent is not None:
            self._route_agent.reset_episode()
        if self._v2g_agent is not None:
            self._v2g_agent.reset_episode()
        self._pending_route_states.clear()
        self._pending_v2g_state = None

    def save(self, path: str) -> None:
        """Save both agents to *path_route.pt* and *path_v2g.pt*."""
        _require_torch("save")
        import os as _os
        base, ext = _os.path.splitext(path)
        self._route_agent.save(f"{base}_route{ext or '.pt'}")
        self._v2g_agent.save(f"{base}_v2g{ext or '.pt'}")

    def load(self, path: str) -> None:
        """Load both agents from the paths produced by save()."""
        _require_torch("load")
        import os as _os
        base, ext = _os.path.splitext(path)
        self._route_agent.load(f"{base}_route{ext or '.pt'}")
        self._v2g_agent.load(f"{base}_v2g{ext or '.pt'}")

    # ── Metadata ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        mode = "eval" if self._eval_mode else f"train ε={self._epsilon:.3f}"
        return f"DRQN({mode})"

    @property
    def is_trainable(self) -> bool:
        return not self._eval_mode

    @property
    def epsilon(self) -> float:
        return self._epsilon

    @property
    def train_steps(self) -> int:
        return self._train_step_count

    # ── State encoding ────────────────────────────────────────────────────────

    def _build_route_state(
        self, ev_feature: dict, stations: dict, grid_state: dict
    ) -> list[float]:
        """Encode EV + station + grid info into a normalised route state vector.

        Layout (for n=3 stations, alphabetical order):
          [battery_pct/100, speed_kmh/120,
           eta_a/60, eta_b/60, eta_c/60,
           util_a, util_b, util_c,
           qdepth_a/10, qdepth_b/10, qdepth_c/10,
           avail_a/slots_a, avail_b/slots_b, avail_c/slots_c,
           stress, (tariff-0.24)/0.20]
        """
        battery  = float(ev_feature.get("battery_pct", 50.0)) / 100.0
        speed    = float(ev_feature.get("speed_kmh", 80.0)) / 120.0
        eta_map  = ev_feature.get("eta_by_station_min", {})

        etas = [
            min(float(eta_map.get(sid, 999.0)), 120.0) / 60.0
            for sid in self._station_ids
        ]
        utils   = [stations[sid].utilization                           for sid in self._station_ids]
        qdepths = [min(stations[sid].queue_depth, 10) / 10.0          for sid in self._station_ids]
        avails  = [
            stations[sid].available_slots / max(1, stations[sid].slots)
            for sid in self._station_ids
        ]

        stress = float(grid_state.get("stress", 0.5))
        tariff = (float(grid_state.get("tariff", 0.35)) - 0.24) / 0.20

        return [battery, speed] + etas + utils + qdepths + avails + [stress, tariff]

    def _build_v2g_state(self, stations: dict, grid_state: dict) -> list[float]:
        """Encode station + grid info into a normalised V2G state vector.

        Layout (for n=3 stations, alphabetical order):
          [active_a/slots_a, avg_batt_a, util_a,
           active_b/slots_b, avg_batt_b, util_b,
           active_c/slots_c, avg_batt_c, util_c,
           stress, (tariff-0.24)/0.20, (v2g_price-0.42)/0.22]
        """
        station_feats: list[float] = []
        for sid in self._station_ids:
            s = stations[sid]
            active_ratio = len(s.active_evs) / max(1, s.slots)
            avg_batt = (
                sum(ev.battery_pct for ev in s.active_evs) / len(s.active_evs) / 100.0
                if s.active_evs else 0.5
            )
            station_feats.extend([active_ratio, avg_batt, s.utilization])

        stress    = float(grid_state.get("stress", 0.5))
        tariff    = (float(grid_state.get("tariff", 0.35)) - 0.24) / 0.20
        v2g_price = (float(grid_state.get("v2g_buy_price", 0.42)) - 0.42) / 0.22

        return station_feats + [stress, tariff, v2g_price]

    # ── Safety constraint ─────────────────────────────────────────────────────

    def _apply_safety_constraint(self, power_kw: float, stations: dict) -> float:
        """Reduce power_kw so no active EV battery drops below 20%.

        Mirrors the hard constraint in config/constraints.yaml:
            min_battery_after_v2g: 20

        Each active EV that is V2G-eligible can supply at most the energy
        that keeps its battery above MIN_BATTERY_AFTER_V2G.  We cap
        power_kw at the aggregate safe limit.

        Research objective mapping: Obj-7 (battery health preservation).
        """
        safe_limit_kw = 0.0
        for station in stations.values():
            for ev in station.active_evs:
                if ev.v2g_eligible and ev.battery_pct > MIN_BATTERY_AFTER_V2G:
                    headroom_pct = ev.battery_pct - MIN_BATTERY_AFTER_V2G
                    # Very conservative: 1 kW per % headroom above threshold.
                    safe_limit_kw += headroom_pct * 1.0
        return min(power_kw, safe_limit_kw)
