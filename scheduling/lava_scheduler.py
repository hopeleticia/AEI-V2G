"""
scheduling/lava_scheduler.py
============================
Thin adapter that wraps the existing LAVAEngine behind the BaseScheduler
interface.  LAVA is left completely untouched — this file only delegates.

LAVA becomes the most informative baseline in the evaluation because it:
  - Is already built and validated against hardware.
  - Represents the best expert-engineered heuristic.
  - Provides the B3 baseline (LAVA + ISAC sensing) in the ablation table.

The DRL scheduler is expected to learn to beat LAVA; if it does not, that is
itself a publishable finding.

Research objective mapping
--------------------------
  Obj-3  LAVA implements proactive scheduling (routing before plug-in).
  Obj-7  LAVA's weighted cost function targets PAR, TEC, wait time.
  Obj-9  LAVA is the B3 baseline in the evaluation.
  Obj-10 LAVA + ISAC sensing = B3 (sensing present, no learned policy).
"""
from __future__ import annotations

import time

from lava.engine import LAVAEngine
from scheduling.base_scheduler import BaseScheduler


class LAVAScheduler(BaseScheduler):
    """Wraps LAVAEngine (three-engine ensemble + median voting) as a scheduler.

    Instantiation is identical to the original coordinator pattern:

        sched = LAVAScheduler.from_yaml(
            "config/lava_weights.yaml",
            "config/rules.yaml",
            "config/constraints.yaml",
        )

    All return dicts are passed through unmodified from LAVAEngine so the
    coordinator sees no difference from calling lava.route_ev() directly.
    """

    def __init__(self, engine: LAVAEngine) -> None:
        self._engine = engine

    @classmethod
    def from_yaml(
        cls,
        weights_path: str = "config/lava_weights.yaml",
        rules_path: str = "config/rules.yaml",
        constraints_path: str = "config/constraints.yaml",
    ) -> "LAVAScheduler":
        return cls(LAVAEngine.from_yaml(weights_path, rules_path, constraints_path))

    # ── BaseScheduler interface ───────────────────────────────────────────────

    def route_ev(self, ev_feature: dict, stations: dict, grid_state: dict) -> dict:
        return self._engine.route_ev(ev_feature, stations, grid_state)

    def dispatch_v2g(self, stations: dict, grid_state: dict) -> dict:
        return self._engine.dispatch_v2g(stations, grid_state)

    # update(), train(), reset_episode(), save(), load() are all no-ops from
    # BaseScheduler — LAVA is deterministic and does not learn.

    @property
    def name(self) -> str:
        return "LAVA"

    @property
    def is_trainable(self) -> bool:
        return False
