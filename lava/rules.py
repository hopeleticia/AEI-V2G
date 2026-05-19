from __future__ import annotations

from lava.candidates import Candidate


class RuleReasoner:
    def __init__(self, rules: dict) -> None:
        self.rules = rules

    def recommend_station(self, ev_feature: dict, stations: dict, grid_state: dict) -> Candidate:
        if ev_feature["battery_pct"] < self.rules["low_battery_threshold"]:
            station_id = ev_feature["nearest_station_id"]
            return Candidate("route", station_id, 0.0, 0.9, "rules", "low battery priority to nearest station")
        available = [s for s in stations.values() if s.available_slots > 0]
        if available:
            station = min(available, key=lambda s: (s.estimated_wait_minutes(), s.base_price, abs(s.km - ev_feature["km"])))
            return Candidate("route", station.id, 0.0, 0.75, "rules", "prefer open slots with low price")
        station = min(stations.values(), key=lambda s: s.queue_depth)
        return Candidate("route", station.id, 0.0, 0.62, "rules", "all full, choose shortest queue")

    def v2g_dispatch(self, stations: dict, grid_state: dict) -> Candidate:
        if grid_state["stress"] >= self.rules["critical_grid_stress"]:
            eligible = sum(1 for s in stations.values() for ev in s.active_evs if ev.battery_pct >= self.rules["v2g_min_battery"])
            return Candidate("v2g", None, eligible * 18.0, 0.88, "rules", "critical grid stress triggers eligible V2G")
        return Candidate("v2g", None, 0.0, 0.8, "rules", "grid stress below dispatch rule")
