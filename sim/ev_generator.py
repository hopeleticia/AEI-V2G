from __future__ import annotations

import math
import random

from sim.entities import EV


class EVGenerator:
    def __init__(self, arrivals_per_hour: float, seed: int) -> None:
        self.arrivals_per_hour = arrivals_per_hour
        self.rng = random.Random(seed)
        self.counter = 0

    def spawn(self, tick_minutes: float, corridor_length_km: float) -> list[EV]:
        expected = self.arrivals_per_hour * tick_minutes / 60.0
        count = self._poisson(expected)
        evs: list[EV] = []
        for _ in range(count):
            self.counter += 1
            battery = max(8.0, min(92.0, self.rng.gauss(46, 18)))
            charge_request = battery < 62 or self.rng.random() < 0.18
            soh = max(0.70, min(1.0, self.rng.gauss(0.92, 0.06)))
            soc_req = max(60.0, min(100.0, self.rng.gauss(80.0, 10.0)))
            t_dep = max(20.0, min(120.0, self.rng.gauss(65.0, 20.0)))
            evs.append(
                EV(
                    id=f"ev_{self.counter:05d}",
                    km=0.0,
                    speed_kmh=self.rng.uniform(70, 105),
                    battery_pct=battery,
                    destination_km=corridor_length_km,
                    charge_request=charge_request,
                    required_kwh=max(8.0, (soc_req - battery) * soh * 0.72),
                    v2g_eligible=battery >= 55,
                    SoH_k=soh,
                    SoC_req_k=soc_req,
                    T_dep_k=t_dep,
                )
            )
        return evs

    def _poisson(self, mean: float) -> int:
        threshold = math.exp(-mean)
        value = 1.0
        count = 0
        while value > threshold:
            count += 1
            value *= self.rng.random()
        return count - 1
