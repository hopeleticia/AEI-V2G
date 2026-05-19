from __future__ import annotations

from lava.candidates import Candidate


class ConstraintEnforcer:
    def __init__(self, constraints: dict) -> None:
        self.constraints = constraints

    def recommend_station(self, ev_feature: dict, stations: dict, grid_state: dict) -> Candidate:
        candidates = [
            station
            for station in stations.values()
            if station.utilization <= self.constraints["max_station_utilization"]
            and ev_feature["eta_by_station_min"].get(station.id, 999.0) < 80
        ]
        station = min(candidates or list(stations.values()), key=lambda s: (s.utilization, s.queue_depth))
        return Candidate("route", station.id, 0.0, 0.82, "constraints", "capacity and reachability bounds")

    def v2g_dispatch(self, stations: dict, grid_state: dict) -> Candidate:
        if abs(50.0 - grid_state["frequency_hz"]) > self.constraints["max_grid_frequency_deviation_hz"]:
            return Candidate("v2g", None, 0.0, 0.92, "constraints", "frequency deviation too high")
        eligible = sum(
            1
            for station in stations.values()
            for ev in station.active_evs
            if ev.battery_pct - 8 >= self.constraints["min_battery_after_v2g"]
        )
        return Candidate("v2g", None, min(eligible * 14.0, 160.0), 0.72, "constraints", "bounded by minimum post-discharge battery")
