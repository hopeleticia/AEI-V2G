from __future__ import annotations

from lava.candidates import Candidate


class GlobalOptimizer:
    def __init__(self, weights: dict) -> None:
        self.weights = weights

    def recommend_station(self, ev_feature: dict, stations: dict, grid_state: dict) -> Candidate:
        best_station = None
        best_score = float("inf")
        values: list[float] = []
        loads = [station.utilization for station in stations.values()]
        avg_load = sum(loads) / max(1, len(loads))
        for station_id, station in stations.items():
            eta = ev_feature["eta_by_station_min"].get(station_id, 999.0)
            wait = station.estimated_wait_minutes()
            imbalance = abs(station.utilization - avg_load)
            price = station.base_price + grid_state["tariff"]
            score = (
                self.weights["grid_stress"] * grid_state["stress"] * station.utilization
                + self.weights["ev_wait_time"] * ((eta + wait) / 60.0)
                + self.weights["station_imbalance"] * imbalance
                + self.weights["energy_cost"] * price
            )
            values.append(score)
            if score < best_score:
                best_station = station_id
                best_score = score
        spread = max(values) - min(values) if values else 0.0
        confidence = max(0.35, min(0.96, 1.0 - spread))
        return Candidate("route", best_station, 0.0, confidence, "optimizer", f"lowest weighted corridor cost {best_score:.3f}")

    def v2g_dispatch(self, stations: dict, grid_state: dict) -> Candidate:
        stress = grid_state["stress"]
        value_kw = max(0.0, (stress - 0.72) * 520.0)
        confidence = min(0.95, max(0.25, stress))
        return Candidate("v2g", None, value_kw, confidence, "optimizer", "stress-weighted discharge search")
