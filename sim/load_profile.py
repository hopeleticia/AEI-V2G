from __future__ import annotations

import csv


class LoadProfile:
    def __init__(self, demand_mw: list[float]) -> None:
        if not demand_mw:
            raise ValueError("load profile must contain at least one demand value")
        self.demand_mw = demand_mw
        self.min_mw = min(demand_mw)
        self.max_mw = max(demand_mw)
        self.avg_mw = sum(demand_mw) / len(demand_mw)

    @classmethod
    def from_csv(cls, path: str, column: str = "current_demand_mw") -> "LoadProfile":
        values: list[float] = []
        with open(path, "r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                raw = row.get(column, "")
                if raw:
                    values.append(float(raw))
        return cls(values)

    def value_at_minute(self, minute: int) -> float:
        # CAISO profile is 5-minute resolution; repeat cyclically for longer studies.
        index = (minute // 5) % len(self.demand_mw)
        return self.demand_mw[index]

    def normalized_at_minute(self, minute: int) -> float:
        span = max(1.0, self.max_mw - self.min_mw)
        return (self.value_at_minute(minute) - self.min_mw) / span
