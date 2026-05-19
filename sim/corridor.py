from __future__ import annotations

import yaml

from sim.entities import Station
from sim.ev_generator import EVGenerator
from sim.grid_model import GridModel
from sim.load_profile import LoadProfile
from sim.rsu_model import RSU


class Corridor:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.length_km = float(config["corridor"]["length_km"])
        self.tick_seconds = int(config.get("tick_seconds", 60))
        self.stations = {
            row["id"]: Station(
                id=row["id"],
                km=float(row["km"]),
                max_kw=float(row["max_kw"]),
                slots=int(row["slots"]),
                base_price=float(row["base_price"]),
            )
            for row in config["stations"]
        }
        self.rsus = [
            RSU(id=row["id"], km=float(row["km"]), range_km=float(config["corridor"]["rsu_range_km"]))
            for row in config["rsus"]
        ]
        grid = config["grid"]
        profile = None
        if grid.get("load_profile_csv"):
            profile = LoadProfile.from_csv(grid["load_profile_csv"])
        self.grid = GridModel(
            base_stress=float(grid["base_stress"]),
            peak_hours=list(grid["peak_hours"]),
            stress_event_hour=int(grid["stress_event_hour"]),
            stress_event_boost=float(grid["stress_event_boost"]),
            v2g_base_price=float(grid["v2g_base_price"]),
            load_profile=profile,
        )
        self.generator = EVGenerator(float(config["corridor"]["ev_arrivals_per_hour"]), int(config["seed"]))

    @classmethod
    def from_yaml(cls, path: str) -> "Corridor":
        with open(path, "r", encoding="utf-8") as handle:
            return cls(yaml.safe_load(handle))

    def sense(self, evs) -> list[dict]:
        by_ev: dict[str, dict] = {}
        for rsu in self.rsus:
            for feature in rsu.sense(evs, self.stations):
                by_ev[feature["ev_id"]] = feature
        return list(by_ev.values())
