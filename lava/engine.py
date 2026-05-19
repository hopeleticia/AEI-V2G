from __future__ import annotations

import time

import yaml

from lava.constraints import ConstraintEnforcer
from lava.ensemble import MedianEnsemble
from lava.optimizer import GlobalOptimizer
from lava.rules import RuleReasoner


class LAVAEngine:
    def __init__(self, weights: dict, rules: dict, constraints: dict) -> None:
        self.optimizer = GlobalOptimizer(weights)
        self.rules = RuleReasoner(rules)
        self.constraints = ConstraintEnforcer(constraints)
        self.ensemble = MedianEnsemble(
            min_confidence=float(constraints["min_decision_confidence"]),
            max_divergence=float(constraints["max_engine_divergence"]),
        )

    @classmethod
    def from_yaml(cls, weights_path: str, rules_path: str, constraints_path: str) -> "LAVAEngine":
        with open(weights_path, "r", encoding="utf-8") as handle:
            weights = yaml.safe_load(handle)
        with open(rules_path, "r", encoding="utf-8") as handle:
            rules = yaml.safe_load(handle)
        with open(constraints_path, "r", encoding="utf-8") as handle:
            constraints = yaml.safe_load(handle)
        return cls(weights, rules, constraints)

    def route_ev(self, ev_feature: dict, stations: dict, grid_state: dict) -> dict:
        started = time.perf_counter()
        candidates = [
            self.optimizer.recommend_station(ev_feature, stations, grid_state),
            self.rules.recommend_station(ev_feature, stations, grid_state),
            self.constraints.recommend_station(ev_feature, stations, grid_state),
        ]
        decision = self.ensemble.combine_route(candidates)
        decision["ev_id"] = ev_feature["ev_id"]
        decision["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return decision

    def dispatch_v2g(self, stations: dict, grid_state: dict) -> dict:
        started = time.perf_counter()
        candidates = [
            self.optimizer.v2g_dispatch(stations, grid_state),
            self.rules.v2g_dispatch(stations, grid_state),
            self.constraints.v2g_dispatch(stations, grid_state),
        ]
        decision = self.ensemble.combine_v2g(candidates)
        decision["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return decision
