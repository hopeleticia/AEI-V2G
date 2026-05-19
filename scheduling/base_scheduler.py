"""
scheduling/base_scheduler.py
============================
Abstract base class that every scheduler in AEI-V2G must implement.

The interface is intentionally narrow:
  - route_ev()    mirrors lava.engine.LAVAEngine.route_ev()   exactly.
  - dispatch_v2g() mirrors lava.engine.LAVAEngine.dispatch_v2g() exactly.
Both return the same dict shape the coordinator and station-validators already
consume, so swapping schedulers requires zero changes outside this package.

DRL schedulers also override:
  - update(reward)  — called once per tick with the scalar reward signal.
  - train()         — performs one gradient step; returns the loss or None.
  - reset_episode() — resets LSTM hidden state between simulation episodes.
  - save(path) / load(path) — model persistence.

Research objective mapping
--------------------------
  Obj-3  Pluggable framework enabling proactive scheduling swap-in.
  Obj-8  Standard interface consumed by the DRL scheduler.
  Obj-9  Ablation study (LAVA vs DRL) requires identical interface.
  Obj-10 Baseline comparison (B1/B2/B3/ours) requires identical interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseScheduler(ABC):
    """Pluggable scheduler interface for AEI-V2G.

    All methods that return dicts must produce output compatible with the
    field names consumed by integration/coordinator.py and
    integration/v2g_dispatcher.py.  Do not rename dict keys here without
    updating all downstream consumers simultaneously.
    """

    # ── Required interface ────────────────────────────────────────────────────

    @abstractmethod
    def route_ev(self, ev_feature: dict, stations: dict, grid_state: dict) -> dict:
        """Select a charging station for an approaching EV.

        Parameters
        ----------
        ev_feature  : dict  — RSU sensing output for one EV. Keys include
                              ev_id, km, speed_kmh, battery_pct,
                              eta_by_station_min, nearest_station_id.
        stations    : dict  — {station_id: Station} mapping (sim.entities.Station).
        grid_state  : dict  — Output of GridModel.state(). Keys: stress, tariff,
                              v2g_buy_price, frequency_hz.

        Returns
        -------
        dict with at minimum:
            station_id   : str | None  — chosen station (None → fallback to nearest)
            latency_ms   : float       — decision time in milliseconds
            confidence   : float       — [0, 1] scheduler confidence
            divergence   : float       — [0, 1] internal disagreement proxy
            action       : str         — "route"
            reason       : str         — human-readable rationale
            ev_id        : str         — copied from ev_feature["ev_id"]
        """

    @abstractmethod
    def dispatch_v2g(self, stations: dict, grid_state: dict) -> dict:
        """Decide how much power (kW) to draw from EVs back to the grid.

        Parameters
        ----------
        stations    : dict  — {station_id: Station} mapping.
        grid_state  : dict  — Output of GridModel.state().

        Returns
        -------
        dict with at minimum:
            value_kw     : float  — aggregate V2G power to dispatch (>= 0)
            latency_ms   : float  — decision time in milliseconds
            confidence   : float  — [0, 1]
            divergence   : float  — [0, 1]
            action       : str    — "v2g"
            reason       : str    — human-readable rationale
        """

    # ── Optional DRL hooks (no-ops in non-learning schedulers) ────────────────

    def update(self, reward: float) -> None:
        """Receive the per-tick scalar reward.

        Called by the coordinator once per simulation tick after all routing
        and V2G decisions for that tick have been executed.  The default
        implementation is a no-op — override in DRL schedulers.

        Reward sign convention (from Section 5.5 of the context doc):
            positive  → good outcome (SoC satisfaction, V2G revenue)
            negative  → bad outcome (high PAR, high TEC, battery degradation)
        """

    def train(self) -> float | None:
        """Perform one gradient update step.

        Returns the scalar training loss, or None if training is not applicable
        (e.g. LAVA heuristic).  Called by the coordinator immediately after
        update() in training mode.
        """
        return None

    def reset_episode(self) -> None:
        """Reset any per-episode state (e.g. LSTM hidden vectors).

        Called by the training loop at the start of each new simulation
        episode.  The default implementation is a no-op.
        """

    def save(self, path: str) -> None:
        """Persist model weights to *path*.  No-op for non-learning schedulers."""

    def load(self, path: str) -> None:
        """Restore model weights from *path*.  No-op for non-learning schedulers."""

    # ── Metadata ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        """Human-readable scheduler name used in metrics output."""
        return self.__class__.__name__

    @property
    def is_trainable(self) -> bool:
        """True if this scheduler supports online learning (overrides train())."""
        return False
