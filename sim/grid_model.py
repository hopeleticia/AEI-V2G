from __future__ import annotations

import math


class GridModel:
    def __init__(
        self,
        base_stress: float,
        peak_hours: list[int],
        stress_event_hour: int,
        stress_event_boost: float,
        v2g_base_price: float,
        load_profile=None,
    ) -> None:
        self.base_stress = base_stress
        self.peak_hours = set(peak_hours)
        self.stress_event_hour = stress_event_hour
        self.stress_event_boost = stress_event_boost
        self.v2g_base_price = v2g_base_price
        self.load_profile = load_profile

    def state(self, minute: int, total_station_load_kw: float, v2g_supply_kw: float = 0.0) -> dict:
        hour = (minute // 60) % 24
        if self.load_profile:
            profile_component = 0.28 * self.load_profile.normalized_at_minute(minute)
            daily_wave = 0.04 * math.sin((hour - 6) / 24.0 * math.tau)
            source_demand_mw = self.load_profile.value_at_minute(minute)
        else:
            profile_component = 0.0
            daily_wave = 0.10 * math.sin((hour - 6) / 24.0 * math.tau)
            source_demand_mw = None
        peak = 0.18 if hour in self.peak_hours else 0.0
        event = self.stress_event_boost if hour == self.stress_event_hour else 0.0
        load_component = min(0.32, total_station_load_kw / 1600.0)
        relief = min(0.2, v2g_supply_kw / 800.0)
        stress = max(0.0, min(1.0, self.base_stress + daily_wave + profile_component + peak + event + load_component - relief))
        return {
            "stress": stress,
            "tariff": 0.24 + 0.20 * stress,
            "v2g_buy_price": self.v2g_base_price + 0.22 * stress,
            "frequency_hz": 50.0 - max(0.0, stress - 0.75) * 0.35,
            "source_demand_mw": source_demand_mw,
        }
