from __future__ import annotations

from dataclasses import dataclass

from sensing.soc_proxy import estimate_soc_proxy, isac_proxy_features
from sim.entities import EV, Station


@dataclass(frozen=True)
class RSU:
    id: str
    km: float
    range_km: float

    def sense(self, evs: list[EV], stations: dict[str, Station]) -> list[dict]:
        features: list[dict] = []
        for ev in evs:
            distance = abs(ev.km - self.km)
            if distance <= self.range_km and ev.charge_request:
                proxy_features = isac_proxy_features(
                    true_soc=ev.battery_pct,
                    speed_kmh=ev.speed_kmh,
                    distance_to_rsu_km=distance,
                    rsu_range_km=self.range_km,
                )
                soc_proxy = estimate_soc_proxy(
                    **proxy_features,
                    onboard_soc_hint=ev.battery_pct,
                )
                features.append(
                    {
                        "ev_id": ev.id,
                        "km": ev.km,
                        "speed_kmh": ev.speed_kmh,
                        "battery_pct": ev.battery_pct,
                        "distance_to_rsu_km": distance,
                        "nearest_station_id": min(stations.values(), key=lambda s: abs(s.km - ev.km)).id,
                        "eta_by_station_min": {
                            station.id: max(0.0, (station.km - ev.km) / max(ev.speed_kmh, 1.0) * 60.0)
                            for station in stations.values()
                            if station.km >= ev.km
                        },
                        # Per-EV battery state (Obj-4, P2) — communicated EV -> RSU -> pi1
                        "SoC_k": ev.battery_pct,
                        "SoH_k": ev.SoH_k,
                        "SoC_req_k": ev.SoC_req_k,
                        "T_dep_k": ev.T_dep_k,
                        "estimated_soc": soc_proxy.estimated_soc,
                        "estimated_soc_confidence": soc_proxy.confidence,
                        "isac_proxy_features": soc_proxy.features,
                    }
                )
        return features
